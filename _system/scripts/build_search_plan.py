#!/usr/bin/env python3
"""build_search_plan.py — Multi-LLM review + synthesis to build search plan.

Uses 3 LLMs to review the repo state, freshness gaps, and existing evidence,
then synthesizes a prioritized search plan for the next cycle.
"""

import sys
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import load_config, now_iso, DATA_DIR, get_sector_configs, get_search_taxonomy
from lib.llm_client import call_llm, call_llm_json, load_prompt

LLM_MODELS_ENDPOINT = os.environ.get("OPENPAI_BASE_URL") or os.environ.get("LLM_API_BASE") or "https://llm.datasolved.org/v1"

MODEL_FALLBACKS = {
    "breadth_scan": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gpt-5.4-mini"],
    "deep_analysis": ["deepseek-ai/deepseek-v4-pro", "deepseek-ai/deepseek-r1-distill-qwen-32b", "gpt-5.4-mini"],
    "synthesis": ["gpt-5.4", "gpt-5.5", "gpt-5.4-mini"],
    "trend_gap": ["gemini-3.1-flash-lite-preview", "gemini-3-flash-preview", "gemini-2.5-flash"],
}


def list_available_models() -> set[str]:
    """Fetch the current model inventory from the LLM endpoint."""
    import urllib.request
    import urllib.error

    url = f"{LLM_MODELS_ENDPOINT}/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ.get('OPENPAI_API_KEY', os.environ.get('LLM_API_KEY', ''))}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
        return {m.get("id") for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")}
    except Exception as ex:
        log.warning(f"Model preflight skipped ({ex}); falling back to configured models")
        return set()


def resolve_review_models(routing: dict) -> list[str]:
    """Resolve review models against the provider and fall back to known-good aliases."""
    available = list_available_models()
    resolved = []
    for key, default in (("breadth_scan", "gemini-2.5-flash"), ("deep_analysis", "gpt-5.4-mini"), ("synthesis", "gpt-5.4")):
        cfg = routing.get(key, {})
        configured = cfg.get("model", default)
        config_fallbacks = cfg.get("fallback_models", []) if isinstance(cfg.get("fallback_models", []), list) else []
        candidates = [configured] + [m for m in config_fallbacks + MODEL_FALLBACKS.get(key, []) if m != configured]
        pick = next((m for m in candidates if not available or m in available), candidates[0])
        if available and pick not in available:
            log.warning(f"No available model match for {key}; using configured value {pick}")
        elif pick != configured:
            log.warning(f"{configured} not available; falling back to {pick} for {key}")
        resolved.append(pick)
    return resolved

log = logging.getLogger("build_search_plan")

MAX_QUERIES = int(os.environ.get("MAX_SEARCH_QUERIES", "60"))
REVIEW_TIMEOUT_SECONDS = int(os.environ.get("SEARCH_PLAN_REVIEW_TIMEOUT_SECONDS", "90"))


def load_repo_summary() -> dict:
    """Load audit results if available, else build a lightweight summary."""
    state_dir = REPO_ROOT / "_system" / "state"
    audit_path = state_dir / "audit_results.json"
    
    if audit_path.exists():
        return json.loads(audit_path.read_text())
    
    # Lightweight fallback
    sectors_dir = REPO_ROOT / "sectors"
    summary = {"sectors": {}, "total_files": 0}
    if sectors_dir.exists():
        for sd in sorted(sectors_dir.iterdir()):
            if sd.is_dir() and not sd.name.startswith("_"):
                md_files = list(sd.rglob("*.md"))
                summary["sectors"][sd.name] = {"file_count": len(md_files)}
                summary["total_files"] += len(md_files)
    return summary


def load_freshness_queue() -> list:
    """Load freshness queue items."""
    state_dir = REPO_ROOT / "_system" / "state"
    fq_path = state_dir / "freshness_queue.json"
    if fq_path.exists():
        data = json.loads(fq_path.read_text())
        return data.get("queue", [])
    return []


def load_latest_evidence() -> list:
    """Load latest evidence file."""
    evidence_dir = DATA_DIR / "evidence"
    if not evidence_dir.exists():
        return []
    files = sorted(evidence_dir.glob("*.json"))
    if not files:
        return []
    return json.loads(files[-1].read_text())


def review_with_model(model: str, context: str) -> dict:
    """Run a single LLM review and return structured output."""
    prompt = load_prompt("review_system")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": context[:12000]},  # Cap context size
    ]
    try:
        return call_llm_json(
            messages,
            model=model,
            temperature=0.2,
            max_tokens=3000,
            timeout=REVIEW_TIMEOUT_SECONDS,
        )
    except Exception as ex:
        msg = str(ex)
        if "404" in msg and model in MODEL_FALLBACKS:
            for fallback in MODEL_FALLBACKS[model]:
                if fallback == model:
                    continue
                log.warning(f"Review failed with {model}: {ex}; retrying with fallback {fallback}")
                try:
                    return call_llm_json(
                        messages,
                        model=fallback,
                        temperature=0.2,
                        max_tokens=3000,
                        timeout=REVIEW_TIMEOUT_SECONDS,
                    )
                except Exception as fallback_ex:
                    log.warning(f"Fallback review failed with {fallback}: {fallback_ex}")
                    continue
        log.warning(f"Review failed with {model}: {ex}")
        return {"model": model, "error": str(ex), "gaps": [], "recommendations": []}


