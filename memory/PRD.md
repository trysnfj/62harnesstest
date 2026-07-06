# PRD — AI Harness Chat

## Original problem statement
ChatGPT-style web app testing a harness-based AI chatbot with RAG, internet
verification, and intelligent model routing over Ollama Cloud models. Harness
modules: query classifier, model router (Auto/Manual), RAG pipeline, internet
verification, prompt compiler, output validator, self-repair loop, model
performance memory. Deliverables: full code, setup, env template, example router
config, example prompts, clean UI, modular backend harness.

## User choices
- Models: Ollama Cloud (real key provided) — 34 cloud models.
- Internet search: DuckDuckGo (keyless) instead of Tavily.
- Auth: none (single-user).
- Scope: Phase 1 + Phase 2.
- Docs: PDF + DOCX + TXT + CSV.

## Architecture
- Frontend: React + Tailwind + shadcn/ui, SSE streaming, Swiss high-contrast design.
- Backend: FastAPI + MongoDB. Harness package: `ollama_client, config, classifier,
  router, rag, websearch, prompt_compiler, validator, pipeline`.
- Collections: chats, messages, documents, document_chunks, model_runs.

## Implemented (2026-06)
- Chat UI: sidebar (new chat, history, documents, settings), streaming chat area,
  input bar (upload, RAG toggle, internet toggle, Auto/Manual, manual model selector).
- Harness pipeline: heuristic classifier → model router → TF-IDF RAG retrieval →
  DuckDuckGo web verification → structured prompt compiler → streamed generation →
  output validation → single self-repair pass. Metadata (model, category, confidence,
  verify status, RAG/web flags, sources, harness trace) shown per answer.
- Reliability / self-correction: all Ollama calls serialized (semaphore) with
  retry/backoff on 429/403/5xx/timeout; automatic model fallback through
  FALLBACK_MODELS when the routed model is unavailable; pipeline always emits a
  terminal done/error; frontend watchdog + error handling (no infinite hang).
- Model performance memory logged to model_runs; surfaced in Settings → Performance.
- Deliverables: README.md, backend/.env.example, /api/config router config.
- Tested: backend 100% (10/10), frontend 100% (iteration_2).

## Backlog / remaining
- P1: Phase 3 multi-model critique (model A drafts, B critiques, C verifies).
- P1: Use model_runs history to bias future routing (adaptive router).
- P2: Persist retrieval scores/citations click-through; document-scoped RAG toggle.
- P2: Full-content web extraction (currently uses search snippets only).
- P2: Higher-tier Ollama key or client-side rate limiting to allow larger models.

## Next tasks
- Offer Phase 3 multi-model critique mode as an opt-in for "difficult" queries.
