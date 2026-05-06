#!/usr/bin/env python3
"""update_sector_docs.py — Regenerate sector markdown files from JSON data.

Reads scored evidence and updates the corresponding sector markdown files
(README, landscape, competitors) with fresh data, preserving structure.
"""

import sys
import json
import logging
import re
import os
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso, DATA_DIR, get_sector_configs
from lib.llm_client import call_llm_text, load_prompt

log = logging.getLogger("update_sector_docs")

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.55"))


def load_scored_evidence() -> list:
    """Load the latest scored evidence."""
    evidence_dir = DATA_DIR / "evidence"
    if not evidence_dir.exists():
        return []
    files = sorted(evidence_dir.glob("*.json"))
    if not files:
        return []
    return json.loads(files[-1].read_text())


def group_evidence_by_sector(evidence: list) -> dict:
    """Group high-confidence evidence by sector."""
    grouped = {}
    for e in evidence:
        if e.get("confidence_score", 0) < CONFIDENCE_THRESHOLD:
            continue
        sector = e.get("sector", "unknown")
        if sector not in grouped:
            grouped[sector] = []
        grouped[sector].append(e)
    return grouped


def read_existing_file(path: Path) -> str:
    """Read existing markdown, stripping frontmatter."""
    if not path.exists():
        return ""
    content = path.read_text()
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            return content[end+3:].lstrip("\n")
    return content


def update_frontmatter(content: str, sector: str, updates: dict) -> str:
    """Update or add YAML frontmatter to a markdown file."""
    fm_lines = ["---"]
    fm_lines.append(f"sector: {sector}")
    
    if content.startswith("---"):
        # Parse existing frontmatter
        end = content.find("---", 3)
        if end > 0:
            fm_text = content[3:end].strip()
            existing = {}
            for line in fm_text.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    existing[k.strip()] = v.strip()
            # Merge updates
            existing.update(updates)
            for k, v in existing.items():
                fm_lines.append(f"{k}: {v}")
            fm_lines.append("---")
            body = content[end+3:].lstrip("\n")
            return "\n".join(fm_lines) + "\n\n" + body
    else:
        for k, v in updates.items():
            fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        return "\n".join(fm_lines) + "\n\n" + content


def inject_evidence_into_readme(existing: str, sector: str, evidence_items: list) -> str:
    """Inject high-confidence evidence into the README as an update section."""
    facts = []
    for e in evidence_items:
        for f in e.get("extracted_facts", []):
            if isinstance(f, dict):
                facts.append(f)
            elif isinstance(f, str):
                facts.append({"fact": f, "confidence": e.get("confidence_score", 0)})

    if not facts:
        return existing

    # Build update section
    update_section = f"\n## Auto-Updated Data ({datetime.now().strftime('%Y-%m-%d')})\n\n"
    update_section += "| Fact | Source | Confidence |\n"
    update_section += "|------|--------|------------|\n"
    
    for f in facts[:15]:  # Top 15 facts
        fact_text = f.get("fact", f.get("value", str(f)))[:80]
        source = f.get("source_domain", "search")
        conf = f.get("confidence", 0.5)
        update_section += f"| {fact_text} | {source} | {conf:.2f} |\n"

    # Check if auto-update section already exists
    marker = "## Auto-Updated Data"
    if marker in existing:
        # Replace existing auto-update section
        idx = existing.find(marker)
        # Find end of this section (next ## or end of file)
        next_h2 = existing.find("\n## ", idx + len(marker))
        if next_h2 > 0:
            existing = existing[:idx] + update_section + existing[next_h2:]
        else:
            existing = existing[:idx] + update_section.rstrip() + "\n"
    else:
        existing = existing.rstrip() + "\n" + update_section

    return existing


