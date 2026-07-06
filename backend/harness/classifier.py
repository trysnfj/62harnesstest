"""Query Classifier — fast, deterministic, keyword/heuristic based.

Runs with zero LLM calls, which removes a failure point and reduces load on the
rate-limited cloud key while still classifying into the required categories.
"""
import re

_CODING = [
    "code", "function", "python", "javascript", "typescript", "java ", "c++", "c#",
    "sql", "regex", "api", "bug", "compile", "algorithm", "script", "html", "css",
    "react", "debug", "stack trace", "def ", "class ", "```", "refactor", "leetcode",
    "endpoint", "docker", "kubernetes", "terminal", "npm", "pip install",
]
_SUMMARISE = ["summarise", "summarize", "summary", "tldr", "tl;dr", "key points", "in short"]
_CREATIVE = ["poem", "story", "song", "lyrics", "fiction", "screenplay", "haiku", "novel", "write a tale"]
_LEGAL = ["legal", "law", "contract", "clause", "liability", "gdpr", "terms of service", "lawsuit", "compliance", "regulation"]
_BUSINESS = ["business", "market", "revenue", "strategy", "roi", "pricing", "startup", "b2b", "kpi", "go-to-market", "profit"]
_WEB = [
    "latest", "current", "today", "right now", "news", "recent", "price of", "stock",
    "weather", "2024", "2025", "2026", "score", "release date", "who won", "this year",
    "up to date", "real-time", "live ", "breaking",
]
_REASON = [
    "solve", "prove", "calculate", "derive", "why ", "step by step", "step-by-step",
    "logic", "reasoning", "analyse", "analyze", "compare", "trade-off", "optimi",
    "how many", "puzzle", "math", "equation",
]
_TECH = ["explain", "how does", "how do", "what is", "difference between", "architecture", "under the hood"]
_DOCQA = ["document", "the doc", "the pdf", "the file", "this text", "the paper", "according to", "in the attachment", "uploaded"]


def _has(text, kws):
    return any(k in text for k in kws)


def classify(user_message, has_docs=False, web_enabled=False):
    t = (user_message or "").lower()
    length = len(user_message or "")

    needs_web = web_enabled or _has(t, _WEB)
    # Document Q&A when docs exist and the user references them / asks a content question
    doc_ref = has_docs and (_has(t, _DOCQA) or length > 0)

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
    elif has_docs and doc_ref:
        category = "document Q&A"
    elif needs_web:
        category = "factual/current-events"
    elif _has(t, _REASON):
        category = "reasoning"
    elif _has(t, _TECH):
        category = "technical explanation"
    else:
        category = "general chat"

    # reasoning depth
    if _has(t, _REASON) or category in ("reasoning", "coding", "legal"):
        depth = "high"
    elif length < 60 and category == "general chat":
        depth = "low"
    else:
        depth = "medium"

    context_length = "long" if (has_docs or length > 800) else "short"
    needs_rag = has_docs

    return {
        "category": category,
        "reasoning_depth": depth,
        "context_length": context_length,
        "needs_rag": needs_rag,
        "needs_web": needs_web,
        "rationale": f"Heuristic match → {category}",
    }
