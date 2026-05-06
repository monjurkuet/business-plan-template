#!/usr/bin/env python3
"""archive_stale.py — Archive stale sector files before they get refreshed.

Moves files with freshness=critical to _archive/ with timestamp,
so they can be restored if needed.
"""

import sys
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import REPO_ROOT as _RR

log = logging.getLogger("archive_stale")


def load_freshness_queue() -> list:
    """Load freshness queue."""
    state_dir = REPO_ROOT / "_system" / "state"
    fq_path = state_dir / "freshness_queue.json"
    if fq_path.exists():
        data = json.loads(fq_path.read_text())
        return data.get("queue", [])
    return []


def archive_file(src: Path, sector: str) -> Path:
    """Archive a file to _archive/sectors/SECTOR/TIMESTAMP/."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rel = src.relative_to(REPO_ROOT / "sectors" / sector)
    dest = REPO_ROOT / "_archive" / "sectors" / sector / timestamp / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    queue = load_freshness_queue()
    critical_items = [q for q in queue if q.get("priority") == "P0"]
    
    if not critical_items:
        log.info("No critical-stale items to archive.")
        return

    archived = 0
    sectors_dir = REPO_ROOT / "sectors"
    archive_dir = REPO_ROOT / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    for item in critical_items:
        sector = item.get("sector", "")
        category = item.get("category", "")
        file_path = item.get("file_path", "")

        if not file_path:
            continue

        src = REPO_ROOT / file_path
        if not src.exists():
            continue

        dest = archive_file(src, sector)
        log.info(f"Archived {file_path} -> {dest.relative_to(REPO_ROOT)}")
        archived += 1

    log.info(f"\n=== ARCHIVE SUMMARY ===")
    log.info(f"Critical-stale items: {len(critical_items)}")
    log.info(f"Files archived: {archived}")


if __name__ == "__main__":
    main()
