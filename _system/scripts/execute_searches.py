#!/usr/bin/env python3
"""execute_searches.py — Execute prioritized search queries via search.datasolved.org.

Reads the freshness queue and search taxonomy to generate and execute
search queries for stale/missing data.
"""

import sys
import json
import logging
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import (
    get_sector_configs, get_search_taxonomy, now_iso, REPO_ROOT, DATA_DIR
)
from lib.search_client import search_text, search_news

log = logging.getLogger("execute_searches")

import os
MAX_QUERIES_PER_RUN = int(os.environ.get("MAX_QUERIES_PER_RUN", "48"))
DELAY_SECONDS = float(os.environ.get("SEARCH_DELAY_SECONDS", "0.2"))

SEARCH_TIMEOUT_SECONDS = float(os.environ.get("SEARCH_TIMEOUT_SECONDS", "15"))
MAX_TEXT_RESULTS = int(os.environ.get("MAX_TEXT_RESULTS", "5"))
MAX_NEWS_RESULTS = int(os.environ.get("MAX_NEWS_RESULTS", "3"))
HEADLESS_FAIL_FAST = os.environ.get("SEARCH_FAIL_FAST", "1") != "0"
SEARCH_PARALLELISM = int(os.environ.get("SEARCH_PARALLELISM", "8"))  # concurrent workers


def generate_queries(freshness_queue: list, sector_configs: dict, taxonomy: dict) -> list[dict]:
    """Generate search queries from freshness queue + taxonomy."""
    queries = []
    seen = set()

    for item in freshness_queue:
        sector = item.get("sector", "")
        category = item.get("category", "default")
        priority = item.get("priority", "P2")
        sconf = sector_configs.get(sector, {})
        keywords = sconf.get("keywords", {})
        en_kws = keywords.get("en", [sector.replace("-", " ")])
        bn_kws = keywords.get("bn", [])

        # Determine which query families are relevant
        family_map = {
            "pricing": "pricing",
            "policy": "policy_tracker",
            "competitor_core_profile": "competitor_discovery",
            "facebook_handle": "competitor_discovery",
            "sentiment": "sentiment",
            "seasonality": "seasonality",
            "supply_chain": "supply_chain",
            "funding": "investment_deal_flow",
            "demographics": "demographics_personas",
            "technology_adoption": "technology_adoption",
            "default": "competitor_discovery",
        }

        family_name = family_map.get(category, "competitor_discovery")
        family = taxonomy.get(family_name, {})
        templates = family.get("templates", [])

        for kw in en_kws[:2]:  # Top 2 keywords per sector
            for template in templates[:3]:  # Top 3 templates per family
                query_str = template.format(
                    sector_keywords=kw,
                    sector_keywords_bn=bn_kws[0] if bn_kws else kw,
                    competitor_name=kw,
                    service_name=kw,
                    product=kw,
                ).strip()
                if not query_str or '""' in query_str or query_str.count('"') % 2 != 0:
                    continue
                if '{' in query_str or '}' in query_str:
                    continue
                # Deduplicate
                qkey = f"{sector}:{family_name}:{query_str}"
                if qkey in seen:
                    continue
                seen.add(qkey)

                queries.append({
                    "query": query_str,
                    "sector": sector,
                    "family": family_name,
                    "priority": priority,
                    "category": category,
                    "expected_yield": "high" if priority == "P0" else "medium" if priority == "P1" else "low",
                })

    # Sort by priority
    p_order = {"P0": 0, "P1": 1, "P2": 2}
    queries.sort(key=lambda x: p_order.get(x["priority"], 9))

    # ── Fair distribution across sectors ──
    # Without this, the sector with the most files/P0 items dominates every cycle.
    # Round-robin: take N/P queries from each sector to fill the cap.
    total_priority_cap = MAX_QUERIES_PER_RUN
    from collections import defaultdict
    by_sector = defaultdict(list)
    for q in queries:
        by_sector[q["sector"]].append(q)

    sector_names = sorted(by_sector.keys())
    fair_queries = []
    queries_per_sector = max(1, total_priority_cap // max(len(sector_names), 1))
    remaining = total_priority_cap

    # Round-robin: pick from each sector until cap met
    while remaining > 0 and sector_names:
        for sector in list(sector_names):
            if by_sector[sector]:
                fair_queries.append(by_sector[sector].pop(0))
                remaining -= 1
            if not by_sector[sector]:
                sector_names.remove(sector)
            if remaining <= 0:
                break
        if not sector_names:
            break

    # Add remaining queries (if any sector has more and we have room)
    if remaining > 0:
        for q in queries:
            if q not in fair_queries:
                fair_queries.append(q)
                remaining -= 1
                if remaining <= 0:
                    break

    return fair_queries[:MAX_QUERIES_PER_RUN]


def _search_single_query(q: dict) -> list[dict]:
    """Execute one search query, return evidence items. Thread-safe."""
    import uuid
    from urllib.parse import urlparse
    from datetime import datetime, timezone
    
    time.sleep(DELAY_SECONDS)  # rate limit per worker
    
    log.info(f"[{q.get('_idx','?')}/{q.get('_total','?')}] {q['query'][:80]}...")

    # Search text
    try:
        text_results = search_text(q["query"], max_results=MAX_TEXT_RESULTS, timeout=SEARCH_TIMEOUT_SECONDS)
    except Exception as ex:
        log.warning(f"Text search failed for {q['query'][:60]!r}: {ex}")
        text_results = [] if HEADLESS_FAIL_FAST else None
        if text_results is None:
            raise

    # Also search news for high-priority queries
    news_results = []
    if q["priority"] == "P0":
        time.sleep(0.25)
        try:
            news_results = search_news(q["query"], max_results=MAX_NEWS_RESULTS, timeout=SEARCH_TIMEOUT_SECONDS)
        except Exception as ex:
            log.warning(f"News search failed for {q['query'][:60]!r}: {ex}")
            if not HEADLESS_FAIL_FAST:
                raise

    all_results = text_results + news_results
    now = datetime.now(timezone.utc).isoformat()

    evidence = []
    for r in all_results:
        source_url = r.get("href", r.get("url", ""))
        source_domain = urlparse(source_url).netloc if source_url else ""
        evidence.append({
            "evidence_id": str(uuid.uuid4())[:12],
            "sector": q["sector"],
            "entity_type": q["category"],
            "entity_slug": "",
            "query": q["query"],
            "query_family": q["family"],
            "query_score_prior": 0.5,
            "search_provider": "search.datasolved.org",
            "retrieved_at": now,
            "source_url": source_url,
            "source_domain": source_domain,
            "source_type": "unknown",
            "title": r.get("title", ""),
            "snippet": r.get("body", r.get("snippet", "")),
            "extracted_facts": [],
            "source_quality_score": 0.0,
            "recency_score": 0.0,
            "consistency_score": 0.0,
            "confidence_score": 0.0,
        })
    return evidence


def execute_queries(queries: list[dict]) -> list[dict]:
    """Execute search queries in parallel and return evidence items."""
    total = len(queries)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Annotate queries with index for logging
    for i, q in enumerate(queries):
        q["_idx"] = i + 1
        q["_total"] = total

    evidence = []
    workers = min(SEARCH_PARALLELISM, total)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_search_single_query, q): q for q in queries}
        for future in as_completed(futures):
            try:
                result = future.result(timeout=SEARCH_TIMEOUT_SECONDS + 10)
                evidence.extend(result)
            except Exception as ex:
                q = futures[future]
                log.warning(f"Search failed for {q['query'][:60]!r}: {ex}")

    return evidence


