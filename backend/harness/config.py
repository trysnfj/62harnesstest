"""Model router configuration for the harness layer.

Roles map to concrete Ollama Cloud models. The models below were chosen for
reliability + reasonable latency on the shared cloud key. If a routed model is
unavailable (rate-limited / 403 / timeout), the pipeline automatically falls
back through FALLBACK_MODELS (self-correction).
"""

MODEL_ROLES = {
    "fast": "gemma3:12b",            # very fast simple chat
    "general": "gpt-oss:20b",        # strong all-round
    "coding": "qwen3-coder-next",    # code-specialised
    "reasoning": "nemotron-3-super", # reasoning-oriented
    "long_context": "minimax-m2.5",  # long document Q&A
    "summarization": "gemma3:27b",
    "factual": "glm-4.7",            # paired with web verification
    "creative": "gemma4:31b",
    "legal": "glm-4.7",
    "business": "nemotron-3-super",
    "technical": "gpt-oss:20b",
    "classifier": "gpt-oss:20b",     # fast, instruction-following router brain
    "validator": "glm-4.7",          # default validator
}

# Ordered reliable, subscription-free, diverse models for fallback / self-correction.
FALLBACK_MODELS = [
    "gemma3:12b",
    "gpt-oss:20b",
    "glm-4.7",
    "qwen3-coder-next",
    "gemma4:31b",
    "nemotron-3-super",
    "ministral-3:8b",
]

# Preferred INDEPENDENT validators (cross-model verification). Capable + free.
VALIDATOR_POOL = [
    "glm-4.7",
    "gpt-oss:20b",
    "nemotron-3-super",
    "gemma4:31b",
    "gemma3:27b",
    "minimax-m2.5",
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
