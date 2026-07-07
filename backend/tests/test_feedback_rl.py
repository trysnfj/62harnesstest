"""Iteration 10 tests: date-bug fix + feedback + RL learned_routes."""
import json
import os
import re
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

STREAM_TIMEOUT = 90
ENSEMBLE_TIMEOUT = 200


def _stream(payload, timeout=STREAM_TIMEOUT):
    events = []
    with requests.post(f"{API}/chat/stream", json=payload, stream=True, timeout=timeout) as r:
        assert r.status_code == 200, f"stream {r.status_code}: {r.text[:200]}"
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            try:
                ev = json.loads(raw[5:].strip())
            except Exception:
                continue
            events.append(ev)
            if ev.get("type") in ("done", "error"):
                break
    return events


@pytest.fixture(scope="module")
def chat_id():
    r = requests.post(f"{API}/chats", json={"title": "TEST_iter10"}, timeout=15)
    assert r.status_code == 200
    cid = r.json()["id"]
    yield cid
    requests.delete(f"{API}/chats/{cid}", timeout=15)


class TestDateBugFix:
    def test_date_answer_no_refusal(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "What is today's date?",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
        }
        events = _stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done, f"no done event, types={[e['type'] for e in events]}"
        d = done[0]
        content = d.get("content", "")
        assert content, "empty content"
        print(f"\n[date] answer: {content[:300]}")

        # Must NOT refuse
        refusal_phrases = [
            "don't have real-time",
            "do not have real-time",
            "cannot provide a verified date",
            "no access to a clock",
            "don't have access to a clock",
        ]
        low = content.lower()
        for p in refusal_phrases:
            assert p not in low, f"model refused with phrase: {p!r} in {content!r}"

        # Must contain 2026 year
        assert "2026" in content, f"answer missing year 2026: {content!r}"

        # message_id must be present in done event
        assert d.get("message_id"), f"done event missing message_id: {d}"


class TestFeedback:
    @pytest.fixture(scope="class")
    def message_id(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "What is today's date?",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
        }
        events = _stream(payload)
        done = [e for e in events if e["type"] == "done"][0]
        mid = done.get("message_id")
        assert mid, "no message_id in done"
        return mid

    def test_feedback_up(self, message_id):
        r = requests.post(f"{API}/feedback", json={"message_id": message_id, "rating": "up"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_feedback_down(self, message_id):
        r = requests.post(f"{API}/feedback", json={"message_id": message_id, "rating": "down"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_feedback_invalid_rating(self, message_id):
        r = requests.post(f"{API}/feedback", json={"message_id": message_id, "rating": "meh"}, timeout=15)
        assert r.status_code == 400, f"expected 400 for invalid rating, got {r.status_code}: {r.text}"


class TestStatsLearnedRoutes:
    def test_stats_shape(self):
        r = requests.get(f"{API}/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "total_runs" in data
        assert "by_model" in data and isinstance(data["by_model"], dict)
        assert "learned_routes" in data and isinstance(data["learned_routes"], dict)
        # by_model entries structure
        for m, s in data["by_model"].items():
            for k in ("runs", "avg_confidence", "repairs", "up", "down"):
                assert k in s, f"by_model[{m}] missing {k}: {s}"

    def test_up_reflected_in_by_model(self, chat_id):
        # do a fresh short prompt, get message_id, submit up, check by_model up incremented
        payload = {"chat_id": chat_id, "message": "hi", "mode": "auto", "use_rag": False, "use_web": False}
        events = _stream(payload)
        done = [e for e in events if e["type"] == "done"][0]
        mid = done["message_id"]
        model = done["model"]

        before = requests.get(f"{API}/stats", timeout=15).json()
        before_up = before["by_model"].get(model, {}).get("up", 0)

        r = requests.post(f"{API}/feedback", json={"message_id": mid, "rating": "up"}, timeout=15)
        assert r.status_code == 200

        time.sleep(0.5)
        after = requests.get(f"{API}/stats", timeout=15).json()
        after_up = after["by_model"].get(model, {}).get("up", 0)
        assert after_up == before_up + 1, f"up count for {model}: {before_up} -> {after_up}"


class TestRegressions:
    def test_coding_prompt_completes(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "Write a python bubble sort in 3 lines.",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
            "use_multi": False,
        }
        events = _stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d["content"]
        role = d["role"] or ""
        assert any(x in role for x in ("coding", "technical", "reasoning")), \
            f"unexpected role for coding prompt: {role}"
        assert d.get("message_id")

    def test_simple_hi_completes(self, chat_id):
        payload = {"chat_id": chat_id, "message": "hi", "mode": "auto", "use_rag": False, "use_web": False}
        events = _stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done and done[0]["content"]

    def test_ensemble_still_works(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "Tabs or spaces? One line.",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
            "use_multi": True,
        }
        events = _stream(payload, timeout=ENSEMBLE_TIMEOUT)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d.get("ensemble") and isinstance(d["ensemble"], dict)
        for k in ("drafter", "critic", "verifier", "finalizer"):
            assert d["ensemble"].get(k)
