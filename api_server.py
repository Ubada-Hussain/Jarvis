"""
JARVIS API Server
-----------------
FastAPI + Uvicorn backend that exposes the MasterAgent over HTTP.
The React frontend (jarvis-ui) calls this server via /api/chat.

Run with:
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.master_agent import MasterAgent

# ─── App Initialization ────────────────────────────────────────────────────────
app = FastAPI(
    title="JARVIS API",
    description="Backend API for the JARVIS multi-agent system.",
    version="1.0.0",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allows the Vite dev server (http://localhost:5173) to call this backend.
# Tighten origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Singleton Initialization ─────────────────────────────────────────────────
# These are expensive — initialize once on startup, not per request.
print("=================================================")
print("  JARVIS API Server Starting...")
print("=================================================")
_memory = MemoryManager()
_llm = LLMEngine()
_master_agent = MasterAgent(_llm, _memory, approval_manager=None)
print("\n[SERVER] JARVIS MasterAgent ready. Awaiting requests.\n")


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    agent_used: str | None = None


class PingResponse(BaseModel):
    status: str
    message: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/ping", response_model=PingResponse, tags=["Health"])
async def ping():
    """
    Health check endpoint.
    The frontend calls this to verify the backend is reachable before
    sending real commands.
    """
    return PingResponse(status="ok", message="JARVIS API is online.")


@app.post("/api/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Passes the user's message to the MasterAgent which routes it to the
    appropriate sub-agent (DevAgent, SystemAgent, AcademicAgent, etc.)
    and returns the response.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        response_text = _master_agent.execute(request.message.strip())
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
