"""Prompt Compiler: builds a structured prompt before any model call."""


def _history_summary(history, max_msgs=6):
    if not history:
        return ""
    recent = history[-max_msgs:]
    lines = []
    for m in recent:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = (m.get("content") or "").strip()
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def compile_prompt(user_message, classification, doc_chunks=None, web_evidence=None, history=None):
    doc_chunks = doc_chunks or []
    web_evidence = web_evidence or []

    system_parts = [
        "You are a rigorous AI assistant operating inside a verification harness.",
        "Follow these rules strictly:",
        "- Answer clearly and in well-structured Markdown.",
        "- Be transparent about uncertainty; never invent facts, names, numbers, or citations.",
    ]

    if doc_chunks:
        system_parts.append(
            "- DOCUMENT MODE: Answer PRIMARILY from the provided document context. "
            "If the documents do not contain the answer, say so explicitly. "
            "Cite sources inline using [S#] markers that match the numbered sources."
        )
    if web_evidence:
        system_parts.append(
            "- WEB EVIDENCE: Ground current/factual claims in the provided web evidence. "
            "Cite sources inline using [S#] markers. Flag any claim you cannot verify."
        )
    if not doc_chunks and not web_evidence:
        system_parts.append(
            "- Answer from your own knowledge. If the question requires current or "
            "real-time information you do not have, state that clearly."
        )

    system = "\n".join(system_parts)

    # Build numbered sources
    sources = []
    context_blocks = []
    n = 1
    for c in doc_chunks:
        sources.append({"n": n, "type": "document", "label": c.get("document_name", "document"), "url": None})
        context_blocks.append(f"[S{n}] (Document: {c.get('document_name','document')})\n{c['text']}")
        n += 1
    for w in web_evidence:
        sources.append({"n": n, "type": "web", "label": w.get("title", "web"), "url": w.get("url")})
        context_blocks.append(f"[S{n}] (Web: {w.get('title','')} — {w.get('url','')})\n{w.get('snippet','')}")
        n += 1

    user_parts = [f"USER INTENT ({classification.get('category','general chat')}):\n{user_message}"]

    hist = _history_summary(history)
    if hist:
        user_parts.append(f"\nCONVERSATION SUMMARY:\n{hist}")

    if context_blocks:
        user_parts.append("\nEVIDENCE / CONTEXT:\n" + "\n\n".join(context_blocks))

    out_req = ["\nOUTPUT REQUIREMENTS:", "- Directly address the user's question."]
    if sources:
        out_req.append("- Include inline [S#] citations for every factual claim drawn from the evidence.")
        out_req.append("- Do not cite sources that were not provided.")
    out_req.append("- If uncertain, add a short 'Uncertainty' note at the end.")
    user_parts.append("\n".join(out_req))

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
    evidence_text = "\n\n".join(context_blocks)
    return messages, sources, evidence_text
