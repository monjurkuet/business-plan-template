#!/usr/bin/env python3
"""audit_repo.py — Build a complete file inventory and identify structural gaps.

Walks sectors/, data/, _templates/, _guides/ and produces:
1. File inventory with paths, sizes, last-modified dates
2. Missing expected files per sector
3. Stale date references (find "2024" or "2023" in content)
4. Duplicate file candidates
5. Write results to _system/state/file_inventory.json and _system/state/audit_results.json
"""

import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

# Bootstrap imports
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import get_sector_configs, get_sector_dirs, now_iso

log = logging.getLogger("audit_repo")

EXPECTED_SECTOR_FILES = [
    "README.md",
    "go-to-market.md",
    "risk-register.md",
    "strategy-canvas.md",
    "regulatory.md",
    "pricing-guide.md",
    "sentiment-analysis.md",
    "seasonality.md",
]

EXPECTED_SUBDIRS = {
    "research": ["landscape-report.md"],
    "competitors": [],  # any *.md is valid
}

STALE_YEAR_PATTERNS = [
    re.compile(r'\b2023\b'),
    re.compile(r'\b2024\b'),
    re.compile(r'\b2025\b'),
]


def file_inventory(path: Path, relative_to: Path) -> dict:
    """Build metadata dict for a single file."""
    stat = path.stat()
    return {
        "path": str(path.relative_to(relative_to)),
        "size_bytes": stat.st_size,
        "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "extension": path.suffix,
    }


def scan_directory(base: Path, relative_to: Path, extensions=None) -> list[dict]:
    """Recursively scan a directory for files."""
    inventory = []
    if not base.exists():
        return inventory
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if extensions and path.suffix not in extensions:
            continue
        inventory.append(file_inventory(path, relative_to))
    return inventory


def check_frontmatter(content: str) -> bool:
    """Check if markdown content has YAML frontmatter."""
    return content.startswith("---") and content.count("---") >= 2


def find_stale_references(content: str) -> list[str]:
    """Find stale year references in content."""
    found = []
    for pattern in STALE_YEAR_PATTERNS:
        if pattern.search(content):
            found.append(pattern.pattern.replace(r'\b', '').replace(r'\b', ''))
    return found


def audit_sector(sector_dir: Path, sector_config: dict) -> dict:
    """Audit a single sector directory."""
    sector_name = sector_dir.name
    bd_market = sector_dir / "bd-market"
    result = {
        "sector": sector_name,
        "present_files": [],
        "missing_files": [],
        "stale_references": [],
        "frontmatter_missing": [],
        "competitor_count": 0,
        "competitor_target": sector_config.get("competitor_target", 10),
        "files_expected": len(EXPECTED_SECTOR_FILES) + 1,  # +1 for landscape
        "files_present": 0,
    }

    if not bd_market.exists():
        result["missing_files"] = EXPECTED_SECTOR_FILES + ["research/landscape-report.md"]
        return result

    # Check expected files
    for fname in EXPECTED_SECTOR_FILES:
        fpath = bd_market / fname
        if fpath.exists():
            result["present_files"].append(fname)
            result["files_present"] += 1
            # Check frontmatter and stale refs
            try:
                content = fpath.read_text()
                if not check_frontmatter(content):
                    result["frontmatter_missing"].append(fname)
                result["stale_references"].extend(find_stale_references(content))
            except Exception:
                pass
        else:
            result["missing_files"].append(fname)

    # Check research/landscape-report.md
    research_dir = bd_market / "research"
    if research_dir.exists():
        for f in research_dir.glob("*.md"):
            result["present_files"].append(f"research/{f.name}")
            result["files_present"] += 1
            try:
                content = f.read_text()
                if not check_frontmatter(content):
                    result["frontmatter_missing"].append(f"research/{f.name}")
                result["stale_references"].extend(find_stale_references(content))
            except Exception:
                pass
    else:
        result["missing_files"].append("research/landscape-report.md")

    # Count competitors
    comp_dir = bd_market / "competitors"
    if comp_dir.exists():
        comp_files = list(comp_dir.glob("*.md"))
        result["competitor_count"] = len(comp_files)
        for f in comp_files:
            try:
                content = f.read_text()
                if not check_frontmatter(content):
                    result["frontmatter_missing"].append(f"competitors/{f.name}")
                result["stale_references"].extend(find_stale_references(content))
            except Exception:
                pass
    else:
        result["missing_files"].append("competitors/ (directory)")

    # Deduplicate stale refs
    result["stale_references"] = list(set(result["stale_references"]))

    return result


