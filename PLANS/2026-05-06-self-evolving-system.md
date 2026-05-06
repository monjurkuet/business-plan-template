# Self-Evolving BD Market Research System — Implementation Plan

> **Date:** 2026-05-06
> **Status:** DRAFT — Awaiting Punisher Review
> **Models Consulted:** GPT-5.4 (synthesis), DeepSeek V4-Pro (strategy), Gemini 2.5 Flash-Lite (breadth), Gemini 3.1 Flash-Lite (trends)
> **Repo:** `monjurkuet/business-plan-template` (main)

---

## 1. VISION

A Hermes-cron-driven system that **every 3 hours**:

1. Audits the codebase for completeness, freshness, and quality
2. Consults 3 LLM reviewers (DeepSeek, Gemini 2.5, Gemini 3.1)
3. Synthesizes findings into a prioritized search plan (GPT-5.4)
4. Executes targeted DDGS searches via `search.datasolved.org`
5. Extracts structured facts with provenance and confidence scores
6. Updates markdown + JSON sidecars
7. Commits and pushes to GitHub
8. **Learns** which queries, sources, and strategies work best over time

---

## 2. CODEBASE ISSUES FOUND (from 4-model review)

### Critical (fix before automation begins)

| # | Issue | Severity | Source |
|---|-------|----------|--------|
| 1 | **Duplicate `travel/` sector** (2 files) vs `travel-tourism/` (12 files) | P0 | All 4 models |
| 2 | **17 files contain 2024 data** — need 2025-2026 evidence-backed refresh | P0 | All 4 models |
| 3 | **`crypto-bitcoin/` only 9 files** — missing competitors, compliance, pricing | P0 | DeepSeek, GPT-5.4 |
| 4 | **No structured data layer** — markdown-only free text, no JSON sidecars | P0 | GPT-5.4 |
| 5 | **No data freshness tracking** — can't tell what's stale | P0 | DeepSeek, GPT-5.4 |

### High (blocks quality automation)

| # | Issue | Severity | Source |
|---|-------|----------|--------|
| 6 | **No confidence scoring** — all data treated equally | P1 | DeepSeek, GPT-5.4 |
| 7 | **Revenue/funding data sparse** — most competitor profiles lack hard numbers | P1 | DeepSeek |
| 8 | **No data provenance** — can't trace which search found which fact | P1 | GPT-5.4 |
| 9 | **No search strategy documentation** — what worked, what didn't | P1 | GPT-5.4 |
| 10 | **Strategy canvases/go-to-market files are generic** — not data-driven | P1 | Gemini 2.5, DeepSeek |

### Medium (data gaps to fill over time)

| # | Issue | Severity | Source |
|---|-------|----------|--------|
| 11 | **No regulatory/compliance data per sector** | P1 | All 4 models |
| 12 | **No supply chain mapping** | P1 | DeepSeek, Gemini 3.1 |
| 13 | **No pricing intelligence tracking** | P1 | Gemini 2.5, DeepSeek |
| 14 | **No customer sentiment/review data** | P1 | DeepSeek, Gemini 3.1 |
| 15 | **No seasonal trend data** | P2 | Gemini 2.5, Gemini 3.1 |
| 16 | **No cross-sector correlation analysis** | P2 | GPT-5.4, Gemini 3.1 |
| 17 | **No government policy tracker** | P1 | DeepSeek |
| 18 | **No technology adoption curves** | P2 | Gemini 3.1 |
| 19 | **No investment/deal flow data** | P1 | DeepSeek |
| 20 | **No import/export tariff data** | P1 | Gemini 2.5 |
| 21 | **Risk registers lack probability/impact quantification** | P2 | GPT-5.4 |

### Blind Spots (models identified what we're NOT seeing at all)

| # | Blind Spot | Source |
|---|-----------|--------|
| 22 | **Bengali-language sources** — most BD market data is in Bengali | DeepSeek |
| 23 | **LinkedIn competitor intelligence** — employee counts, hiring signals | DeepSeek |
| 24 | **Chaldal/Daraz/app store review mining** | DeepSeek |
| 25 | **LightCastle Partners / LankaBangla industry reports** | DeepSeek |
| 26 | **Google Trends seasonal data per sector** | Gemini 3.1 |
| 27 | **Currency fluctuation impact on import-heavy sectors** | Gemini 3.1 |
| 28 | **BIDA one-stop-service registration data** | DeepSeek |
| 29 | **NBR customs/VAT circulars** | DeepSeek |
| 30 | **Facebook group sentiment mining** | DeepSeek, Gemini 2.5 |