def build_context(repo_summary: dict, freshness_queue: list, evidence: list) -> str:
    """Build the review context string."""
    lines = ["## Repository State\n"]
    lines.append(f"Total files: {repo_summary.get('total_files', 'unknown')}")
    
    for sector, info in repo_summary.get("sectors", {}).items():
        lines.append(f"- {sector}: {info.get('file_count', '?')} files")
    
    lines.append(f"\n## Freshness Queue ({len(freshness_queue)} items)\n")
    for item in freshness_queue[:30]:
        lines.append(f"- [{item.get('priority','?')}] {item.get('sector','?')}/{item.get('category','?')}: {item.get('reason','')}")
    
    lines.append(f"\n## Latest Evidence ({len(evidence)} items)\n")
    high_conf = sum(1 for e in evidence if e.get("confidence_score", 0) >= 0.75)
    lines.append(f"High confidence: {high_conf}")
    lines.append(f"Total extracted facts: {sum(len(e.get('extracted_facts', [])) for e in evidence)}")
    
    # Show low-confidence gaps
    low_conf = [e for e in evidence if e.get("confidence_score", 0) < 0.5]
    if low_conf:
        lines.append(f"\nLow-confidence evidence needing re-search:")
        for e in low_conf[:10]:
            lines.append(f"- {e.get('sector','?')}/{e.get('entity_type','?')}: {e.get('query','?')[:60]} (conf={e.get('confidence_score',0)})")
    
    return "\n".join(lines)


def synthesize_plans(reviews: list[dict], freshness_queue: list, 
                     sector_configs: dict, taxonomy: dict) -> list[dict]:
    """Synthesize multiple LLM reviews into a prioritized search plan."""
    # Collect all identified gaps
    all_gaps = []
    for review in reviews:
        if "error" in review:
            continue
        gaps = review.get("gaps", [])
        recs = review.get("recommendations", [])
        for g in gaps:
            g["source_model"] = review.get("model", "unknown")
            all_gaps.append(g)
        for r in recs:
            all_gaps.append({
                "sector": r.get("sector", ""),
                "category": r.get("category", "gap"),
                "reason": r.get("reason", str(r)),
                "source_model": review.get("model", "unknown"),
                "priority": r.get("priority", "P2"),
            })
    
    # Merge with freshness queue items
    for item in freshness_queue:
        all_gaps.append({
            "sector": item.get("sector", ""),
            "category": item.get("category", ""),
            "reason": item.get("reason", "stale data"),
            "source_model": "freshness_policy",
            "priority": item.get("priority", "P2"),
        })
    
    # Deduplicate by sector+category
    seen = set()
    unique_gaps = []
    for g in all_gaps:
        key = f"{g.get('sector','')}:{g.get('category','')}"
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)
    
    # Build search queries from gaps
    queries = []
    for gap in unique_gaps:
        sector = gap.get("sector", "")
        category = gap.get("category", "")
        sconf = sector_configs.get(sector, {})
        keywords = sconf.get("keywords", {})
        en_kws = keywords.get("en", [sector.replace("-", " ")])
        
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
            "gap": "competitor_discovery",
        }
        
        family_name = family_map.get(category, "competitor_discovery")
        family = taxonomy.get(family_name, {})
        templates = family.get("templates", ["{sector_keywords} Bangladesh 2026"])
        
        bn_kws = keywords.get("bn", en_kws)
        for kw in en_kws[:1]:
            for tmpl in templates[:2]:
                query_str = tmpl.format(
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
                queries.append({
                    "query": query_str,
                    "sector": sector,
                    "family": family_name,
                    "priority": gap.get("priority", "P2"),
                    "reason": gap.get("reason", ""),
                    "source_model": gap.get("source_model", ""),
                })
    
    # Sort by priority, cap
    p_order = {"P0": 0, "P1": 1, "P2": 2}
    queries.sort(key=lambda x: p_order.get(x.get("priority", "P2"), 9))
    queries = queries[:MAX_QUERIES]
    
    return queries


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    # Load context
    repo_summary = load_repo_summary()
    freshness_queue = load_freshness_queue()
    evidence = load_latest_evidence()
    
    context = build_context(repo_summary, freshness_queue, evidence)
    log.info(f"Built review context ({len(context)} chars)")

    # Multi-LLM review
    routing = load_config("model-routing").get("review_models", {})
    models = resolve_review_models(routing)
    models = list(dict.fromkeys(models))
    reviews = []
    with ThreadPoolExecutor(max_workers=len(models)) as pool:
        futures = {pool.submit(review_with_model, model, context): model for model in models}
        for future in as_completed(futures):
            model = futures[future]
            log.info(f"Reviewing with {model}...")
            try:
                review = future.result(timeout=REVIEW_TIMEOUT_SECONDS + 5)
            except Exception as ex:
                log.warning(f"Review future failed with {model}: {ex}")
                review = {"model": model, "error": str(ex), "gaps": [], "recommendations": []}
            review["model"] = model
            reviews.append(review)
    reviews.sort(key=lambda r: models.index(r.get("model", models[0])) if r.get("model") in models else len(models))

    # Synthesize
    sector_configs = get_sector_configs()
    taxonomy = get_search_taxonomy()
    
    search_plan = synthesize_plans(reviews, freshness_queue, sector_configs, taxonomy)
    
    # Save
    state_dir = REPO_ROOT / "_system" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    plan_path = state_dir / "search_plan.json"
    plan_data = {
        "generated_at": now_iso(),
        "models_used": models,
        "reviews": reviews,
        "total_queries": len(search_plan),
        "queries": search_plan,
    }
    plan_path.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False, default=str))
    
    log.info(f"\n=== SEARCH PLAN SUMMARY ===")
    log.info(f"Models consulted: {len(reviews)}")
    log.info(f"Total search queries: {len(search_plan)}")
    for p in ["P0", "P1", "P2"]:
        count = sum(1 for q in search_plan if q.get("priority") == p)
        log.info(f"  {p}: {count} queries")
    log.info(f"Plan saved to: {plan_path}")


if __name__ == "__main__":
    main()