def compute_health_score(audit: dict) -> float:
    """Compute sector health score: 0.0-1.0."""
    file_ratio = audit["files_present"] / max(audit["files_expected"], 1)
    comp_ratio = min(audit["competitor_count"] / max(audit["competitor_target"], 1), 1.0)
    total_files = len(audit["present_files"])
    fm_missing = len(audit["frontmatter_missing"])
    fm_ratio = (total_files - fm_missing) / max(total_files, 1)
    return round(file_ratio * 0.5 + comp_ratio * 0.3 + fm_ratio * 0.2, 3)


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    sectors_config = get_sector_configs()
    sector_dirs = get_sector_dirs()
    state_dir = REPO_ROOT / "_system" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Build full inventory
    log.info("Scanning repository...")
    inventory = []
    for scan_dir in ["sectors", "data", "_templates", "_guides", "_system"]:
        d = REPO_ROOT / scan_dir
        if d.exists():
            inventory.extend(scan_directory(d, REPO_ROOT, extensions={".md", ".json", ".yaml"}))

    log.info(f"Found {len(inventory)} files")

    # Audit each sector
    sector_audits = []
    for sdir in sorted(sector_dirs):
        sname = sdir.name
        sconf = sectors_config.get(sname, {})
        audit = audit_sector(sdir, sconf)
        audit["health_score"] = compute_health_score(audit)
        sector_audits.append(audit)
        log.info(f"  {sname}: health={audit['health_score']:.2f}, "
                 f"files={audit['files_present']}/{audit['files_expected']}, "
                 f"competitors={audit['competitor_count']}/{audit['competitor_target']}, "
                 f"missing={len(audit['missing_files'])}, stale_refs={len(audit['stale_references'])}")

    # Build audit results
    audit_results = {
        "generated_at": now_iso(),
        "total_files": len(inventory),
        "sectors_audited": len(sector_audits),
        "all_missing_files": [],
        "all_stale_references": [],
        "all_frontmatter_missing": [],
        "sector_audits": sector_audits,
    }

    # Flatten
    for sa in sector_audits:
        for mf in sa["missing_files"]:
            audit_results["all_missing_files"].append(f"{sa['sector']}/{mf}")
        for sr in sa["stale_references"]:
            audit_results["all_stale_references"].append(f"{sa['sector']}: {sr}")
        for fm in sa["frontmatter_missing"]:
            audit_results["all_frontmatter_missing"].append(f"{sa['sector']}/{fm}")

    # Save
    (state_dir / "file_inventory.json").write_text(
        json.dumps(inventory, indent=2, default=str))
    (state_dir / "audit_results.json").write_text(
        json.dumps(audit_results, indent=2, default=str))

    log.info(f"\n=== AUDIT SUMMARY ===")
    log.info(f"Total files: {len(inventory)}")
    log.info(f"Sectors audited: {len(sector_audits)}")
    log.info(f"Missing files: {len(audit_results['all_missing_files'])}")
    log.info(f"Stale references: {len(audit_results['all_stale_references'])}")
    log.info(f"Frontmatter missing: {len(audit_results['all_frontmatter_missing'])}")
    log.info(f"Results saved to _system/state/")

    return audit_results


if __name__ == "__main__":
    main()
