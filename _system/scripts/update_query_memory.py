#!/usr/bin/env python3
"""update_query_memory.py — Learning loop: update query success rates.

Tracks which search queries yield high-confidence evidence and
which ones don't, so future runs can prioritize successful queries.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso, DATA_DIR

log = logging.getLogger("update_query_memory")

MEMORY_PATH = REPO_ROOT / "data" / "query_memory.json"

# Decay factor: older observations decay
DECAY = 0.95


def load_memory() -> dict:
    """Load existing query memory."""
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text())
    return {"queries": {}, "updated_at": now_iso()}


def save_memory(memory: dict):
    """Save query memory."""
    memory["updated_at"] = now_iso()
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, indent=2, ensure_ascii=False, default=str))


def decay_memory(memory: dict):
    """Apply decay to existing query scores."""
    for qkey, entry in memory.get("queries", {}).items():
        current = entry.get("score", 0.5)
        entry["score"] = round(current * DECAY, 4)
        entry["decayed_at"] = now_iso()


def update_from_evidence(memory: dict, evidence: list):
    """Update query scores based on evidence results."""
    for e in evidence:
        query = e.get("query", "")
        if not query:
            continue
        
        qkey = query[:200]  # Cap key length
        conf = e.get("confidence_score", 0)
        facts_count = len(e.get("extracted_facts", []))
        
        if qkey not in memory["queries"]:
            memory["queries"][qkey] = {
                "score": 0.5,
                "hits": 0,
                "high_conf_hits": 0,
                "total_facts": 0,
                "sectors": set(),
                "first_seen": now_iso(),
            }
        
        entry = memory["queries"][qkey]
        entry["hits"] = entry.get("hits", 0) + 1
        
        if conf >= 0.75:
            entry["high_conf_hits"] = entry.get("high_conf_hits", 0) + 1
            # Boost score
            entry["score"] = round(min(entry.get("score", 0.5) + 0.1, 1.0), 4)
        elif conf < 0.35:
            # Penalize low-confidence results
            entry["score"] = round(max(entry.get("score", 0.5) - 0.05, 0.0), 4)
        
        entry["total_facts"] = entry.get("total_facts", 0) + facts_count
        sector = e.get("sector", "")
        if sector:
            sectors = entry.get("sectors", [])
            if isinstance(sectors, set):
                sectors.add(sector)
            elif sector not in sectors:
                sectors.append(sector)
            entry["sectors"] = list(sectors) if isinstance(sectors, set) else sectors
        
        entry["last_seen"] = now_iso()


def prune_low_performers(memory: dict, min_hits: int = 3, min_score: float = 0.15):
    """Remove queries that have been tried enough but never succeed."""
    to_remove = []
    for qkey, entry in memory.get("queries", {}).items():
        hits = entry.get("hits", 0)
        score = entry.get("score", 0)
        high = entry.get("high_conf_hits", 0)
        if hits >= min_hits and score < min_score and high == 0:
            to_remove.append(qkey)
    
    for qkey in to_remove:
        del memory["queries"][qkey]
    
    return len(to_remove)


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    memory = load_memory()
    log.info(f"Loaded query memory: {len(memory.get('queries', {}))} tracked queries")

    # Load latest evidence
    evidence_dir = DATA_DIR / "evidence"
    if evidence_dir.exists():
        files = sorted(evidence_dir.glob("*.json"))
        if files:
            evidence = json.loads(files[-1].read_text())
            log.info(f"Processing {len(evidence)} evidence items")

            # Decay existing scores
            decay_memory(memory)
            
            # Update from new evidence
            update_from_evidence(memory, evidence)
            
            # Prune
            pruned = prune_low_performers(memory)
            if pruned:
                log.info(f"Pruned {pruned} low-performing queries")
            
            # Save
            save_memory(memory)
            
            # Stats
            total = len(memory.get("queries", {}))
            high = sum(1 for q in memory["queries"].values() if q.get("score", 0) >= 0.7)
            low = sum(1 for q in memory["queries"].values() if q.get("score", 0) < 0.3)
            
            log.info(f"\n=== QUERY MEMORY SUMMARY ===")
            log.info(f"Total tracked queries: {total}")
            log.info(f"High performers (>=0.7): {high}")
            log.info(f"Low performers (<0.3): {low}")
            log.info(f"Memory saved to: {MEMORY_PATH}")
        else:
            log.info("No evidence files found to learn from.")
    else:
        log.info("No evidence directory. Nothing to learn.")


if __name__ == "__main__":
    main()
