"""OpenAI-compatible LLM client using the Datasolved endpoint."""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("llm_client")

# Defaults from environment
DEFAULT_BASE_URL = os.environ.get("OPENPAI_BASE_URL") or os.environ.get("LLM_API_BASE") or "https://llm.datasolved.org/v1"
DEFAULT_API_KEY = os.environ.get("OPENPAI_API_KEY") or os.environ.get("LLM_API_KEY") or ""
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "90"))
DEFAULT_REQUEST_RETRIES = int(os.environ.get("LLM_REQUEST_RETRIES", "2"))
DEFAULT_BACKOFF_SECONDS = float(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", "1.5"))

# Known alias normalizations. Keep these conservative: only map variants that
# are known to behave like the same model on compatible providers.
DEFAULT_MODEL_ALIASES = {
    "openai/gpt-5.4": "gpt-5.4",
    "openai/gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.4-preview": "gpt-5.4",
    "gpt-5.4-mini-preview": "gpt-5.4-mini",
    "google/gemini-2.5-flash": "gemini-2.5-flash",
    "google/gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "google/gemini-3-flash-preview": "gemini-3-flash-preview",
    "google/gemini-3.1-flash-lite-preview": "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite-preview": "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-v4-pro": "deepseek-ai/deepseek-v4-pro",
}

RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}


def _load_env_alias_map() -> dict[str, str]:
    """Load optional model alias overrides from the environment."""
    raw = os.environ.get("LLM_MODEL_ALIAS_MAP_JSON", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception as ex:
        log.warning(f"Ignoring invalid LLM_MODEL_ALIAS_MAP_JSON: {ex}")
        return {}
    if not isinstance(payload, dict):
        log.warning("Ignoring LLM_MODEL_ALIAS_MAP_JSON: expected a JSON object")
        return {}
    return {str(k).strip(): str(v).strip() for k, v in payload.items() if str(k).strip() and str(v).strip()}


def normalize_model_name(model: str) -> str:
    """Normalize a requested model name to a canonical provider alias."""
    if model is None:
        return ""

    normalized = str(model).strip()
    if not normalized:
        return normalized

    alias_map = {**DEFAULT_MODEL_ALIASES, **_load_env_alias_map()}
    if normalized in alias_map:
        return alias_map[normalized]

    # Strip only well-known vendor prefixes when the remaining ID is otherwise valid.
    for prefix in ("openai/", "google/", "anthropic/"):
        if normalized.startswith(prefix):
            remainder = normalized[len(prefix):].strip()
            if remainder:
                return alias_map.get(remainder, remainder)

    return normalized


def _model_candidates(model: str) -> list[str]:
    """Return a de-duplicated candidate list for retrying model aliases."""
    candidates = [model, normalize_model_name(model)]
    # Also add reverse matches for canonical names so we can fall back to any known aliases.
    alias_map = {**DEFAULT_MODEL_ALIASES, **_load_env_alias_map()}
    canonical = normalize_model_name(model)
    for alias, target in alias_map.items():
        if target == canonical:
            candidates.append(alias)
    return [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]


def _urlopen_with_retry(req, timeout: int, retries: int = DEFAULT_REQUEST_RETRIES, backoff_seconds: float = DEFAULT_BACKOFF_SECONDS):
    """Open a URL with bounded retries for transient transport/server failures."""
    last_ex = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            if e.code not in RETRYABLE_HTTP_STATUS_CODES or attempt >= max(1, retries):
                log.error(f"  → HTTP {e.code}: {e.reason} | {body[:500]}")
                raise
            log.warning(f"  → HTTP {e.code}: {e.reason} | retrying in {backoff_seconds * attempt:.1f}s")
            last_ex = e
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            if attempt >= max(1, retries):
                log.error(f"  → Error: {e}")
                raise
            log.warning(f"  → Error: {e} | retrying in {backoff_seconds * attempt:.1f}s")
            last_ex = e

        time.sleep(backoff_seconds * attempt)

    if last_ex:
        raise last_ex
    raise RuntimeError("urlopen retry loop exited unexpectedly")


def call_llm(
    messages: list[dict],
    model: str = "gpt-5.4",
    temperature: float = 0.1,
    max_tokens: int = 8000,
    base_url: str = None,
    api_key: str = None,
    response_format: dict = None,
    timeout: int = None,
) -> dict:
    """Call the OpenAI-compatible chat completions API.

    Returns: {"content": str, "usage": dict, "model": str}
    """
    base_url = base_url or DEFAULT_BASE_URL
    api_key = api_key or DEFAULT_API_KEY
    timeout = DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout

    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    candidates = _model_candidates(model)
    last_ex = None

    for candidate in candidates:
        body = {
            "model": candidate,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )

        log.info(f"Calling {candidate} ({len(json.dumps(body))} bytes input)")

        try:
            with _urlopen_with_retry(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            log.info(f"  → {len(content)} chars, usage: {usage}")

            return {
                "content": content,
                "usage": usage,
                "model": data.get("model", candidate),
            }
        except urllib.error.HTTPError as e:
            last_ex = e
            body = e.read().decode() if e.fp else ""
            if e.code == 404 and candidate != candidates[-1]:
                log.warning(f"  → HTTP 404 for {candidate} | {body[:200]} | trying next alias")
                continue
            log.error(f"  → HTTP {e.code}: {e.reason} | {body[:500]}")
            raise
        except Exception as e:
            last_ex = e
            log.error(f"  → Error: {e}")
            raise

    if last_ex:
        raise last_ex
    raise RuntimeError("No model candidates available")


def call_llm_json(
    messages: list[dict],
    model: str = "gpt-5.4",
    temperature: float = 0.1,
    max_tokens: int = 8000,
    **kwargs,
) -> dict:
    """Call LLM and parse JSON from the response. Handles markdown code fences."""
    result = call_llm(messages, model, temperature, max_tokens, **kwargs)
    content = result["content"].strip()
    
    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first line (```json) and last line (```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON in the content
        import re
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())
        log.warning(f"Could not parse JSON from LLM response (first 200 chars): {content[:200]}")
        return {"raw_response": content, "parse_error": True}


def call_llm_text(
    messages: list[dict],
    model: str = "gpt-5.4",
    temperature: float = 0.1,
    max_tokens: int = 8000,
    **kwargs,
) -> str:
    """Call LLM and return raw text content."""
    result = call_llm(messages, model, temperature, max_tokens, **kwargs)
    return result["content"]


def load_prompt(name: str) -> str:
    """Load a prompt template from _system/prompts/."""
    prompt_dir = Path(__file__).resolve().parent.parent / "prompts"
    path = prompt_dir / f"{name}.md"
    if path.exists():
        return path.read_text()
    raise FileNotFoundError(f"Prompt not found: {name}")


def format_review_messages(prompt_name: str, context: str) -> list[dict]:
    """Build messages list from a prompt template + context."""
    system_prompt = load_prompt(prompt_name)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ]
