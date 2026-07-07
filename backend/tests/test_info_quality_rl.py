"""Iteration 12 — RL over INFORMATION QUALITY (not model routing).

Verifies:
- GET /api/stats returns 'info_quality' + 'escalated' (learned_routes removed).
- Deterministic routing per category (coding vs general).
- POST /api/feedback still works; down increments category down count.
- Escalation mechanism structure exists; a plain done event completes.
- Speed: non-grounded AUTO -> validator_model=='heuristic'.
- Web AUTO still completes (validator real or heuristic if DDG empty).
"""
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://rag-verify-ai.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
STREAM_TIMEOUT = 120


def _read_sse(resp):
    for raw in resp.iter_lines(decode_unicode=True):
        if raw and raw.startswith("data:"):
            try:
                yield json.loads(raw[5:].strip())
            except Exception:
                continue


def _run_stream(payload, timeout=STREAM_TIMEOUT):
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
    r = requests.post(f"{API}/chats", json={"title": "TEST_iter12_rl"}, timeout=15)
    assert r.status_code == 200
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{API}/chats/{cid}", timeout=15)


class TestStatsShape:
    def test_stats_new_fields(self):
        r = requests.get(f"{API}/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        # New RL-over-information fields
        assert "info_quality" in data, f"missing info_quality: keys={list(data.keys())}"
        assert isinstance(data["info_quality"], dict)
        assert "escalated" in data, f"missing escalated: keys={list(data.keys())}"
        assert isinstance(data["escalated"], list)
        # Old field must be gone
        assert "learned_routes" not in data, "learned_routes should be REMOVED"
        # by_model still present
        assert "by_model" in data and isinstance(data["by_model"], dict)
        # info_quality entries have shape
        for cat, d in data["info_quality"].items():
            assert set(["info_quality", "runs", "up", "down"]).issubset(d.keys()), \
                f"info_quality[{cat}] wrong shape: {d}"


class TestDeterministicRouting:
    """Same category should route to same specialist regardless of past feedback."""

    def test_coding_and_general_route_to_distinct_sensible_models(self, chat_id):
        # coding prompt
        coding_events = _run_stream({
            "chat_id": chat_id,
            "message": "Write a python function to add two numbers.",
            "mode": "auto", "use_rag": False, "use_web": False,
        })
        cdone = [e for e in coding_events if e["type"] == "done"]
        assert cdone
        cd = cdone[0]
        assert cd["role"] in ("coding", "technical", "reasoning"), \
            f"coding prompt got role={cd['role']}, model={cd['model']}"

        # general/simple prompt
        gen_events = _run_stream({
            "chat_id": chat_id,
            "message": "hi",
            "mode": "auto", "use_rag": False, "use_web": False,
        })
        gdone = [e for e in gen_events if e["type"] == "done"]
        assert gdone
        gd = gdone[0]
        assert gd["role"] in ("fast", "general"), \
            f"'hi' got role={gd['role']}, model={gd['model']}"

        # Distinct models used for the two very different tasks
        assert cd["model"] != gd["model"], (
            f"coding & general collapsed to same model {cd['model']} — routing may not be category-based"
        )


class TestFeedbackInfoQuality:
    def test_feedback_invalid_rating_400(self):
        r = requests.post(f"{API}/feedback",
                          json={"message_id": "nonexistent", "rating": "meh"},
                          timeout=15)
        assert r.status_code == 400

    def test_feedback_down_increments_category_down(self, chat_id):
        # Fresh AUTO run to get a message_id
        events = _run_stream({
            "chat_id": chat_id,
            "message": "Say a one-word greeting.",
            "mode": "auto", "use_rag": False, "use_web": False,
        })
        done = [e for e in events if e["type"] == "done"]
        assert done, "no done event"
        d = done[0]
        mid = d.get("message_id")
        cat = d.get("category")
        assert mid, f"no message_id in done: {d}"
        assert cat, f"no category in done: {d}"

        # baseline stats
        s0 = requests.get(f"{API}/stats", timeout=15).json()
        base_down = ((s0.get("info_quality") or {}).get(cat) or {}).get("down", 0)

        # 👎
        r = requests.post(f"{API}/feedback",
                          json={"message_id": mid, "rating": "down"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}

        # small delay for mongo write
        time.sleep(0.5)
        s1 = requests.get(f"{API}/stats", timeout=15).json()
        new_down = ((s1.get("info_quality") or {}).get(cat) or {}).get("down", 0)
        assert new_down == base_down + 1, (
            f"down count for '{cat}' did not increment: {base_down} -> {new_down}"
        )


class TestSpeedRegression:
    def test_simple_auto_uses_heuristic_validator(self, chat_id):
        events = _run_stream({
            "chat_id": chat_id,
            "message": "hey!",
            "mode": "auto", "use_rag": False, "use_web": False,
        })
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d.get("validator_model") == "heuristic", \
            f"expected heuristic validator for simple non-grounded prompt, got {d.get('validator_model')}"

    def test_web_prompt_still_runs(self, chat_id):
        events = _run_stream({
            "chat_id": chat_id,
            "message": "What is the capital of France?",
            "mode": "auto", "use_rag": False, "use_web": True,
        }, timeout=180)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d.get("content")
        # If DDG returned evidence, validator should be real (not heuristic)
        if d.get("used_web"):
            assert d.get("validator_model") and d["validator_model"] != d["model"]
