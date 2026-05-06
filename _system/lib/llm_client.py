"""OpenAI-compatible LLM client using the Datasolved endpoint."""

import json
import os
import logging
import urllib.request
import urllib.error
from pathlib import Path

log = logging.getLogger("llm_client")

# Defaults from environment
DEFAULT_BASE_URL = os.environ.get("OPENPAI_BASE_URL", "https://llm.datasolved.org/v1")
DEFAULT_API_KEY = os.environ.get("OPENPAI_API_KEY", "")


def call_llm(
    messages: list[dict],
    model: str = "gpt-5.4",
    temperature: float = 0.1,
    max_tokens: int = 8000,
    base_url: str = None,
    api_key: str = None,
    response_format: dict = None,
) -> dict:
    """Call the OpenAI-compatible chat completions API.
    
    Returns: {"content": str, "usage": dict, "model": str}
    """
    base_url = base_url or DEFAULT_BASE_URL
    api_key = api_key or DEFAULT_API_KEY
    
    url = f"{base_url}/chat/completions"
    
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    
    log.info(f"Calling {model} ({len(json.dumps(body))} bytes input)")
    
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        log.info(f"  → {len(content)} chars, usage: {usage}")
        
        return {
            "content": content,
            "usage": usage,
            "model": data.get("model", model),
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        log.error(f"  → HTTP {e.code}: {e.reason} | {body[:500]}")
        raise
    except Exception as e:
        log.error(f"  → Error: {e}")
        raise


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