---

## 3. TARGET REPOSITORY STRUCTURE

```
business-plan-template/
├── README.md
├── CHANGELOG.md
├── LICENSE, .gitignore
├── .github/workflows/validate.yml
├── _archive/
│   └── sectors/travel/2026-05-06/   ← merged duplicate
├── _guides/
│   ├── research-methodology.md
│   ├── facebook-handle-verification.md
│   ├── data-confidence-scoring.md       ← NEW
│   ├── query-strategy-playbook.md       ← NEW
│   └── markdown-schema.md               ← NEW
├── _templates/
│   ├── 01-idea-brief/
│   ├── 02-competitor-analysis/
│   ├── 03-strategy-canvas/
│   ├── 04-financial-model/
│   ├── 05-go-to-market/
│   ├── 06-risk-register/
│   └── 07-regulatory-compliance/        ← NEW
├── _system/                              ← NEW: automation layer
│   ├── config/
│   │   ├── sectors.yaml                 ← sector definitions + keywords
│   │   ├── search-taxonomy.yaml         ← query families + cadence
│   │   ├── source-rankings.yaml         ← domain trust weights
│   │   ├── freshness-policy.yaml        ← staleness thresholds
│   │   ├── scoring-rules.yaml           ← confidence formula
│   │   ├── model-routing.yaml           ← LLM model assignments
│   │   └── cron.env.example
│   ├── prompts/
│   │   ├── deepseek-review.md
│   │   ├── gemini-breadth-audit.md
│   │   ├── gemini-trend-gap.md
│   │   ├── gpt-synthesis.md
│   │   ├── extraction-facts.md
│   │   └── markdown-regeneration.md
│   ├── schemas/
│   │   ├── competitor.schema.json
│   │   ├── sector-index.schema.json
│   │   ├── evidence.schema.json
│   │   └── pricing-observation.schema.json
│   ├── scripts/
│   │   ├── run_pipeline.py              ← main orchestrator
│   │   ├── bootstrap_cleanup.py         ← one-time init
│   │   ├── audit_repo.py                ← completeness scan
│   │   ├── detect_duplicates.py
│   │   ├── evaluate_freshness.py
│   │   ├── build_search_plan.py         ← LLM-powered search strategy
│   │   ├── execute_searches.py          ← DDGS API calls
│   │   ├── extract_facts.py             ← LLM extraction
│   │   ├── score_confidence.py
│   │   ├── update_sector_docs.py
│   │   ├── archive_stale.py
│   │   ├── generate_changelog.py
│   │   ├── update_query_memory.py       ← learning loop
│   │   ├── git_commit_push.py
│   │   └── validate_markdown.py
│   ├── lib/
│   │   ├── llm_client.py               ← OpenAI-compatible API client
│   │   ├── search_client.py            ← search.datasolved.org wrapper
│   │   ├── scoring.py
│   │   ├── provenance.py
│   │   └── markdown_utils.py
│   └── state/
│       ├── query-memory.json            ← learns which queries work
│       ├── source-performance.json      ← learns which sources are reliable
│       ├── sector-health.json           ← per-sector completeness scores
│       └── run-history/<run_id>/        ← full run artifacts
├── data/                                ← NEW: structured data layer
│   ├── sector-index/<sector>.json
│   ├── competitors/<sector>/<slug>.json
│   ├── evidence/<sector>/<entity>/<timestamp>.json
│   ├── pricing/<sector>/
│   ├── sentiment/<sector>/
│   ├── compliance/<sector>/
│   └── changelog/YYYY-MM-DD/
├── sectors/                             ← presentation layer (markdown)
│   ├── automotive-car-care/
│   ├── clothing-fashion/
│   ├── crypto-bitcoin/
│   ├── electronics-gadgets/
│   ├── high-roi-niches/
│   ├── jewellery/
│   ├── media-marketing-digital/
│   └── travel-tourism/                  ← travel/ merged into this
└── reports/                             ← NEW: dashboards
    ├── repo-health-dashboard.md
    ├── sector-priority-queue.md
    ├── run-summary-latest.md
    └── cross-sector-correlation.md
```

---

## 4. SECTOR FILE CONTRACT (every sector must have)

