# Business Plan Template — Makefile
# Convenience targets for common pipeline operations.
# Usage: make <target>

PYTHON := python3
SYSTEM := _system
SCRIPTS := $(SYSTEM)/scripts
STATE  := $(SYSTEM)/state

.PHONY: help audit freshness search extract score update archive validate pipeline \
        plan health changelog commit all clean

help:
	@echo 'Usage: make <target>'
	@echo ''
	@echo 'Pipeline steps (ordered):'
	@echo '  audit        — Scan repo, build file inventory, find gaps (audit_repo.py)'
	@echo '  freshness    — Apply freshness policy, build stale-queue (evaluate_freshness.py)'
	@echo '  plan         — Multi-LLM review → search plan (build_search_plan.py)'
	@echo '  search       — Execute search queries via search.datasolved.org (execute_searches.py)'
	@echo '  extract      — Extract structured facts from evidence (extract_facts.py)'
	@echo '  score        — Score extracted evidence confidence (score_confidence.py)'
	@echo '  update       — Update sector docs from scored evidence (update_sector_docs.py)'
	@echo '  archive      — Archive stale/abandoned content (archive_stale.py)'
	@echo '  validate     — Validate sector markdown structure (validate_markdown.py)'
	@echo '  changelog    — Regenerate changelog (generate_changelog.py)'
	@echo ''
	@echo 'Combined:'
	@echo '  pipeline     — Run full pipeline: audit → freshness → plan → search → extract → score → update → archive → validate → changelog'
	@echo '  quick        — audit → freshness → changelog (no LLM calls, no network)'
	@echo ''
	@echo 'Monitoring:'
	@echo '  health       — Run sector-health.py dashboard (requires audit first)'
	@echo ''
	@echo 'Utilities:'
	@echo '  all          — pipeline + health'
	@echo '  clean        — Remove runtime state (not evidence)'

# ── Pipeline steps ────────────────────────────────────────────────

audit:
	@echo '=== AUDIT ==='
	$(PYTHON) $(SCRIPTS)/audit_repo.py

freshness: audit
	@echo '=== FRESHNESS ==='
	$(PYTHON) $(SCRIPTS)/evaluate_freshness.py

plan: freshness
	@echo '=== PLAN (multi-LLM review) ==='
	$(PYTHON) $(SCRIPTS)/build_search_plan.py

search: plan
	@echo '=== SEARCH ==='
	$(PYTHON) $(SCRIPTS)/execute_searches.py

extract: search
	@echo '=== EXTRACT ==='
	$(PYTHON) $(SCRIPTS)/extract_facts.py

score: extract
	@echo '=== SCORE ==='
	$(PYTHON) $(SCRIPTS)/score_confidence.py

update: score
	@echo '=== UPDATE ==='
	$(PYTHON) $(SCRIPTS)/update_sector_docs.py

archive: update
	@echo '=== ARCHIVE ==='
	$(PYTHON) $(SCRIPTS)/archive_stale.py

validate: archive
	@echo '=== VALIDATE ==='
	$(PYTHON) $(SCRIPTS)/validate_markdown.py

changelog: validate
	@echo '=== CHANGELOG ==='
	$(PYTHON) $(SCRIPTS)/generate_changelog.py

# ── Combined ──────────────────────────────────────────────────────

pipeline: changelog
	@echo ''
	@echo '=== FULL PIPELINE COMPLETE ==='
	@$(PYTHON) $(SCRIPTS)/generate_changelog.py 2>/dev/null || true

quick: audit freshness changelog
	@echo '=== QUICK RUN COMPLETE ==='

# ── Monitoring ────────────────────────────────────────────────────

health:
	@echo '=== SECTOR HEALTH ==='
	$(PYTHON) $(SCRIPTS)/sector_health.py

# ── Utilities ─────────────────────────────────────────────────────

all: pipeline health
	@echo '=== ALL DONE ==='

clean:
	@echo 'Removing runtime state...'
	rm -f $(STATE)/audit_results.json
	rm -f $(STATE)/file_inventory.json
	rm -f $(STATE)/freshness_queue.json
	rm -f $(STATE)/search_plan.json
	rm -f $(STATE)/validation_results.json
	rm -f $(STATE)/last_pipeline_run.json
	@echo 'Done.'
