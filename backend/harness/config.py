"""Model router configuration for the harness layer.

Roles map to concrete Ollama Cloud models. The models below were chosen for
reliability + reasonable latency on the shared cloud key. If a routed model is
unavailable (rate-limited / 403 / timeout), the pipeline automatically falls
back through FALLBACK_MODELS (self-correction).
"""

MODEL_ROLES = {
    "fast": "ministral-3:8b",       # fast, cheap simple chat
    "general": "glm-4.7",           # strong all-round
    "coding": "qwen3-coder:480b",   # code-specialised
    "reasoning": "deepseek-v4-flash",  # fast reasoning
    "long_context": "glm-4.7",      # long document Q&A
    "summarization": "ministral-3:8b",
    "factual": "glm-4.7",           # paired with web verification
    "creative": "glm-4.7",
    "legal": "glm-4.7",
    "business": "glm-4.7",
    "technical": "glm-4.7",
    "validator": "ministral-3:8b",  # fast output validation
}

# Ordered by reliability + speed. Used for automatic fallback / self-correction.
FALLBACK_MODELS = [
    "ministral-3:8b",
    "glm-4.7",
    "qwen3-coder:480b",
    "gpt-oss:20b",
    "gemma3:12b",
]

# Preferred models for INDEPENDENT validation (cross-model verification).
# Ordered by capability + reliability. The harness auto-selects the best one
# that differs from the model that drafted the answer.
VALIDATOR_POOL = [
    "glm-4.7",
    "gemma4:31b",
    "deepseek-v4-flash",
    "gpt-oss:20b",
    "ministral-3:8b",
    "glm-5.2",
    "qwen3.5:397b",
]

CATEGORY_TO_ROLE = {
    "general chat": "fast",
    "coding": "coding",
    "reasoning": "reasoning",
    "summarisation": "summarization",
    "document Q&A": "long_context",
    "research": "factual",
    "factual/current-events": "factual",
    "creative writing": "creative",
    "legal": "legal",
    "business": "business",
    "technical explanation": "technical",
}

CATEGORIES = list(CATEGORY_TO_ROLE.keys())

ROLE_NOTES = {
    "fast": "Fastest, cheapest model for simple chat",
    "general": "Strong general-purpose model",
    "coding": "Code-specialised model",
    "reasoning": "Fast step-by-step reasoning",
    "long_context": "Handles long documents",
    "summarization": "Efficient summarisation",
    "factual": "Used with internet verification for current facts",
    "creative": "Creative & narrative writing",
    "legal": "Careful, high-precision responses",
    "business": "Structured business analysis",
    "technical": "Clear technical explanation",
}


def resolve_model(role: str) -> str:
    return MODEL_ROLES.get(role, MODEL_ROLES["general"])


def build_candidates(primary: str, limit: int = 4, available=None):
    """Ordered list of models to try: primary first, then reliable fallbacks,
    then any other available cloud model (so the harness can reach ALL models)."""
    candidates = [primary]
    for m in FALLBACK_MODELS:
        if m not in candidates:
            candidates.append(m)
    if available:
        for m in available:
            if m not in candidates:
                candidates.append(m)
    return candidates[:limit]


def choose_validator(draft_model: str, available=None):
    """Auto-select the most appropriate INDEPENDENT model to validate the answer.
    Prefers a capable, reliable model that differs from the drafting model
    (cross-model verification)."""
    for m in VALIDATOR_POOL:
        if m != draft_model and (not available or m in available):
            return m
    for m in (available or []):
        if m != draft_model:
            return m
    return draft_model