def main():
    import os
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    state_dir = REPO_ROOT / "_system" / "state"
    fq_path = state_dir / "freshness_queue.json"

    if not fq_path.exists():
        log.error("freshness_queue.json not found. Run evaluate_freshness.py first.")
        return

    fq = json.loads(fq_path.read_text())
    queue = fq.get("queue", [])

    sector_configs = get_sector_configs()
    taxonomy = get_search_taxonomy()

    # Generate queries
    queries = generate_queries(queue, sector_configs, taxonomy)
    log.info(f"Generated {len(queries)} queries from {len(queue)} queue items")

    if not queries:
        log.info("No queries to execute. All data is fresh!")
        return

    # Execute
    evidence = execute_queries(queries)

    # Save evidence
    evidence_dir = DATA_DIR / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    evidence_path = evidence_dir / f"{run_id}.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))

    # Also save search plan
    search_plan_path = state_dir / "search_plan.json"
    search_plan_path.write_text(json.dumps({
        "run_id": run_id,
        "generated_at": now_iso(),
        "total_queries": len(queries),
        "total_evidence": len(evidence),
        "queries": queries,
    }, indent=2, default=str))

    log.info(f"\n=== SEARCH EXECUTION SUMMARY ===")
    log.info(f"Queries executed: {len(queries)}")
    log.info(f"Evidence items collected: {len(evidence)}")
    log.info(f"Evidence saved to: {evidence_path}")
    log.info(f"Search plan saved to: {search_plan_path}")

    return evidence


if __name__ == "__main__":
    main()
