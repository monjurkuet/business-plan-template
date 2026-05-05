# Business Plan Template

A structured repository for researching, analyzing, and documenting business ideas across any sector. Each sector gets its own directory, and every business plan follows the same set of reusable templates.

## Directory Structure

```
.
├── _templates/              # Reusable templates — copy into a sector when starting a new plan
│   ├── 01-idea-brief/       # One-page idea summary
│   ├── 02-competitor-analysis/  # Competitive landscape deep-dive
│   ├── 03-strategy-canvas/  # Value proposition & positioning (Blue Ocean style)
│   ├── 04-financial-model/  # Revenue, costs, unit economics
│   ├── 05-go-to-market/     # Launch plan, channels, timeline
│   └── 06-risk-register/    # Risks, mitigations, assumptions
│
├── _guides/                 # How-to docs for research methodology
│
├── sectors/                 # One directory per industry/sector
│   └── automotive-car-care/ # Example: Bangladesh car care market
│       └── bd-market/
│           ├── README.md            # Sector overview
│           ├── competitors/         # Individual competitor profiles
│           └── research/            # Raw research, screenshots, data
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
- **Archive, don't delete** — moved abandoned work to `_archive/`
- **Date every file** — when was this analysis done? Stale research is dangerous
- **One competitor, one file** — makes it easy to update individual profiles

## License

MIT
