"""Model Router module of the harness.

Supports a lightweight reinforcement-learning style adaptation: when
`learned_routes` (category -> best-performing model, derived from reward signals
= validation confidence + user feedback) is provided, the router prefers the
learned model. An epsilon-greedy exploration flag lets the caller occasionally
fall back to the default routing so the system keeps learning.
"""
from .config import CATEGORY_TO_ROLE, resolve_model


def route(classification, mode="auto", manual_model=None, use_rag=False, use_web=False,
          learned_routes=None, explore=False):
    """Select the best model + role. Returns (model_name, role, reason)."""
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

    default_model = resolve_model(role)

    # Reinforcement: prefer the learned best model for this category (exploit),
    # unless we're exploring or there is no learned route / evidence conflict.
    if (not explore) and learned_routes and learned_routes.get(category):
        learned = learned_routes[category]
        # Don't override the long-context / web routes which are hard requirements.
        if role not in ("long_context", "factual") and learned != default_model:
            return learned, f"{role} (learned)", f"learned best model for '{category}' (RL feedback)"

    return default_model, role, reason
