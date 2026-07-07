"""Multi-model critique ensemble (Phase 3).

For hard questions: model A drafts, model B critiques, model C fact-checks, then
the strongest model synthesises the FINAL answer. This amalgamates model
strengths by routing the same question through several models for
critique/verification rather than trusting any single one.
"""


def critique_msgs(question, draft):
    system = (
        "You are a rigorous critical reviewer. Read the user's question and a draft "
        "answer from another model. Identify concrete problems ONLY — factual errors, "
        "weak or missing reasoning, unsupported claims, gaps, and anything unclear. "
        "Be specific and concise as a bullet list. Do NOT rewrite the answer."
    )
    user = f"QUESTION:\n{question}\n\nDRAFT ANSWER:\n{draft}\n\nList the issues to fix:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def verify_msgs(question, draft, evidence_text=""):
    system = (
        "You are a meticulous fact-checker. Check the factual claims in the draft "
        "answer. Flag anything incorrect, outdated, or unsupported, and give the "
        "correction. If evidence is provided, verify against it and cite [S#]. "
        "Return a concise bullet list of verified/false/uncertain claims. Do NOT rewrite the answer."
    )
    ev = f"\n\nEVIDENCE:\n{evidence_text}" if evidence_text else ""
    user = f"QUESTION:\n{question}\n\nDRAFT ANSWER:\n{draft}{ev}\n\nFact-check:"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def finalize_msgs(question, draft, critique_text, verify_text, evidence_text="", citations_required=False):
    parts = [
        "You are the lead author producing the FINAL, authoritative answer.",
        "You are given the question, a draft (model A), a critique (model B), and a "
        "fact-check (model C). Produce the best possible answer: fix every valid issue "
        "from the critique, apply the fact-check corrections, keep the correct content, "
        "and be transparent about any remaining uncertainty.",
        "Write clear, well-structured Markdown. Do not mention the other models or this process.",
    ]
    if citations_required:
        parts.append("Include inline [S#] citations for claims supported by the evidence; do not cite sources that were not provided.")
    system = "\n".join(parts)

    blocks = [f"QUESTION:\n{question}", f"\nDRAFT ANSWER (model A):\n{draft}"]
    if critique_text:
        blocks.append(f"\nCRITIQUE (model B):\n{critique_text}")
    if verify_text:
        blocks.append(f"\nFACT-CHECK (model C):\n{verify_text}")
    if evidence_text:
        blocks.append(f"\nEVIDENCE:\n{evidence_text}")
    blocks.append("\nNow write the final answer:")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(blocks)}]
