# Business Plan Template

A structured repository for researching, analyzing, and documenting business ideas across any sector. Each sector gets its own directory, and every business plan follows the same set of reusable templates.

## Researched Sectors (Bangladesh Market)

| # | Sector | Directory | Competitors | Docs | Status |
|---|--------|-----------|:-----------:|:----:|:------:|
| 1 | Automotive & Car Care | `sectors/automotive-car-care/` | 12 | 9/9 | ✅ Complete |
| 2 | Clothing & Fashion | `sectors/clothing-fashion/` | 8 | 8/9 | 🟢 Good |
| 3 | Jewellery | `sectors/jewellery/` | 6 | 8/9 | 🟢 Good |
| 4 | Travel & Tourism | `sectors/travel-tourism/` | 7 | 8/9 | 🟢 Good |
| 5 | Media, Marketing & Digital | `sectors/media-marketing-digital/` | 7 | 8/9 | 🟢 Good |
| 6 | Bitcoin & Cryptocurrency | `sectors/crypto-bitcoin/` | 4 | 9/9 | 🟢 Good |
| 7 | iPhone, Electronics & Gadgets | `sectors/electronics-gadgets/` | 7 | 8/9 | 🟢 Good |
| 8 | High-ROI Niches | `sectors/high-roi-niches/` | 7 | 8/9 | 🟢 Good |
| 9 | BIM Global Outreach | `sectors/bim-global-outreach/` | — | — | 🆕 Active (YAML) |
| 10 | Healthcare & Pharma | `sectors/healthcare-pharma/` | — | 1/9 | 🔴 Critical |
| 11 | Construction & Real Estate | `sectors/construction-real-estate/` | — | 1/9 | 🔴 Critical |
| 12 | Food & Beverage | `sectors/food-beverage/` | — | 1/9 | 🔴 Critical |
| 13 | Education & Training | `sectors/education-training/` | — | 1/9 | 🔴 Critical |
| 14 | Logistics & Transport | `sectors/logistics-transport/` | — | 1/9 | 🔴 Critical |
| 15 | Agriculture & Agro-processing | `sectors/agriculture-agro/` | — | 1/9 | 🔴 Critical |

**Total:** 15 sectors (165 files, ~2,183 evidence items). 9 sectors fully researched, 6 with scaffolded READMEs — self-evolving pipeline will auto-populate remaining docs.

> **Status key:** `9/9 docs` = all standard sector docs present (incl. financial-model). `8/9` = missing financial-model. 🆕 Active (YAML) = sector defined in `_system/config/sectors.yaml` for GMaps lead pipeline; research docs not yet scaffolded. See `make health` for full dashboard.

## Quick Start

```bash
# Full pipeline (audit → freshness → search → extract → score → update → archive → validate → changelog)
make pipeline

# Quick health check (no LLM calls, no network)
make health

# Specific pipeline step
make audit
make freshness
```

## What's New

- **`docs/ARCHITECTURE.md`** — complete system documentation covering data flow, pipeline scripts, config, conventions
- **`data/sector-index/`** — per-sector metadata JSON for tooling and dashboards
- **Financial models** for automotive & crypto sectors (`financial-model.md`)
- **`Makefile`** — convenience targets for pipeline steps (`make audit`, `make freshness`, `make search`, ...)
- **Sector health dashboard** — `make health` or `python _system/scripts/sector_health.py`
- **Fair pipeline distribution** — round-robin query allocation across all 15 sectors (not just the busiest 2)
- **Zero-evidence detection** — pipeline auto-injects P0 data collection for sectors with no evidence

---

## Directory Structure

