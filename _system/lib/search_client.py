"""Search client using search.datasolved.org DDGS API."""

import json
import time
import logging
from pathlib import Path

import urllib.request
import urllib.parse
import urllib.error

SEARCH_API_BASE = "https://search.datasolved.org"
ENDPOINTS = {
    "text": "/search/text",
    "images": "/search/images",
    "news": "/search/news",
    "videos": "/search/videos",
}

log = logging.getLogger("search_client")

# Install 308 redirect handler (idempotent)

class _SearchHTTP308Handler(urllib.request.HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        if fp:
            fp.read()
            fp.close()
        newurl = headers.get('Location')
        if newurl is None:
            raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)
        newurl = urllib.parse.urljoin(req.full_url, newurl)
        new = urllib.request.Request(
            newurl, data=req.data, headers=req.headers,
            origin_req_host=getattr(req, 'origin_req_host', None),
            unverifiable=True, method=req.get_method(),
        )
        return self.parent.open(new, timeout=req.timeout)

urllib.request.install_opener(urllib.request.build_opener(_SearchHTTP308Handler))


def search_text(query: str, max_results: int = 15, region: str = "bd-bn", **kwargs) -> list[dict]:
    """Search DuckDuckGo via the datasolved API — text results."""
    return _search("text", query, max_results, region, **kwargs)


def search_news(query: str, max_results: int = 10, region: str = "bd-bn", **kwargs) -> list[dict]:
    """Search DuckDuckGo via the datasolved API — news results."""
    return _search("news", query, max_results, region, **kwargs)


def search_images(query: str, max_results: int = 10, region: str = "bd-bn", **kwargs) -> list[dict]:
    """Search DuckDuckGo via the datasolved API — image results."""
    return _search("images", query, max_results, region, **kwargs)


def _search(endpoint: str, query: str, max_results: int, region: str, **kwargs) -> list[dict]:
    """Core search function. Only query-relevant kwargs are forwarded to the API."""
    # Extract timeout from kwargs (used for HTTP timeout) — don't pass to URL params
    http_timeout = kwargs.pop("timeout", 30)
    
    params = {
        "query": query,
        "max_results": max_results,
        "region": region,
    }
    params.update(kwargs)
    
    url = f"{SEARCH_API_BASE}{ENDPOINTS[endpoint]}?{urllib.parse.urlencode(params)}"
    
    log.info(f"Searching: {query!r} ({endpoint})")
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "business-plan-research/1.0"})
        with urllib.request.urlopen(req, timeout=http_timeout) as resp:
            data = json.loads(resp.read().decode())
        
        results = data if isinstance(data, list) else data.get("results", data.get("data", []))
        log.info(f"  → {len(results)} results")
        return results
    except urllib.error.HTTPError as e:
        log.warning(f"  → HTTP {e.code}: {e.reason}")
        return []
    except Exception as e:
        log.warning(f"  → Error: {e}")
        return []


def batch_search(queries: list[str], endpoint: str = "text", max_results: int = 10,
                 delay_seconds: float = 1.0, region: str = "bd-bn") -> dict[str, list[dict]]:
    """Run multiple searches with rate-limit delay. Returns {query: [results]}."""
    results = {}
    for i, q in enumerate(queries):
        if i > 0:
            time.sleep(delay_seconds)
        results[q] = _search(endpoint, q, max_results, region)
    return results


def save_search_results(results: dict, output_path: Path):
    """Save batch search results to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    log.info(f"Saved {len(results)} query results to {output_path}")
