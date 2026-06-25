#!/usr/bin/env python3
"""evaluate_freshness.py — Apply freshness policy to produce a stale update queue.

Reads audit_results.json and applies _system/config/freshness-policy.yaml
to determine which data items need re-verification and with what priority.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import get_freshness_policy, now_iso

log = logging.getLogger("evaluate_freshness")

# Category detection from file path/name
CATEGORY_PATTERNS = {
    "pricing": ["pricing", "price", "cost", "rate"],
    "policy": ["regulatory", "compliance", "license", "permit", "gov", "circular", "tax"],
    "competitor_core_profile": ["competitor", "landscape", "profile"],
    "facebook_handle": ["handle", "facebook"],
    "sentiment": ["sentiment", "review"],
    "seasonality": ["seasonal", "season", "eid"],
    "supply_chain": ["supply", "supplier", "sourcing", "wholesale"],
    "funding": ["funding", "investment", "raised", "vc"],
    "demographics": ["demograph", "persona", "segment", "customer"],
    "technology_adoption": ["technology", "digital", "app", "adoption"],
}


def detect_category(file_path: str) -> str:
    """Detect data category from file path."""
    lower = file_path.lower()
    for cat, patterns in CATEGORY_PATTERNS.items():
        for p in patterns:
            if p in lower:
                return cat
    return "default"


def get_freshness_thresholds(sector: str, category: str) -> dict:
    """Get stale/critical thresholds for a sector+category."""
    policy = get_freshness_policy(sector)
    if category in policy:
        return {
            "stale_after_days": policy[category].get("stale_after_days", 90),
            "critical_stale_after_days": policy[category].get("critical_stale_after_days", 180),
        }
    return {
        "stale_after_days": policy.get("stale_after_days", 90) if isinstance(policy, dict) and "stale_after_days" in policy else 90,
        "critical_stale_after_days": policy.get("critical_stale_after_days", 180) if isinstance(policy, dict) and "critical_stale_after_days" in policy else 180,
    }


def classify_freshness(age_days: int, stale_after: int, critical_after: int) -> tuple:
    """Classify freshness and priority based on age vs thresholds."""
    if age_days >= critical_after:
        return "critical", "P0"
    elif age_days >= stale_after:
        return "stale", "P1"
    elif age_days >= stale_after * 0.75:
        return "approaching_stale", "P2"
    else:
        return "fresh", None


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    state_dir = REPO_ROOT / "_system" / "state"
    audit_path = state_dir / "audit_results.json"

    if not audit_path.exists():
        log.error("audit_results.json not found. Run audit_repo.py first.")
        return

    audit = json.loads(audit_path.read_text())
    now = datetime.now(timezone.utc)

    queue = []
    summary = {"fresh": 0, "stale": 0, "critical": 0, "approaching_stale": 0}

    for sa in audit.get("sector_audits", []):
        sector = sa["sector"]
        stale_years = sorted(sa.get("stale_references", []))

        # Process each present file
        for fname in sa.get("present_files", []):
            rel_path = f"sectors/{sector}/bd-market/{fname}"
            full_path = REPO_ROOT / rel_path

            if not full_path.exists():
                continue

            # Get file modification time
            mtime = datetime.fromtimestamp(full_path.stat().st_mtime, tz=timezone.utc)
            age_days = (now - mtime).days
            category = detect_category(fname)
            thresholds = get_freshness_thresholds(sector, category)
            freshness, priority = classify_freshness(
                age_days, thresholds["stale_after_days"], thresholds["critical_stale_after_days"])

            summary[freshness] = summary.get(freshness, 0) + 1

            if priority:
                queue.append({
                    "path": rel_path,
                    "sector": sector,
                    "category": category,
                    "age_days": age_days,
                    "stale_type": freshness,
                    "priority": priority,
                    "stale_after_days": thresholds["stale_after_days"],
                    "critical_after_days": thresholds["critical_stale_after_days"],
                    "reason": f"File age {age_days}d exceeds freshness threshold for {category}",
                })

            if stale_years:
                stale_priority = "P0" if category == "policy" or sector == "crypto-bitcoin" else "P1"
                queue.append({
                    "path": rel_path,
                    "sector": sector,
                    "category": category,
                    "age_days": age_days,
                    "stale_type": "stale_reference",
                    "priority": stale_priority,
                    "stale_after_days": thresholds["stale_after_days"],
                    "critical_after_days": thresholds["critical_stale_after_days"],
                    "reason": f"Contains stale year references: {', '.join(stale_years)}",
                })
                summary["stale"] = summary.get("stale", 0) + 1

        # Also add missing files as P0
        for mf in sa.get("missing_files", []):
            queue.append({
                "path": f"sectors/{sector}/bd-market/{mf}",
                "sector": sector,
                "category": detect_category(mf),
                "age_days": 9999,
                "stale_type": "missing",
                "priority": "P0",
                "stale_after_days": 0,
                "critical_after_days": 0,
                "reason": "Required file is missing",
            })
            summary["critical"] = summary.get("critical", 0) + 1

    # Sort by priority
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    queue.sort(key=lambda x: priority_order.get(x["priority"], 9))

    # ── Inject P0 data-collection entries for sectors with zero evidence ──
    # Many sectors exist as files but the pipeline has never collected evidence
    # for them, so they never appear in the freshness queue. Insert explicit
    # entries so search queries get generated.
    evidence_dir = REPO_ROOT / "data" / "evidence"
    sector_with_evidence = set()
    if evidence_dir.exists():
        for ef in sorted(evidence_dir.glob("*.json"))[-5:]:  # last 5 files
            try:
                items = json.loads(ef.read_text())
                for item in items:
                    if item.get("sector"):
                        sector_with_evidence.add(item["sector"])
            except Exception:
                pass

    from lib.config_loader import get_sector_configs
    all_sectors = set(get_sector_configs().keys())
    zero_evidence_sectors = all_sectors - sector_with_evidence

    for zs in sorted(zero_evidence_sectors):
        # Add one data-collection entry per category for zero-evidence sectors
        for cat in ["pricing", "policy", "competitor_core_profile", "sentiment", "seasonality"]:
            key = f"{zs}:{cat}:data_collection"
            if not any(q.get("path", "").endswith(key) for q in queue):
                queue.append({
                    "path": f"sectors/{zs}/bd-market/data_collection:{cat}",
                    "sector": zs,
                    "category": cat,
                    "age_days": 9999,
                    "stale_type": "missing",
                    "priority": "P1",  # P1 (not P0) — zero-evidence sectors need initial data but shouldn't crowd out critical-stale items
                    "stale_after_days": 0,
                    "critical_after_days": 0,
                    "reason": f"Zero evidence collected for sector — initial data collection needed ({cat})",
                })
                summary["critical"] = summary.get("critical", 0) + 1

    result = {
        "generated_at": now_iso(),
        "summary": summary,
        "queue": queue,
    }

    output_path = state_dir / "freshness_queue.json"
    output_path.write_text(json.dumps(result, indent=2, default=str))

    log.info(f"\n=== FRESHNESS EVALUATION ===")
    log.info(f"Fresh: {summary.get('fresh', 0)}")
    log.info(f"Approaching stale: {summary.get('approaching_stale', 0)}")
    log.info(f"Stale: {summary.get('stale', 0)}")
    log.info(f"Critical: {summary.get('critical', 0)}")
    log.info(f"Queue size: {len(queue)}")
    log.info(f"Results saved to {output_path}")

    return result


if __name__ == "__main__":
    main()
