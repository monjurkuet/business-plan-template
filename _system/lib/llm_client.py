"""OpenAI-compatible LLM client using the Datasolved or local gateway endpoint.

Handles 308 redirects (Python's urllib doesn't by default), strips SSE
streaming artifacts (data: [DONE]) from local gateway responses, and
normalizes model names across providers.
"""

import io
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import re
from pathlib import Path
from http.client import HTTPResponse

log = logging.getLogger("llm_client")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CRON_ENV_PATH = REPO_ROOT / "_system" / "config" / "cron.env"


# ---------------------------------------------------------------------------
# Custom redirect handler to support HTTP 308 (Permanent Redirect, preserve
# method).  Python 3.11's urllib HTTPRedirectHandler handles 301/302/303/307
# but NOT 308, causing HTTPError on gateway routers that issue 308 to
# re-route POST traffic.
# ---------------------------------------------------------------------------
class _HTTP308RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 (Permanent Redirect) preserving POST method.

    Python 3.11's HTTPRedirectHandler doesn't handle 308 — when aliased
    via ``http_error_308 = http_error_307`` the downstream
    ``redirect_request()`` rejects it because 308 is not in its allowed
    code list.  We provide an explicit handler here.
    """

    def http_error_308(self, req, fp, code, msg, headers):
        if fp:
            fp.read()
            fp.close()
        newurl = headers.get('Location')
        if newurl is None:
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)
        # Resolve relative Location headers against the original URL
        newurl = urllib.parse.urljoin(req.full_url, newurl)
        # Preserve POST method + data for 308 permanent redirect
        new = urllib.request.Request(
            newurl,
            data=req.data,
            headers=req.headers,
            origin_req_host=getattr(req, 'origin_req_host', None),
            unverifiable=True,
            method=req.get_method(),
        )
        return self.parent.open(new, timeout=req.timeout)


# Install at module import time so ALL urllib.request.urlopen() calls in this
# process benefit (including calls from other scripts that import llm_client).
urllib.request.install_opener(urllib.request.build_opener(_HTTP308RedirectHandler))


# ---------------------------------------------------------------------------
# Some local gateways append SSE streaming artifacts (``data: [DONE]``) to
# the response body even when streaming is not requested.  Strip trailing
# SSE tokens before JSON parsing so these endpoints work transparently.
# ---------------------------------------------------------------------------
_STREAMING_ARTIFACT_RE = re.compile(r'[\n\r]*data:\s*\[DONE\]\s*$', re.MULTILINE)


def _strip_streaming_artifacts(raw: str) -> str:
    """Remove trailing SSE streaming tokens (``data: [DONE]`` etc)."""
    return _STREAMING_ARTIFACT_RE.sub('', raw.strip()).strip()


def _load_env_file(path: Path = CRON_ENV_PATH) -> dict[str, str]:
    """Load a simple KEY=VALUE env file if it exists."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    try:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    except Exception as ex:
        log.warning(f"Failed to load {path}: {ex}")
    return values


_ENV_FILE_VALUES = _load_env_file()


def _env_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    for name in names:
        value = _ENV_FILE_VALUES.get(name)
        if value:
            return value
    return default


# Defaults from environment or _system/config/cron.env
DEFAULT_BASE_URL = _env_value("OPENPAI_BASE_URL", "LLM_API_BASE", default="https://llm.datasolved.org/v1")
DEFAULT_API_KEY = _env_value("OPENPAI_API_KEY", "LLM_API_KEY", default="")
DEFAULT_TIMEOUT_SECONDS = int(_env_value("LLM_REQUEST_TIMEOUT_SECONDS", default="90"))
DEFAULT_REQUEST_RETRIES = int(_env_value("LLM_REQUEST_RETRIES", default="2"))
DEFAULT_BACKOFF_SECONDS = float(_env_value("LLM_RETRY_BACKOFF_SECONDS", default="1.5"))
DEFAULT_SKIP_MODELS_PREFLIGHT = _env_value("LLM_SKIP_MODELS_PREFLIGHT", default="0") in {"1", "true", "True", "yes", "on"}
_MODELS_PREFLIGHT_SUPPORTED: bool | None = None
_MODELS_PREFLIGHT_FAILED_ONCE = False

# Some providers expose canonical model names under different aliases. Keep this
# mapping conservative and easy to override via LLM_MODEL_ALIAS_MAP_JSON.

# Known alias normalizations. Keep these conservative: only map variants that
# are known to behave like the same model on compatible providers.
DEFAULT_MODEL_ALIASES = {
    "openai/gpt-5.4": "gpt-5.4",
    "openai/gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.4-preview": "gpt-5.4",
    "gpt-5.4-mini-preview": "gpt-5.4-mini",
    "google/gemini-2.5-flash": "gemini-2.5-flash-lite",
    "google/gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "google/gemini-3-flash-preview": "gemini-3-flash-preview",
    "google/gemini-3.1-flash-lite-preview": "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash-lite-preview": "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
    "deepseek/deepseek-v4-pro": "deepseek-ai/deepseek-v4-pro",
    "mistral/mistral-large-latest": "mistral/mistral-large-latest",
    "mistralai/mistral-large": "mistral/mistral-large-latest",
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


def _should_skip_models_preflight(base_url: str | None = None) -> bool:
    """Return True when /models should not be probed for this endpoint."""
    if DEFAULT_SKIP_MODELS_PREFLIGHT:
        return True
    if _env_value("LLM_SKIP_MODELS_PREFLIGHT", default="0") in {"1", "true", "True", "yes", "on"}:
        return True
    return _env_value("LLM_DISABLE_MODELS_PREFLIGHT", default="0") in {"1", "true", "True", "yes", "on"}


def _probe_models_endpoint(base_url: str, api_key: str, timeout: int) -> bool:
    """Return True if /models appears to be supported for this endpoint."""
    global _MODELS_PREFLIGHT_SUPPORTED, _MODELS_PREFLIGHT_FAILED_ONCE

    if _MODELS_PREFLIGHT_SUPPORTED is False:
        return False
    if _MODELS_PREFLIGHT_SUPPORTED is True:
        return True
    if _should_skip_models_preflight(base_url):
        _MODELS_PREFLIGHT_SUPPORTED = False
        return False
    if _MODELS_PREFLIGHT_FAILED_ONCE:
        return False

    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    req = urllib.request.Request(url, headers=headers)
    try:
        with _urlopen_with_retry(req, timeout=timeout, retries=1) as resp:
            resp.read()
        _MODELS_PREFLIGHT_SUPPORTED = True
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info("/models preflight not supported by this endpoint; disabling future probes")
            _MODELS_PREFLIGHT_SUPPORTED = False
            _MODELS_PREFLIGHT_FAILED_ONCE = True
            return False
        raise
    except Exception:
        _MODELS_PREFLIGHT_FAILED_ONCE = True
        return False


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

    # Avoid /models probing on endpoints that don't support it.
    _probe_models_endpoint(base_url, api_key, min(10, timeout))

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
                raw_body = resp.read().decode()
            # Strip trailing SSE streaming artifacts (local gateways)
            raw_body = _strip_streaming_artifacts(raw_body)
            data = json.loads(raw_body)

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
