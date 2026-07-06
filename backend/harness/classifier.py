"""Query Classifier module of the harness."""
from . import ollama_client
from .config import MODEL_ROLES, CATEGORIES

_SYSTEM = (
    "You are a query classification engine for an AI routing system. "
    "Classify the user's request precisely. Respond with ONLY a JSON object, no prose."
)


def _prompt(user_message, has_docs, web_enabled):
    cats = ", ".join(CATEGORIES)
    return (
        f"Categories: [{cats}].\n"
        f"Documents attached to this chat: {has_docs}.\n"
        f"User manually enabled internet search: {web_enabled}.\n\n"
        f"User request:\n\"\"\"\n{user_message}\n\"\"\"\n\n"
        "Return JSON with keys:\n"
        '  "category": one of the categories,\n'
        '  "reasoning_depth": "low" | "medium" | "high",\n'
        '  "context_length": "short" | "long",\n'
        '  "needs_rag": true/false (true if the answer should come from attached documents),\n'
        '  "needs_web": true/false (true if the question needs current/real-time facts or verification),\n'
        '  "rationale": one short sentence.'
    )


async def classify(user_message, has_docs=False, web_enabled=False):
    result = await ollama_client.chat_json(
        MODEL_ROLES["classifier"],
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _prompt(user_message, has_docs, web_enabled)},
        ],
    )
    category = result.get("category")
    if category not in CATEGORIES:
        category = "general chat"
    depth = result.get("reasoning_depth", "medium")
    if depth not in ("low", "medium", "high"):
        depth = "medium"
    ctx = result.get("context_length", "short")
    if ctx not in ("short", "long"):
        ctx = "short"
    needs_rag = bool(result.get("needs_rag", False)) and has_docs
    needs_web = bool(result.get("needs_web", False)) or web_enabled
    return {
        "category": category,
        "reasoning_depth": depth,
        "context_length": ctx,
        "needs_rag": needs_rag,
        "needs_web": needs_web,
        "rationale": result.get("rationale", ""),
    }
