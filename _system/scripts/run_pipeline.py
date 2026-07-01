#!/usr/bin/env python3
"""run_pipeline.py — Main orchestrator for the self-evolving research system.

Executes the full pipeline: Audit → Freshness → Search → Extract → Score → Update → Archive → Validate → Commit → Learn

Usage:
    python _system/scripts/run_pipeline.py [--dry-run] [--skip-commit] [--phase PHASE]
"""

import sys
import json
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "_system"))

from lib.config_loader import now_iso

log = logging.getLogger("run_pipeline")

SCRIPTS_DIR = REPO_ROOT / "_system" / "scripts"


def run_script(name: str, dry_run: bool = False) -> bool:
    """Run a pipeline script and return success status."""
    script_path = SCRIPTS_DIR / name
    if not script_path.exists():
        log.error(f"Script not found: {name}")
        return False
    
    if dry_run:
        log.info(f"[DRY-RUN] Would run: python {script_path}")
        return True
    
    log.info(f"\n{'='*60}")
    log.info(f"Running: {name}")
    log.info(f"{'='*60}")
    
    # Load cron.env into subprocess environment so scripts see pipeline config
    import os as _os
    cron_env = {}
    cron_env_path = REPO_ROOT / "_system" / "config" / "cron.env"
    if cron_env_path.exists():
        for raw in cron_env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            cron_env[key.strip()] = val.strip().strip('"').strip("'")
    
    env = {**_os.environ, **cron_env}
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(REPO_ROOT),
            env=env,
        )
        if result.stdout:
            log.info(result.stdout[-2000:])  # Last 2000 chars
        if result.stderr:
            log.warning(result.stderr[-1000:])
        if result.returncode != 0:
            log.error(f"{name} exited with code {result.returncode}")
            return False
        log.info(f"✓ {name} completed successfully")
        return True
    except subprocess.TimeoutExpired:
        log.error(f"{name} timed out (600s)")
        return False
    except Exception as ex:
        log.error(f"{name} failed: {ex}")
        return False


def git_commit(dry_run: bool = False) -> bool:
    """Stage and commit all changes."""
    if dry_run:
        log.info("[DRY-RUN] Would git add + commit")
        return True
    
    try:
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        if not result.stdout.strip():
            log.info("No changes to commit.")
            return True
        
        # Stage all
        subprocess.run(["git", "add", "-A"], cwd=str(REPO_ROOT), check=True)
        
        # Commit
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        msg = f"auto: pipeline run {timestamp}"
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        
        if result.returncode == 0:
            log.info(f"✓ Committed: {msg}")
            # Push
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True, text=True, cwd=str(REPO_ROOT)
            )
            if push_result.returncode == 0:
                log.info("✓ Pushed to origin/main")
            else:
                log.warning(f"Push failed: {push_result.stderr[:200]}")
            return True
        else:
            log.warning(f"Commit issue: {result.stderr[:200]}")
            return True  # Non-fatal
            
    except Exception as ex:
        log.error(f"Git operations failed: {ex}")
        return False


def run_full_pipeline(dry_run: bool = False, skip_commit: bool = False, 
                      start_phase: str = None) -> dict:
    """Run the complete pipeline."""
    results = {}
    start = datetime.now(timezone.utc)
    
    phases = [
        ("phase1_audit", [
            ("audit_repo.py", "Audit repository"),
            ("evaluate_freshness.py", "Evaluate freshness"),
        ]),
        ("phase1_validate", [
            ("validate_markdown.py", "Validate markdown"),
        ]),
        ("phase2_search", [
            ("execute_searches.py", "Execute searches"),
        ]),
        ("phase2_extract", [
            ("extract_facts.py", "Extract facts"),
        ]),
        ("phase2_score", [
            ("score_confidence.py", "Score confidence"),
        ]),
        ("phase3_plan", [
            ("build_search_plan.py", "Build next search plan"),
        ]),
        ("phase3_update", [
            ("update_sector_docs.py", "Update sector docs"),
        ]),
        ("phase3_archive", [
            ("archive_stale.py", "Archive stale files"),
        ]),
        ("phase4_changelog", [
            ("generate_changelog.py", "Generate changelog"),
        ]),
        ("phase4_learn", [
            ("generate_sidecars.py", "Generate competitor JSON sidecars"),
            ("update_query_memory.py", "Update query memory"),
        ]),
    ]
    
    # Find starting phase if specified
    phase_names = [p[0] for p in phases]
    start_idx = 0
    if start_phase:
        if start_phase in phase_names:
            start_idx = phase_names.index(start_phase)
        else:
            log.warning(f"Unknown phase: {start_phase}. Starting from beginning.")
    
    running = False
    for i, (phase_name, steps) in enumerate(phases):
        if i < start_idx:
            continue
        running = True
        
        log.info(f"\n{'#'*60}")
        log.info(f"# {phase_name}")
        log.info(f"{'#'*60}")
        
        for script, desc in steps:
            success = run_script(script, dry_run)
            results[script] = "ok" if success else "failed"
            if not success and not dry_run:
                log.warning(f"Step failed: {script}. Continuing...")
    
    # Git commit
    if not skip_commit and running:
        git_commit(dry_run)
    
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    results["elapsed_seconds"] = round(elapsed, 1)
    results["timestamp"] = now_iso()
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Self-evolving research pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    parser.add_argument("--skip-commit", action="store_true", help="Skip git commit/push")
    parser.add_argument("--phase", type=str, default=None, help="Start from a specific phase")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    log.info("=" * 60)
    log.info("SELF-EVOLVING RESEARCH PIPELINE")
    log.info(f"Dry run: {args.dry_run}")
    log.info(f"Skip commit: {args.skip_commit}")
    if args.phase:
        log.info(f"Start phase: {args.phase}")
    log.info("=" * 60)

    results = run_full_pipeline(
        dry_run=args.dry_run,
        skip_commit=args.skip_commit,
        start_phase=args.phase,
    )

    # Save pipeline run log
    state_dir = REPO_ROOT / "_system" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    run_log = state_dir / "last_pipeline_run.json"
    run_log.write_text(json.dumps(results, indent=2, default=str))

    log.info("\n" + "=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)
    for script, status in results.items():
        icon = "✓" if status == "ok" else "✗"
        log.info(f"  {icon} {script}: {status}")


if __name__ == "__main__":
    main()
