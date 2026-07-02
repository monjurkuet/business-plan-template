# Business Plan Template — Agent Guide

## Architecture

This repo defines 15 business sectors (9 researched + 6 pipeline-only) for the BD market. It drives two downstream systems:

1. **Self-evolving research pipeline** (`c52a5f33e4e9` cron, every 6h) — audits, searches, extracts, and updates sector docs
2. **InfiniteCrawler GMaps lead pipeline** — reads `_system/config/sectors.yaml` to generate Google Maps search queries across all 15 sectors

## Sectors

15 sectors defined in `_system/config/sectors.yaml`:

| Researched (9) | Pipeline-only (6) |
|----------------|-------------------|
| automotive-car-care | healthcare-pharma |
| clothing-fashion | construction-real-estate |
| jewellery | food-beverage |
| travel-tourism | education-training |
| media-marketing-digital | logistics-transport |
| crypto-bitcoin | agriculture-agro |
| electronics-gadgets | |
| high-roi-niches | |
| bim-global-outreach | |

Each sector YAML entry has `keywords.en`, `keywords.bn`, `subsegments`, and `priority_weight`.

## Key Files

| Path | Purpose |
|------|---------|
| `_system/config/sectors.yaml` | Sector definitions (keywords, subsegments, weights) |
| `_system/scripts/pipeline_manager.py` | BPT self-evolving pipeline orchestrator |
| `_system/scripts/sector_health.py` | Health dashboard (`make health`) |
| `sectors/<name>/bd-market/` | Per-sector research docs (9 researched sectors) |

## Commands

```bash
make health         # Sector health dashboard
make pipeline       # Full self-evolving research pipeline
make audit          # Audit repo files
make freshness      # Evaluate data freshness
```

## Integration with InfiniteCrawler

`daemons/query_generator.py` (in `/root/codebase/vhd/infinitecrawler`) reads this repo's `sectors.yaml` to build 21,356 unique GMaps search queries across 3 pools:

| Pool | Size | Description |
|------|------|-------------|
| BD-Local | 17,130 | "{keyword} in {city}" × 15 cities × 15 sectors |
| BD-National | 1,094 | "{keyword} Bangladesh" / "{keyword} outside Dhaka" |
| Global | 3,132 | "{keyword} {country}" × 6 markets × 11 export-eligible sectors |

## Adding a Sector

1. Add entry to `_system/config/sectors.yaml` with `status: active`, keywords, and subsegments
2. Optionally scaffold `sectors/<name>/bd-market/` with research templates
3. Restart `infinitecrawler-search` daemon to pick up new queries