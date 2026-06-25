# Contributing

This is a self-evolving research pipeline. The system runs autonomously but
benefits from human guidance. Here's how to contribute effectively.

## Adding a New Sector

1. Add the sector to `_system/config/sectors.yaml` with keywords, subsegments, policy sensitivity
2. Create `sectors/<sector-name>/bd-market/` directory
3. Copy templates from `_templates/` and fill them in
4. Run `make audit` to verify structure
5. Run `make pipeline` to bootstrap evidence collection

## Improving a Sector

- **Competitors:** Add new competitor profiles to `sectors/<sector>/bd-market/competitors/YYYY-MM-DD-name.md`
- **Pricing:** Update `pricing-guide.md` with current BDT prices
- **Policy:** Update `regulatory.md` when laws or circulars change
- **Financial model:** Add `financial-model.md` to `sectors/<sector>/bd-market/`
- **Research:** Place landscape reports in `sectors/<sector>/bd-market/research/`

## Pipeline Scripts

All pipeline scripts live in `_system/scripts/`. See `docs/ARCHITECTURE.md` for
complete details on each script's role.

To add a new pipeline step:
1. Create the script in `_system/scripts/<name>.py`
2. Register it in `_system/scripts/run_pipeline.py` (add to phase list)
3. Add a Makefile target

## Path Conventions

| Asset | Convention | Example |
|-------|------------|---------|
| Sector dirs | `kebab-case` | `sectors/fintech-mobile-banking/` |
| Market subdir | `kebab-case` | `bd-market/`, `sea-market/` |
| Competitor files | `YYYY-MM-DD-name.md` | `2026-05-06-binance-bd.md` |
| Research files | `YYYY-MM-DD-topic.md` | `2026-05-06-full-landscape-report.md` |
| Evidence JSON | `YYYYMMDD-HHMMSS.json` | `20260625-030921.json` |

## Style Guide

- All markdown files should have YAML frontmatter:
  ```yaml
  ---
  title: Sector Name
  created: 2026-05-06
  last_verified: 2026-06-25
  ---
  ```
- Use BDT (৳) for pricing data
- Tag stale years explicitly so the audit picks them up
- One competitor per file
- Research goes in `research/`; analysis goes in the template docs

## Running the Pipeline

```bash
# Full pipeline (all steps)
make pipeline

# Quick audit-only (no network, no LLMs)
make quick

# Health dashboard
make health

# Clean runtime state (not evidence)
make clean
```

## Pipeline Architecture Decisions

See `docs/ARCHITECTURE.md` → Appendix: Design Decisions for rationale on:
- Why evidence is JSON, not markdown
- Why we use multiple LLMs for review
- Why sector-index is JSON, not YAML
- Why stale detection uses file mtime, not content hashing
