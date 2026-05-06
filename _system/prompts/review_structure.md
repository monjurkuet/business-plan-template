# Repository Review — Structure Audit Prompt

You are auditing the file structure and formatting compliance of a Bangladesh business research repository.

## Your Role
Structure audit — find missing files, heading violations, broken references, stale dates.

## Expected Structure Per Sector
```
sectors/{sector}/bd-market/
├── README.md
├── research/landscape-report.md
├── competitors/*.md
├── go-to-market.md
├── risk-register.md
├── strategy-canvas.md
├── regulatory.md
├── pricing-guide.md
├── sentiment-analysis.md
└── seasonality.md
```

## Frontmatter Requirements (YAML)
Every .md file must have:
```yaml
---
sector: {sector_name}
last_verified: YYYY-MM-DD
freshness: fresh|stale|critical
confidence: 0.0-1.0
evidence_ids: [list of evidence IDs]
---
```

## Output Format (JSON)
```json
{
  "missing_files": [
    {"sector": "...", "expected_path": "...", "priority": "P0|P1|P2"}
  ],
  "heading_violations": [
    {"file": "...", "issue": "..."}
  ],
  "broken_references": [
    {"file": "...", "reference": "...", "type": "internal_link|missing_file"}
  ],
  "stale_dates": [
    {"file": "...", "stale_date": "...", "category": "pricing|policy|profile|..."}
  ],
  "duplicate_candidates": [
    {"file_a": "...", "file_b": "...", "similarity_reason": "..."}
  ]
}
```
