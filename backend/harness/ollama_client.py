"""Thin async wrapper around the Ollama Cloud API.

Reliability features:
- Global semaphore serialises requests (the API key rate-limits concurrent calls).
- Automatic retry with backoff on transient errors (429 rate-limit, 403, 5xx, timeouts).
- Streaming does not retry after tokens are produced (avoids duplicate output).
"""
import os
import json
import time
import asyncio
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.environ["OLLAMA_API_KEY"]
HEADERS = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}

# Serialise all calls on this key to avoid "too many concurrent requests".
_SEM = asyncio.Semaphore(1)
RETRY_STATUS = {429, 403, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


class ModelUnavailable(Exception):
    pass


async def list_models():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{OLLAMA_HOST}/api/tags", headers=HEADERS)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


_MODELS_CACHE = {"ts": 0.0, "models": []}


async def get_available_models(ttl=300):
    """Cached list of ALL available Ollama cloud models."""
    now = time.time()
    if _MODELS_CACHE["models"] and (now - _MODELS_CACHE["ts"] < ttl):
        return _MODELS_CACHE["models"]
    try:
        models = await list_models()
        if models:
            _MODELS_CACHE["models"] = models
            _MODELS_CACHE["ts"] = now
    except Exception as e:  # noqa: BLE001
        logger.warning(f"get_available_models failed: {e}")
    return _MODELS_CACHE["models"]


async def chat(model, messages, options=None, timeout=150):
    """Non-streaming chat completion with retry. Raises ModelUnavailable on failure."""
    payload = {"model": model, "messages": messages, "stream": False}
    if options:
        payload["options"] = options
    async with _SEM:
        for attempt in range(MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=timeout) as c:
                    r = await c.post(f"{OLLAMA_HOST}/api/chat", headers=HEADERS, json=payload)
                if r.status_code == 200:
                    return r.json().get("message", {}).get("content", "")
                if r.status_code in RETRY_STATUS:
                    logger.warning(f"chat {model} status {r.status_code}: {r.text[:120]} (attempt {attempt+1})")
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise ModelUnavailable(f"{model} returned {r.status_code}: {r.text[:120]}")
            except (httpx.TimeoutException, httpx.TransportError) as e:
                logger.warning(f"chat {model} transport error {e} (attempt {attempt+1})")
                await asyncio.sleep(2 * (attempt + 1))
        raise ModelUnavailable(f"{model} unavailable after {MAX_ATTEMPTS} attempts")


async def chat_stream(model, messages, options=None):
    """Streaming chat. Retries only before the first token is produced.
    Raises ModelUnavailable if it never produces output."""
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    async with _SEM:
        last_err = None
        for attempt in range(MAX_ATTEMPTS):
            produced = False
            try:
                async with httpx.AsyncClient(timeout=None) as c:
                    async with c.stream("POST", f"{OLLAMA_HOST}/api/chat", headers=HEADERS, json=payload) as r:
                        if r.status_code != 200:
                            body = (await r.aread()).decode("utf-8", errors="ignore")
                            if r.status_code in RETRY_STATUS:
                                last_err = ModelUnavailable(f"{model} {r.status_code}: {body[:120]}")
                                logger.warning(f"stream {model} {r.status_code}: {body[:120]} (attempt {attempt+1})")
                                await asyncio.sleep(2 * (attempt + 1))
                                continue
                            raise ModelUnavailable(f"{model} returned {r.status_code}: {body[:120]}")
                        async for line in r.aiter_lines():
                            if not line or not line.strip():
                                continue
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            piece = data.get("message", {}).get("content", "")
                            if piece:
                                produced = True
                                yield piece
                            if data.get("done"):
                                return
                        return
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_err = e
                if produced:
                    raise ModelUnavailable(f"{model} interrupted mid-stream: {e}")
                logger.warning(f"stream {model} transport error {e} (attempt {attempt+1})")
                await asyncio.sleep(2 * (attempt + 1))
        raise ModelUnavailable(f"{model} unavailable after {MAX_ATTEMPTS} attempts: {last_err}")


def _extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return None


async def chat_json(model, messages, options=None):
    content = await chat(model, messages, options=options)
    return _extract_json(content) or {}
