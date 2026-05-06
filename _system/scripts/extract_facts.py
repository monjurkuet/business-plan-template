#!/usr/bin/env python3
"""extract_facts.py — Use LLM to extract structured facts from search evidence.

Reads raw evidence from data/evidence/ and uses the LLM to extract
structured facts per the evidence schema.
"""

import sys
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso, DATA_DIR
from lib.llm_client import call_llm_json, load_prompt

log = logging.getLogger("extract_facts")

# Limit per run to control costs
MAX_EVIDENCE_PER_RUN = int(os.environ.get("MAX_EVIDENCE_PER_RUN", "80"))
BATCH_SIZE = 10  # Process evidence in batches to reduce API calls


def build_extraction_prompt(evidence_batch: list[dict]) -> str:
    """Build the user message for fact extraction."""
    prompt = load_prompt("extract_facts")
    items = []
    for e in evidence_batch:
        items.append(f"""---
Query: {e.get('query', 'N/A')}
Sector: {e.get('sector', 'N/A')}
Entity Type: {e.get('entity_type', 'N/A')}
Source: {e.get('source_domain', 'N/A')}
Title: {e.get('title', 'N/A')}
Snippet: {e.get('snippet', 'N/A')[:500]}
---""")
    
    return prompt + "\n\n## Search Results to Process\n\n" + "\n".join(items)


def extract_batch(evidence_batch: list[dict], model: str = "gemini-2.5-flash-lite") -> list[dict]:
    """Extract facts from a batch of evidence items using LLM."""
    if not evidence_batch:
        return []

    user_content = build_extraction_prompt(evidence_batch)
    messages = [
        {"role": "system", "content": "Extract structured facts from the search results. Return JSON with 'items' array, each having 'evidence_id' and 'extracted_facts' array."},
        {"role": "user", "content": user_content},
    ]

    try:
        result = call_llm_json(messages, model=model, temperature=0.1, max_tokens=4000)
        items = result.get("items", [])
        
        # Map back to evidence
        for e in evidence_batch:
            eid = e.get("evidence_id", "")
            for item in items:
                if item.get("evidence_id") == eid:
                    e["extracted_facts"] = item.get("extracted_facts", [])
                    break
        
        return evidence_batch
    except Exception as ex:
        log.warning(f"LLM extraction failed for batch: {ex}")
        return evidence_batch


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    evidence_dir = DATA_DIR / "evidence"
    if not evidence_dir.exists():
        log.error("No evidence directory found. Run execute_searches.py first.")
        return

    # Find latest evidence file
    evidence_files = sorted(evidence_dir.glob("*.json"))
    if not evidence_files:
        log.error("No evidence files found.")
        return

    latest = evidence_files[-1]
    log.info(f"Processing evidence from: {latest}")

    evidence = json.loads(latest.read_text())
    log.info(f"Total evidence items: {len(evidence)}")

    # Filter to items without extracted facts
    unprocessed = [e for e in evidence if not e.get("extracted_facts")]
    unprocessed = unprocessed[:MAX_EVIDENCE_PER_RUN]
    log.info(f"Items to process: {len(unprocessed)}")

    if not unprocessed:
        log.info("All evidence items already have extracted facts.")
        return

    # Process in batches
    processed = []
    for i in range(0, len(unprocessed), BATCH_SIZE):
        batch = unprocessed[i:i+BATCH_SIZE]
        log.info(f"Extracting batch {i//BATCH_SIZE + 1}/{(len(unprocessed)-1)//BATCH_SIZE + 1}")
        batch = extract_batch(batch)
        processed.extend(batch)

    # Update evidence file with extracted facts
    for p in processed:
        for i, e in enumerate(evidence):
            if e.get("evidence_id") == p.get("evidence_id"):
                evidence[i] = p
                break

    latest.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))

    # Count extracted facts
    total_facts = sum(len(e.get("extracted_facts", [])) for e in evidence)
    
    log.info(f"\n=== FACT EXTRACTION SUMMARY ===")
    log.info(f"Evidence items processed: {len(processed)}")
    log.info(f"Total extracted facts: {total_facts}")
    log.info(f"Updated evidence saved to: {latest}")

    return evidence


if __name__ == "__main__":
    main()
