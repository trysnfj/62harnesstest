"""Self-Repair Loop orchestrator (the harness pipeline).

Yields SSE-friendly event dicts as it progresses:
  {"type": "status", "stage": ..., "message": ...}
  {"type": "meta", ...}          -> routing/classification info
  {"type": "token", "text": ...} -> streamed answer tokens
  {"type": "replace", "text": ...} -> repaired final answer (replaces streamed draft)
  {"type": "done", ...}          -> final metadata (also persisted by caller)
"""
from . import classifier, router, rag, websearch, prompt_compiler, validator, ollama_client


async def run_pipeline(*, user_message, history, mode, manual_model, use_rag, use_web, chunk_docs):
    has_docs = bool(chunk_docs)

    # 1. Classify
    yield {"type": "status", "stage": "classify", "message": "Classifying your request..."}
    classification = await classifier.classify(user_message, has_docs=has_docs, web_enabled=use_web)

    # 2. Route
    model, role, route_reason = router.route(
        classification, mode=mode, manual_model=manual_model, use_rag=use_rag, use_web=use_web
    )
    yield {
        "type": "meta",
        "classification": classification,
        "model": model,
        "role": role,
        "route_reason": route_reason,
    }

    # 3. Retrieve documents (RAG)
    retrieved = []
    do_rag = (use_rag or classification.get("needs_rag")) and has_docs
    if do_rag:
        yield {"type": "status", "stage": "retrieve", "message": "Retrieving relevant document passages..."}
        retrieved = rag.retrieve(user_message, chunk_docs, top_k=4)

    # 4. Internet verification
    web_evidence = []
    do_web = use_web or classification.get("needs_web")
    if do_web:
        yield {"type": "status", "stage": "search", "message": "Searching the web for verification..."}
        web_evidence = await websearch.search(user_message, max_results=5)

    # 5. Compile prompt
    messages, sources = prompt_compiler.compile_prompt(
        user_message, classification, doc_chunks=retrieved, web_evidence=web_evidence, history=history
    )

    # 6. Generate draft (streamed live)
    yield {"type": "status", "stage": "generate", "message": f"Generating with {model}..."}
    draft = ""
    async for tok in ollama_client.chat_stream(model, messages):
        draft += tok
        yield {"type": "token", "text": tok}

    # 7. Validate
    yield {"type": "status", "stage": "validate", "message": "Validating answer quality..."}
    citations_required = bool(sources)
    evidence_provided = bool(retrieved or web_evidence)
    validation = await validator.validate(
        user_message, draft, citations_required=citations_required, evidence_provided=evidence_provided
    )

    # 8. Self-repair if needed (single pass)
    final = draft
    repaired = False
    if validation.get("needs_repair"):
        yield {"type": "status", "stage": "repair", "message": "Answer failed validation — repairing..."}
        final = await validator.repair(model, messages, draft, validation)
        repaired = True
        # re-validate the repaired answer for the confidence score
        validation = await validator.validate(
            user_message, final, citations_required=citations_required, evidence_provided=evidence_provided
        )
        yield {"type": "replace", "text": final}

    confidence, verify_status = validator.compute_confidence(validation, bool(retrieved), bool(web_evidence))

    yield {
        "type": "done",
        "content": final,
        "model": model,
        "role": role,
        "category": classification.get("category"),
        "route_reason": route_reason,
        "used_rag": bool(retrieved),
        "used_web": bool(web_evidence),
        "sources": sources,
        "validation": validation,
        "repaired": repaired,
        "confidence": confidence,
        "verify_status": verify_status,
    }
