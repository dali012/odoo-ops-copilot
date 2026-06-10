from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from .agent import stream_chat
from .config import config
from .odoo_client import odoo
from .session_store import (
    create_session,
    get_session_engine,
    get_session_snapshot,
    init_session_store,
    list_writeback_actions,
    session_exists,
)
from .writeback import WritebackError, execute_writeback, reject_writeback


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_session_store()
    yield


app = FastAPI(title="Odoo Ops Copilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.BACKEND_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class SessionOut(BaseModel):
    session_id: str


@app.get("/health")
def health():
    checks: dict[str, str] = {"postgres": "ok", "odoo": "ok"}

    try:
        with get_session_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        checks["postgres"] = "error"

    try:
        odoo.execute("res.company", "search", [], limit=1)
    except Exception:
        checks["odoo"] = "error"

    ok = all(status == "ok" for status in checks.values())
    status_code = 200 if ok else 503
    return JSONResponse({"ok": ok, **checks}, status_code=status_code)


@app.post("/chat/sessions", response_model=SessionOut)
def create_chat_session():
    return {"session_id": create_session()}


@app.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str):
    snapshot = get_session_snapshot(session_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return snapshot


@app.get("/chat/sessions/{session_id}/writebacks")
def get_session_writebacks(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {"actions": list_writeback_actions(session_id)}


@app.post("/chat/stream")
async def chat_stream_endpoint(body: ChatIn):
    if not body.session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    if not session_exists(body.session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")

    return StreamingResponse(
        stream_chat(body.message, body.session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _assert_writes_allowed() -> None:
    if config.DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail="Write-back is disabled in demo mode. Fork the repo and run locally to approve actions.",
        )


@app.post("/writebacks/{action_id}/approve")
def approve_writeback(action_id: str):
    _assert_writes_allowed()
    try:
        return execute_writeback(action_id)
    except WritebackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/writebacks/{action_id}/reject")
def reject_writeback_endpoint(action_id: str):
    _assert_writes_allowed()
    try:
        return reject_writeback(action_id)
    except WritebackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
