import os
import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional

from harness import ollama_client, rag
from harness import pipeline as harness_pipeline
from harness.config import MODEL_ROLES, CATEGORY_TO_ROLE, ROLE_NOTES

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI Harness Chat")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def new_id():
    return str(uuid.uuid4())


# ---------------- Models ----------------
class ChatCreate(BaseModel):
    title: Optional[str] = "New chat"


class ChatSettings(BaseModel):
    mode: str = "auto"            # auto | manual
    manual_model: Optional[str] = None
    use_rag: bool = True
    use_web: bool = False


class SendMessage(BaseModel):
    chat_id: str
    message: str
    mode: str = "auto"
    manual_model: Optional[str] = None
    use_rag: bool = True
    use_web: bool = False


# ---------------- Basic ----------------
@api_router.get("/")
async def root():
    return {"message": "AI Harness Chat API"}


@api_router.get("/models")
async def get_models():
    try:
        models = await ollama_client.list_models()
    except Exception as e:
        logger.error(f"list_models failed: {e}")
        raise HTTPException(status_code=502, detail="Could not reach Ollama Cloud")
    return {"models": models}


@api_router.get("/config")
async def get_config():
    """Expose the router configuration (example model router config)."""
    return {
        "model_roles": MODEL_ROLES,
        "category_to_role": CATEGORY_TO_ROLE,
        "role_notes": ROLE_NOTES,
    }


# ---------------- Chats ----------------
@api_router.post("/chats")
async def create_chat(body: ChatCreate):
    chat = {"id": new_id(), "title": body.title or "New chat", "created_at": now_iso(), "updated_at": now_iso()}
    await db.chats.insert_one(dict(chat))
    return chat


@api_router.get("/chats")
async def list_chats():
    chats = await db.chats.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return chats


@api_router.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str):
    msgs = await db.messages.find({"chat_id": chat_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return msgs


@api_router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    await db.chats.delete_one({"id": chat_id})
    await db.messages.delete_many({"chat_id": chat_id})
    return {"ok": True}


@api_router.patch("/chats/{chat_id}")
async def rename_chat(chat_id: str, body: ChatCreate):
    await db.chats.update_one({"id": chat_id}, {"$set": {"title": body.title, "updated_at": now_iso()}})
    return {"ok": True}


# ---------------- Documents ----------------
@api_router.post("/documents")
async def upload_document(file: UploadFile = File(...), chat_id: Optional[str] = Form(None)):
    data = await file.read()
    try:
        text = rag.extract_text(file.filename, data)
    except Exception as e:
        logger.error(f"extract failed: {e}")
        raise HTTPException(status_code=400, detail="Could not parse document")
    chunks = rag.chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No text extracted from document")

    doc_id = new_id()
    doc = {
        "id": doc_id,
        "chat_id": chat_id,
        "name": file.filename,
        "size": len(data),
        "num_chunks": len(chunks),
        "created_at": now_iso(),
    }
    await db.documents.insert_one(dict(doc))
    chunk_docs = [
        {"id": new_id(), "document_id": doc_id, "chat_id": chat_id, "document_name": file.filename,
         "index": i, "text": c}
        for i, c in enumerate(chunks)
    ]
    await db.document_chunks.insert_many([dict(c) for c in chunk_docs])
    return doc


@api_router.get("/documents")
async def list_documents(chat_id: Optional[str] = None):
    q = {}
    if chat_id:
        q = {"$or": [{"chat_id": chat_id}, {"chat_id": None}]}
    docs = await db.documents.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    await db.documents.delete_one({"id": doc_id})
    await db.document_chunks.delete_many({"document_id": doc_id})
    return {"ok": True}


# ---------------- Chat streaming (the harness) ----------------
async def _load_chunks_for_chat(chat_id):
    chunks = await db.document_chunks.find({"chat_id": chat_id}, {"_id": 0}).to_list(5000)
    return chunks


@api_router.post("/chat/stream")
async def chat_stream(body: SendMessage):
    # persist user message
    history = await db.messages.find({"chat_id": body.chat_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    user_msg = {
        "id": new_id(), "chat_id": body.chat_id, "role": "user",
        "content": body.message, "created_at": now_iso(),
    }
    await db.messages.insert_one(dict(user_msg))

    # auto-title chat from first user message
    if not history:
        title = body.message.strip()[:60] or "New chat"
        await db.chats.update_one({"id": body.chat_id}, {"$set": {"title": title, "updated_at": now_iso()}})
    else:
        await db.chats.update_one({"id": body.chat_id}, {"$set": {"updated_at": now_iso()}})

    chunk_docs = await _load_chunks_for_chat(body.chat_id) if body.use_rag else []

    async def event_gen():
        final_meta = None
        try:
            async for event in harness_pipeline.run_pipeline(
                user_message=body.message,
                history=history,
                mode=body.mode,
                manual_model=body.manual_model,
                use_rag=body.use_rag,
                use_web=body.use_web,
                chunk_docs=chunk_docs,
            ):
                if event["type"] == "done":
                    final_meta = event
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.exception("pipeline error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        if final_meta:
            assistant_msg = {
                "id": new_id(), "chat_id": body.chat_id, "role": "assistant",
                "content": final_meta["content"], "created_at": now_iso(),
                "meta": {
                    "model": final_meta["model"], "role": final_meta["role"],
                    "category": final_meta["category"], "route_reason": final_meta["route_reason"],
                    "used_rag": final_meta["used_rag"], "used_web": final_meta["used_web"],
                    "sources": final_meta["sources"], "validation": final_meta["validation"],
                    "repaired": final_meta["repaired"], "confidence": final_meta["confidence"],
                    "verify_status": final_meta["verify_status"],
                },
            }
            await db.messages.insert_one(dict(assistant_msg))
            # Model Performance Memory log
            await db.model_runs.insert_one({
                "id": new_id(), "chat_id": body.chat_id, "created_at": now_iso(),
                "category": final_meta["category"], "model": final_meta["model"],
                "role": final_meta["role"], "used_rag": final_meta["used_rag"],
                "used_web": final_meta["used_web"], "repaired": final_meta["repaired"],
                "confidence": final_meta["confidence"], "verify_status": final_meta["verify_status"],
                "validation_issues": final_meta["validation"].get("issues", []),
            })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@api_router.get("/stats")
async def stats():
    """Model Performance Memory summary."""
    runs = await db.model_runs.find({}, {"_id": 0}).to_list(5000)
    by_model = {}
    for r in runs:
        m = r["model"]
        d = by_model.setdefault(m, {"runs": 0, "avg_confidence": 0, "repairs": 0})
        d["runs"] += 1
        d["avg_confidence"] += r.get("confidence", 0)
        d["repairs"] += 1 if r.get("repaired") else 0
    for m, d in by_model.items():
        d["avg_confidence"] = round(d["avg_confidence"] / d["runs"], 1) if d["runs"] else 0
    return {"total_runs": len(runs), "by_model": by_model}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
