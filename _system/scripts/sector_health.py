#!/usr/bin/env python3
"""sector_health.py — Sector health dashboard.

Reads sector-index JSONs, audit results, and evidence to produce
a real-time health overview of all sectors in the repo.

Usage:
    python _system/scripts/sector_health.py
    python _system/scripts/sector_health.py --json   # machine-readable output
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SECTOR_INDEX_DIR = REPO_ROOT / "data" / "sector-index"
STATE_DIR = REPO_ROOT / "_system" / "state"
SECTORS_DIR = REPO_ROOT / "sectors"
EVIDENCE_DIR = REPO_ROOT / "data" / "evidence"

EXPECTED_DOCS = [
    "README.md",
    "strategy-canvas.md",
    "go-to-market.md",
    "risk-register.md",
    "pricing-guide.md",
    "regulatory.md",
    "sentiment-analysis.md",
    "seasonality.md",
    "financial-model.md",
]


def load_sector_indices():
    """Load all sector-index JSON files."""
    if not SECTOR_INDEX_DIR.exists():
        return {}
    indices = {}
    for f in sorted(SECTOR_INDEX_DIR.glob("*.json")):
        indices[f.stem] = json.loads(f.read_text())
    return indices


def load_audit():
    """Load latest audit results."""
    audit_path = STATE_DIR / "audit_results.json"
    if audit_path.exists():
        return json.loads(audit_path.read_text())
    return None


def load_latest_evidence_stats():
    """Compute evidence counts per sector from latest evidence files."""
    if not EVIDENCE_DIR.exists():
        return {}
    files = sorted(EVIDENCE_DIR.glob("*.json"))
    if not files:
        return {}

    # Use last few files for a rolling picture
    recent = files[-5:]
    sector_counts = {}
    sector_confidences = {}

    for f in recent:
        try:
            data = json.loads(f.read_text())
            for item in data:
                sector = item.get("sector", "unknown")
                score = item.get("confidence_score", 0.0)
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
                if sector not in sector_confidences:
                    sector_confidences[sector] = []
                sector_confidences[sector].append(score)
        except (json.JSONDecodeError, Exception):
            continue

    # Average confidence
    avg_conf = {}
    for s, scores in sector_confidences.items():
        avg_conf[s] = round(sum(scores) / len(scores), 3) if scores else 0.0

    return {"counts": sector_counts, "avg_confidence": avg_conf}


def compute_disk_usage(sector_name: str) -> tuple:
    """Return file count and total size MB for a sector."""
    sector_path = SECTORS_DIR / sector_name
    if not sector_path.exists():
        return (0, 0.0)
    file_count = 0
    total_bytes = 0
    for f in sector_path.rglob("*"):
        if f.is_file():
            file_count += 1
            total_bytes += f.stat().st_size
    return (file_count, round(total_bytes / (1024 * 1024), 2))


def health_status(score: float) -> str:
    """Return a coloured status string based on health score."""
    if score >= 0.8:
        return "✅ Excellent"
    elif score >= 0.6:
        return "🟢 Good"
    elif score >= 0.4:
        return "🟡 Fair"
    elif score >= 0.2:
        return "🟠 Poor"
    else:
        return "🔴 Critical"


def main():
    parser = argparse.ArgumentParser(description="Sector health dashboard")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    args = parser.parse_args()

    indices = load_sector_indices()
    audit = load_audit()
    evidence_stats = load_latest_evidence_stats()

    # Build sector list from directories
    sector_dirs = sorted([
        d.name for d in SECTORS_DIR.iterdir()
        if d.is_dir() and (d / "bd-market").exists()
    ])

    if not sector_dirs:
        print("No sectors found.")
        return

    rows = []
    for sname in sector_dirs:
        idx = indices.get(sname, {})
        files, size_mb = compute_disk_usage(sname)

        # Count actual docs present
        bd_dir = SECTORS_DIR / sname / "bd-market"
        present_docs = sum(1 for d in EXPECTED_DOCS if (bd_dir / d).exists())
        doc_ratio = present_docs / len(EXPECTED_DOCS) if EXPECTED_DOCS else 0

        # Competitor info
        comp_count = idx.get("competitor_count", 0)
        comp_target = idx.get("competitor_target", 10)
        comp_ratio = comp_count / comp_target if comp_target else 0

        # Evidence
        ev_count = evidence_stats.get("counts", {}).get(sname, 0)
        avg_conf = evidence_stats.get("avg_confidence", {}).get(sname, 0.0)

        # Health score: weighted combination
        health = round(
            doc_ratio * 0.35 +
            comp_ratio * 0.25 +
            min(ev_count / 50, 1.0) * 0.20 +
            avg_conf * 0.20,
            3
        )

        rows.append({
            "sector": sname,
            "display": idx.get("display_name", sname.replace("-", " ").title()),
            "files": files,
            "size_mb": size_mb,
            "docs": f"{present_docs}/{len(EXPECTED_DOCS)}",
            "comp": f"{comp_count}/{comp_target}",
            "evidence": ev_count,
            "confidence": avg_conf,
            "health": health,
            "status": health_status(health),
        })

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    # ── Table output ──────────────────────────────────────────
    status_width = max(len(r["status"]) for r in rows) if rows else 12

    print(f"\n{'=' * 90}")
    print(f"  BUSINESS PLAN TEMPLATE — SECTOR HEALTH DASHBOARD")
    print(f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'=' * 90}")
    print()
    print(f"  {'Sector':<28} {'Files':>6} {'Size':>6} {'Docs':>8} {'Comp':>10} {'Evid.':>6} {'Conf.':>7} {'Health':>7}  Status")
    print(f"  {'-'*27} {'-'*6} {'-'*6} {'-'*8} {'-'*10} {'-'*6} {'-'*7} {'-'*7}  {'-'*12}")
    for r in rows:
        print(
            f"  {r['display']:<28} "
            f"{r['files']:>6} "
            f"{r['size_mb']:>5.1f}M "
            f"{r['docs']:>8} "
            f"{r['comp']:>10} "
            f"{r['evidence']:>6} "
            f"{r['confidence']:>6.2f} "
            f"{r['health']:>6.2f}  "
            f"{r['status']}"
        )
    print()

    # Summary
    avg_health = sum(r["health"] for r in rows) / len(rows) if rows else 0
    total_files = sum(r["files"] for r in rows)
    total_evidence = sum(r["evidence"] for r in rows)
    healthy_count = sum(1 for r in rows if r["health"] >= 0.6)
    print(f"  {'─' * 88}")
    print(f"  Total: {len(rows)} sectors, {total_files} files, {total_evidence} evidence items")
    print(f"  Avg health: {avg_health:.2f}  |  Healthy (≥0.6): {healthy_count}/{len(rows)}")
    print()

    # Bottom-line alerts
    critical = [r for r in rows if r["health"] < 0.4]
    if critical:
        print(f"  ⚠ Sectors needing attention:")
        for r in critical:
            print(f"    {r['display']:<30} health={r['health']} — evidence={r['evidence']}, conf={r['confidence']}")
        print()

    evidence_gaps = [r for r in rows if r["evidence"] == 0]
    if evidence_gaps:
        print(f"  ⚠ Sectors with zero evidence (pipeline not collecting data):")
        for r in evidence_gaps:
            print(f"    {r['display']:<30} — no evidence items in recent runs")

    # Recommended actions
    print()
    print(f"  Recommended next steps:")
    if evidence_gaps:
        print(f"    - Run pipeline for zero-evidence sectors to bootstrap data collection")
    low_docs = [r for r in rows if r["health"] < 0.6]
    if low_docs:
        print(f"    - Generate missing docs for {len(low_docs)} sectors (financial-model, idea-brief)")
    print(f"    - Run 'make pipeline' to refresh all evidence and update docs")
    print(f"  {'=' * 90}")
    print()


if __name__ == "__main__":
    main()
