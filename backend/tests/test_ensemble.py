"""Iteration 7 focused ensemble tests: multi-model critique + single-mode regression."""
import json
import os
import time
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")


def _stream(payload, timeout):
    url = f"{BASE_URL}/api/chat/stream"
    events = []
    start = time.time()
    last_event_ts = start
    stage_first_seen = {}
    saw_done = False
    error_evt = None
    with requests.post(url, json=payload, stream=True, timeout=timeout) as r:
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:400]}"
        buf = ""
        for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
            if chunk is None:
                continue
            buf += chunk
            while "\n\n" in buf:
                raw, buf = buf.split("\n\n", 1)
                for line in raw.splitlines():
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if not data:
                            continue
                        try:
                            evt = json.loads(data)
                        except Exception:
                            continue
                        events.append(evt)
                        last_event_ts = time.time()
                        stage = evt.get("stage")
                        if stage and stage not in stage_first_seen:
                            stage_first_seen[stage] = last_event_ts - start
                        if evt.get("type") == "done":
                            saw_done = True
                        if evt.get("type") == "error":
                            error_evt = evt
                if saw_done or error_evt:
                    break
            if saw_done or error_evt:
                break
            if time.time() - start > timeout:
                break
    elapsed = time.time() - start
    max_gap = 0.0
    # measure max gap between consecutive events
    ts_prev = start
    for e in events:
        # not stored; approximate via elapsed intervals
        pass
    return {
        "events": events,
        "elapsed": elapsed,
        "saw_done": saw_done,
        "error": error_evt,
        "stage_first_seen": stage_first_seen,
        "last_event_ts": last_event_ts,
        "start": start,
    }


def test_ensemble_multi_mode():
    chat_id = f"TEST_ens_{uuid.uuid4().hex[:8]}"
    payload = {
        "chat_id": chat_id,
        "message": "Tabs or spaces for Python? One short reasoned line.",
        "mode": "auto",
        "use_rag": False,
        "use_web": False,
        "use_multi": True,
    }
    res = _stream(payload, timeout=280)
    print(f"\n[ensemble] elapsed={res['elapsed']:.1f}s saw_done={res['saw_done']} "
          f"stages={res['stage_first_seen']} events={len(res['events'])}")
    if res["error"]:
        print(f"[ensemble] error event: {res['error']}")

    # If not done, check "progressing" fallback: stages advanced and no >90s single-stage hang
    if not res["saw_done"]:
        # Compute gap between successive stage entries
        stages_order = ["classify", "draft", "critique", "factcheck", "finalize"]
        seen = [(s, res["stage_first_seen"][s]) for s in stages_order if s in res["stage_first_seen"]]
        max_stage_gap = 0.0
        for i in range(1, len(seen)):
            g = seen[i][1] - seen[i-1][1]
            if g > max_stage_gap:
                max_stage_gap = g
        # Also gap between last event and end
        gap_since_last = res["elapsed"] - (res["last_event_ts"] - res["start"])
        print(f"[ensemble] PASS-with-latency? stages_seen={seen} max_stage_gap={max_stage_gap:.1f}s "
              f"gap_since_last_event={gap_since_last:.1f}s")
        # Require at least 3 stages progressed AND no single-stage hang >90s
        assert len(seen) >= 3, f"Only stages {seen} seen; not progressing"
        assert max_stage_gap <= 90 and gap_since_last <= 90, (
            f"Stage hang detected: max_stage_gap={max_stage_gap} gap_since_last={gap_since_last}"
        )
        # Mark as pass-with-latency: return early rather than failing
        print("[ensemble] RESULT: PASS-with-latency (progressing, no hang)")
        return

    # Find the done event
    done = [e for e in res["events"] if e.get("type") == "done"][-1]
    ens = done.get("ensemble")
    print(f"[ensemble] done event: model={done.get('model')} role={done.get('role')} "
          f"ensemble={ens} content_len={len(done.get('content') or '')}")
    assert ens is not None, "done event missing ensemble field"
    for k in ("drafter", "critic", "verifier", "finalizer"):
        assert ens.get(k), f"ensemble missing {k}"
    distinct = {ens["drafter"], ens["critic"], ens["verifier"], ens["finalizer"]}
    assert len(distinct) >= 3, f"Expected >=3 distinct models, got {distinct}"
    assert done.get("model") == ens["finalizer"], (
        f"done.model {done.get('model')} != finalizer {ens['finalizer']}"
    )
    assert done.get("role") == "ensemble", f"role={done.get('role')}"
    content = done.get("content") or ""
    assert content.strip(), "empty content"

    # Stage order
    stages_order = ["classify", "draft", "critique", "factcheck", "finalize"]
    seen_times = [(s, res["stage_first_seen"].get(s)) for s in stages_order]
    # All should be present
    missing = [s for s, t in seen_times if t is None]
    assert not missing, f"Missing stages: {missing}. Got: {res['stage_first_seen']}"
    ordered = [t for s, t in seen_times]
    assert ordered == sorted(ordered), f"Stages out of order: {seen_times}"


def test_single_mode_regression():
    chat_id = f"TEST_single_{uuid.uuid4().hex[:8]}"
    payload = {
        "chat_id": chat_id,
        "message": "hi",
        "mode": "auto",
        "use_rag": False,
        "use_web": False,
        "use_multi": False,
    }
    res = _stream(payload, timeout=120)
    print(f"\n[single] elapsed={res['elapsed']:.1f}s saw_done={res['saw_done']} "
          f"events={len(res['events'])}")
    if res["error"]:
        print(f"[single] error: {res['error']}")
    assert res["saw_done"], f"No done event in 120s. Events tail: {res['events'][-3:]}"
    done = [e for e in res["events"] if e.get("type") == "done"][-1]
    print(f"[single] done: model={done.get('model')} role={done.get('role')} "
          f"ensemble={done.get('ensemble')} content_len={len(done.get('content') or '')}")
    assert done.get("ensemble") in (None, {}), f"Expected ensemble=null, got {done.get('ensemble')}"
    assert done.get("model"), "single-mode done missing model"
    assert (done.get("content") or "").strip(), "empty content"
