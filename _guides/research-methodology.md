# Research Guide: How to Analyze a New Sector

This guide covers the methodology for researching and documenting a new business sector in this repository.

---

## Step 1: Define the Sector

Before researching, answer these questions:

- What industry/sector is this?
- What geographic market? (BD, SEA, global?)
- What specific niche within the sector?
- What time period is this research valid for?

Create a directory: `sectors/<sector-name>/<market>/`

---

## Step 2: Map the Competitive Landscape

### Finding Competitors

**Facebook search** (for BD/SEA markets):
- Search `facebook.com/search/pages?q=<keyword>` for relevant terms
- Sort through results by follower count
- Visit each competitor page for details

**Google search:**
- `"<sector> in <country>"` — find top players
- `"best <product> for <use case>"` — find what ranks
- Check Google Maps for local businesses

**Industry directories:**
- Local business directories (e.g., Bikroy, Daraz for BD)
- Industry association websites
- LinkedIn company search

### What to Document Per Competitor

Use the `_templates/02-competitor-analysis/competitor-analysis.md` template. Key fields:

1. **Basic profile** — name, website, social, location, category
2. **Market position** — followers, reviews, verified status, reach
3. **Product lines** — everything they sell, pricing, best-sellers
4. **Strengths** — what they do better than anyone
5. **Weaknesses** — where they're vulnerable
6. **Strategy observations** — marketing, content, sales model, partnerships
7. **Social media analysis** — posting frequency, content types, engagement
8. **Threat level** — overlap score + key takeaway

### How Many Competitors?

- **Minimum:** 5–7 competitors to see patterns
- **Ideal:** 10–15 for thorough landscape
- **Include:** 1–2 "aspiration" competitors (much bigger/different market) for context

---

## Step 3: Identify Market Gaps

After profiling competitors, write a landscape summary that answers:

1. **What does nobody offer?** (product, service, guarantee, channel)
2. **What do customers complain about?** (check reviews, comments, forums)
3. **Where are competitors weakest online?** (no website? no SEO? no content?)
4. **What's growing but underserved?** (hybrid cars in BD, for example)
5. **What business model does nobody use?** (subscription, community, financing)

---

## Step 4: Fill Strategy Templates

1. **Strategy Canvas** — score each competitor on key factors, identify ERRC opportunities
2. **Idea Brief** — define the business idea, customer, model
3. **Go-to-Market** — how to acquire first 1,000 customers
4. **Financial Model** — unit economics, projections
5. **Risk Register** — what could go wrong, mitigation plans

---

## Step 5: Validate Assumptions

Every plan has assumptions. The most dangerous ones are:

- "Customers will buy online" (vs. in-store)
- "This price point is acceptable"
- "We can acquire customers at this cost"
- "This supplier will deliver reliably"
- "Regulations won't change"

For each assumption, define:
- **How to validate** (test, survey, MVP, ad campaign)
- **By when** (deadline)
- **Kill criteria** (what result means the assumption is wrong)

---

## Research Quality Checklist

- [ ] All competitor profiles have real data (not guesses marked as facts)
- [ ] Follower counts and review scores are from actual pages (not estimates)
- [ ] Pricing comes from websites or posts (not assumptions)
- [ ] Market gaps are supported by evidence (not just "I think")
- [ ] Assumptions are explicitly listed (not hidden)
- [ ] Kill criteria are defined (not just optimistic projections)
- [ ] Date is on every document (stale research is dangerous)

---

## Updating Existing Research

- **Update the existing file** — don't create `2026-05-07-irfan-imports-v2.md`
- **Change "Last updated" date** in the metadata
- **Add new data with dates** — e.g., "Follower count: 83K (May 2026), 92K (Aug 2026)"
- **Archive outdated sectors** in `_archive/` — don't delete

---

## Tools for Research

| Task | Tool | Notes |
|------|------|-------|
| Facebook competitor search | Facebook search + manual page visits | Use logged-in Chrome for full access |
| Website analysis | Browser + DevTools | Check for e-commerce, blog, SEO |
| SEO keywords | Google Search Console, Ahrefs free tier | Find what people search for |
| Pricing data | Competitor websites, Facebook posts, Daraz/Bikroy | Cross-reference multiple sources |
| Customer sentiment | Facebook comments, Google reviews | Read the 1-3 star reviews especially |
| Market size data | Bangladesh Bureau of Statistics, industry reports | Hard to find for BD — triangulate |
