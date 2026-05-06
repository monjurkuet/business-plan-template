#!/usr/bin/env python3
"""generate_changelog.py — Generate a human-readable changelog from pipeline state.

Reads evidence, scoring, and update results to produce a CHANGELOG entry
for this pipeline run.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso, DATA_DIR

log = logging.getLogger("generate_changelog")


def load_state(key: str) -> dict:
    """Load a state file by key name."""
    state_dir = REPO_ROOT / "_system" / "state"
    path = state_dir / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def load_latest_evidence() -> list:
    """Load latest evidence."""
    evidence_dir = DATA_DIR / "evidence"
    if not evidence_dir.exists():
        return []
    files = sorted(evidence_dir.glob("*.json"))
    if not files:
        return []
    return json.loads(files[-1].read_text())


def generate_entry() -> str:
    """Generate a changelog entry for this run."""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d %H:%M UTC")
    
    audit = load_state("audit_results")
    fq = load_state("freshness_queue")
    search_plan = load_state("search_plan")
    evidence = load_latest_evidence()
    
    lines = [f"## {date_str}", ""]
    
    # Audit summary
    if audit:
        total = audit.get("total_files", 0)
        sectors = len(audit.get("sectors", {}))
        lines.append(f"**Repo Audit**: {total} files across {sectors} sectors")
    
    # Freshness queue
    if fq:
        queue = fq.get("queue", [])
        p0 = sum(1 for q in queue if q.get("priority") == "P0")
        p1 = sum(1 for q in queue if q.get("priority") == "P1")
        p2 = sum(1 for q in queue if q.get("priority") == "P2")
        lines.append(f"**Freshness Queue**: {len(queue)} items (P0: {p0}, P1: {p1}, P2: {p2})")
    
    # Search execution
    if search_plan:
        n_queries = search_plan.get("total_queries", 0)
        lines.append(f"**Searches Executed**: {n_queries} queries")
    
    # Evidence
    if evidence:
        total_facts = sum(len(e.get("extracted_facts", [])) for e in evidence)
        high_conf = sum(1 for e in evidence if e.get("confidence_score", 0) >= 0.75)
        avg_conf = sum(e.get("confidence_score", 0) for e in evidence) / max(len(evidence), 1)
        lines.append(f"**Evidence Collected**: {len(evidence)} items, {total_facts} facts extracted")
        lines.append(f"**Confidence**: {high_conf} high (>=0.75), avg {avg_conf:.2f}")
        
        # Sector breakdown
        by_sector = {}
        for e in evidence:
            s = e.get("sector", "unknown")
            by_sector.setdefault(s, []).append(e)
        
        if by_sector:
            lines.append("")
            lines.append("### Sector Breakdown")
            for sector, items in sorted(by_sector.items()):
                facts = sum(len(e.get("extracted_facts", [])) for e in items)
                avg = sum(e.get("confidence_score", 0) for e in items) / max(len(items), 1)
                lines.append(f"- **{sector}**: {len(items)} evidence, {facts} facts, avg conf {avg:.2f}")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    entry = generate_entry()
    
    # Prepend to CHANGELOG.md
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    
    if changelog_path.exists():
        existing = changelog_path.read_text()
        # Insert after the header if there is one
        if existing.startswith("# "):
            first_nl = existing.find("\n")
            header = existing[:first_nl+1]
            body = existing[first_nl+1:]
            changelog_path.write_text(header + "\n" + entry + body)
        else:
            changelog_path.write_text(entry + existing)
    else:
        changelog_path.write_text("# Changelog\n\n" + entry)
    
    log.info(f"Changelog entry added to {changelog_path}")
    log.info(entry)


if __name__ == "__main__":
    main()
