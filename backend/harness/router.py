"""Model Router module of the harness.

Routing is deterministic: each task category maps to the best *specialist* model.
We intentionally do NOT bias routing based on user feedback — the reinforcement
signal is used to improve the *information* (more grounding + stricter
verification for weak topics), not to favour any particular model.
"""
from .config import CATEGORY_TO_ROLE, resolve_model


def route(classification, mode="auto", manual_model=None, use_rag=False, use_web=False):
    """Select the best model + role for the task. Returns (model_name, role, reason)."""
    if mode == "manual" and manual_model:
        return manual_model, "manual", "Manual model selection by user"

    category = classification.get("category", "general chat")
    depth = classification.get("reasoning_depth", "medium")
    ctx = classification.get("context_length", "short")
    needs_rag = classification.get("needs_rag", False) or use_rag
    needs_web = classification.get("needs_web", False) or use_web

    role = CATEGORY_TO_ROLE.get(category, "general")
    reason = f"category='{category}'"

    if needs_rag or ctx == "long":
        role = "long_context"
        reason = "long document context required"
    elif needs_web:
        role = "factual"
        reason = "current facts / internet verification required"
    elif depth == "high" and role in ("fast", "general", "technical"):
        role = "reasoning"
        reason = "high reasoning depth required"

    return resolve_model(role), role, reason
