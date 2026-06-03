"""
TFNK™ Connection Monitor
Parallel health checks for all AI/cloud services with latency tracking,
auto-refresh every 60s, and WebSocket broadcast on status change.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger("tfnk.connections")


@dataclass
class ConnectionStatus:
    name: str
    display_name: str
    status: str = "unknown"         # ok | error | unknown
    latency_ms: Optional[float] = None
    connected_since: Optional[str] = None
    last_checked: Optional[str] = None
    is_actually_used: bool = False
    error_msg: Optional[str] = None
    endpoint: str = ""
    requires_key: bool = True
    key_configured: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Endpoint definitions ──────────────────────────────────────────────────────

def _build_default_connections(settings: Any) -> Dict[str, ConnectionStatus]:
    return {
        "ollama": ConnectionStatus(
            name="ollama",
            display_name="Ollama (本地)",
            endpoint=f"{settings.ollama_base_url}/api/tags",
            requires_key=False,
            key_configured=True,
        ),
        "anthropic": ConnectionStatus(
            name="anthropic",
            display_name="Anthropic Claude",
            endpoint="https://api.anthropic.com/v1/messages",
            requires_key=True,
            key_configured=bool(settings.anthropic_api_key),
        ),
        "openai": ConnectionStatus(
            name="openai",
            display_name="OpenAI",
            endpoint="https://api.openai.com/v1/models",
            requires_key=True,
            key_configured=bool(settings.openai_api_key),
        ),
        "openrouter": ConnectionStatus(
            name="openrouter",
            display_name="OpenRouter",
            endpoint="https://openrouter.ai/api/v1/models",
            requires_key=True,
            key_configured=bool(settings.openrouter_api_key),
        ),
        "groq": ConnectionStatus(
            name="groq",
            display_name="Groq",
            endpoint="https://api.groq.com/openai/v1/models",
            requires_key=True,
            key_configured=bool(settings.groq_api_key),
        ),
        "gemini": ConnectionStatus(
            name="gemini",
            display_name="Google Gemini",
            endpoint="https://generativelanguage.googleapis.com/v1/models",
            requires_key=True,
            key_configured=bool(settings.gemini_api_key),
        ),
        "google": ConnectionStatus(
            name="google",
            display_name="Google Custom Search",
            endpoint="https://customsearch.googleapis.com/customsearch/v1",
            requires_key=True,
            key_configured=bool(settings.google_api_key and settings.google_cse_id),
        ),
        "cerebras": ConnectionStatus(
            name="cerebras",
            display_name="Cerebras",
            endpoint="https://api.cerebras.ai/v1/models",
            requires_key=True,
            key_configured=False,
        ),
        "sambanova": ConnectionStatus(
            name="sambanova",
            display_name="SambaNova",
            endpoint="https://api.sambanova.ai/v1/models",
            requires_key=True,
            key_configured=False,
        ),
        "huggingface": ConnectionStatus(
            name="huggingface",
            display_name="HuggingFace Hub",
            endpoint="https://huggingface.co/api/models",
            requires_key=False,
            key_configured=True,
        ),
        "github_models": ConnectionStatus(
            name="github_models",
            display_name="GitHub Models",
            endpoint="https://models.inference.ai.azure.com",
            requires_key=True,
            key_configured=False,
        ),
        "mistral": ConnectionStatus(
            name="mistral",
            display_name="Mistral AI",
            endpoint="https://api.mistral.ai/v1/models",
            requires_key=True,
            key_configured=False,
        ),
        "youtube": ConnectionStatus(
            name="youtube",
            display_name="YouTube Data API",
            endpoint="https://www.googleapis.com/youtube/v3",
            requires_key=True,
            key_configured=bool(settings.youtube_api_key),
        ),
        "tailscale": ConnectionStatus(
            name="tailscale",
            display_name="Tailscale",
            endpoint="https://api.tailscale.com/api/v2/tailnet/-/devices",
            requires_key=True,
            key_configured=bool(settings.tailscale_auth_key),
        ),
        "image_gen_flux": ConnectionStatus(
            name="image_gen_flux",
            display_name="Flux Image Gen",
            endpoint="https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
            requires_key=False,
            key_configured=True,
        ),
        "image_gen_sd": ConnectionStatus(
            name="image_gen_sd",
            display_name="Stable Diffusion (HF)",
            endpoint="https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
            requires_key=False,
            key_configured=True,
        ),
        "finnhub": ConnectionStatus(
            name="finnhub",
            display_name="Finnhub 金融",
            endpoint="https://finnhub.io/api/v1/stock/symbol",
            requires_key=True,
            key_configured=bool(settings.finnhub_api_key),
        ),
        "alpha_vantage": ConnectionStatus(
            name="alpha_vantage",
            display_name="Alpha Vantage 金融",
            endpoint="https://www.alphavantage.co/query",
            requires_key=True,
            key_configured=bool(settings.alpha_vantage_api_key),
        ),
    }


class ConnectionMonitor:
    """
    Monitors health of all connected services.
    Auto-checks every 60 seconds, broadcasts changes via registered callbacks.
    """

    CHECK_INTERVAL = 60  # seconds

    def __init__(self) -> None:
        self._settings = get_settings()
        self._connections = _build_default_connections(self._settings)
        self._change_callbacks: List[Callable[[ConnectionStatus], Any]] = []
        self._auto_check_task: Optional[asyncio.Task] = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def check_all(self) -> Dict[str, Dict[str, Any]]:
        """Run parallel health checks for all connections."""
        tasks = {
            name: asyncio.create_task(self._check_one(name, conn))
            for name, conn in self._connections.items()
        }
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {name: conn.to_dict() for name, conn in self._connections.items()}

    async def check_connection(self, name: str) -> Optional[Dict[str, Any]]:
        """Check a single connection by name."""
        conn = self._connections.get(name)
        if not conn:
            return None
        await self._check_one(name, conn)
        return conn.to_dict()

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Return cached status without re-checking."""
        return {name: conn.to_dict() for name, conn in self._connections.items()}

    def get_status(self, name: str) -> Optional[Dict[str, Any]]:
        conn = self._connections.get(name)
        return conn.to_dict() if conn else None

    def remove_connection(self, name: str) -> bool:
        """Remove a connection from monitoring."""
        if name in self._connections:
            del self._connections[name]
            logger.info("已移除連接監控: %s", name)
            return True
        return False

    def add_connection(
        self,
        name: str,
        display_name: str,
        endpoint: str,
        requires_key: bool = True,
        key_configured: bool = False,
    ) -> None:
        self._connections[name] = ConnectionStatus(
            name=name,
            display_name=display_name,
            endpoint=endpoint,
            requires_key=requires_key,
            key_configured=key_configured,
        )

    def on_change(self, callback: Callable[[ConnectionStatus], Any]) -> None:
        """Register a callback to be called when any connection status changes."""
        self._change_callbacks.append(callback)

    # ── Auto check ────────────────────────────────────────────────────────────

    def start_auto_check(self) -> None:
        """Start background task to auto-check connections every 60s."""
        if self._auto_check_task is None or self._auto_check_task.done():
            self._auto_check_task = asyncio.create_task(self._auto_check_loop())
            logger.info("連接自動檢查已啟動（每 %ds）", self.CHECK_INTERVAL)

    def stop_auto_check(self) -> None:
        if self._auto_check_task and not self._auto_check_task.done():
            self._auto_check_task.cancel()

    async def _auto_check_loop(self) -> None:
        while True:
            try:
                await self.check_all()
                logger.debug("連接狀態已更新")
            except Exception as exc:
                logger.warning("自動連接檢查失敗: %s", exc)
            await asyncio.sleep(self.CHECK_INTERVAL)

    # ── Individual checks ─────────────────────────────────────────────────────

    async def _check_one(self, name: str, conn: ConnectionStatus) -> None:
        old_status = conn.status
        start = time.monotonic()

        try:
            await self._probe(name, conn)
            conn.latency_ms = round((time.monotonic() - start) * 1000, 1)
            conn.last_checked = datetime.utcnow().isoformat()
            if conn.status == "ok" and old_status != "ok":
                conn.connected_since = datetime.utcnow().isoformat()
                await self._broadcast_change(conn)
            elif conn.status != "ok" and old_status == "ok":
                await self._broadcast_change(conn)

        except Exception as exc:
            conn.status = "error"
            conn.error_msg = str(exc)[:200]
            conn.latency_ms = None
            conn.last_checked = datetime.utcnow().isoformat()
            if old_status != "error":
                await self._broadcast_change(conn)

    async def _probe(self, name: str, conn: ConnectionStatus) -> None:
        """Dispatch to specific probe for each service."""
        settings = self._settings

        if name == "ollama":
            await self._probe_http_get(conn.endpoint, timeout=3)

        elif name == "anthropic":
            if not settings.anthropic_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 API 金鑰"
                return
            await self._probe_http_get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=8,
            )

        elif name == "openai":
            if not settings.openai_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 API 金鑰"
                return
            await self._probe_http_get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=8,
            )

        elif name == "openrouter":
            if not settings.openrouter_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 API 金鑰"
                return
            await self._probe_http_get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                timeout=8,
            )

        elif name == "groq":
            if not settings.groq_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 API 金鑰"
                return
            await self._probe_http_get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                timeout=8,
            )

        elif name == "gemini":
            if not settings.gemini_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 API 金鑰"
                return
            await self._probe_http_get(
                f"https://generativelanguage.googleapis.com/v1/models?key={settings.gemini_api_key}",
                timeout=8,
            )

        elif name == "google":
            await self._probe_http_get("https://www.google.com", timeout=5)

        elif name in ("cerebras", "sambanova", "github_models", "mistral"):
            await self._probe_http_get(conn.endpoint, timeout=8)

        elif name == "huggingface":
            await self._probe_http_get("https://huggingface.co/api/models?limit=1", timeout=8)

        elif name == "youtube":
            if not settings.youtube_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 YouTube API 金鑰"
                return
            await self._probe_http_get(
                f"https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&key={settings.youtube_api_key}",
                timeout=8,
            )

        elif name == "tailscale":
            if not settings.tailscale_auth_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 Tailscale 金鑰"
                return
            await self._probe_http_get(
                "https://api.tailscale.com/api/v2/tailnet/-/devices",
                headers={"Authorization": f"Bearer {settings.tailscale_auth_key}"},
                timeout=8,
            )

        elif name in ("image_gen_flux", "image_gen_sd"):
            await self._probe_http_get(conn.endpoint, timeout=8)

        elif name == "finnhub":
            if not settings.finnhub_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 Finnhub 金鑰"
                return
            await self._probe_http_get(
                f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={settings.finnhub_api_key}",
                timeout=8,
            )

        elif name == "alpha_vantage":
            if not settings.alpha_vantage_api_key:
                conn.status = "unknown"
                conn.error_msg = "未設置 Alpha Vantage 金鑰"
                return
            await self._probe_http_get(
                f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={settings.alpha_vantage_api_key}",
                timeout=8,
            )

        else:
            await self._probe_http_get(conn.endpoint, timeout=8)

    async def _probe_http_get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 8,
    ) -> None:
        """Perform a GET request and update status."""
        conn_name = None
        for name, conn in self._connections.items():
            if conn.endpoint == url or url.startswith(conn.endpoint.split("?")[0]):
                conn_name = name
                break

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers or {})

        # Find the connection to update
        for name, conn in self._connections.items():
            # Match by checking which probe is running via call stack...
            # Instead we rely on the caller _check_one to set conn directly.
            pass

        # Status based on HTTP code
        conn_ref = self._connections.get(conn_name) if conn_name else None
        if conn_ref:
            if resp.status_code < 400:
                conn_ref.status = "ok"
                conn_ref.error_msg = None
            elif resp.status_code == 401:
                conn_ref.status = "error"
                conn_ref.error_msg = "認證失敗 (401)"
            elif resp.status_code == 403:
                conn_ref.status = "error"
                conn_ref.error_msg = "權限被拒 (403)"
            else:
                conn_ref.status = "error"
                conn_ref.error_msg = f"HTTP {resp.status_code}"

    async def _probe_and_set(self, conn: ConnectionStatus, url: str, headers: Optional[Dict] = None, timeout: float = 8) -> None:
        """Probe a URL and directly update the given connection status."""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers or {})
            if resp.status_code < 400:
                conn.status = "ok"
                conn.error_msg = None
            elif resp.status_code == 401:
                conn.status = "error"
                conn.error_msg = "認證失敗 (401)"
            elif resp.status_code == 403:
                conn.status = "error"
                conn.error_msg = "權限被拒 (403)"
            elif resp.status_code == 404:
                # Some APIs return 404 for list endpoints without auth; treat as reachable
                conn.status = "ok"
                conn.error_msg = None
            else:
                conn.status = "error"
                conn.error_msg = f"HTTP {resp.status_code}"
        except httpx.ConnectTimeout:
            conn.status = "error"
            conn.error_msg = "連接超時"
        except httpx.ConnectError:
            conn.status = "error"
            conn.error_msg = "無法連接"
        except Exception as exc:
            conn.status = "error"
            conn.error_msg = str(exc)[:100]

    async def _broadcast_change(self, conn: ConnectionStatus) -> None:
        for cb in self._change_callbacks:
            try:
                result = cb(conn)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("連接狀態廣播回調失敗: %s", exc)


