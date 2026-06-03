"""
TFNK™ Main FastAPI Server
Full REST + WebSocket API integrating all backend modules.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root is on sys.path
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent_runtime import AgentRuntime, TaskState, get_agent_runtime
from src.cloud_client import get_cloud_client
from src.config import get_settings, reload_settings
from src.connections import get_connection_monitor
from src.controller import get_controller
from src.files import get_file_manager
from src.intel import get_intel_manager
from src.mobile_bridge import get_mobile_bridge
from src.scheduler import get_scheduler
from src.skills import get_skills_manager
from src.text_fix import get_text_fixer
from src.voice import get_voice_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tfnk.server")


# ── WebSocket manager ─────────────────────────────────────────────────────────

class WSManager:
    """Manages multiple categories of WebSocket connections."""

    def __init__(self) -> None:
        self.chat: List[WebSocket] = []
        self.stats: List[WebSocket] = []
        self.voice: List[WebSocket] = []

    async def broadcast(self, sockets: List[WebSocket], data: Any) -> None:
        dead: List[WebSocket] = []
        message = json.dumps(data, ensure_ascii=False, default=str)
        for ws in list(sockets):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in sockets:
                sockets.remove(ws)


ws_manager = WSManager()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle manager."""
    settings = get_settings()
    logger.info("TFNK™ 伺服器啟動中...")

    # Initialize directories
    for d in [settings.get_backup_dir(), settings.get_log_dir(),
               settings.get_memory_dir(), settings.get_skills_dir()]:
        d.mkdir(parents=True, exist_ok=True)

    # Start scheduler
    scheduler = get_scheduler()
    scheduler.start()

    # Start connection monitor
    monitor = get_connection_monitor()
    monitor.start_auto_check()

    # Register connection change broadcast
    async def _broadcast_conn_change(conn: Any) -> None:
        await ws_manager.broadcast(ws_manager.stats, {
            "type": "connection_change",
            "connection": conn.to_dict(),
        })
    monitor.on_change(_broadcast_conn_change)

    # Start stats streaming task
    stats_task = asyncio.create_task(_stats_streamer())

    # Load file manager locks
    fm = get_file_manager()
    fm.load_persisted_locks()

    logger.info("TFNK™ 伺服器已就緒 http://%s:%d",
                settings.server_host, settings.server_port)

    yield

    # Shutdown
    logger.info("TFNK™ 伺服器關閉中...")
    stats_task.cancel()
    scheduler.stop()
    monitor.stop_auto_check()
    fm.stop_watching()
    logger.info("TFNK™ 伺服器已關閉")


async def _stats_streamer() -> None:
    """Background task: push system stats to connected WebSocket clients every 2s."""
    controller = get_controller()
    while True:
        try:
            if ws_manager.stats:
                stats = controller.get_system_stats()
                await ws_manager.broadcast(ws_manager.stats, {
                    "type": "stats",
                    "data": stats,
                    "ts": datetime.utcnow().isoformat(),
                })
        except Exception as exc:
            logger.debug("統計廣播錯誤: %s", exc)
        await asyncio.sleep(2)


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="TFNK™ API",
    description="TFNK™ Autonomous Agent Backend",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── Request/Response Models ───────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None
    mode: Optional[str] = None  # basic | thinking | collaborative
    conversation_id: Optional[str] = None
    stream: bool = True


class SelectModelRequest(BaseModel):
    model: str
    provider: str = "ollama"


class TaskCreateRequest(BaseModel):
    description: str
    task_type: str = "once"
    priority: int = 2
    interval_seconds: Optional[int] = None
    cron_expression: Optional[str] = None
    run_at: Optional[str] = None
    estimated_duration_seconds: int = 60


class TaskUpdateRequest(BaseModel):
    description: Optional[str] = None
    priority: Optional[int] = None
    state: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    agent_mode: Optional[str] = None
    tool_policies: Optional[Dict[str, str]] = None
    lock_list: Optional[List[str]] = None


class SearchRequest(BaseModel):
    query: str
    num: int = 10


class ImageTranslateRequest(BaseModel):
    image_base64: Optional[str] = None


class ImageGenRequest(BaseModel):
    prompt: str
    model: str = "flux"
    width: int = 1024
    height: int = 1024


class LockRequest(BaseModel):
    path: str


class SkillSearchRequest(BaseModel):
    query: str
    limit: int = 10


class YouTubeSearchRequest(BaseModel):
    query: str
    max_results: int = 10


