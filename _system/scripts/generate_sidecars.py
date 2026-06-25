#!/usr/bin/env python3
"""generate_sidecars.py — Extract markdown docs into structured JSON sidecars.

Phase 1: Competitor profiles (competitors/*.md)
  data/competitors/all_competitors.json         — aggregate index
  data/competitors/<sector>.json                — per-sector sidecar
  data/competitors/YYYY-MM-DD-<slug>.json       — per-competitor sidecar

Phase 2: Pricing guides (pricing-guide.md)
Phase 3: Sentiment analysis (sentiment-analysis.md)
Phase 4: Compliance/regulatory (regulatory.md, regulatory-compliance.md)

Run after any markdown is created or updated. Fast (<1s), no network/LLM.
"""

import sys
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SECTORS_DIR = REPO_ROOT / "sectors"
DATA_DIR = REPO_ROOT / "data"


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


def parse_table(text: str) -> list[dict]:
    """Parse a markdown table (pipe-delimited) into list of dicts."""
    rows = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---") and stripped != "||":
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] != "Item":
                rows.append({
                    "item": cells[0] if len(cells) > 0 else "",
                    "value": cells[1] if len(cells) > 1 else "",
                    "date": cells[2] if len(cells) > 2 else "",
                    "source": cells[3] if len(cells) > 3 else "",
                })
    return rows


# ── Phase 1: Competitor profiles ──────────────────────────────────


def extract_competitor(fpath: Path) -> dict:
    """Parse a single competitor markdown into a structured JSON sidecar."""
    text = fpath.read_text()
    fm = parse_frontmatter(text)
    slug = fpath.stem
    sector = fm.get("sector", fpath.parts[1] if len(fpath.parts) > 1 else "unknown")
    name = slug.split("-", 3)[-1] if "-" in slug else slug

    threatsect = _extract_section(text, "Threat Level")
    pricingsect = _extract_section(text, "Pricing Signals")

    return {
        "doc_type": "competitor",
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
        "pricing_signals": parse_table(pricingsect),
        "customer_segments": _numbered_items(_extract_section(text, "Customer Segments")),
        "operations_notes": _extract_section(text, "Operations & Supply Chain")[:200] if _extract_section(text, "Operations & Supply Chain") else "",
        "financial_signals": _extract_section(text, "Financial/Funding Signals")[:200] if _extract_section(text, "Financial/Funding Signals") else "",
        "sentiment_summary": _extract_section(text, "Reviews & Sentiment")[:200] if _extract_section(text, "Reviews & Sentiment") else "",
        "compliance_notes": _extract_section(text, "Compliance/Regulatory Notes")[:200] if _extract_section(text, "Compliance/Regulatory Notes") else "",
        "evidence_sources": _numbered_items(_extract_section(text, "Evidence & Sources")),
        "file_path": str(fpath.relative_to(REPO_ROOT)),
    }


# ── Phase 2: Pricing guides ───────────────────────────────────────


def extract_pricing_guide(fpath: Path) -> dict:
    """Parse a pricing-guide.md into structured sidecar."""
    text = fpath.read_text()
    fm = parse_frontmatter(text)
    sector = fm.get("sector", fpath.parts[1])

    pricing_table = parse_table(_extract_section(text, "Market Price Ranges"))
    service_table = parse_table(_extract_section(text, "Service/Product"))

    # Try both heading patterns
    if not pricing_table and service_table:
        pricing_table = service_table

    return {
        "doc_type": "pricing_guide",
        "sector": sector,
        "last_verified_at": fm.get("last_verified_at", ""),
        "freshness_status": fm.get("freshness_status", "unknown"),
        "confidence_score": float(fm.get("confidence_score", 0) or 0),
        "pricing_entries": pricing_table,
        "total_entries": len(pricing_table),
        "has_data": any(e["value"] not in ("*TODO*", "*Research needed*", "*Pending*", "") for e in pricing_table),
        "file_path": str(fpath.relative_to(REPO_ROOT)),
    }


# ── Phase 3: Sentiment analysis ───────────────────────────────────


def extract_sentiment(fpath: Path) -> dict:
    """Parse a sentiment-analysis.md into structured sidecar."""
    text = fpath.read_text()
    fm = parse_frontmatter(text)
    sector = fm.get("sector", fpath.parts[1])

    sentiment_text = _extract_section(text, "Overall Market Sentiment")
    positive_themes = _numbered_items(_extract_section(text, "Top Positive Themes"))
    negative_themes = _numbered_items(_extract_section(text, "Top Negative Themes"))
    review_volume_table = parse_table(_extract_section(text, "Review Volume by Platform")) or \
                          parse_table(_extract_section(text, "Review Volume"))

    # Determine if data is populated
    has_data = bool(positive_themes or negative_themes) and \
               all(t not in sentiment_text for t in ["*Pending", "*Awaiting", "*TODO"])

    return {
        "doc_type": "sentiment_analysis",
        "sector": sector,
        "last_verified_at": fm.get("last_verified_at", ""),
        "freshness_status": fm.get("freshness_status", "unknown"),
        "confidence_score": float(fm.get("confidence_score", 0) or 0),
        "overall_sentiment": sentiment_text[:300] if sentiment_text else "",
        "positive_themes": positive_themes,
        "negative_themes": negative_themes,
        "review_volume": review_volume_table,
        "has_data": has_data,
        "file_path": str(fpath.relative_to(REPO_ROOT)),
    }


# ── Phase 4: Compliance/regulatory ────────────────────────────────


