#!/usr/bin/env python3
"""generate_sidecars.py — Extract competitor data from markdown into JSON sidecars.

Reads all competitor markdown files and produces:
  data/competitors/all_competitors.json         — aggregate index
  data/competitors/<sector>.json                — per-sector sidecar
  data/competitors/YYYY-MM-DD-<slug>.json       — per-competitor sidecar

Run after any competitor markdown is created or updated.
Add to pipeline: this is fast (<1s), no network or LLM calls needed.
"""

import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPETITORS_DIR = REPO_ROOT / "sectors"
DATA_DIR = REPO_ROOT / "data" / "competitors"


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter fields as a flat dict."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for k, v in re.findall(r"^(\w[\w_]*):\s*(.*)?$", m.group(1), re.MULTILINE):
        result[k.strip()] = v.strip().strip("\"'") if v else ""
    return result


def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a ## Heading section."""
    m = re.search(rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _numbered_items(text: str) -> list[str]:
    """Extract numbered/bullet list items from text."""
    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+\.\s", stripped):
            items.append(stripped)
        elif stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def extract_competitor(fpath: Path) -> dict:
    """Parse a single competitor markdown into a structured JSON sidecar."""
    text = fpath.read_text()
    fm = parse_frontmatter(text)
    slug = fpath.stem
    sector = fm.get("sector", fpath.parts[1] if len(fpath.parts) > 1 else "unknown")
    name = slug.split("-", 3)[-1] if "-" in slug else slug

    threatsect = _extract_section(text, "Threat Level")
    pricingsect = _extract_section(text, "Pricing Signals")

    # Parse pricing table rows (pipe-delimited, skip header/separator)
    pricing_rows = []
    for line in pricingsect.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---") and stripped != "||":
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] != "Item":
                pricing_rows.append({
                    "item": cells[0] if len(cells) > 0 else "",
                    "value": cells[1] if len(cells) > 1 else "",
                    "date": cells[2] if len(cells) > 2 else "",
                    "source": cells[3] if len(cells) > 3 else "",
                })

    return {
        "slug": slug,
        "name": name,
        "sector": sector,
        "frontmatter": fm,
        "profile_category": fm.get("category", ""),
        "entity_slug": fm.get("entity_slug", slug),
        "last_verified_at": fm.get("last_verified_at", ""),
        "freshness_status": fm.get("freshness_status", "unknown"),
        "confidence_score": float(fm.get("confidence_score", 0) or 0),
        "strengths": _numbered_items(_extract_section(text, "Strengths")),
        "weaknesses": _numbered_items(_extract_section(text, "Weaknesses")),
        "threat_level": threatsect.split("\n")[0].strip() if threatsect else "",
        "threat_overlap_score": None,
        "pricing_signals": pricing_rows,
        "customer_segments": _numbered_items(_extract_section(text, "Customer Segments")),
        "operations_notes": _extract_section(text, "Operations & Supply Chain")[:200] if _extract_section(text, "Operations & Supply Chain") else "",
        "financial_signals": _extract_section(text, "Financial/Funding Signals")[:200] if _extract_section(text, "Financial/Funding Signals") else "",
        "sentiment_summary": _extract_section(text, "Reviews & Sentiment")[:200] if _extract_section(text, "Reviews & Sentiment") else "",
        "compliance_notes": _extract_section(text, "Compliance/Regulatory Notes")[:200] if _extract_section(text, "Compliance/Regulatory Notes") else "",
        "evidence_sources": _numbered_items(_extract_section(text, "Evidence & Sources")),
        "file_path": str(fpath.relative_to(REPO_ROOT)),
    }


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="generate_sidecars %(levelname)s: %(message)s")
    log = logging.getLogger("generate_sidecars")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_competitors = []
    sector_groups: dict[str, list[dict]] = {}

    for fpath in sorted(COMPETITORS_DIR.rglob("competitors/*.md")):
        if not fpath.is_file():
            continue
        entry = extract_competitor(fpath)
        all_competitors.append(entry)
        sector_groups.setdefault(entry["sector"], []).append(entry)

    # Save aggregate
    aggregate = {"total": len(all_competitors), "competitors": all_competitors}
    (DATA_DIR / "all_competitors.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False, default=str)
    )

    # Save per-sector
    for sector, entries in sorted(sector_groups.items()):
        sector_data = {
            "sector": sector,
            "total": len(entries),
            "competitors": entries,
        }
        (DATA_DIR / f"{sector}.json").write_text(
            json.dumps(sector_data, indent=2, ensure_ascii=False, default=str)
        )

    # Save per-competitor
    for entry in all_competitors:
        (DATA_DIR / f"{entry['slug']}.json").write_text(
            json.dumps(entry, indent=2, ensure_ascii=False, default=str)
        )

    # Stats
    with_pricing = sum(1 for c in all_competitors if c["pricing_signals"])
    with_evidence = sum(1 for c in all_competitors if c["evidence_sources"])
    complete = sum(1 for c in all_competitors if len(c["strengths"]) >= 3 and len(c["weaknesses"]) >= 3 and c["pricing_signals"])

    log.info(f"Generated {len(all_competitors)} competitor sidecars across {len(sector_groups)} sectors")
    log.info(f"  Complete (3+ str, 3+ wk, pricing): {complete}")
    log.info(f"  With pricing signals: {with_pricing}")
    log.info(f"  With evidence sources: {with_evidence}")

    for sector in sorted(sector_groups):
        sc = sector_groups[sector]
        sc_complete = sum(1 for c in sc if len(c["strengths"]) >= 3 and len(c["weaknesses"]) >= 3 and c["pricing_signals"])
        log.info(f"  {sector}: {len(sc)} profiles, {sc_complete} complete")


if __name__ == "__main__":
    main()