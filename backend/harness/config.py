"""Model router configuration for the harness layer.

Maps abstract roles to concrete Ollama Cloud models and defines how query
categories map onto those roles. Kept in one place so routing is transparent
and easy to tune (see /api/config).
"""

# Role -> concrete Ollama Cloud model
MODEL_ROLES = {
    "fast": "gpt-oss:20b",             # cheap/fast simple chat
    "general": "gpt-oss:120b",         # strong all-round
    "coding": "qwen3-coder:480b",      # strongest code model
    "reasoning": "deepseek-v3.1:671b", # deep reasoning
    "long_context": "qwen3.5:397b",    # long document Q&A
    "summarization": "gemma4:31b",     # efficient summariser
    "factual": "gpt-oss:120b",         # paired with web verification
    "creative": "kimi-k2.6",           # creative writing
    "legal": "glm-5.2",
    "business": "glm-5.2",
    "technical": "glm-5.2",
    "critique": "deepseek-v3.1:671b",  # multi-model critique (phase 3)
    "verify": "gpt-oss:120b",
    "classifier": "gpt-oss:20b",       # fast classification
    "validator": "gpt-oss:20b",        # fast output validation
}

# Query category -> role
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

# Human-readable notes surfaced in the UI/Settings
ROLE_NOTES = {
    "fast": "Fastest, cheapest model for simple chat",
    "general": "Strong general-purpose model",
    "coding": "Strongest code-specialised model",
    "reasoning": "Deep step-by-step reasoning",
    "long_context": "Largest context window for long documents",
    "summarization": "Efficient summarisation",
    "factual": "Used with internet verification for current facts",
    "creative": "Creative & narrative writing",
    "legal": "Careful, high-precision responses",
    "business": "Structured business analysis",
    "technical": "Clear technical explanation",
}


def resolve_model(role: str) -> str:
    return MODEL_ROLES.get(role, MODEL_ROLES["general"])
