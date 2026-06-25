#!/usr/bin/env python3
"""migrate_to_12section.py — Convert old-format competitor profiles to 12-section format.

Strategy: For each competitor, extract existing data (name, sector, profile table, strengths,
weaknesses, threat level, any evidence) and wrap it in the new 12-section template.
When the old file has pricing/evidence data, include it. When missing, mark as TODO.

Run: python3 _system/scripts/migrate_to_12section.py [--sector=sector-slug]
Omit --sector to process all 7 old-format sectors (skips crypto-bitcoin).
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SECTORS_DIR = REPO_ROOT / "sectors"
MIGRATED_LOG = REPO_ROOT / "_system" / "state" / "migration_log.json"

ALREADY_DONE = {
    "crypto-bitcoin",  # already in 12-section format
}

def parse_old_frontmatter(text: str) -> dict:
    """Parse the old frontmatter (sector, last_verified, freshness, confidence)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for k, v in re.findall(r"^(\w[\w_]*):\s*(.*)?$", m.group(1), re.MULTILINE):
        result[k.strip()] = v.strip().strip("\"'") if v else ""
    return result

def parse_profile_table(text: str) -> dict:
    """Extract the Profile table rows."""
    m = re.search(r"## Profile\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    if not m:
        return {}
    rows = {}
    for line in m.group(1).split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] != "Field":
                rows[cells[0]] = cells[1] if len(cells) > 1 else ""
    return rows

