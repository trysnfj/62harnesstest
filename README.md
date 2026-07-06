# AI Harness Chat

A ChatGPT-style app that wraps Ollama Cloud models in a reliability **harness**:
every query is classified, routed to the best model, grounded in your documents
and/or the web, then validated and self-repaired before you see it.

## Architecture (harness pipeline)

```
user query
  → classify query            (harness/classifier.py)
  → route to best model       (harness/router.py + config.py)
  → retrieve documents        (harness/rag.py, TF-IDF cosine)
  → search internet           (harness/websearch.py, DuckDuckGo)
  → compile structured prompt (harness/prompt_compiler.py)
  → stream draft answer        (harness/ollama_client.py)
  → validate answer            (harness/validator.py)
  → self-repair if needed      (harness/validator.repair)
  → final response + metadata
```

Model runs are logged to `model_runs` (Model Performance Memory, see /api/stats).

## Tech stack
- Frontend: React + Tailwind + shadcn/ui (ChatGPT-style, streaming via SSE)
- Backend: FastAPI, streaming Server-Sent Events
- Models: Ollama Cloud (34 models: gpt-oss, deepseek, qwen, glm, gemma, kimi, ...)
- RAG: TF-IDF retrieval (scikit-learn), PDF/DOCX/TXT/CSV parsing
- Internet verification: DuckDuckGo (keyless)
- DB: MongoDB (chats, messages, documents, document_chunks, model_runs)

## Setup
1. Backend env (`backend/.env`) — see `backend/.env.example`:
   - `OLLAMA_API_KEY` (from https://ollama.com settings → keys)
   - `MONGO_URL`, `DB_NAME` (pre-set)
2. Install: `pip install -r backend/requirements.txt` and `yarn install` in `frontend/`.
3. Services are managed by supervisor (`sudo supervisorctl restart backend frontend`).

## Example router config
See `harness/config.py` (`MODEL_ROLES` + `CATEGORY_TO_ROLE`) or GET `/api/config`.

| Role | Model |
|------|-------|
| fast | gpt-oss:20b |
| general | gpt-oss:120b |
| coding | qwen3-coder:480b |
| reasoning | deepseek-v3.1:671b |
| long_context | qwen3.5:397b |
| creative | kimi-k2.6 |

## Example prompts
- "Explain how transformers work, simply" → reasoning/technical route
- "Write a Python web scraper for a news site" → coding route (qwen3-coder)
- Upload a PDF, then "Summarise section 3" → long_context + RAG, cited
- "What's the latest on Mars missions?" (Internet ON) → factual + web verify, cited

## API
- `GET /api/models` – available Ollama Cloud models
- `GET /api/config` – router configuration
- `POST /api/chats`, `GET /api/chats`, `DELETE /api/chats/{id}`
- `POST /api/documents` (multipart), `GET /api/documents`, `DELETE /api/documents/{id}`
- `POST /api/chat/stream` – SSE harness pipeline
- `GET /api/stats` – model performance memory
