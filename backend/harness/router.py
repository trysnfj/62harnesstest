"""Model Router module of the harness."""
from .config import CATEGORY_TO_ROLE, resolve_model


def route(classification, mode="auto", manual_model=None, use_rag=False, use_web=False):
    """Select the best model + role given the classification and flags.

    Returns (model_name, role, reason).
    """
    if mode == "manual" and manual_model:
        return manual_model, "manual", "Manual model selection by user"

    category = classification.get("category", "general chat")
    depth = classification.get("reasoning_depth", "medium")
    ctx = classification.get("context_length", "short")
    needs_rag = classification.get("needs_rag", False) or use_rag
    needs_web = classification.get("needs_web", False) or use_web

    role = CATEGORY_TO_ROLE.get(category, "general")
    reason = f"category='{category}'"

    # Long document Q&A / long context wins on context length
    if needs_rag or ctx == "long":
        role = "long_context"
        reason = "long document context required"
    # Current facts / verification routes to the web-verified model
    elif needs_web:
        role = "factual"
        reason = "current facts / internet verification required"
    # Escalate deep reasoning
    elif depth == "high" and role in ("fast", "general", "technical"):
        role = "reasoning"
        reason = "high reasoning depth required"

    return resolve_model(role), role, reason
