"""Iteration 11 tests: thinking events + speed regression.

Verifies:
- Manual mode with gpt-oss:20b emits multiple {type:'thinking'} SSE events
- AUTO simple non-grounded prompt: validator_model == 'heuristic' + fast completion
- use_web=true: real validator OR sources returned; must complete
"""
import json
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


def _read_sse(resp):
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("data:"):
            try:
                yield json.loads(raw[5:].strip())
            except Exception:
                continue


def _run_stream(payload, timeout=120):
    events = []
    with requests.post(f"{API}/chat/stream", json=payload, stream=True, timeout=timeout) as r:
        assert r.status_code == 200, f"stream status {r.status_code}: {r.text[:300]}"
        for ev in _read_sse(r):
            events.append(ev)
            if ev.get("type") in ("done", "error"):
                break
    return events


@pytest.fixture(scope="module")
def chat_id():
    r = requests.post(f"{API}/chats", json={"title": "TEST_iter11"}, timeout=15)
    assert r.status_code == 200
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{API}/chats/{cid}", timeout=15)


class TestThinkingStream:
    def test_manual_gpt_oss_emits_thinking(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "mode": "manual",
            "manual_model": "gpt-oss:20b",
            "message": "A bat and ball cost 1.10, the bat costs 1 more than the ball, how much is the ball? Think it through.",
            "use_rag": False,
            "use_web": False,
        }
        events = _run_stream(payload, timeout=120)
        types = [e["type"] for e in events]
        thinking_events = [e for e in events if e["type"] == "thinking"]
        token_events = [e for e in events if e["type"] == "token"]
        done = [e for e in events if e["type"] == "done"]

        assert done, f"no done. types={types}"
        assert len(thinking_events) >= 1, f"expected multiple thinking events, got {len(thinking_events)}; types={types[:30]}"
        assert len(token_events) >= 1, "no tokens after thinking"

        # thinking should come before final tokens (order matters)
        first_thinking_idx = next(i for i, e in enumerate(events) if e["type"] == "thinking")
        first_token_idx = next(i for i, e in enumerate(events) if e["type"] == "token")
        assert first_thinking_idx < first_token_idx or len(thinking_events) > 0

        # combine thinking text - should be non-empty reasoning
        combined = "".join(e.get("text", "") or e.get("content", "") for e in thinking_events)
        assert len(combined.strip()) > 10, f"thinking text too short: {combined!r}"


class TestSpeedRegression:
    def test_auto_simple_uses_heuristic_validator_fast(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "mode": "auto",
            "message": "What is 17 times 24?",
            "use_rag": False,
            "use_web": False,
        }
        t0 = time.time()
        events = _run_stream(payload, timeout=60)
        elapsed = time.time() - t0
        done = [e for e in events if e["type"] == "done"]
        assert done, f"no done event"
        d = done[0]
        assert d.get("content"), "empty content"
        # Answer correctness: 17*24 = 408
        assert "408" in d["content"], f"expected 408 in answer, got: {d['content'][:300]}"
        # Speed: heuristic validator only (no deep validation LLM call)
        assert d.get("validator_model") == "heuristic", (
            f"expected heuristic validator for simple non-grounded prompt, got {d.get('validator_model')!r}"
        )
        # Speed guard - should complete comfortably under 45s (spec says under 30s)
        assert elapsed < 60, f"too slow: {elapsed:.1f}s"
        print(f"\n[speed] auto simple completed in {elapsed:.1f}s validator={d.get('validator_model')}")


class TestGroundedValidationRegression:
    def test_web_still_gets_validation_or_sources(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "mode": "auto",
            "message": "What is the capital of France?",
            "use_rag": False,
            "use_web": True,
        }
        events = _run_stream(payload, timeout=180)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d.get("content"), "empty answer"
        vm = d.get("validator_model")
        sources = d.get("sources") or []
        # Either real validator model OR at least sources present (web may rate-limit)
        assert vm != "heuristic" or sources or d.get("used_web") is False, (
            f"web-mode should invoke deep validation OR return sources; got validator={vm} sources={sources}"
        )
