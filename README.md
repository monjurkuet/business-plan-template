# Business Plan Template

A structured repository for researching, analyzing, and documenting business ideas across any sector. Each sector gets its own directory, and every business plan follows the same set of reusable templates.

## Researched Sectors (Bangladesh Market)

| # | Sector | Directory | Competitors | Status |
|---|--------|-----------|-----------|--------|
| 1 | Automotive & Car Care | `sectors/automotive-car-care/` | 9 | ✅ Complete |
| 2 | Clothing & Fashion | `sectors/clothing-fashion/` | 8 | ✅ Complete |
| 3 | Jewellery | `sectors/jewellery/` | 6 | ✅ Complete |
| 4 | Travel & Tourism | `sectors/travel-tourism/` | 7 | ✅ Complete |
| 5 | Media, Marketing & Digital | `sectors/media-marketing-digital/` | 6 | ✅ Complete |
| 6 | Bitcoin & Cryptocurrency | `sectors/crypto-bitcoin/` | 4 | ✅ Complete |
| 7 | iPhone, Electronics & Gadgets | `sectors/electronics-gadgets/` | 7 | ✅ Complete |
| 8 | High-ROI Niches | `sectors/high-roi-niches/` | 7 | ✅ Complete |

**Total:** 111 files, 8 sectors, 54 competitor profiles

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
│   └── high-roi-niches/
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