```
sectors/<sector>/
├── README.md
├── idea-brief.md
├── strategy-canvas.md
├── go-to-market.md
├── risk-register.md
├── regulatory-compliance.md      ← NEW
├── customer-personas.md          ← NEW
├── pricing-intelligence.md       ← NEW
├── sentiment-reviews.md          ← NEW
├── seasonality-trends.md         ← NEW
├── supply-chain-map.md           ← NEW
├── investment-deal-flow.md       ← NEW
├── policy-tracker.md             ← NEW
├── research/
│   ├── full-landscape-report.md
│   ├── search-log.md             ← NEW
│   └── freshness-ledger.md       ← NEW
└── competitors/
    ├── README.md
    └── <competitor-slug>.md (minimum 8-12 per sector)
```

---

## 5. CLEANUP PRIORITIES (execution order)

### Phase 0: Stop the bleeding (before automation)
1. **Merge `travel/` → `travel-tourism/`** — archive duplicate
2. **Scaffold all missing files** across all 8 sectors
3. **Create `_system/` infrastructure** — configs, schemas, lib, scripts
4. **Create `data/` layer** — JSON sidecars from existing markdown
5. **Add YAML frontmatter** to all existing markdown (last_verified, confidence)

### Phase 1: Fix stale data
6. **Audit all 2024 references** — search for each stale claim
7. **Prioritize crypto-bitcoin** — bring to parity with other sectors
8. **Verify all Facebook handles** — targeted DDGS + CDP verification

### Phase 2: Build automation
9. **Implement `run_pipeline.py`** — the orchestrator
10. **Implement `audit_repo.py`** — completeness + quality scanner
11. **Implement `execute_searches.py`** — DDGS via search.datasolved.org
12. **Implement `extract_facts.py`** — LLM-powered structured extraction
13. **Implement `build_search_plan.py`** — LLM-powered search strategy

### Phase 3: Activate learning loop
14. **Implement `update_query_memory.py`** — track which queries yield best data
15. **Implement `score_confidence.py`** — evidence-backed confidence scoring
16. **Implement `generate_changelog.py`** — track what changed each run

### Phase 4: Deploy cron
17. **Configure Hermes cron** — every 3 hours
18. **Dry-run mode** — no push, just analysis
19. **Enable push mode** — full auto

---

## 6. PIPELINE FLOW (every 3 hours)

```
┌─────────────────────────────────────────────────┐
│ 1. git pull origin main                         │
│ 2. audit_repo.py → file inventory, stale refs   │
│ 3. evaluate_freshness.py → stale queue          │
│ 4. LLM REVIEW (parallel):                       │
│    • DeepSeek V4-Pro → strategic gaps           │
│    • Gemini 2.5 Flash-Lite → structure audit    │
│    • Gemini 3.1 Flash-Lite → trends/weak signals│
│ 5. GPT-5.4 SYNTHESIS → prioritized search plan  │
│ 6. execute_searches.py → DDGS API calls         │
│ 7. extract_facts.py → structured facts + provenance│
│ 8. score_confidence.py → confidence scoring     │
│ 9. update_sector_docs.py → markdown regeneration │
│10. archive_stale.py → move old data to _archive │
│11. validate_markdown.py → quality check          │
│12. generate_changelog.py → track changes         │
│13. update_query_memory.py → learn from results   │
│14. git commit + push                             │
└─────────────────────────────────────────────────┘
```

---

## 7. CONFIDENCE SCORING FORMULA

```
confidence = 0.30 × source_quality
           + 0.20 × recency
           + 0.20 × cross_source_consistency
           + 0.15 × extraction_certainty
           + 0.10 × entity_match_precision
           + 0.05 × query_historical_success
```

**Source quality weights:**
- `gov.bd` domains: 0.95
- Official company sites: 0.82
- News (Daily Star, bdnews24, Dhaka Tribune): 0.73
- LinkedIn: 0.68
- Facebook: 0.64
- Classifieds (Bikroy, etc): 0.49

---

## 8. FRESHNESS POLICY

| Data Category | Stale After | Critical Stale After |
|--------------|-------------|---------------------|
| Pricing | 14 days | 30 days |
| Policy (crypto) | 3 days | 7 days |
| Policy (other) | 7 days | 21 days |
| Facebook handles | 60 days | 90 days |
| Competitor profiles | 45 days | 90 days |
| Sentiment | 21 days | 42 days |
| Seasonality | 180 days | 365 days |
| Supply chain | 60 days | 120 days |
| Funding | 30 days | 60 days |
| Default | 90 days | 180 days |

---

