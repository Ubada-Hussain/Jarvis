"""
JARVIS API Server
-----------------
FastAPI + Uvicorn backend that exposes the MasterAgent over HTTP.
The React frontend (jarvis-ui) calls this server via /api/chat.

Run with:
    python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import sys
import io

# Force UTF-8 stdout/stderr on Windows to avoid cp1252 UnicodeEncodeError
# caused by emoji characters in dependency print statements.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from typing import List
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.llm_engine import LLMEngine
from core.memory_manager import MemoryManager
from agents.master_agent import MasterAgent

from contextlib import asynccontextmanager
import json

_wake_word_listener = None
main_loop = None

def handle_wake_word():
    message = json.dumps({"type": "wake_word"})
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), main_loop)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _wake_word_listener, main_loop
    main_loop = asyncio.get_running_loop()
    try:
        from io_manager.voice_listener import WakeWordListener
        _wake_word_listener = WakeWordListener(on_wake_word_detected=handle_wake_word)
        _wake_word_listener.start()
    except Exception as e:
        print(f"Wake word listener failed to start: {e}")
    yield
    if _wake_word_listener:
        _wake_word_listener.stop()

# ─── App Initialization ────────────────────────────────────────────────────────
app = FastAPI(
    title="JARVIS API",
    description="Backend API for the JARVIS multi-agent system.",
    version="1.0.0",
    lifespan=lifespan
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

from security.api_approval_manager import APIApprovalManager

# ─── Singleton Initialization ─────────────────────────────────────────────────
# These are expensive — initialize once on startup, not per request.
print("=================================================")
print("  JARVIS API Server Starting...")
print("=================================================")
_memory = MemoryManager()
_llm = LLMEngine()
_approval_manager = APIApprovalManager()
_master_agent = MasterAgent(_llm, _memory, approval_manager=_approval_manager)
print("\n[SERVER] JARVIS MasterAgent ready. Awaiting requests.\n")


from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File
import os
import shutil

# Mount static files for audio
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from core.tts_engine import generate_audio
from core.stt_engine import transcribe_audio

# ─── WebSocket State Manager ───────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.current_state = "idle"

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await websocket.send_text(self.current_state)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, state: str):
        self.current_state = state
        for connection in self.active_connections:
            try:
                await connection.send_text(state)
            except Exception:
                pass

ws_manager = ConnectionManager()

# ─── Agent Status WebSocket Manager ────────────────────────────────────────────
class AgentStatusManager:
    """Broadcasts real-time agent status (idle/working) to connected frontends."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send current agent states immediately on connect
        from agents.master_agent import agent_status
        await websocket.send_text(json.dumps(agent_status))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, status_dict: dict):
        payload = json.dumps(status_dict)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                self.active_connections.remove(connection)

agent_ws_manager = AgentStatusManager()

def _on_agent_status_change(status_dict: dict):
    """Called from MasterAgent threads when an agent's status changes."""
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(agent_ws_manager.broadcast(status_dict), main_loop)

# Register callback so MasterAgent can push status changes
from agents.master_agent import set_agent_status_callback
set_agent_status_callback(_on_agent_status_change)

# Helper function to fire and forget async broadcast from sync code if needed, 
# but FastAPI routes can just use await.
def broadcast_state_sync(state: str):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(state), main_loop)

# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    agent_used: str | None = None
    audio_url: str | None = None


class PingResponse(BaseModel):
    status: str
    message: str

class ApprovalRespondRequest(BaseModel):
    approved: bool

# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.websocket("/api/ws/state")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@app.websocket("/api/ws/agents")
async def agent_status_ws(websocket: WebSocket):
    await agent_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        agent_ws_manager.disconnect(websocket)

@app.get("/api/approval/status", tags=["Approval"])
async def approval_status():
    """
    Returns the currently pending action that requires approval, if any.
    """
    action = _approval_manager.get_pending_action()
    return {"pending_action": action}

@app.post("/api/approval/respond", tags=["Approval"])
async def approval_respond(request: ApprovalRespondRequest):
    """
    Responds to a pending approval request.
    """
    _approval_manager.respond(request.approved)
    return {"status": "ok"}

@app.get("/api/ping", response_model=PingResponse, tags=["Health"])
async def ping():
    return PingResponse(status="ok", message="JARVIS API is online.")


@app.post("/api/transcribe", tags=["Voice"])
async def transcribe(file: UploadFile = File(...)):
    """
    Accepts an audio file from the frontend and transcribes it using Groq Whisper.
    """
    temp_path = os.path.join(AUDIO_DIR, f"temp_{file.filename}")
    try:
        broadcast_state_sync("listening")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        broadcast_state_sync("thinking")
        transcription = transcribe_audio(temp_path)
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/api/chat", response_model=ChatResponse, tags=["Agent"])
def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Passes the user's message to the MasterAgent which routes it to the
    appropriate sub-agent (DevAgent, SystemAgent, AcademicAgent, etc.)
    and returns the response.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    broadcast_state_sync("thinking")

    try:
        response_text = _master_agent.execute(request.message.strip())
        
        # Determine language for TTS
        try:
            from langdetect import detect
            # default to english if detection fails
            lang = detect(response_text)
        except:
            lang = "en"
            
        # Map some common ISO codes
        if lang not in ["en", "ur", "pa"]:
            # If it detected hindi but it's close to urdu/punjabi script
            if lang == "hi":
                lang = "ur"
            else:
                lang = "en"
                
        # Generate Audio
        broadcast_state_sync("speaking")
        audio_url = generate_audio(response_text, language=lang)
        
        # Will return to idle after audio plays via frontend logic, or we could delay it here
        # But frontend is better positioned to know when audio finishes.
        
        return ChatResponse(response=response_text, audio_url=audio_url)
    except Exception as e:
        broadcast_state_sync("idle")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

