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


def build_candidates(primary: str, limit: int = 4):
    """Ordered list of models to try: primary first, then reliable fallbacks."""
    candidates = [primary]
    for m in FALLBACK_MODELS:
        if m not in candidates:
            candidates.append(m)
    return candidates[:limit]