def parse_section(text: str, heading: str) -> str:
    """Extract paragraph content of a ## heading."""
    m = re.search(rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""

def name_from_path(fpath: Path) -> str:
    """Derive human-readable name from filename."""
    stem = fpath.stem
    # Strip YYYY-MM-DD- prefix
    parts = stem.split("-", 3)
    if len(parts) >= 4:
        return parts[3].replace("-", " ").title()
    return stem.replace("-", " ").title()

def migrate_one(fpath: Path) -> tuple[bool, str]:
    """Migrate one competitor file to 12-section format. Returns (changed, reason)."""
    text = fpath.read_text()
    fm = parse_old_frontmatter(text)
    profile = parse_profile_table(text)
    name = profile.get("Competitor name", name_from_path(fpath))
    sector = fm.get("sector", fpath.parts[1] if len(fpath.parts) > 1 else "unknown")
    slug = fpath.stem

    # Check if already migrated (has entity_type frontmatter)
    if "entity_type" in fm:
        return False, "already migrated"

    # Extract existing data
    strengths_raw = parse_section(text, "Strengths")
    weaknesses_raw = parse_section(text, "Weaknesses")
    threat_raw = parse_section(text, "Threat Level")
    overview_raw = parse_section(text, "Overview") or parse_section(text, "Business Model")
    recent_raw = parse_section(text, "Recent Findings")
    verified_raw = parse_section(text, "Key Metrics")
    strategy_raw = parse_section(text, "Strategy Observation")
    fb_data = parse_section(text, "Verified Facebook Data")

    # Convert strengths/weaknesses from paragraph to bullet list
    def para_to_bullets(raw: str) -> list[str]:
        """Convert paragraph text to bullet points."""
        if not raw:
            return []
        sentences = re.split(r'(?<=[.!?])\s+', raw)
        items = []
        for s in sentences:
            s = s.strip()
            if s and len(s) > 10:
                items.append(s)
        if not items:
            items = [raw]
        return items

    strengths = para_to_bullets(strengths_raw)
    weaknesses = para_to_bullets(weaknesses_raw)

    # Derive threat level
    threat_level = "Medium"
    if threat_raw:
        first_line = threat_raw.split("\n")[0].strip()
        if any(t in first_line.lower() for t in ["high", "critical"]):
            threat_level = "High"
        elif any(t in first_line.lower() for t in ["low"]):
            threat_level = "Low"
        elif "medium" in first_line.lower():
            threat_level = "Medium"

    # Collect evidence fragments
    evidence = []
    if recent_raw:
        for line in recent_raw.split("\n"):
            if "http" in line or "www." in line:
                evidence.append(line.strip())
    if fb_data:
        evidence.append(fb_data[:200] + ("..." if len(fb_data) > 200 else ""))

    # Build new frontmatter
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT12:00:00Z")
    conf = float(fm.get("confidence", 0.5) or 0.5)
    freshness = fm.get("freshness", "fresh")

    new_fm = f"""---
entity_type: competitor
sector: {sector}
entity_slug: {slug}
last_verified_at: {today}
freshness_status: {freshness}
confidence_score: {conf:.2f}
primary_sources:
{chr(10).join(f'  - {e[:80]}' for e in evidence[:5]) or '  - []'}
---"""

    # Build strengths/weaknesses numbered lists
    str_list = "\n".join(f"{i}. {s}" for i, s in enumerate(strengths, 1)) or "1. *TODO: Research strengths*"
    wk_list = "\n".join(f"{i}. {w}" for i, w in enumerate(weaknesses, 1)) or "1. *TODO: Research weaknesses*"

    # Profile table
    fb = profile.get("Facebook", profile.get("facebook", "") or profile.get("URL", ""))
    followers = profile.get("Followers", profile.get("followers", "") or profile.get("Active Users", ""))
    location = profile.get("Location", profile.get("location", "") or profile.get("HQ", ""))
    verified = profile.get("Verified", profile.get("verified", "") or "Unknown")
    category = profile.get("Category", profile.get("category", "") or profile.get("Type", ""))

    new_body = f"""
# Competitor: {name}

## Metadata

- **Date:** 2026-06-25
- **Last updated:** 2026-06-25
- **Competitor name:** {name}
- **Sector:** {sector}

---

## Profile

| Field | Detail |
|-------|--------|
| Category | {category} |
| Facebook/URL | {fb} |
| Followers | {followers} |
| Location | {location} |
| Verified | {verified} |

---

## Strengths

{str_list}

## Weaknesses

{wk_list}

---

## Threat Level: {threat_level}

*Source data migrated from old format on 2026-06-25. Full research needed for competitive depth.*

---

## Pricing Signals

| Item | Price/Metric | Date | Source |
|------|-------------|------|--------|
| *TODO* | *Research needed* | 2026-06 | |

---

## Customer Segments

*TODO: Research from BD market sources*

---

## Operations & Supply Chain

*TODO: Research from BD market sources*

---

## Financial/Funding Signals

| Metric | Detail |
|--------|--------|
| *TODO* | *Research needed* |

---

## Reviews & Sentiment

*TODO: Research from BD market sources*

---

## Compliance/Regulatory Notes

*TODO: Research from BD market sources*

---

## Evidence & Sources

{chr(10).join(f'- {e}' for e in evidence) if evidence else '- *TODO: Add verifiable sources*'}

*Last updated: 2026-06-25 — migrated from old format*"""

    # Preserve old data as an appendix
    if overview_raw or strategy_raw or recent_raw:
        appendix = "\n\n---\n\n## ⚠️ Raw Old-Format Data (To Be Refined Into Sections Above)\n\n"
        if overview_raw:
            appendix += f"### Overview\n{overview_raw}\n\n"
        if strategy_raw:
            appendix += f"### Strategy Observation\n{strategy_raw}\n\n"
        if recent_raw:
            appendix += f"### Recent Findings\n{recent_raw}\n\n"
        if verified_raw:
            appendix += f"### Key Metrics (Verified)\n{verified_raw}\n\n"
        new_body += appendix

    new_content = new_fm + new_body
    fpath.write_text(new_content)
    return True, f"migrated ({len(strengths)} strengths, {len(weaknesses)} weaknesses, {len(evidence)} evidence)"


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="migrate %(levelname)s: %(message)s")
    log = logging.getLogger("migrate")

    sector_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--sector="):
            sector_filter = arg.split("=", 1)[1]

    migrated = []
    skipped = []
    for sector_dir in sorted(SECTORS_DIR.iterdir()):
        if not sector_dir.is_dir():
            continue
        sector = sector_dir.name
        if sector in ALREADY_DONE:
            continue
        if sector_filter and sector != sector_filter:
            continue

        comp_dir = sector_dir / "bd-market" / "competitors"
        if not comp_dir.is_dir():
            continue

        for fpath in sorted(comp_dir.glob("*.md")):
            try:
                changed, reason = migrate_one(fpath)
                if changed:
                    migrated.append(str(fpath.relative_to(REPO_ROOT)))
                    log.info(f"  ✅ {fpath.relative_to(REPO_ROOT)} — {reason}")
                else:
                    skipped.append(str(fpath.relative_to(REPO_ROOT)))
                    log.debug(f"  ⏭️  {fpath.relative_to(REPO_ROOT)} — {reason}")
            except Exception as e:
                log.error(f"  ❌ {fpath.relative_to(REPO_ROOT)} — {e}")

    log.info(f"\nDone: {len(migrated)} migrated, {len(skipped)} skipped")
    MIGRATED_LOG.parent.mkdir(parents=True, exist_ok=True)
    MIGRATED_LOG.write_text(json.dumps({
        "migrated": migrated,
        "skipped": skipped,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


if __name__ == "__main__":
    main()