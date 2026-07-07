"""Query Classifier — LLM-based intelligent classification with a heuristic fallback.

Primary path: a fast Ollama model reads the query and returns a structured
classification (category, reasoning depth, context length, RAG/web needs). This
gives nuanced, query-appropriate routing so different questions reach different
specialist models. If the LLM call fails (rate-limit/unavailable), we fall back
to fast keyword heuristics so the pipeline never stalls.
"""
import logging
from . import ollama_client
from .config import CATEGORIES, MODEL_ROLES

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are the routing brain of an AI harness. Read the user's request and "
    "classify it precisely so it can be routed to the best specialist model. "
    "Respond with ONLY a compact JSON object, no prose."
)


def _prompt(user_message, has_docs, web_enabled):
    cats = ", ".join(f'"{c}"' for c in CATEGORIES)
    return (
        f"Available categories: [{cats}].\n"
        f"Documents are attached to this chat: {has_docs}.\n"
        f"User manually enabled internet search: {web_enabled}.\n\n"
        f"User request:\n\"\"\"\n{user_message}\n\"\"\"\n\n"
        "Return JSON with exactly these keys:\n"
        '  "category": one of the categories that best fits,\n'
        '  "reasoning_depth": "low" | "medium" | "high" (how much step-by-step thinking is needed),\n'
        '  "context_length": "short" | "long",\n'
        '  "needs_rag": true/false (answer should come from the attached documents),\n'
        '  "needs_web": true/false (needs current/real-time facts or verification),\n'
        '  "rationale": one short sentence explaining the choice.'
    )


# ----- keyword sets for the heuristic fallback -----
_CODING = ["code", "function", "python", "javascript", "typescript", "java ", "c++", "sql",
           "regex", "api ", "bug", "compile", "algorithm", "script", "html", "css", "react",
           "debug", "def ", "class ", "```", "refactor", "endpoint", "docker"]
_SUMMARISE = ["summarise", "summarize", "summary", "tldr", "tl;dr", "key points", "in short"]
_CREATIVE = ["poem", "story", "song", "lyrics", "fiction", "screenplay", "haiku", "novel"]
_LEGAL = ["legal", "law", "contract", "clause", "liability", "gdpr", "lawsuit", "compliance"]
_BUSINESS = ["business", "market", "revenue", "strategy", "roi", "pricing", "startup", "kpi", "profit"]
_WEB = ["latest", "current", "today", "right now", "news", "recent", "price of", "stock",
        "weather", "2024", "2025", "2026", "score", "release date", "who won", "up to date", "real-time"]
_REASON = ["solve", "prove", "calculate", "derive", "step by step", "step-by-step", "logic",
           "analyse", "analyze", "compare", "trade-off", "how many", "puzzle", "equation", "why "]
_TECH = ["explain", "how does", "how do", "what is", "difference between", "architecture"]


def _has(text, kws):
    return any(k in text for k in kws)


def heuristic_classify(user_message, has_docs=False, web_enabled=False):
    t = (user_message or "").lower()
    length = len(user_message or "")
    needs_web = web_enabled or _has(t, _WEB)

    if _has(t, _CODING):
        category = "coding"
    elif _has(t, _SUMMARISE):
        category = "summarisation"
    elif _has(t, _CREATIVE):
        category = "creative writing"
    elif _has(t, _LEGAL):
        category = "legal"
    elif _has(t, _BUSINESS):
        category = "business"
    elif has_docs:
        category = "document Q&A"
    elif needs_web:
        category = "factual/current-events"
    elif _has(t, _REASON):
        category = "reasoning"
    elif _has(t, _TECH):
        category = "technical explanation"
    else:
        category = "general chat"

    if _has(t, _REASON) or category in ("reasoning", "coding", "legal"):
        depth = "high"
    elif length < 60 and category == "general chat":
        depth = "low"
    else:
        depth = "medium"

    return {
        "category": category,
        "reasoning_depth": depth,
        "context_length": "long" if (has_docs or length > 800) else "short",
        "needs_rag": has_docs,
        "needs_web": needs_web,
        "rationale": f"Heuristic fallback → {category}",
    }


def _normalise(result, has_docs, web_enabled):
    category = result.get("category")
    if category not in CATEGORIES:
        return None
    depth = result.get("reasoning_depth", "medium")
    if depth not in ("low", "medium", "high"):
        depth = "medium"
    ctx = result.get("context_length", "short")
    if ctx not in ("short", "long"):
        ctx = "short"
    return {
        "category": category,
        "reasoning_depth": depth,
        "context_length": ctx,
        "needs_rag": bool(result.get("needs_rag", False)) and has_docs,
        "needs_web": bool(result.get("needs_web", False)) or web_enabled,
        "rationale": result.get("rationale", "") or f"Classified as {category}",
    }


async def classify(user_message, has_docs=False, web_enabled=False):
    """Intelligent LLM classification with heuristic fallback."""
    try:
        raw = await ollama_client.chat_json(
            MODEL_ROLES["classifier"],
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _prompt(user_message, has_docs, web_enabled)},
            ],
        )
        norm = _normalise(raw, has_docs, web_enabled)
        if norm:
            return norm
    except Exception as e:  # noqa: BLE001
        logger.warning(f"LLM classifier unavailable, using heuristic: {e}")
    return heuristic_classify(user_message, has_docs, web_enabled)
