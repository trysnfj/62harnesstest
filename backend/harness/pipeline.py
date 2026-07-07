"""Self-Repair Loop orchestrator (the harness pipeline).

Resilient by design:
- Heuristic classification (no LLM call).
- Automatic model fallback if the routed model is unavailable (self-correction).
- LLM validation only when the answer is grounded in evidence; otherwise a
  heuristic check. All LLM steps are wrapped so the pipeline always emits 'done'
  (or a clean 'error' if every model is unavailable).

Yields SSE-friendly event dicts:
  {"type": "status", "stage": ..., "message": ...}
  {"type": "meta", ...}          -> routing/classification info (can be re-sent on fallback)
  {"type": "token", "text": ...} -> streamed answer tokens
  {"type": "replace", "text": ...} -> repaired final answer
  {"type": "done", ...}          -> final metadata
  {"type": "error", "message": ...}
"""
import logging
from . import classifier, router, rag, websearch, prompt_compiler, validator, ollama_client
from .config import build_candidates, choose_validator

logger = logging.getLogger(__name__)

_DEEP_VALIDATE_CATEGORIES = {
    "reasoning", "factual/current-events", "research", "document Q&A",
    "legal", "business", "technical explanation",
}


async def run_pipeline(*, user_message, history, mode, manual_model, use_rag, use_web, chunk_docs):
    has_docs = bool(chunk_docs)

    # 1. Classify (intelligent LLM classification, heuristic fallback)
    yield {"type": "status", "stage": "classify", "message": "Understanding & classifying your request..."}
    classification = await classifier.classify(user_message, has_docs=has_docs, web_enabled=use_web)

    # 2. Route
    model, role, route_reason = router.route(
        classification, mode=mode, manual_model=manual_model, use_rag=use_rag, use_web=use_web
    )
    yield {
        "type": "meta", "classification": classification,
        "model": model, "role": role, "route_reason": route_reason,
    }

    # 3. RAG retrieval
    retrieved = []
    if (use_rag or classification.get("needs_rag")) and has_docs:
        yield {"type": "status", "stage": "retrieve", "message": "Retrieving relevant document passages..."}
        retrieved = rag.retrieve(user_message, chunk_docs, top_k=4)

    # 4. Internet verification
    web_evidence = []
    if use_web or classification.get("needs_web"):
        yield {"type": "status", "stage": "search", "message": "Searching the web for verification..."}
        web_evidence = await websearch.search(user_message, max_results=5)

    # 5. Compile prompt
    messages, sources = prompt_compiler.compile_prompt(
        user_message, classification, doc_chunks=retrieved, web_evidence=web_evidence, history=history
    )

    # 6. Generate draft with automatic model fallback (self-correction)
    available = await ollama_client.get_available_models()
    candidates = build_candidates(model, limit=5, available=available) if mode != "manual" else [model]
    draft = ""
    used_model = model
    generated = False
    last_err = None

    for idx, cand in enumerate(candidates):
        if idx > 0:
            yield {"type": "status", "stage": "generate",
                   "message": f"'{candidates[idx-1]}' unavailable — switching to {cand}..."}
            yield {"type": "meta", "classification": classification,
                   "model": cand, "role": role,
                   "route_reason": f"{route_reason} (auto-switched: previous model unavailable)"}
        else:
            yield {"type": "status", "stage": "generate", "message": f"Generating with {cand}..."}

        draft = ""
        produced = False
        try:
            async for tok in ollama_client.chat_stream(cand, messages):
                produced = True
                draft += tok
                yield {"type": "token", "text": tok}
            used_model = cand
            generated = True
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.warning(f"generation failed on {cand}: {e}")
            if produced:  # partial output already streamed — accept it
                used_model = cand
                generated = True
                break
            continue

    if not generated:
        yield {"type": "error",
               "message": "All models are currently rate-limited or unavailable. Please retry in a moment."}
        return

    # 7. Validate with an INDEPENDENT, auto-selected model (cross-model verification)
    citations_required = bool(sources)
    evidence_provided = bool(retrieved or web_evidence)
    deep = (
        evidence_provided
        or classification.get("category") in _DEEP_VALIDATE_CATEGORIES
        or classification.get("reasoning_depth") == "high"
    )
    validator_model = choose_validator(used_model, available)
    validation = None
    if deep:
        yield {"type": "status", "stage": "validate",
               "message": f"Validating with {validator_model} (independent check)..."}
        try:
            validation = await validator.validate(
                user_message, draft, citations_required=citations_required,
                evidence_provided=evidence_provided, model=validator_model,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"validator unavailable, falling back to heuristic: {e}")
            validation = validator.heuristic_validate(draft, citations_required)
            validator_model = "heuristic"
    else:
        validation = validator.heuristic_validate(draft, citations_required)
        validator_model = "heuristic"

    # 8. Self-repair (single pass, best-effort, fully behind the scenes)
    final = draft
    repaired = False
    if validation.get("needs_repair"):
        yield {"type": "status", "stage": "repair", "message": "Answer failed validation — self-correcting..."}
        try:
            final = await validator.repair(used_model, messages, draft, validation)
            repaired = True
            try:
                validation = await validator.validate(
                    user_message, final, citations_required=citations_required,
                    evidence_provided=evidence_provided,
                    model=(validator_model if validator_model != "heuristic" else used_model),
                )
            except Exception:  # noqa: BLE001
                pass
            yield {"type": "replace", "text": final}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"repair unavailable, keeping draft: {e}")
            final = draft

    confidence, verify_status = validator.compute_confidence(validation, bool(retrieved), bool(web_evidence))

    yield {
        "type": "done", "content": final, "model": used_model, "role": role,
        "validator_model": validator_model,
        "category": classification.get("category"), "route_reason": route_reason,
        "used_rag": bool(retrieved), "used_web": bool(web_evidence), "sources": sources,
        "validation": validation, "repaired": repaired,
        "confidence": confidence, "verify_status": verify_status,
    }