# Rewrite _probe to use _probe_and_set properly
_original_probe = ConnectionMonitor._probe


async def _fixed_probe(self: ConnectionMonitor, name: str, conn: ConnectionStatus) -> None:
    settings = self._settings

    async def probe(url: str, headers: Optional[Dict] = None, t: float = 8) -> None:
        await self._probe_and_set(conn, url, headers, t)

    if name == "ollama":
        await probe(f"{settings.ollama_base_url}/api/tags", t=3)
    elif name == "anthropic":
        if not settings.anthropic_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 API 金鑰"; return
        await probe("https://api.anthropic.com/v1/models",
                    {"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"})
    elif name == "openai":
        if not settings.openai_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 API 金鑰"; return
        await probe("https://api.openai.com/v1/models",
                    {"Authorization": f"Bearer {settings.openai_api_key}"})
    elif name == "openrouter":
        if not settings.openrouter_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 API 金鑰"; return
        await probe("https://openrouter.ai/api/v1/models",
                    {"Authorization": f"Bearer {settings.openrouter_api_key}"})
    elif name == "groq":
        if not settings.groq_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 API 金鑰"; return
        await probe("https://api.groq.com/openai/v1/models",
                    {"Authorization": f"Bearer {settings.groq_api_key}"})
    elif name == "gemini":
        if not settings.gemini_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 API 金鑰"; return
        await probe(f"https://generativelanguage.googleapis.com/v1/models?key={settings.gemini_api_key}")
    elif name == "google":
        await probe("https://www.google.com", t=5)
    elif name == "huggingface":
        await probe("https://huggingface.co/api/models?limit=1")
    elif name == "youtube":
        if not settings.youtube_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 YouTube API 金鑰"; return
        await probe(f"https://www.googleapis.com/youtube/v3/videos?part=id&id=dQw4w9WgXcQ&key={settings.youtube_api_key}")
    elif name == "tailscale":
        if not settings.tailscale_auth_key:
            conn.status = "unknown"; conn.error_msg = "未設置 Tailscale 金鑰"; return
        await probe("https://api.tailscale.com/api/v2/tailnet/-/devices",
                    {"Authorization": f"Bearer {settings.tailscale_auth_key}"})
    elif name == "finnhub":
        if not settings.finnhub_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 Finnhub 金鑰"; return
        await probe(f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={settings.finnhub_api_key}")
    elif name == "alpha_vantage":
        if not settings.alpha_vantage_api_key:
            conn.status = "unknown"; conn.error_msg = "未設置 Alpha Vantage 金鑰"; return
        await probe(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={settings.alpha_vantage_api_key}")
    else:
        await probe(conn.endpoint)


# Replace with corrected implementation
ConnectionMonitor._probe = _fixed_probe  # type: ignore


# Global singleton
_monitor: Optional[ConnectionMonitor] = None


def get_connection_monitor() -> ConnectionMonitor:
    global _monitor
    if _monitor is None:
        _monitor = ConnectionMonitor()
    return _monitor
