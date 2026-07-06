"""Thin async wrapper around the Ollama Cloud API."""
import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "https://ollama.com")
OLLAMA_API_KEY = os.environ["OLLAMA_API_KEY"]
HEADERS = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}


async def list_models():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{OLLAMA_HOST}/api/tags", headers=HEADERS)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


async def chat(model, messages, options=None, timeout=240):
    """Non-streaming chat completion. Returns the assistant content string."""
    payload = {"model": model, "messages": messages, "stream": False}
    if options:
        payload["options"] = options
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(f"{OLLAMA_HOST}/api/chat", headers=HEADERS, json=payload)
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")


async def chat_stream(model, messages, options=None):
    """Async generator yielding content token chunks."""
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    async with httpx.AsyncClient(timeout=None) as c:
        async with c.stream("POST", f"{OLLAMA_HOST}/api/chat", headers=HEADERS, json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break


def _extract_json(text):
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text else text
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
    """Chat that expects and parses a JSON object response."""
    content = await chat(model, messages, options=options)
    return _extract_json(content) or {}
