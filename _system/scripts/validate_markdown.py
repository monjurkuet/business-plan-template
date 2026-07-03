#!/usr/bin/env python3
"""validate_markdown.py — Validate YAML frontmatter and heading structure.

Checks that all .md files under sectors/ have:
1. Valid YAML frontmatter with required fields (sector, last_verified, freshness, confidence)
2. No broken internal references
3. Proper heading hierarchy
"""

import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso

log = logging.getLogger("validate_markdown")

# Accept both short names and JSON-schema names (last_verified ↔ last_verified_at, etc.)
_FM_ALIASES = {
    "last_verified": "last_verified_at",
    "freshness": "freshness_status",
    "confidence": "confidence_score",
}
REQUIRED_FRONTMATTER_FIELDS = ["sector", "last_verified", "freshness"]
COMPETITOR_FRONTMATTER_FIELDS = ["sector", "last_verified", "freshness", "confidence"]
VALID_FRESHNESS_VALUES = {"fresh", "stale", "critical"}

HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (metadata_dict, body)."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm_text = parts[1].strip()
    body = parts[2].strip()

    # Simple YAML parser for frontmatter
    metadata = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            # Coerce types
            if val.lower() in ("true", "false"):
                metadata[key] = val.lower() == "true"
            else:
                try:
                    metadata[key] = float(val) if "." in val else int(val)
                except ValueError:
                    metadata[key] = val
    return metadata, body


def validate_frontmatter(file_path: Path, content: str) -> list[dict]:
    """Validate frontmatter of a single file."""
    violations = []
    rel_path = str(file_path.relative_to(REPO_ROOT))

    metadata, body = parse_frontmatter(content)
    if not metadata:
        violations.append({
            "file": rel_path,
            "type": "missing_frontmatter",
            "detail": "No YAML frontmatter found",
        })
        return violations

    # Check required fields — accept both short names and JSON-schema aliases.
    # The repo uses last_verified_at / freshness_status / confidence_score in frontmatter
    # (matching competitor.schema.json) but the validator checks the short contract names.
    def _has_field(meta: dict, name: str) -> bool:
        return name in meta or (_FM_ALIASES.get(name) in meta)

    required_fields = COMPETITOR_FRONTMATTER_FIELDS if "/competitors/" in rel_path else REQUIRED_FRONTMATTER_FIELDS
    for field in required_fields:
        if not _has_field(metadata, field):
            violations.append({
                "file": rel_path,
                "type": "missing_field",
                "detail": f"Missing required field: {field}",
            })

    # Validate freshness values (also check aliased name)
    freshness_key = _FM_ALIASES.get("freshness", "freshness")
    freshness_val = metadata.get("freshness") or metadata.get(freshness_key)
    if freshness_val and freshness_val not in VALID_FRESHNESS_VALUES:
        violations.append({
            "file": rel_path,
            "type": "invalid_field",
            "detail": f"Invalid freshness value: {freshness_val} (expected: fresh/stale/critical)",
        })

    # Validate confidence (also check aliased name)
    confidence_key = _FM_ALIASES.get("confidence", "confidence")
    confidence_val = metadata.get("confidence") or metadata.get(confidence_key)
    if confidence_val is not None:
        try:
            conf = float(confidence_val)
            if not (0.0 <= conf <= 1.0):
                violations.append({
                    "file": rel_path,
                    "type": "invalid_field",
                    "detail": f"Confidence out of range: {conf} (expected 0.0-1.0)",
                })
        except (ValueError, TypeError):
            violations.append({
                "file": rel_path,
                "type": "invalid_field",
                "detail": f"Confidence not a number: {confidence_val}",
            })

    # Validate last_verified format (also check aliased name)
    lv_key = _FM_ALIASES.get("last_verified", "last_verified")
    lv_val = metadata.get("last_verified") or metadata.get(lv_key)
    if lv_val is not None:
        val = str(lv_val)
        if not re.match(r'^\d{4}-\d{2}-\d{2}', val):
            violations.append({
                "file": rel_path,
                "type": "invalid_field",
                "detail": f"Invalid last_verified format: {val} (expected YYYY-MM-DD)",
            })

    return violations


def validate_headings(file_path: Path, content: str) -> list[dict]:
    """Validate heading hierarchy."""
    violations = []
    rel_path = str(file_path.relative_to(REPO_ROOT))

    _, body = parse_frontmatter(content)
    headings = HEADING_RE.findall(body)

    if not headings:
        return []

    # First heading should be H1 for presentation docs. Some generated
    # markdown blocks still intentionally start at H2, so we only enforce this
    # on files outside the generated sector docs that already carry their own
    # top-level title in frontmatter or embedded content.
    first_level = len(headings[0][0])
    if first_level != 1 and "/competitors/" not in rel_path:
        violations.append({
            "file": rel_path,
            "type": "heading_violation",
            "detail": f"First heading is H{first_level}, expected H1",
        })

    # Check for skipped levels (e.g., H1 -> H3)
    prev_level = first_level
    for hashes, text in headings[1:]:
        level = len(hashes)
        if level > prev_level + 1:
            violations.append({
                "file": rel_path,
                "type": "heading_violation",
                "detail": f"Skipped heading level: H{prev_level} -> H{level} ('{text[:50]}')",
            })
        prev_level = level

    return violations


def validate_links(file_path: Path, content: str) -> list[dict]:
    """Check for broken internal links."""
    violations = []
    rel_path = str(file_path.relative_to(REPO_ROOT))

    _, body = parse_frontmatter(content)
    links = LINK_RE.findall(body)

    for text, href in links:
        # Skip external links and anchors
        if href.startswith(("http://", "https://", "mailto:", "#", "tel:")):
            continue

        # Resolve relative path
        target = (file_path.parent / href).resolve()
        if not target.exists():
            violations.append({
                "file": rel_path,
                "type": "broken_link",
                "detail": f"Broken link: [{text}]({href})",
            })

    return violations


def validate_all() -> list[dict]:
    """Validate all markdown files under sectors/ and persist results."""
    state_dir = REPO_ROOT / "_system" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    sectors_dir = REPO_ROOT / "sectors"
    if not sectors_dir.exists():
        log.error("No sectors/ directory found")
        return []

    violations = []
    warnings = []
    files_checked = 0

    for md_file in sorted(sectors_dir.rglob("*.md")):
        files_checked += 1
        try:
            content = md_file.read_text()
        except Exception as e:
            warnings.append({
                "file": str(md_file.relative_to(REPO_ROOT)),
                "type": "read_error",
                "detail": str(e),
            })
            continue

        violations.extend(validate_frontmatter(md_file, content))
        violations.extend(validate_headings(md_file, content))
        violations.extend(validate_links(md_file, content))

    result = {
        "generated_at": now_iso(),
        "summary": {
            "files_checked": files_checked,
            "violations": len(violations),
            "warnings": len(warnings),
        },
        "violations": violations,
        "warnings": warnings,
    }

    output_path = state_dir / "validation_results.json"
    output_path.write_text(json.dumps(result, indent=2, default=str))

    log.info(f"\n=== VALIDATION SUMMARY ===")
    log.info(f"Files checked: {files_checked}")
    log.info(f"Violations: {len(violations)}")
    log.info(f"Warnings: {len(warnings)}")
    log.info(f"Results saved to {output_path}")

    return violations


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
    validate_all()


if __name__ == "__main__":
    main()
