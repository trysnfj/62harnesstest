"""Output Validator + Self-Repair for the harness."""
from . import ollama_client
from .config import MODEL_ROLES

_VALIDATOR_SYSTEM = (
    "You are a strict answer-quality validator. Given a user question, the assistant's "
    "draft answer, and whether citations were required, judge the draft. "
    "Respond with ONLY a JSON object."
)


async def validate(user_message, draft, citations_required=False, evidence_provided=False):
    prompt = (
        f"User question:\n\"\"\"\n{user_message}\n\"\"\"\n\n"
        f"Draft answer:\n\"\"\"\n{draft}\n\"\"\"\n\n"
        f"Citations required: {citations_required}. Evidence was provided to the model: {evidence_provided}.\n\n"
        "Return JSON with keys:\n"
        '  "addresses_question": true/false,\n'
        '  "has_required_citations": true/false (true if citations not required),\n'
        '  "hallucination_risk": "low" | "medium" | "high",\n'
        '  "ignored_evidence": true/false (did it ignore the provided evidence?),\n'
        '  "issues": [short strings],\n'
        '  "needs_repair": true/false'
    )
    result = await ollama_client.chat_json(
        MODEL_ROLES["validator"],
        [
            {"role": "system", "content": _VALIDATOR_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    if not result:
        return {
            "addresses_question": True,
            "has_required_citations": not citations_required,
            "hallucination_risk": "low",
            "ignored_evidence": False,
            "issues": [],
            "needs_repair": False,
        }
    result.setdefault("addresses_question", True)
    result.setdefault("has_required_citations", not citations_required)
    result.setdefault("hallucination_risk", "low")
    result.setdefault("ignored_evidence", False)
    result.setdefault("issues", [])
    # Derive needs_repair defensively
    needs = result.get("needs_repair")
    if needs is None:
        needs = (
            not result["addresses_question"]
            or (citations_required and not result["has_required_citations"])
            or result["hallucination_risk"] == "high"
            or result["ignored_evidence"]
        )
    result["needs_repair"] = bool(needs)
    return result


async def repair(model, original_messages, draft, validation):
    """Ask the same model to repair its draft given validator feedback."""
    issues = "; ".join(validation.get("issues", [])) or "quality/citation issues"
    repair_msgs = list(original_messages) + [
        {"role": "assistant", "content": draft},
        {
            "role": "user",
            "content": (
                "Your previous answer failed validation for these reasons: "
                f"{issues}. Concerns: addresses_question="
                f"{validation.get('addresses_question')}, citations_ok="
                f"{validation.get('has_required_citations')}, hallucination_risk="
                f"{validation.get('hallucination_risk')}, ignored_evidence="
                f"{validation.get('ignored_evidence')}.\n\n"
                "Rewrite a corrected, complete answer. Only use the evidence provided earlier, "
                "add proper [S#] citations where required, remove unsupported claims, and be "
                "explicit about any uncertainty. Return only the improved answer."
            ),
        },
    ]
    return await ollama_client.chat(model, repair_msgs)


def compute_confidence(validation, used_rag, used_web):
    score = 70
    risk = validation.get("hallucination_risk", "low")
    if risk == "low":
        score += 15
    elif risk == "high":
        score -= 35
    if validation.get("addresses_question"):
        score += 5
    else:
        score -= 20
    if validation.get("ignored_evidence"):
        score -= 15
    if used_rag or used_web:
        score += 10  # grounded in evidence
    if validation.get("has_required_citations"):
        score += 5
    score = max(5, min(99, score))
    if score >= 75 and not validation.get("needs_repair", False):
        status = "VERIFIED"
    elif score >= 55:
        status = "LIKELY"
    else:
        status = "UNCERTAIN"
    return score, status
