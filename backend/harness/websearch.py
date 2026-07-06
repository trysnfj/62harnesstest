"""Internet Verification Layer using DuckDuckGo (keyless)."""
import asyncio
from ddgs import DDGS


def _search_sync(query: str, max_results: int = 5):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href") or r.get("url", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception:
        return []
    return results


async def search(query: str, max_results: int = 5):
    """Async wrapper - runs the sync DDG client in a thread."""
    return await asyncio.to_thread(_search_sync, query, max_results)
