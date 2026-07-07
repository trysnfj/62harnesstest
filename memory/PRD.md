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

## Implemented (2026-06 / 07)
- Chat UI, sidebar, input bar (upload, RAG, internet, Auto/Manual, manual model selector).
- Harness: hybrid intelligent classifier (heuristic + LLM refine) → diverse per-category
  model router → TF-IDF RAG → DuckDuckGo web verify → prompt compiler → streamed
  generation with automatic model fallback (self-correction) → independent cross-model
  validation → self-repair. 403/subscription models fail-fast; calls serialized w/ retry.
- Phase 3 Multi-model critique ENSEMBLE (opt-in 'Ensemble' toggle): draft (model A) →
  critique (model B) → fact-check (model C) → finalize/synthesise (strongest model).
  done event carries ensemble={drafter,critic,verifier,finalizer}; shown as badge + trace.
- Model performance memory (model_runs) surfaced in Settings → Performance.
- All 34 cloud models available in Manual selector.
- Tested: iterations 1-7 pass (routing diversity, self-correction, independent validator, ensemble).

## Backlog / remaining
- P1: Use model_runs history to bias future routing (adaptive router).
- P2: Auto-trigger ensemble for very hard queries (currently opt-in only).
- P2: Full-content web extraction (currently uses search snippets).
- P2: Grey-out subscription-locked models in the manual dropdown.
- P2: Higher-tier Ollama key to unlock large models + reduce rate-limit fallback.

## Next tasks
- Adaptive routing from performance memory; optional auto-ensemble for hard queries.
