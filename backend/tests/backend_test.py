"""Backend API tests for AI Harness Chat.

Covers:
- GET /api/models, /api/config
- Chats CRUD + listing
- POST /api/chat/stream SSE (AUTO, manual, web, rag)
- Documents upload + list
- Stats
"""
import io
import json
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://rag-verify-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Long timeouts because pipeline runs multiple LLM calls
STREAM_TIMEOUT = 300


def _read_sse(resp):
    """Yield parsed JSON events from an SSE response."""
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("data:"):
            try:
                yield json.loads(raw[5:].strip())
            except Exception:
                continue


def _run_stream(payload):
    """POST /api/chat/stream and collect all events."""
    events = []
    with requests.post(f"{API}/chat/stream", json=payload, stream=True, timeout=STREAM_TIMEOUT) as r:
        assert r.status_code == 200, f"stream status {r.status_code}: {r.text[:300]}"
        for ev in _read_sse(r):
            events.append(ev)
            if ev.get("type") == "done" or ev.get("type") == "error":
                break
    return events


# ---------------- Basic ----------------
class TestBasic:
    def test_models(self):
        r = requests.get(f"{API}/models", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) > 0
        assert all(isinstance(m, str) for m in data["models"])

    def test_config(self):
        r = requests.get(f"{API}/config", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "model_roles" in data and isinstance(data["model_roles"], dict)
        assert "category_to_role" in data and isinstance(data["category_to_role"], dict)
        assert len(data["model_roles"]) > 0
        assert len(data["category_to_role"]) > 0


# ---------------- Chats ----------------
@pytest.fixture(scope="module")
def chat_id():
    r = requests.post(f"{API}/chats", json={"title": "TEST_pytest_chat"}, timeout=15)
    assert r.status_code == 200
    cid = r.json()["id"]
    yield cid
    # cleanup
    requests.delete(f"{API}/chats/{cid}", timeout=15)


class TestChats:
    def test_create_and_list(self, chat_id):
        r = requests.get(f"{API}/chats", timeout=15)
        assert r.status_code == 200
        chats = r.json()
        ids = [c["id"] for c in chats]
        assert chat_id in ids

    def test_messages_empty(self, chat_id):
        r = requests.get(f"{API}/chats/{chat_id}/messages", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Streaming (AUTO simple) ----------------
class TestStreamAuto:
    def test_auto_simple(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "What is 2 + 2? Answer briefly.",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
        }
        events = _run_stream(payload)
        types = [e["type"] for e in events]
        assert "status" in types, f"no status events. got: {types[:15]}"
        assert "meta" in types
        assert any(t == "token" for t in types), "no tokens streamed"
        done = [e for e in events if e["type"] == "done"]
        assert done, f"no done event. types={types}"
        d = done[0]
        assert d["content"], "empty final content"
        assert d["model"], "no model reported"
        assert "category" in d
        assert "confidence" in d
        assert "verify_status" in d
        assert d["used_rag"] is False
        assert d["used_web"] is False

        # Verify persistence
        time.sleep(1)
        m = requests.get(f"{API}/chats/{chat_id}/messages", timeout=15).json()
        assert any(x["role"] == "assistant" for x in m)
        asst = [x for x in m if x["role"] == "assistant"][-1]
        assert "meta" in asst and asst["meta"]["model"]


# ---------------- Manual mode ----------------
class TestManualMode:
    def test_manual_model_selection(self, chat_id):
        models = requests.get(f"{API}/models", timeout=15).json()["models"]
        # pick a known-general model
        target = "gpt-oss:20b" if "gpt-oss:20b" in models else models[0]
        payload = {
            "chat_id": chat_id,
            "message": "Say hi in one word.",
            "mode": "manual",
            "manual_model": target,
            "use_rag": False,
            "use_web": False,
        }
        events = _run_stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done
        assert done[0]["model"] == target, f"expected {target} got {done[0]['model']}"


# ---------------- Web verification ----------------
class TestWebSearch:
    def test_use_web(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "What is the capital of France?",
            "mode": "auto",
            "use_rag": False,
            "use_web": True,
        }
        events = _run_stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        # Answer must be produced even if DuckDuckGo rate-limited
        assert d["content"]
        # If web sources are present, verify structure
        if d.get("used_web"):
            web_sources = [s for s in d.get("sources", []) if s.get("type") == "web"]
            assert web_sources, "used_web true but no web sources"
            assert any(s.get("url") for s in web_sources)


# ---------------- Documents + RAG ----------------
@pytest.fixture(scope="module")
def uploaded_doc(chat_id):
    text = (
        "TEST_SECRET_MARKER: The office WiFi password for Project Zephyr is 'BluePenguin42'. "
        "This document is only for internal use by TEST_pytest suite."
    )
    files = {"file": ("test_zephyr.txt", io.BytesIO(text.encode()), "text/plain")}
    data = {"chat_id": chat_id}
    r = requests.post(f"{API}/documents", files=files, data=data, timeout=30)
    assert r.status_code == 200, r.text
    doc = r.json()
    yield doc
    requests.delete(f"{API}/documents/{doc['id']}", timeout=15)


class TestDocumentsAndRAG:
    def test_upload_and_list(self, chat_id, uploaded_doc):
        r = requests.get(f"{API}/documents", params={"chat_id": chat_id}, timeout=15)
        assert r.status_code == 200
        docs = r.json()
        assert any(d["id"] == uploaded_doc["id"] for d in docs)
        assert uploaded_doc["num_chunks"] >= 1

    def test_rag_answer(self, chat_id, uploaded_doc):
        payload = {
            "chat_id": chat_id,
            "message": "What is the WiFi password for Project Zephyr according to the uploaded doc?",
            "mode": "auto",
            "use_rag": True,
            "use_web": False,
        }
        events = _run_stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d["used_rag"] is True, f"used_rag not true, sources={d.get('sources')}"
        doc_sources = [s for s in d.get("sources", []) if s.get("type") in ("doc", "document")]
        assert doc_sources, f"no doc sources: {d.get('sources')}"
        # Answer should mention the secret marker password
        assert "BluePenguin42" in d["content"] or "bluepenguin42" in d["content"].lower(), \
            f"answer did not reference document content: {d['content'][:300]}"


# ---------------- Iteration 3: Independent validator + full catalog ----------------
class TestModelsCatalog:
    def test_models_full_catalog(self):
        r = requests.get(f"{API}/models", timeout=30)
        assert r.status_code == 200
        models = r.json()["models"]
        # Expect a large catalog (~34 models) with well-known variants
        assert len(models) >= 20, f"expected many models, got {len(models)}: {models}"
        # A few representative models that should appear
        for expected in ["gpt-oss:20b", "gpt-oss:120b", "qwen3-coder:480b"]:
            assert expected in models, f"missing expected model {expected} in catalog"


class TestIndependentValidator:
    def test_validator_model_present_and_differs(self, chat_id):
        payload = {
            "chat_id": chat_id,
            "message": "Why is the sky blue? Explain step by step.",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
        }
        events = _run_stream(payload)
        types = [e["type"] for e in events]
        done = [e for e in events if e["type"] == "done"]
        assert done, f"no done event; types={types}"
        d = done[0]
        assert d["content"], "empty answer"
        assert "validator_model" in d, f"no validator_model key in done: {d.keys()}"
        vm = d["validator_model"]
        # For reasoning category deep validation must run -> real model (not 'heuristic')
        assert vm and vm != "heuristic", f"expected real validator model, got {vm!r}"
        assert vm != d["model"], f"validator {vm} must differ from drafting model {d['model']} (cross-model)"
        # confidence + verify_status
        assert "verify_status" in d
        assert "confidence" in d

        # A validate status message that references the validator model should appear
        statuses = [e for e in events if e["type"] == "status" and e.get("stage") == "validate"]
        assert statuses, "no validate status stage emitted"
        assert any(vm in (s.get("message") or "") for s in statuses), \
            f"validate status did not reference validator model {vm}: {[s.get('message') for s in statuses]}"

    def test_general_chat_heuristic_validator(self, chat_id):
        """Simple greeting -> fast route, no deep validation -> validator_model=='heuristic'."""
        payload = {
            "chat_id": chat_id,
            "message": "hi there!",
            "mode": "auto",
            "use_rag": False,
            "use_web": False,
        }
        events = _run_stream(payload)
        done = [e for e in events if e["type"] == "done"]
        assert done
        d = done[0]
        assert d["content"]
        # heuristic is expected for plain general chat with no evidence
        assert d.get("validator_model") in ("heuristic",), \
            f"expected heuristic validator for general chat, got {d.get('validator_model')}"

    def test_persisted_validator_model(self, chat_id):
        """After the reasoning stream above, the assistant message meta must persist validator_model."""
        msgs = requests.get(f"{API}/chats/{chat_id}/messages", timeout=15).json()
        asst = [m for m in msgs if m["role"] == "assistant"]
        assert asst
        # find one with a real (non-heuristic) validator_model
        real = [m for m in asst if (m.get("meta") or {}).get("validator_model") not in (None, "heuristic")]
        assert real, "no persisted assistant message with an independent validator_model"
        m = real[-1]
        assert m["meta"]["validator_model"] != m["meta"]["model"]


# ---------------- Iteration 5: INTELLIGENT LLM-based diverse routing ----------------
class TestIntelligentDiverseRouting:
    """Verify LLM-based classification routes 5 varied prompts to DIVERSE, sensible models.
    Requirement: >=4 distinct models across the 5 prompts; categories are sensible
    (coding-y prompts route to coding/reasoning role, haiku to creative, etc.);
    never a single-model collapse.
    """

    # (prompt, list of acceptable role labels)
    PROMPTS = [
        ("hey there", {"fast", "general"}),
        ("Write a python bubble sort", {"coding"}),
        ("Give me a short bedtime story about a robot", {"creative"}),
        ("Why is the sky blue? Explain step by step.", {"reasoning", "technical"}),
        ("How do I center a div in CSS?", {"coding", "technical"}),
    ]

    def test_intelligent_diverse_routing(self):
        results = []
        for prompt, acceptable_roles in self.PROMPTS:
            cr = requests.post(f"{API}/chats", json={"title": f"TEST_iroute_{prompt[:20]}"}, timeout=15)
            assert cr.status_code == 200
            cid = cr.json()["id"]
            try:
                payload = {
                    "chat_id": cid, "message": prompt, "mode": "auto",
                    "use_rag": False, "use_web": False,
                }
                events = _run_stream(payload)
                done = [e for e in events if e["type"] == "done"]
                err = [e for e in events if e["type"] == "error"]
                assert not err, f"[{prompt!r}] pipeline error: {err}"
                assert done, f"[{prompt!r}] no done event; types={[e['type'] for e in events]}"
                d = done[0]
                results.append({
                    "prompt": prompt,
                    "acceptable_roles": acceptable_roles,
                    "category": d.get("category"),
                    "model": d.get("model"),
                    "role": d.get("role"),
                    "validator_model": d.get("validator_model"),
                    "content_len": len(d.get("content") or ""),
                })
                assert d.get("content"), f"[{prompt!r}] empty content"
                assert d.get("model"), f"[{prompt!r}] no model reported"
            finally:
                requests.delete(f"{API}/chats/{cid}", timeout=15)

        print("\nIntelligent routing results:")
        for r in results:
            print(f"  prompt={r['prompt']!r:60s} -> category={r['category']!s:24s} role={r['role']!s:14s} model={r['model']!s:22s} validator={r['validator_model']}")

        # 1. Diversity: at least 4 of 5 must use DISTINCT models
        used_models = [r["model"] for r in results]
        distinct = set(used_models)
        assert len(distinct) >= 4, \
            f"routing collapsed - only {len(distinct)} distinct models across 5 prompts: {used_models}"

        # 2. Sensible role for each prompt (LLM classifier can pick from an acceptable set)
        for r in results:
            assert r["role"] in r["acceptable_roles"], (
                f"prompt {r['prompt']!r} classified to role={r['role']} "
                f"(model={r['model']}); expected one of {r['acceptable_roles']}"
            )

        # 3. Bedtime story must be creative
        story = next(r for r in results if "bedtime" in r["prompt"].lower())
        assert story["role"] == "creative", f"bedtime story not routed to creative role: {story}"

        # 4. At least one coding-flavoured prompt actually gets the coding role
        coding_ones = [r for r in results if r["role"] == "coding"]
        assert coding_ones, f"no coding prompt routed to coding role: {results}"


# ---------------- Stats ----------------
class TestStats:
    def test_stats(self):
        r = requests.get(f"{API}/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "total_runs" in data
        assert "by_model" in data
        assert isinstance(data["by_model"], dict)
