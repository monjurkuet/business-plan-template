"""Load and cache YAML/JSON config files from _system/config/ and _system/schemas/."""

import json
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # business-plan-template/
SYSTEM_DIR = REPO_ROOT / "_system"
CONFIG_DIR = SYSTEM_DIR / "config"
SCHEMA_DIR = SYSTEM_DIR / "schemas"
DATA_DIR = REPO_ROOT / "data"
SECTORS_DIR = REPO_ROOT / "sectors"


def _load_yaml(path: Path) -> dict:
    """Load a YAML file. Falls back to simple parsing if pyyaml not available."""
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Minimal YAML parser for our simple configs
        with open(path) as f:
            text = f.read()
        return _simple_yaml_parse(text)


def _simple_yaml_parse(text: str) -> dict:
    """Very simple YAML parser for nested key: value configs. Not general-purpose."""
    result = {}
    current_path = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if ":" in stripped and not stripped.strip().startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            depth = indent // 2
            current_path = current_path[:depth]
            if val:
                # Leaf value
                val = _coerce(val)
                _set_nested(result, current_path + [key], val)
            else:
                current_path.append(key)
    return result


def _coerce(val: str):
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    return val


def _set_nested(d: dict, keys: list, value):
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


@lru_cache(maxsize=32)
def load_config(name: str) -> dict:
    """Load a config file by name (without extension). Tries .yaml then .json."""
    for ext in (".yaml", ".json"):
        path = CONFIG_DIR / f"{name}{ext}"
        if path.exists():
            if ext == ".json":
                return json.loads(path.read_text())
            return _load_yaml(path)
    raise FileNotFoundError(f"Config not found: {name}")


@lru_cache(maxsize=16)
def load_schema(name: str) -> dict:
    """Load a JSON schema by name (without extension)."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    if path.exists():
        return json.loads(path.read_text())
    raise FileNotFoundError(f"Schema not found: {name}")


def get_sector_configs() -> dict:
    """Return the full sectors config."""
    return load_config("sectors").get("sectors", {})


def get_sector_config(sector: str) -> dict:
    """Return config for a single sector."""
    return get_sector_configs().get(sector, {})


def get_freshness_policy(sector: str = None) -> dict:
    """Load freshness policy, optionally merged with sector overrides."""
    cfg = load_config("freshness-policy")
    policy = dict(cfg.get("default", {}))
    categories = cfg.get("categories", {})
    if sector:
        overrides = cfg.get("sector_overrides", {}).get(sector, {})
        for cat, cat_policy in categories.items():
            if cat in overrides:
                policy[cat] = {**cat_policy, **overrides[cat]}
            else:
                policy[cat] = cat_policy
    else:
        policy.update(categories)
    return policy


def get_source_weights() -> dict:
    """Load source domain trust weights."""
    return load_config("source-rankings")


def get_search_taxonomy() -> dict:
    """Load search query families."""
    return load_config("search-taxonomy").get("query_families", {})


def get_model_routing() -> dict:
    """Load LLM model routing config."""
    return load_config("model-routing")


def get_scoring_rules() -> dict:
    """Load confidence scoring rules."""
    return load_config("scoring-rules")


def now_iso() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def get_sector_dirs() -> list[Path]:
    """List all active sector directories."""
    if not SECTORS_DIR.exists():
        return []
    return [p for p in SECTORS_DIR.iterdir() if p.is_dir() and (p / "bd-market").exists()]
