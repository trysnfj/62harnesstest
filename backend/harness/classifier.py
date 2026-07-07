"""Query Classifier — hybrid intelligent classification.

Strategy (fast + intelligent + low rate-limit pressure):
- Heuristic first. For clearly-signalled queries (coding, creative, summarisation,
  legal, business, explicit web/reasoning cues, or when documents are attached)
  we trust the heuristic and make ZERO extra LLM calls.
- Only when the query is ambiguous (falls into generic "general chat" /
  "technical explanation") do we spend one fast LLM call to classify it properly.
This keeps routing intelligent while minimising calls on the rate-limited key.
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
        '  "category": the single best-fitting category,\n'
        '  "reasoning_depth": "low" | "medium" | "high",\n'
        '  "context_length": "short" | "long",\n'
        '  "needs_rag": true/false,\n'
        '  "needs_web": true/false,\n'
        '  "rationale": one short sentence.'
    )


_CODING = ["code", "function", "python", "javascript", "typescript", "java ", "c++", "sql",
           "regex", "api ", "bug", "compile", "algorithm", "script", "html", "css", "react",
           "debug", "def ", "class ", "```", "refactor", "endpoint", "docker", "useeffect", "stack trace"]
_SUMMARISE = ["summarise", "summarize", "summary", "tldr", "tl;dr", "key points"]
_CREATIVE = ["poem", "story", "song", "lyrics", "fiction", "screenplay", "haiku", "novel", "write a tale"]
_LEGAL = ["legal", "law", "contract", "clause", "liability", "gdpr", "lawsuit", "compliance"]
_BUSINESS = ["business plan", "market", "revenue", "strategy", "roi", "pricing", "startup", "kpi", "go-to-market"]
_WEB = ["latest", "current", "today", "right now", "news", "recent", "price of", "stock",
        "weather", "2024", "2025", "2026", "score", "release date", "who won", "up to date", "real-time"]
_REASON = ["solve", "prove", "calculate", "derive", "step by step", "step-by-step", "reason it out",
           "logic", "analyse", "analyze", "compare", "trade-off", "how many", "puzzle", "equation",
           "complexity", "why is", "why do", "why does"]
_TECH = ["explain", "how does", "how do", "what is", "difference between", "architecture", "how to"]


def _has(text, kws):
    return any(k in text for k in kws)


def heuristic_classify(user_message, has_docs=False, web_enabled=False):
    t = (user_message or "").lower()
    length = len(user_message or "")
    needs_web = web_enabled or _has(t, _WEB)
    strong = True

    if _has(t, _CODING):
        category = "coding"
    elif _has(t, _CREATIVE):
        category = "creative writing"
    elif _has(t, _SUMMARISE):
        category = "summarisation"
    elif _has(t, _LEGAL):
        category = "legal"
    elif _has(t, _BUSINESS):
        category = "business"
    elif has_docs:
        category = "document Q&A"
    elif _has(t, _REASON):
        category = "reasoning"
    elif needs_web:
        category = "factual/current-events"
    elif _has(t, _TECH):
        category = "technical explanation"
        strong = False  # ambiguous ("what is X" could be factual/reasoning/coding)
    else:
        category = "general chat"
        strong = False

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
        "rationale": f"Heuristic → {category}",
        "_strong": strong,
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
    """Hybrid: trust confident heuristics; use a fast LLM call only when ambiguous."""
    h = heuristic_classify(user_message, has_docs=has_docs, web_enabled=web_enabled)
    if h.pop("_strong", False):
        return h
    # Ambiguous → refine with a fast LLM classifier
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
    return h