```
.
├── _templates/              # Reusable templates — copy into a sector when starting a new plan
│   ├── 01-idea-brief/       # One-page idea summary
│   ├── 02-competitor-analysis/ # Competitive landscape deep-dive
│   ├── 03-strategy-canvas/  # Value proposition & positioning (Blue Ocean style)
│   ├── 04-financial-model/  # Revenue, costs, unit economics
│   ├── 05-go-to-market/     # Launch plan, channels, timeline
│   └── 06-risk-register/    # Risks, mitigations, assumptions
│
├── _guides/                 # How-to docs for research methodology
├── Makefile                 # Convenience targets for pipeline steps
│
├── sectors/                 # One directory per industry/sector
│   ├── automotive-car-care/ # Bangladesh car care market
│   │   └── bd-market/
│   │       ├── README.md            # Sector overview
│   │       ├── competitors/         # Individual competitor profiles
│   │       ├── research/            # Raw research and landscape reports
│   │       ├── strategy-canvas.md   # Blue Ocean strategy canvas
│   │       ├── go-to-market.md      # GTM plan
│   │       └── risk-register.md     # Risk assessment
│   ├── clothing-fashion/
│   ├── jewellery/
│   ├── travel-tourism/
│   ├── media-marketing-digital/
│   ├── crypto-bitcoin/
│   ├── electronics-gadgets/
│   ├── high-roi-niches/
│   ├── bim-global-outreach/    # BIM/architecture global outreach
│   ├── healthcare-pharma/      # Healthcare & Pharma (pipeline-ready, research pending)
│   ├── construction-real-estate/ # Construction & Real Estate (pipeline-ready)
│   ├── food-beverage/          # Food & Beverage (pipeline-ready)
│   ├── education-training/     # Education & Training (pipeline-ready)
│   ├── logistics-transport/    # Logistics & Transport (pipeline-ready)
│   └── agriculture-agro/       # Agriculture & Agro-processing (pipeline-ready)
│
└── _archive/                # Deprecated or abandoned plans (don't delete, archive)
```

## How to Use

### Starting a New Sector

1. Create a directory under `sectors/<sector-name>/<market>/`
2. Copy the templates you need from `_templates/` into that directory
3. Fill them in — each template has instructions inside
4. Add competitor profiles, raw research data, and any supporting files

### Template Workflow

Templates are numbered in the order you typically fill them:

1. **Idea Brief** — What's the opportunity? Who's the customer? Why now?
2. **Competitor Analysis** — Who else is playing? What are their strengths and gaps?
3. **Strategy Canvas** — Where do you differentiate? What factors do you compete on?
4. **Financial Model** — How does this make money? What are the unit economics?
5. **Go-to-Market** — How do you acquire your first 100/1,000/10,000 customers?
6. **Risk Register** — What could kill this? What are you assuming?

Not every business needs every template. Use what's relevant. Skip the rest.

### Naming Conventions

- Sectors: `kebab-case` (e.g., `fintech-mobile-banking`)
- Markets: `kebab-case` with region if needed (e.g., `bd-market`, `sea-market`)
- Competitor files: `YYYY-MM-DD-competitor-name.md`
- Research files: `YYYY-MM-DD-topic.md`

## Principles

- **Raw data stays in `research/`** — screenshots, scrape output, interview notes
- **Analysis lives in templates** — synthesis, not raw data
- **Archive, don't delete** — move abandoned work to `_archive/`
- **Date every file** — when was this analysis done? Stale research is dangerous
- **One competitor, one file** — makes it easy to update individual profiles
- **Legal warnings where needed** — sectors with regulatory restrictions (e.g., crypto) carry explicit disclaimers

## Adding a New Sector

Each sector follows this standard structure:

```
sectors/<sector-name>/bd-market/
├── README.md                              # Market overview, key segments, why this sector
├── competitors/
│   └── YYYY-MM-DD-competitor-name.md      # One file per competitor
├── research/
│   └── YYYY-MM-DD-full-landscape-report.md # Comprehensive market report
├── strategy-canvas.md                     # Blue Ocean ERRC + competing factors
├── go-to-market.md                        # Phased launch plan with 90-day milestones
└── risk-register.md                       # Risk matrix with kill criteria
```

## License

MIT