## 9. SEARCH TAXONOMY (query families + cadence)

| Family | Cadence | Template Queries |
|--------|---------|-----------------|
| **competitor_discovery** | 24h | `"{sector}" Bangladesh top companies`, `site:facebook.com "{sector}" Bangladesh` |
| **pricing** | 12h | `"{competitor}" price Bangladesh`, `site:facebook.com "{competitor}" offer` |
| **compliance** | 24h | `site:gov.bd "{sector}" license`, `site:nbr.gov.bd "{sector}" VAT customs` |
| **sentiment** | 24h | `"{competitor}" review`, `"{competitor}" Facebook reviews Bangladesh` |
| **seasonality** | 168h | `"{sector}" Eid sales Bangladesh`, `"{sector}" seasonal demand Dhaka` |
| **policy_tracker** | 6h (crypto), 24h (others) | `"{sector}" regulation Bangladesh 2026`, `site:gov.bd "{sector}" circular` |
| **supply_chain** | 72h | `"{sector}" importer Bangladesh`, `"{material}" wholesale Dhaka` |
| **investment** | 24h | `"{sector}" funding Bangladesh`, `"{competitor}" raised series` |
| **bengali_sources** | 72h | `"বাংলাদেশ {sector_bengali} বাজার ২০২৬"` |

---

## 10. LEARNING / SELF-EVOLUTION MECHANISM

The system gets smarter over time via 3 feedback loops:

### Loop 1: Query Memory (`_system/state/query-memory.json`)
- Tracks every query template: runs, avg results, acceptance rate, avg confidence
- **Promote** queries with acceptance > 0.72 and high unique evidence yield
- **Demote** queries with acceptance < 0.25 over 10 consecutive runs
- **Generate variants** with LLM if sector gaps persist after 3 runs

### Loop 2: Source Performance (`_system/state/source-performance.json`)
- Tracks per-domain: hit rate, extraction success, conflict frequency, confidence contribution
- Learns: `gov.bd` = high trust, `facebook.com` = good for pricing/promos, news = good for funding

### Loop 3: Sector Health (`_system/state/sector-health.json`)
- Per-sector: completeness score, stale claim count, coverage gaps
- **Priority formula**: `0.20 × incompleteness + 0.20 × staleness + 0.15 × low_confidence + 0.15 × volatility + 0.10 × revenue_gap + 0.10 × regulatory_risk + 0.10 × cross_sector_weight`
- First 30-day priority: crypto > travel > electronics > fashion > jewellery > media > niches > automotive

---

## 11. HERMES CRON SPECIFICATION

### Job A: Full Pipeline (every 3 hours)
```yaml
name: bd-business-plan-self-evolver
schedule: "every 3h"
prompt: |
  Run the BD business plan research pipeline:
  1. cd /root/codebase/vhd/business-plan-template && git pull origin main
  2. python _system/scripts/run_pipeline.py
  3. If any errors, log them to _system/logs/ and continue
  4. If no changes, skip commit
workdir: /root/codebase/vhd/business-plan-template
enabled_toolsets: ["terminal", "file"]
```

### Job B: Quick Validation (every hour)
```yaml
name: bd-business-plan-validator
schedule: "every 1h"
prompt: |
  Quick validation of BD business plan repo:
  1. cd /root/codebase/vhd/business-plan-template
  2. python _system/scripts/audit_repo.py --quick
  3. python _system/scripts/evaluate_freshness.py --quick
  Report any critical issues.
workdir: /root/codebase/vhd/business-plan-template
enabled_toolsets: ["terminal"]
```

### Environment Variables Needed
```
SEARCH_API_BASE=https://search.datasolved.org
LLM_API_BASE=https://llm.datasolved.org/v1
LLM_API_KEY=<from OPENPAI_API_KEY>
TZ=Asia/Dhaka
MAX_QUERIES_PER_RUN=120
MAX_LLM_COST_USD_PER_RUN=8
```

---

## 12. 14-DAY ROLLOUT SCHEDULE

| Day | Phase | Deliverables |
|-----|-------|-------------|
| 1-2 | Foundation | `_system/` dir, configs, schemas, merge `travel/` |
| 3-4 | Validation | `audit_repo.py`, `validate_markdown.py`, `evaluate_freshness.py`, GitHub Actions |
| 5-6 | Search + Provenance | `search_client.py`, `execute_searches.py`, evidence model |
| 7-8 | LLM Review | `llm_client.py`, prompts, 3 reviewers + synthesis |
| 9-10 | Extraction + Docs | `extract_facts.py`, `score_confidence.py`, `update_sector_docs.py` |
| 11-12 | Learning Loop | `update_query_memory.py`, source performance, query promotion/demotion |
| 13-14 | Harden + Deploy | Changelog, archival, Hermes cron, dry-run, enable push |

