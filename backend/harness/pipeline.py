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
import random
from . import classifier, router, rag, websearch, prompt_compiler, validator, ollama_client, critique
from .config import build_candidates, choose_validator, pick_ensemble

logger = logging.getLogger(__name__)

_DEEP_VALIDATE_CATEGORIES = {
    "reasoning", "factual/current-events", "research", "document Q&A",
    "legal", "business", "technical explanation",
}


async def run_pipeline(*, user_message, history, mode, manual_model, use_rag, use_web, use_multi, chunk_docs, learned_routes=None):
    has_docs = bool(chunk_docs)

    # 1. Classify (intelligent LLM classification, heuristic fallback)
    yield {"type": "status", "stage": "classify", "message": "Understanding & classifying your request..."}
    classification = await classifier.classify(user_message, has_docs=has_docs, web_enabled=use_web)

    # 2. Route (with reinforcement-learned preference + epsilon exploration)
    explore = random.random() < 0.2
    model, role, route_reason = router.route(
        classification, mode=mode, manual_model=manual_model, use_rag=use_rag, use_web=use_web,
        learned_routes=learned_routes, explore=explore,
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
    messages, sources, evidence_text = prompt_compiler.compile_prompt(
        user_message, classification, doc_chunks=retrieved, web_evidence=web_evidence, history=history
    )
    citations_required = bool(sources)
    evidence_provided = bool(retrieved or web_evidence)
    available = await ollama_client.get_available_models()

    # 6. Generate the answer.
    draft = ""
    used_model = model
    ensemble_meta = None

    if use_multi:
        # ---- Multi-model critique ensemble (draft -> critique -> fact-check -> finalize) ----
        drafter, critic_m, verifier_m, finalizer = pick_ensemble(model, available)

        yield {"type": "status", "stage": "draft", "message": f"Drafting with {drafter}..."}
        try:
            drafter_used, draft = await ollama_client.chat_with_fallback(
                build_candidates(drafter, 4, available), messages)
        except Exception:  # noqa: BLE001
            yield {"type": "error", "message": "All models are currently unavailable. Please retry."}
            return

        yield {"type": "status", "stage": "critique", "message": f"Critiquing with {critic_m}..."}
        critique_text = ""
        critic_used = critic_m
        try:
            critic_used, critique_text = await ollama_client.chat_with_fallback(
                build_candidates(critic_m, 3, available), critique.critique_msgs(user_message, draft))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"critique step skipped: {e}")

        yield {"type": "status", "stage": "factcheck", "message": f"Fact-checking with {verifier_m}..."}
        verify_text = ""
        verifier_used = verifier_m
        try:
            verifier_used, verify_text = await ollama_client.chat_with_fallback(
                build_candidates(verifier_m, 3, available),
                critique.verify_msgs(user_message, draft, evidence_text))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"fact-check step skipped: {e}")

        final_msgs = critique.finalize_msgs(
            user_message, draft, critique_text, verify_text, evidence_text, citations_required=citations_required)
        yield {"type": "status", "stage": "finalize", "message": f"Synthesising final answer with {finalizer}..."}

        fcands = build_candidates(finalizer, 4, available)
        generated = False
        for idx, cand in enumerate(fcands):
            if idx > 0:
                yield {"type": "status", "stage": "finalize",
                       "message": f"'{fcands[idx-1]}' unavailable — finalising with {cand}..."}
            draft = ""
            produced = False
            try:
                async for kind, tok in ollama_client.chat_stream(cand, final_msgs):
                    if kind == "thinking":
                        yield {"type": "thinking", "text": tok}
                        continue
                    produced = True
                    draft += tok
                    yield {"type": "token", "text": tok}
                used_model = cand
                generated = True
                break
            except Exception as e:  # noqa: BLE001
                logger.warning(f"finalize failed on {cand}: {e}")
                if produced:
                    used_model = cand
                    generated = True
                    break
                continue

        if not generated:
            yield {"type": "error", "message": "All models are currently unavailable. Please retry."}
            return

        ensemble_meta = {"drafter": drafter_used, "critic": critic_used,
                         "verifier": verifier_used, "finalizer": used_model}
        yield {"type": "meta", "classification": classification, "model": used_model,
               "role": "ensemble", "route_reason": "multi-model critique ensemble",
               "ensemble": ensemble_meta}
    else:
        # ---- Single-model generation with automatic fallback (self-correction) ----
        candidates = build_candidates(model, limit=5, available=available) if mode != "manual" else [model]
        generated = False

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
                async for kind, tok in ollama_client.chat_stream(cand, messages):
                    if kind == "thinking":
                        yield {"type": "thinking", "text": tok}
                        continue
                    produced = True
                    draft += tok
                    yield {"type": "token", "text": tok}
                used_model = cand
                generated = True
                break
            except Exception as e:  # noqa: BLE001
                logger.warning(f"generation failed on {cand}: {e}")
                if produced:
                    used_model = cand
                    generated = True
                    break
                continue

        if not generated:
            yield {"type": "error",
                   "message": "All models are currently rate-limited or unavailable. Please retry in a moment."}
            return

    # 7. Validate with an INDEPENDENT model — but ONLY when it matters (grounded
    #    answers or high-stakes legal), to keep latency low. Other answers use the
    #    fast heuristic check.
    deep = (evidence_provided or classification.get("category") == "legal") and not use_multi
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
        "type": "done", "content": final, "model": used_model,
        "role": ("ensemble" if use_multi else role),
        "validator_model": validator_model,
        "ensemble": ensemble_meta,
        "category": classification.get("category"), "route_reason": route_reason,
        "used_rag": bool(retrieved), "used_web": bool(web_evidence), "sources": sources,
        "validation": validation, "repaired": repaired,
        "confidence": confidence, "verify_status": verify_status,
    }