def update_sector_readme(sector: str, evidence_items: list, sector_dir: Path):
    """Update a sector's README.md with new evidence."""
    readme_path = sector_dir / "bd-market" / "README.md"
    existing = read_existing_file(readme_path)
    
    if not existing:
        log.warning(f"No README found for {sector}")
        return
    
    updated = inject_evidence_into_readme(existing, sector, evidence_items)
    
    # Update frontmatter
    updated = update_frontmatter(updated, sector, {
        "last_verified": datetime.now().strftime("%Y-%m-%d"),
        "freshness": "fresh",
        "confidence": round(
            sum(e.get("confidence_score", 0) for e in evidence_items) / max(len(evidence_items), 1), 3
        ),
        "evidence_ids": [e.get("evidence_id", "") for e in evidence_items[:20]],
    })
    
    readme_path.write_text(updated)
    log.info(f"Updated {readme_path.relative_to(REPO_ROOT)}")


def update_competitor_files(sector: str, evidence_items: list, sector_dir: Path):
    """Update competitor .md files with new evidence."""
    comp_dir = sector_dir / "bd-market" / "competitors"
    if not comp_dir.exists():
        return

    for comp_file in sorted(comp_dir.glob("*.md")):
        existing = read_existing_file(comp_file)
        if not existing:
            continue

        # Find evidence matching this competitor
        comp_slug = comp_file.stem  # e.g., 2026-05-06-aarong
        comp_name = comp_slug.split("-", 3)[-1] if "-" in comp_slug else comp_slug
        
        matching = [e for e in evidence_items 
                    if comp_name.lower() in e.get("query", "").lower() 
                    or comp_name.lower() in e.get("snippet", "").lower()]
        
        if not matching:
            continue

        # Add recent findings section
        findings = f"\n## Recent Findings ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        for e in matching[:5]:
            snippet = e.get("snippet", "")[:200]
            source = e.get("source_domain", "")
            conf = e.get("confidence_score", 0)
            findings += f"- **{source}** (conf: {conf:.2f}): {snippet}\n\n"

        marker = "## Recent Findings"
        if marker in existing:
            idx = existing.find(marker)
            next_h2 = existing.find("\n## ", idx + len(marker))
            if next_h2 > 0:
                existing = existing[:idx] + findings + existing[next_h2:]
            else:
                existing = existing[:idx] + findings.rstrip() + "\n"
        else:
            existing = existing.rstrip() + "\n" + findings

        # Update frontmatter
        existing = update_frontmatter(existing, sector, {
            "last_verified": datetime.now().strftime("%Y-%m-%d"),
            "freshness": "fresh",
        })

        comp_file.write_text(existing)
        log.info(f"Updated {comp_file.relative_to(REPO_ROOT)}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    evidence = load_scored_evidence()
    if not evidence:
        log.info("No evidence to process. Run execute_searches + extract_facts + score_confidence first.")
        return

    by_sector = group_evidence_by_sector(evidence)
    log.info(f"Evidence for {len(by_sector)} sectors meets confidence threshold ({CONFIDENCE_THRESHOLD})")

    sectors_dir = REPO_ROOT / "sectors"
    updated_count = 0

    for sector, items in by_sector.items():
        sector_dir = sectors_dir / sector
        if not sector_dir.exists():
            log.warning(f"Sector directory not found: {sector}")
            continue

        log.info(f"\nUpdating sector: {sector} ({len(items)} evidence items)")
        
        # Update README
        update_sector_readme(sector, items, sector_dir)
        
        # Update competitor files
        update_competitor_files(sector, items, sector_dir)
        
        updated_count += 1

    # Validate markdown after updates
    from validate_markdown import validate_all
    issues = validate_all()
    if issues:
        log.warning(f"Markdown validation found {len(issues)} issues after updates")

    log.info(f"\n=== SECTOR DOC UPDATE SUMMARY ===")
    log.info(f"Sectors updated: {updated_count}")
    log.info(f"Evidence items applied: {sum(len(v) for v in by_sector.values())}")


if __name__ == "__main__":
    main()