---

## 13. SECTOR-SPECIFIC DATA GAPS (from DeepSeek V4-Pro)

| Sector | Missing | Priority Queries |
|--------|---------|-----------------|
| **crypto-bitcoin** | Policy, compliance, competitor profiles, user volume data | `"Bangladesh Bank circular 2026 crypto"`, `"Binance P2P Bangladesh volume"`, `site:gov.bd "cryptocurrency"` |
| **travel-tourism** | Seasonality, visa providers, domestic tourism stats, hotel chains | `"Cox's Bazar tourism statistics 2026"`, `"Bangladesh domestic tourism Eid 2026"` |
| **electronics** | Import tariffs, distributor map, warranty/service network | `"Bangladesh electronics import duty 2026 budget"`, `site:nbr.gov.bd "electronics HS code"` |
| **clothing-fashion** | Fabric sourcing, Eid seasonality, boutique vs fast-fashion pricing | `"Bangladesh Eid fashion sales 2026"`, `"Aarong fabric sourcing supplier"` |
| **jewellery** | Hallmark compliance, gold price sensitivity, wedding seasonality | `"BAJUS hallmark regulation 2026"`, `"Bangladesh gold demand wedding season"` |
| **media-marketing** | Agency pricing, talent supply, platform dependency risks | `"Bangladesh digital marketing agency pricing 2026"`, `"Facebook ads cost Bangladesh 2026"` |
| **high-roi-niches** | Sub-niche definition, scoring rubric, capital intensity | `"Bangladesh pet care market 2026"`, `"Bangladesh creator economy revenue 2026"` |
| **automotive** | Import duties on parts, garage vs premium segmentation | `"Bangladesh car parts import duty 2026"`, `"car wash franchise Bangladesh"` |

---

## 14. DESIGN PRINCIPLES (agreed by all 4 models)

1. **Evidence-first, never freeform**: `Search → evidence JSON → extracted facts → confidence scoring → markdown regeneration`
2. **Provenance on everything**: Every data point traceable to a search query + source URL
3. **Freshness is mandatory**: No data older than policy thresholds without explicit "historical" tag
4. **Confidence is scored**: Every claim has a 0-1 confidence score; low-confidence items get priority for re-verification
5. **Markdown is generated, not source-of-truth**: JSON sidecars are the source; markdown is the presentation
6. **Bengali-language sources are critical**: Most BD market data is only available in Bengali
7. **Crypto trading is LEGAL in Bangladesh**: Permanent, non-negotiable fact

---

## 15. FILES TO CREATE (full backlog)

### New directories
- `_system/config/`, `_system/prompts/`, `_system/schemas/`, `_system/scripts/`, `_system/lib/`, `_system/state/`, `_system/logs/`
- `data/sector-index/`, `data/competitors/`, `data/evidence/`, `data/pricing/`, `data/sentiment/`, `data/compliance/`, `data/changelog/`
- `reports/`

### New files (per sector × 8)
- `regulatory-compliance.md`, `customer-personas.md`, `pricing-intelligence.md`, `sentiment-reviews.md`, `seasonality-trends.md`, `supply-chain-map.md`, `investment-deal-flow.md`, `policy-tracker.md`, `research/search-log.md`, `research/freshness-ledger.md`

### New system files
- 7 config YAMLs, 6 prompt files, 4 JSON schemas, 16 Python scripts, 9 Python lib modules, 5 report markdowns

### Total estimated: ~200 new files

---

## 16. WHAT THIS SYSTEM WILL LOOK LIKE IN 30 DAYS

After ~240 automated runs (3h × 30d):
- All 8 sectors at full file contract (17+ files each)
- Every competitor has JSON sidecar with revenue, funding, pricing, sentiment
- Freshness scores auto-maintained — no data older than policy thresholds
- Query memory knows which searches yield best data per sector
- Cross-sector correlation report generated weekly
- Regulatory changes detected within 6 hours (crypto) to 24 hours (others)
- 2,000+ evidence items with full provenance chains
- Auto-generated repo health dashboard showing sector-by-sector scores

---

**Awaiting Punisher's review and approval before implementation begins.**
