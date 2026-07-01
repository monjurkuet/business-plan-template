#!/usr/bin/env python3
"""score_confidence.py — Apply confidence scoring to evidence items.

Uses source-rankings.yaml and scoring-rules.yaml to compute
confidence scores for each evidence item and its extracted facts.
"""

import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import (
    get_source_weights, get_scoring_rules, get_freshness_policy,
    now_iso, DATA_DIR
)

log = logging.getLogger("score_confidence")


def get_domain_weight(domain: str, source_weights: dict) -> float:
    """Look up trust weight for a source domain."""
    if not domain:
        return 0.35  # unknown default

    for category, cfg in source_weights.items():
        if category == "unknown":
            continue
        domains = cfg.get("domains", [])
        for d in domains:
            if d.startswith("*."):
                # Wildcard match
                suffix = d[2:]
                if domain.endswith(suffix) or domain == suffix:
                    return cfg.get("weight", 0.35)
            elif domain == d or domain.endswith("." + d):
                return cfg.get("weight", 0.35)

    return source_weights.get("unknown", {}).get("weight", 0.35)


def compute_recency_score(evidence: dict, freshness_policy: dict) -> float:
    """Compute recency score based on when the evidence was retrieved."""
    retrieved = evidence.get("retrieved_at", "")
    if not retrieved:
        return 0.5

    try:
        ret_dt = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - ret_dt).days
    except Exception:
        return 0.5

    # Default stale threshold
    stale_after = 90
    category = evidence.get("entity_type", "default")
    cat_policy = freshness_policy.get(category, {})
    if isinstance(cat_policy, dict) and "stale_after_days" in cat_policy:
        stale_after = cat_policy["stale_after_days"]

    score = 1.0 - min(age_days / max(stale_after, 1), 1.0)
    return round(max(score, 0.0), 3)


def compute_consistency_score(evidence: dict, all_evidence: list) -> float:
    """Check if multiple sources agree on the same facts."""
    facts = evidence.get("extracted_facts", [])
    if not facts:
        return 0.5  # Single source, no facts to compare

    # Simple heuristic: check if other evidence in same sector has similar facts
    sector = evidence.get("sector", "")
    entity = evidence.get("entity_slug", "")
    
    similar = [e for e in all_evidence 
               if e.get("sector") == sector 
               and e.get("evidence_id") != evidence.get("evidence_id")
               and e.get("entity_slug") == entity
               and e.get("extracted_facts")]
    
    if len(similar) >= 2:
        return 1.0  # Three-plus sources agree
    elif len(similar) >= 1:
        return 0.8  # Two sources agree
    else:
        return 0.5  # Single source


def compute_confidence(evidence: dict, all_evidence: list, 
                       source_weights: dict, freshness_policy: dict,
                       scoring_rules: dict) -> float:
    """Compute overall confidence score for an evidence item."""
    formula = scoring_rules.get("scoring_formula", {})
    
    # Source quality
    domain = evidence.get("source_domain", "")
    source_quality = get_domain_weight(domain, source_weights)
    sq_weight = formula.get("source_quality", {}).get("weight", 0.30)
    
    # Recency
    recency = compute_recency_score(evidence, freshness_policy)
    r_weight = formula.get("recency", {}).get("weight", 0.20)
    
    # Consistency
    consistency = compute_consistency_score(evidence, all_evidence)
    c_weight = formula.get("cross_source_consistency", {}).get("weight", 0.20)
    
    # Extraction certainty (average of fact confidences)
    facts = evidence.get("extracted_facts", [])
    if facts:
        fact_confs = []
        for f in facts:
            if isinstance(f, dict):
                conf = f.get("confidence", 0.5)
                try:
                    fact_confs.append(float(conf))
                except (TypeError, ValueError):
                    fact_confs.append(0.5)
        extraction_certainty = sum(fact_confs) / len(fact_confs) if fact_confs else 0.5
    else:
        extraction_certainty = 0.3
    e_weight = formula.get("extraction_certainty", {}).get("weight", 0.15)
    
    # Entity match (simplified — assume 0.7 for now)
    entity_match = 0.7
    em_weight = formula.get("entity_match_precision", {}).get("weight", 0.10)
    
    # Query historical success (default 0.5)
    qh_score = evidence.get("query_score_prior", 0.5)
    qh_weight = formula.get("query_historical_success", {}).get("weight", 0.05)
    
    # Weighted sum
    confidence = (
        sq_weight * source_quality +
        r_weight * recency +
        c_weight * consistency +
        e_weight * extraction_certainty +
        em_weight * entity_match +
        qh_weight * qh_score
    )
    
    return round(min(max(confidence, 0.0), 1.0), 3)


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")

    evidence_dir = DATA_DIR / "evidence"
    if not evidence_dir.exists():
        log.error("No evidence directory found.")
        return

    evidence_files = sorted(evidence_dir.glob("*.json"))
    if not evidence_files:
        log.error("No evidence files found.")
        return

    latest = evidence_files[-1]
    evidence = json.loads(latest.read_text())
    log.info(f"Scoring {len(evidence)} evidence items from: {latest}")

    source_weights = get_source_weights()
    # Unwrap top-level key if YAML has 'source_weights' envelope
    if "source_weights" in source_weights and isinstance(source_weights["source_weights"], dict):
        source_weights = source_weights["source_weights"]
    scoring_rules = get_scoring_rules()
    freshness_policy = get_freshness_policy()

    # Score each evidence item
    for e in evidence:
        domain = e.get("source_domain", "")
        e["source_quality_score"] = get_domain_weight(domain, source_weights)
        e["recency_score"] = compute_recency_score(e, freshness_policy)
        e["consistency_score"] = compute_consistency_score(e, evidence)
        e["confidence_score"] = compute_confidence(
            e, evidence, source_weights, freshness_policy, scoring_rules)

    # Save scored evidence
    latest.write_text(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))

    # Summary
    high = sum(1 for e in evidence if e["confidence_score"] >= 0.75)
    medium = sum(1 for e in evidence if 0.50 <= e["confidence_score"] < 0.75)
    low = sum(1 for e in evidence if e["confidence_score"] < 0.50)
    avg = sum(e["confidence_score"] for e in evidence) / max(len(evidence), 1)

    log.info(f"\n=== CONFIDENCE SCORING SUMMARY ===")
    log.info(f"Evidence items scored: {len(evidence)}")
    log.info(f"High confidence (>=0.75): {high}")
    log.info(f"Medium confidence (0.50-0.75): {medium}")
    log.info(f"Low confidence (<0.50): {low}")
    log.info(f"Average confidence: {avg:.3f}")

    return evidence


if __name__ == "__main__":
    main()