def extract_regulatory(fpath: Path) -> dict:
    """Parse a regulatory.md into structured sidecar."""
    text = fpath.read_text()
    fm = parse_frontmatter(text)
    sector = fm.get("sector", fpath.parts[1])

    legal_status = _extract_section(text, "Legal Status")
    biz_registration = _numbered_items(_extract_section(text, "Business Registration"))
    sector_requirements = _numbered_items(_extract_section(text, "Sector-Specific Requirements"))
    key_bodies = _numbered_items(_extract_section(text, "Key Regulatory Bodies"))

    # Also check for "Regulatory Requirements" heading (alternate format)
    if not legal_status:
        legal_status = _extract_section(text, "Regulatory Requirements")[:300]

    has_data = bool(biz_registration or sector_requirements or key_bodies)

    return {
        "doc_type": "regulatory",
        "sector": sector,
        "last_verified_at": fm.get("last_verified_at", ""),
        "freshness_status": fm.get("freshness_status", "unknown"),
        "confidence_score": float(fm.get("confidence_score", 0) or 0),
        "legal_status": legal_status[:300] if legal_status else "",
        "registration_requirements": biz_registration,
        "sector_specific_requirements": sector_requirements,
        "regulatory_bodies": key_bodies,
        "has_data": has_data,
        "file_path": str(fpath.relative_to(REPO_ROOT)),
    }


# ── Main ────────────────────────────────────────────────────────────


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="generate_sidecars %(levelname)s: %(message)s")
    log = logging.getLogger("generate_sidecars")

    comp_dir = DATA_DIR / "competitors"
    comp_dir.mkdir(parents=True, exist_ok=True)

    meta_dir = DATA_DIR / "sector-research"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Competitors ──
    all_competitors = []
    sector_groups: dict[str, list[dict]] = {}

    for fpath in sorted(SECTORS_DIR.rglob("competitors/*.md")):
        if not fpath.is_file():
            continue
        entry = extract_competitor(fpath)
        all_competitors.append(entry)
        sector_groups.setdefault(entry["sector"], []).append(entry)

    # Save aggregate
    (comp_dir / "all_competitors.json").write_text(
        json.dumps({"total": len(all_competitors), "competitors": all_competitors},
                   indent=2, ensure_ascii=False, default=str))
    for sector, entries in sector_groups.items():
        (comp_dir / f"{sector}.json").write_text(
            json.dumps({"sector": sector, "total": len(entries), "competitors": entries},
                       indent=2, ensure_ascii=False, default=str))
    for entry in all_competitors:
        (comp_dir / f"{entry['slug']}.json").write_text(
            json.dumps(entry, indent=2, ensure_ascii=False, default=str))

    with_pricing = sum(1 for c in all_competitors if c["pricing_signals"])
    complete = sum(1 for c in all_competitors if len(c["strengths"]) >= 3 and len(c["weaknesses"]) >= 3 and c["pricing_signals"])
    log.info(f"Phase 1: {len(all_competitors)} competitor sidecars, {complete} complete, {with_pricing} with pricing")

    # ── Phase 2: Pricing guides ──
    pricing_index = []
    for fpath in sorted(SECTORS_DIR.rglob("bd-market/pricing-guide.md")):
        entry = extract_pricing_guide(fpath)
        pricing_index.append(entry)
        # Write per-sector
        (meta_dir / f"pricing_{entry['sector']}.json").write_text(
            json.dumps(entry, indent=2, ensure_ascii=False, default=str))

    (meta_dir / "pricing_all.json").write_text(
        json.dumps({"total": len(pricing_index), "entries": pricing_index},
                   indent=2, ensure_ascii=False, default=str))
    with_data = sum(1 for p in pricing_index if p["has_data"])
    log.info(f"Phase 2: {len(pricing_index)} pricing guides, {with_data} with real data")

    # ── Phase 3: Sentiment ──
    sentiment_index = []
    for fpath in sorted(SECTORS_DIR.rglob("bd-market/sentiment-analysis.md")):
        entry = extract_sentiment(fpath)
        sentiment_index.append(entry)
        (meta_dir / f"sentiment_{entry['sector']}.json").write_text(
            json.dumps(entry, indent=2, ensure_ascii=False, default=str))

    (meta_dir / "sentiment_all.json").write_text(
        json.dumps({"total": len(sentiment_index), "entries": sentiment_index},
                   indent=2, ensure_ascii=False, default=str))
    with_data = sum(1 for s in sentiment_index if s["has_data"])
    log.info(f"Phase 3: {len(sentiment_index)} sentiment analyses, {with_data} with real data")

    # ── Phase 4: Regulatory ──
    regulatory_index = []
    for fpath in sorted(SECTORS_DIR.rglob("bd-market/regulatory*.md")):
        if not fpath.is_file():
            continue
        entry = extract_regulatory(fpath)
        regulatory_index.append(entry)
        (meta_dir / f"regulatory_{entry['sector']}.json").write_text(
            json.dumps(entry, indent=2, ensure_ascii=False, default=str))

    (meta_dir / "regulatory_all.json").write_text(
        json.dumps({"total": len(regulatory_index), "entries": regulatory_index},
                   indent=2, ensure_ascii=False, default=str))
    with_data = sum(1 for r in regulatory_index if r["has_data"])
    log.info(f"Phase 4: {len(regulatory_index)} regulatory documents, {with_data} with real data")

    total = len(all_competitors) + len(pricing_index) + len(sentiment_index) + len(regulatory_index)
    log.info(f"Total: {total} sidecars generated")


if __name__ == "__main__":
    main()