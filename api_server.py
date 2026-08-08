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
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
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
        audio_url = generate_audio(response_text, language=lang)
        
        return ChatResponse(response=response_text, audio_url=audio_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