class YouTubeDownloadRequest(BaseModel):
    url: str
    audio_only: bool = False
    output_dir: str = "/tmp/tfnk_downloads"


class IntelRefreshRequest(BaseModel):
    section: Optional[str] = None  # all | models | news | free | agents | tools


# ── Auth helper ───────────────────────────────────────────────────────────────

def _get_current_model() -> Dict[str, str]:
    """Return currently selected model info from settings."""
    settings = get_settings()
    return {
        "model": settings.model_for_mode(),
        "provider": "anthropic" if settings.anthropic_api_key else "ollama",
        "mode": settings.agent_mode,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    """Serve the main UI or a status page."""
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return HTMLResponse(content=index.read_text(encoding="utf-8"))
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head><title>TFNK™</title>
<style>body{font-family:Rajdhani,sans-serif;background:#0a0a0a;color:#e0e0e0;display:flex;
align-items:center;justify-content:center;height:100vh;flex-direction:column;}
h1{color:#f97316;font-size:3rem;letter-spacing:0.2em;}
p{color:#6b7280;}a{color:#3b82f6;}</style>
</head>
<body>
<h1>TFNK™</h1>
<p>伺服器運行中。前端 UI 未找到。</p>
<p><a href="/api/docs">API 文件</a> | <a href="/api/health">健康檢查</a></p>
</body></html>
""")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check() -> JSONResponse:
    settings = get_settings()
    return JSONResponse({
        "status": "ok",
        "app": "TFNK™",
        "mode": settings.agent_mode,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    })


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint.
    Returns Server-Sent Events (text/event-stream).
    """
    settings = get_settings()

    if req.mode:
        settings.agent_mode = req.mode

    model = req.model or settings.model_for_mode()
    provider = req.provider or (
        "anthropic" if settings.anthropic_api_key else "ollama"
    )

    system_prompt = (
        "你是 TFNK™ 智能助理。請用繁體中文（廣東話風格）回答所有問題。"
        "保持專業但親切的語氣。如果用戶用英文提問，仍用繁體中文回答。"
    )

    messages = [{"role": "user", "content": req.message}]

    async def _generate() -> AsyncIterator[str]:
        try:
            cloud = get_cloud_client()
            if provider == "anthropic" and settings.anthropic_api_key:
                async for chunk in cloud.anthropic_chat_stream(model, messages, system_prompt):
                    yield f"data: {json.dumps({'content': chunk, 'done': False}, ensure_ascii=False)}\n\n"
            elif provider == "groq" and settings.groq_api_key:
                async for chunk in cloud.groq_chat_stream(model, messages, system_prompt):
                    yield f"data: {json.dumps({'content': chunk, 'done': False}, ensure_ascii=False)}\n\n"
            elif provider == "ollama":
                async for chunk in cloud.ollama_chat_stream(model, messages, system_prompt):
                    yield f"data: {json.dumps({'content': chunk, 'done': False}, ensure_ascii=False)}\n\n"
            else:
                # Fallback: non-streaming
                result = await cloud.chat(provider, model, messages, system_prompt)
                yield f"data: {json.dumps({'content': result, 'done': False}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("聊天錯誤: %s", exc)
            yield f"data: {json.dumps({'content': f'錯誤: {exc}', 'done': False, 'error': True}, ensure_ascii=False)}\n\n"
        finally:
            yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Models ────────────────────────────────────────────────────────────────────

@app.get("/api/models")
async def list_models() -> JSONResponse:
    """List all available models (Ollama local + cloud)."""
    cloud = get_cloud_client()
    settings = get_settings()
    models: List[Dict[str, Any]] = []

    # Ollama local models
    try:
        ollama_models = await cloud.ollama_list_models()
        models.extend(ollama_models)
    except Exception as exc:
        logger.debug("Ollama 模型列表失敗: %s", exc)

    # Free cloud models
    from src.intel import FREE_MODELS_STATIC
    for m in FREE_MODELS_STATIC[:6]:
        models.append({
            "name": m["name"],
            "provider": m["provider"],
            "context_window": m["context"],
            "type": m["type"],
            "source": "cloud_free",
        })

    # Current selection
    current = _get_current_model()

    return JSONResponse({
        "models": models,
        "current": current,
        "active_model": current.get("id", ""),  # frontend alias
        "mode": settings.agent_mode,
    })


@app.post("/api/select-model")
async def select_model(req: SelectModelRequest) -> JSONResponse:
    """Select the active model."""
    settings = get_settings()
    # Store model selection in memory
    mem_file = settings.get_memory_dir() / "selected_model.json"
    mem_file.write_text(
        json.dumps({"model": req.model, "provider": req.provider,
                    "updated_at": datetime.utcnow().isoformat()},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    return JSONResponse({"status": "ok", "model": req.model, "provider": req.provider})


# ── System Stats ──────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats() -> JSONResponse:
    """Return current system stats."""
    controller = get_controller()
    stats = controller.get_system_stats()
    return JSONResponse(stats)


# ── Connections ───────────────────────────────────────────────────────────────

@app.get("/api/connections")
async def get_connections() -> JSONResponse:
    """Return all connection statuses as list (frontend expects {connections: [...]})."""
    monitor = get_connection_monitor()
    raw = monitor.get_all()
    # raw is {name: dict} — convert to [{name, ...}, ...]
    connections = [{"name": k, **v} for k, v in raw.items()]
    return JSONResponse({"connections": connections})


@app.post("/api/connections/check")
async def force_check_connections() -> JSONResponse:
    """Force immediate re-check of all connections."""
    monitor = get_connection_monitor()
    result = await monitor.check_all()
    connections = [{"name": k, **v} for k, v in result.items()]
    return JSONResponse({"connections": connections})


@app.delete("/api/connections/{name}")
async def remove_connection(name: str) -> JSONResponse:
    monitor = get_connection_monitor()
    removed = monitor.remove_connection(name)
    if not removed:
        raise HTTPException(404, f"連接不存在: {name}")
    return JSONResponse({"status": "ok", "removed": name})


# ── Tasks ─────────────────────────────────────────────────────────────────────

@app.get("/api/tasks")
async def list_tasks() -> JSONResponse:
    """List all tasks. Frontend expects {tasks: [{id, label, status, progress, ...}]}."""
    agent = get_agent_runtime()
    scheduler = get_scheduler()

    def _norm_agent_task(t: dict) -> dict:
        return {
            "id":                 t.get("task_id") or t.get("id", ""),
            "label":              t.get("label") or t.get("description", "")[:60],
            "status":             t.get("status", "PENDING"),
            "progress":           t.get("progress", 0),
            "started_at":         t.get("started_at"),
            "estimated_remaining":t.get("estimated_remaining"),
            "current_step":       t.get("current_step"),
            "requires_auth":      t.get("requires_auth", False),
            "estimated_total":    t.get("estimated_total", 60),
        }

    def _norm_sched_task(t: dict) -> dict:
        return {
            "id":                 t.get("task_id", ""),
            "label":              t.get("name", ""),
            "status":             {"running": "RUNNING", "paused": "PAUSED",
                                   "pending": "PENDING", "completed": "COMPLETED",
                                   "failed": "FAILED"}.get(t.get("state", "pending"), "PENDING"),
            "progress":           t.get("progress", 0),
            "started_at":         t.get("last_run"),
            "estimated_remaining":None,
            "current_step":       None,
            "requires_auth":      False,
            "estimated_total":    t.get("estimated_duration_seconds", 60),
        }

    agent_tasks = [_norm_agent_task(t) for t in (agent.list_tasks() or [])]
    sched_tasks = [_norm_sched_task(t) for t in (scheduler.list_tasks() or [])]
    all_tasks = agent_tasks + sched_tasks

    return JSONResponse({
        "tasks": all_tasks,
        "gantt": scheduler.get_gantt_data(),
    })


@app.post("/api/tasks")
async def create_task(req: TaskCreateRequest) -> JSONResponse:
    """Create a new agent task and start it."""
    agent = get_agent_runtime()
    task = await agent.create_task(req.description)
    await agent.start_task(task.task_id)
    return JSONResponse(task.to_dict(), status_code=201)


@app.put("/api/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdateRequest) -> JSONResponse:
    """Update task properties."""
    agent = get_agent_runtime()
    task = agent.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任務不存在: {task_id}")
    if req.description:
        task.description = req.description
    return JSONResponse(task.to_dict())


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, confirmed: bool = Query(False)) -> JSONResponse:
    """Delete/cancel a task. Requires confirmed=true."""
    if not confirmed:
        raise HTTPException(
            400,
            "刪除任務需要明確確認。請添加 ?confirmed=true 參數。"
        )
    agent = get_agent_runtime()
    task = agent.get_task(task_id)
    if not task:
        # Try scheduler
        scheduler = get_scheduler()
        scheduler.remove_task(task_id)
        return JSONResponse({"status": "ok", "deleted": task_id})
    await agent.cancel_task(task_id)
    return JSONResponse({"status": "ok", "deleted": task_id})


@app.post("/api/tasks/{task_id}/start")
async def start_task(task_id: str) -> JSONResponse:
    agent = get_agent_runtime()
    task = agent.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任務不存在: {task_id}")
    await agent.start_task(task_id)
    return JSONResponse(task.to_dict())


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: str) -> JSONResponse:
    agent = get_agent_runtime()
    task = agent.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任務不存在: {task_id}")
    await agent.pause_task(task_id)
    return JSONResponse(task.to_dict())


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> JSONResponse:
    agent = get_agent_runtime()
    task = agent.get_task(task_id)
    if not task:
        raise HTTPException(404, f"任務不存在: {task_id}")
    await agent.cancel_task(task_id)
    return JSONResponse(task.to_dict())


# ── Voice ─────────────────────────────────────────────────────────────────────

@app.get("/api/voice/status")
async def voice_status() -> JSONResponse:
    voice = get_voice_manager()
    return JSONResponse(voice.get_status())


@app.post("/api/voice/tts")
async def text_to_speech(req: TTSRequest) -> Response:
    """Convert text to speech. Returns MP3 audio bytes."""
    voice = get_voice_manager()
    try:
        audio_bytes = await voice.speak(req.text)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=tts.mp3"},
        )
    except Exception as exc:
        raise HTTPException(500, f"TTS 失敗: {exc}")


@app.post("/api/voice/stt")
async def speech_to_text(audio: UploadFile = File(...)) -> JSONResponse:
    """Convert uploaded audio to text (Cantonese STT)."""
    voice = get_voice_manager()
    try:
        audio_bytes = await audio.read()
        corrected, original = await voice.transcribe_and_fix(audio_bytes)
        return JSONResponse({
            "text": corrected,
            "original": original,
            "language": "zh-HK",
        })
    except Exception as exc:
        raise HTTPException(500, f"STT 失敗: {exc}")


# ── Intelligence Center ───────────────────────────────────────────────────────

@app.get("/api/intel/models")
async def get_intel_models() -> JSONResponse:
    intel = get_intel_manager()
    return JSONResponse({"models": intel.get_model_comparison()})


@app.get("/api/intel/news")
async def get_intel_news() -> JSONResponse:
    intel = get_intel_manager()
    news = intel.get_ai_news()
    return JSONResponse({"items": news, "news": news, "last_updated": intel.last_updated})


@app.get("/api/intel/free-models")
async def get_free_models() -> JSONResponse:
    intel = get_intel_manager()
    free = intel.get_free_models()
    return JSONResponse({"models": free, "free_models": free, "last_updated": intel.last_updated})


@app.get("/api/intel/agents")
async def get_agent_comparison() -> JSONResponse:
    intel = get_intel_manager()
    return JSONResponse({"agents": intel.get_agent_comparison()})


@app.get("/api/intel/tools")
async def get_popular_tools() -> JSONResponse:
    intel = get_intel_manager()
    tools = intel.get_popular_tools()
    return JSONResponse({"categories": tools, "tools": tools})


@app.post("/api/intel/refresh")
async def refresh_intel(
    req: IntelRefreshRequest, background: BackgroundTasks
) -> JSONResponse:
    """Trigger async refresh of intelligence data."""
    intel = get_intel_manager()
    background.add_task(intel.update_all)
    return JSONResponse({"status": "ok", "message": "情報更新已在後台啟動"})


# ── Config ────────────────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config() -> JSONResponse:
    """Return non-sensitive configuration."""
    settings = get_settings()
    return JSONResponse({
        "mode": settings.agent_mode,          # frontend alias
        "agent_mode": settings.agent_mode,
        "tts_voice": getattr(settings, "tts_voice", "zh-HK-HiuMaanNeural"),
        "wake_word": getattr(settings, "wake_word", "嘿 TFNK"),
        "tool_policies": settings.tool_policies,
        "lock_list": settings.lock_list_parsed,
        "ollama_base_url": settings.ollama_base_url,
        "server_host": settings.server_host,
        "server_port": settings.server_port,
        "debug": settings.debug,
        "has_anthropic_key": bool(settings.anthropic_api_key),
        "has_openai_key": bool(settings.openai_api_key),
        "has_google_key": bool(settings.google_api_key),
        "has_groq_key": bool(settings.groq_api_key),
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_youtube_key": bool(settings.youtube_api_key),
        "has_finnhub_key": bool(settings.finnhub_api_key),
    })


@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest) -> JSONResponse:
    """Update runtime configuration."""
    settings = get_settings()
    agent = get_agent_runtime()

    if req.agent_mode:
        settings.agent_mode = req.agent_mode
        agent.set_mode(req.agent_mode)

    if req.tool_policies:
        for tool, policy in req.tool_policies.items():
            if policy not in ("allow", "deny", "confirm"):
                raise HTTPException(400, f"無效的策略值: {policy}")
            setattr(settings, f"tool_policy_{tool}", policy)

    if req.lock_list is not None:
        fm = get_file_manager()
        for path in req.lock_list:
            fm.add_lock(path)

    return JSONResponse({"status": "ok", "mode": settings.agent_mode})


# ── Skills ────────────────────────────────────────────────────────────────────

@app.get("/api/skills")
async def list_skills() -> JSONResponse:
    skills = get_skills_manager()
    return JSONResponse({"skills": skills.list_skills()})


@app.post("/api/skills/search")
async def search_skills(req: SkillSearchRequest) -> JSONResponse:
    skills = get_skills_manager()
    results = skills.search_skills(req.query, limit=req.limit)
    return JSONResponse({"results": [s.to_dict() for s in results]})


# ── Memory ────────────────────────────────────────────────────────────────────

@app.get("/api/memory")
async def list_memory(limit: int = Query(50)) -> JSONResponse:
    agent = get_agent_runtime()
    entries = agent.list_memory()
    return JSONResponse({"entries": entries[-limit:], "total": len(entries)})


# ── File Locks ────────────────────────────────────────────────────────────────

@app.get("/api/files/locks")
async def list_locks() -> JSONResponse:
    fm = get_file_manager()
    return JSONResponse({"locks": fm.list_locks()})


@app.post("/api/files/locks")
async def add_lock(req: LockRequest) -> JSONResponse:
    fm = get_file_manager()
    fm.add_lock(req.path)
    return JSONResponse({"status": "ok", "locked": req.path})


@app.delete("/api/files/locks/{path:path}")
async def remove_lock(path: str) -> JSONResponse:
    fm = get_file_manager()
    fm.remove_lock(path)
    return JSONResponse({"status": "ok", "unlocked": path})


# ── Image Generation ──────────────────────────────────────────────────────────

@app.post("/api/imagegen")
async def generate_image(req: ImageGenRequest) -> Response:
    """Generate an image using FLUX or SDXL."""
    cloud = get_cloud_client()
    try:
        if req.model.lower() in ("flux", "flux.1"):
            image_bytes = await cloud.generate_image_flux(
                req.prompt, req.width, req.height
            )
        else:
            image_bytes = await cloud.generate_image_sdxl(req.prompt)
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=generated.png"},
        )
    except Exception as exc:
        raise HTTPException(500, f"圖像生成失敗: {exc}")


# ── Google Custom Search ──────────────────────────────────────────────────────

@app.post("/api/search")
async def google_search(req: SearchRequest) -> JSONResponse:
    cloud = get_cloud_client()
    try:
        results = await cloud.google_search(req.query, req.num)
        return JSONResponse({"results": results, "query": req.query})
    except Exception as exc:
        raise HTTPException(500, f"搜索失敗: {exc}")


# ── Image Translation ─────────────────────────────────────────────────────────

@app.post("/api/translate-image")
async def translate_image(
    image: Optional[UploadFile] = File(None),
    image_base64: Optional[str] = Form(None),
) -> Response:
    """In-place translate all text in an image to Traditional Chinese."""
    from src.screen_translate import get_screen_translator
    translator = get_screen_translator()

    try:
        if image:
            image_bytes = await image.read()
            filename = image.filename or "input.png"
        elif image_base64:
            import base64
            image_bytes = base64.b64decode(image_base64)
            filename = "input.png"
        else:
            raise HTTPException(400, "請提供 image 文件或 image_base64")

        result_bytes = translator.translate_image_bytes(image_bytes, filename)
        return Response(
            content=result_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=translated.png"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"圖像翻譯失敗: {exc}")


# ── Knowledge / Relation Graph ────────────────────────────────────────────────

@app.get("/api/graph")
async def get_graph() -> JSONResponse:
    """Return knowledge graph data for visualization."""
    agent = get_agent_runtime()
    skills = get_skills_manager()
    memory = agent.list_memory()
    all_skills = skills.list_skills()

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Add task nodes
    for task in agent.list_tasks()[:20]:
        nodes.append({
            "id": f"task_{task['task_id']}",
            "label": task["description"][:30],
            "type": "task",
            "state": task["state"],
        })

    # Add skill nodes
    for skill in all_skills[:20]:
        skill_id = f"skill_{skill['skill_id']}"
        nodes.append({
            "id": skill_id,
            "label": skill["name"][:30],
            "type": "skill",
            "success_count": skill["success_count"],
        })

    # Add memory nodes (sampled)
    for i, entry in enumerate(memory[-10:]):
        mem_id = f"mem_{i}"
        nodes.append({
            "id": mem_id,
            "label": entry.get("content", "")[:20],
            "type": "memory",
        })

    return JSONResponse({
        "nodes": nodes,
        "links": edges,   # D3.js convention used by graph.js panel
        "edges": edges,   # keep for backwards compat
        "meta": {
            "task_count": len(agent.list_tasks()),
            "skill_count": len(all_skills),
            "memory_count": len(memory),
        },
    })


# ── Emergency Stop ────────────────────────────────────────────────────────────

@app.post("/api/emergency-stop")
async def emergency_stop() -> JSONResponse:
    """Immediately halt all agent activity."""
    agent = get_agent_runtime()
    agent.emergency_stop()
    logger.warning("緊急停止已觸發")
    return JSONResponse({
        "status": "stopped",
        "message": "所有代理活動已停止",
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.post("/api/emergency-resume")
async def emergency_resume() -> JSONResponse:
    """Resume after emergency stop."""
    agent = get_agent_runtime()
    agent.resume_after_stop()
    return JSONResponse({"status": "resumed"})


# ── Mobile Bridge ─────────────────────────────────────────────────────────────

@app.get("/api/mobile/pending")
async def mobile_pending_auths() -> JSONResponse:
    bridge = get_mobile_bridge()
    return JSONResponse({
        "pending": bridge.get_pending_authorizations(),
        "status": bridge.get_status(),
    })


@app.post("/api/mobile/authorize/{auth_id}")
async def mobile_authorize(
    auth_id: str, approved: bool = Query(True)
) -> JSONResponse:
    """Approve or deny a pending mobile authorization."""
    bridge = get_mobile_bridge()
    await bridge.resolve_authorization(auth_id, approved)
    return JSONResponse({
        "status": "ok",
        "auth_id": auth_id,
        "approved": approved,
    })


@app.post("/api/mobile/continue/{task_id}")
async def mobile_continue_task(task_id: str) -> JSONResponse:
    """Signal that a paused task should continue."""
    bridge = get_mobile_bridge()
    await bridge.resolve_task_continue(task_id)
    return JSONResponse({"status": "ok", "task_id": task_id})


# ── Screenshot ────────────────────────────────────────────────────────────────

@app.get("/api/screenshot")
async def take_screenshot() -> Response:
    """Capture a full-screen screenshot."""
    controller = get_controller()
    try:
        png_bytes = controller.take_screenshot()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as exc:
        raise HTTPException(500, f"截圖失敗: {exc}")


# ── YouTube ───────────────────────────────────────────────────────────────────

@app.get("/api/youtube/search")
async def youtube_search(q: str = Query(...), max_results: int = Query(10)) -> JSONResponse:
    cloud = get_cloud_client()
    try:
        results = await cloud.youtube_search(q, max_results)
        return JSONResponse({"results": results, "query": q})
    except Exception as exc:
        raise HTTPException(500, f"YouTube 搜索失敗: {exc}")


@app.post("/api/youtube/download")
async def youtube_download(
    req: YouTubeDownloadRequest, background: BackgroundTasks
) -> JSONResponse:
    """Start YouTube download in background."""
    cloud = get_cloud_client()

    # Create output dir
    Path(req.output_dir).mkdir(parents=True, exist_ok=True)

    download_id = str(uuid.uuid4())

    async def _dl() -> None:
        try:
            info = await cloud.youtube_download(
                req.url, req.output_dir, audio_only=req.audio_only
            )
            logger.info("下載完成: %s", info.get("title"))
        except Exception as exc:
            logger.error("下載失敗: %s", exc)

    background.add_task(_dl)
    return JSONResponse({
        "status": "downloading",
        "download_id": download_id,
        "url": req.url,
        "output_dir": req.output_dir,
    })


# ── Text Fix ──────────────────────────────────────────────────────────────────

@app.post("/api/text-fix")
async def fix_text(text: str = Form(...)) -> JSONResponse:
    fixer = get_text_fixer()
    corrected, changes = fixer.fix(text)
    return JSONResponse({
        "original": text,
        "corrected": corrected,
        "changes": changes,
    })


# ── Finance (basic proxy) ─────────────────────────────────────────────────────

@app.get("/api/finance/quote/{symbol}")
async def get_stock_quote(symbol: str) -> JSONResponse:
    """Get stock quote via yfinance."""
    try:
        import yfinance as yf  # type: ignore
        ticker = yf.Ticker(symbol.upper())
        info = ticker.fast_info
        return JSONResponse({
            "symbol": symbol.upper(),
            "price": info.last_price,
            "currency": info.currency,
            "exchange": info.exchange,
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as exc:
        raise HTTPException(500, f"股價查詢失敗: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    """
    Real-time chat WebSocket.
    Client sends: {"message": "...", "model": "...", "provider": "...", "mode": "..."}
    Server streams: {"content": "...", "done": false} ... {"content": "", "done": true}
    """
    await ws.accept()
    ws_manager.chat.append(ws)
    settings = get_settings()
    cloud = get_cloud_client()

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            message = data.get("message", "")
            model = data.get("model") or settings.model_for_mode()
            provider = data.get("provider") or (
                "anthropic" if settings.anthropic_api_key else "ollama"
            )
            mode = data.get("mode", settings.agent_mode)
            settings.agent_mode = mode

            system_prompt = (
                "你是 TFNK™ 智能助理。請用繁體中文（廣東話風格）回答所有問題。"
                "保持專業、簡潔。"
            )
            messages = [{"role": "user", "content": message}]

            try:
                if provider == "anthropic" and settings.anthropic_api_key:
                    async for chunk in cloud.anthropic_chat_stream(model, messages, system_prompt):
                        await ws.send_text(json.dumps({
                            "content": chunk, "done": False
                        }, ensure_ascii=False))
                elif provider == "groq" and settings.groq_api_key:
                    async for chunk in cloud.groq_chat_stream(model, messages, system_prompt):
                        await ws.send_text(json.dumps({
                            "content": chunk, "done": False
                        }, ensure_ascii=False))
                elif provider == "ollama":
                    async for chunk in cloud.ollama_chat_stream(model, messages, system_prompt):
                        await ws.send_text(json.dumps({
                            "content": chunk, "done": False
                        }, ensure_ascii=False))
                else:
                    result = await cloud.chat(provider, model, messages, system_prompt)
                    await ws.send_text(json.dumps({
                        "content": result, "done": False
                    }, ensure_ascii=False))
            except Exception as exc:
                await ws.send_text(json.dumps({
                    "content": f"錯誤: {exc}", "done": False, "error": True
                }, ensure_ascii=False))
            finally:
                await ws.send_text(json.dumps({"content": "", "done": True}, ensure_ascii=False))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS Chat 錯誤: %s", exc)
    finally:
        if ws in ws_manager.chat:
            ws_manager.chat.remove(ws)


@app.websocket("/ws/voice")
async def ws_voice(ws: WebSocket) -> None:
    """
    Voice stream WebSocket.
    Accepts raw audio bytes (PCM/WAV), returns JSON with transcription.
    Also supports TTS: {"type": "tts", "text": "..."} -> binary MP3 chunks.
    """
    await ws.accept()
    ws_manager.voice.append(ws)
    voice = get_voice_manager()

    try:
        while True:
            msg = await ws.receive()
            if "bytes" in msg:
                # STT: received audio bytes
                audio_bytes = msg["bytes"]
                voice.push_ptt_chunk(audio_bytes)

            elif "text" in msg:
                data = json.loads(msg["text"])
                msg_type = data.get("type")

                if msg_type == "ptt_start":
                    await voice.start_ptt_recording()
                    await ws.send_text(json.dumps({"type": "ptt_started"}))

                elif msg_type == "ptt_stop":
                    text = await voice.stop_ptt_recording()
                    await ws.send_text(json.dumps({
                        "type": "transcription",
                        "text": text,
                    }, ensure_ascii=False))

                elif msg_type == "tts":
                    text = data.get("text", "")
                    if text:
                        async def _send(chunk: bytes) -> None:
                            await ws.send_bytes(chunk)
                        await voice.speak_streaming(text, _send)
                        await ws.send_text(json.dumps({"type": "tts_done"}))

                elif msg_type == "transcribe":
                    # Client sent base64 audio
                    import base64
                    audio_b64 = data.get("audio", "")
                    audio_bytes = base64.b64decode(audio_b64)
                    corrected, original = await voice.transcribe_and_fix(audio_bytes)
                    await ws.send_text(json.dumps({
                        "type": "transcription",
                        "text": corrected,
                        "original": original,
                    }, ensure_ascii=False))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS Voice 錯誤: %s", exc)
    finally:
        if ws in ws_manager.voice:
            ws_manager.voice.remove(ws)


@app.websocket("/ws/stats")
async def ws_stats(ws: WebSocket) -> None:
    """
    Live system stats WebSocket.
    Server pushes stats every 2 seconds automatically via _stats_streamer.
    Client can also request: {"type": "request_stats"} for immediate push.
    """
    await ws.accept()
    ws_manager.stats.append(ws)
    controller = get_controller()

    # Send initial stats immediately
    try:
        stats = controller.get_system_stats()
        await ws.send_text(json.dumps({
            "type": "stats",
            "data": stats,
            "ts": datetime.utcnow().isoformat(),
        }, ensure_ascii=False, default=str))
    except Exception:
        pass

    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30)
                data = json.loads(raw)
                if data.get("type") == "request_stats":
                    stats = controller.get_system_stats()
                    await ws.send_text(json.dumps({
                        "type": "stats", "data": stats,
                        "ts": datetime.utcnow().isoformat(),
                    }, ensure_ascii=False, default=str))
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS Stats 錯誤: %s", exc)
    finally:
        if ws in ws_manager.stats:
            ws_manager.stats.remove(ws)


@app.websocket("/ws/mobile")
async def ws_mobile(ws: WebSocket) -> None:
    """
    Mobile bridge WebSocket.
    Authentication via token query parameter: /ws/mobile?token=...
    """
    token = ws.query_params.get("token", "")
    bridge = get_mobile_bridge()

    connected = await bridge.connect(ws, token)
    if not connected:
        return

    try:
        while True:
            raw = await ws.receive_text()
            await bridge.handle_message(ws, raw)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS Mobile 錯誤: %s", exc)
    finally:
        await bridge.disconnect(ws)


# ── Agent confirm/deny (for tool policy) ────────────────────────────────────

@app.post("/api/agent/confirm/{confirmation_id}")
async def agent_confirm(
    confirmation_id: str, approved: bool = Query(True)
) -> JSONResponse:
    """Approve or deny a pending agent confirmation."""
    agent = get_agent_runtime()
    await agent.confirm_action(confirmation_id, approved)
    return JSONResponse({"status": "ok", "confirmation_id": confirmation_id, "approved": approved})


@app.get("/api/agent/pending-confirmations")
async def agent_pending_confirmations() -> JSONResponse:
    agent = get_agent_runtime()
    return JSONResponse({"pending": agent.list_pending_confirmations()})


# ── Agent mode ────────────────────────────────────────────────────────────────

@app.post("/api/agent/mode")
async def set_agent_mode(mode: str = Query(...)) -> JSONResponse:
    """Switch agent mode: basic | thinking | collaborative"""
    if mode not in ("basic", "thinking", "collaborative"):
        raise HTTPException(400, f"無效的模式: {mode}")
    agent = get_agent_runtime()
    agent.set_mode(mode)
    return JSONResponse({"status": "ok", "mode": mode})


# ── Scheduler tasks ───────────────────────────────────────────────────────────

@app.get("/api/scheduler/tasks")
async def list_scheduled_tasks() -> JSONResponse:
    scheduler = get_scheduler()
    return JSONResponse({
        "tasks": scheduler.list_tasks(),
        "queue": scheduler.get_queue(),
        "gantt": scheduler.get_gantt_data(),
    })


@app.post("/api/scheduler/tasks/{task_id}/trigger")
async def trigger_scheduled_task(task_id: str) -> JSONResponse:
    """Immediately trigger a scheduled task (mobile trigger support)."""
    scheduler = get_scheduler()
    try:
        scheduler.trigger_task(task_id)
        return JSONResponse({"status": "ok", "triggered": task_id})
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/scheduler/tasks/{task_id}/pause")
async def pause_scheduled_task(task_id: str) -> JSONResponse:
    scheduler = get_scheduler()
    try:
        scheduler.pause_task(task_id)
        return JSONResponse({"status": "ok", "paused": task_id})
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/scheduler/tasks/{task_id}/resume")
async def resume_scheduled_task(task_id: str) -> JSONResponse:
    scheduler = get_scheduler()
    try:
        scheduler.resume_task(task_id)
        return JSONResponse({"status": "ok", "resumed": task_id})
    except KeyError as exc:
        raise HTTPException(404, str(exc))


# ── Main entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "webui.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        access_log=True,
    )
