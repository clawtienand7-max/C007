"""
TFNK™ Mobile Bridge (G0)
WebSocket + REST server for real-time mobile↔desktop communication.
Auth token validation, push notifications, action authorization queue.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.config import get_settings

logger = logging.getLogger("tfnk.mobile")


class PendingAuthorization(BaseModel):
    auth_id: str
    action_description: str
    task_id: Optional[str] = None
    requested_at: str
    expires_at: Optional[str] = None
    resolved: bool = False
    approved: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class MobilePushNotification(BaseModel):
    notification_id: str
    title: str
    body: str
    action_required: bool = False
    auth_id: Optional[str] = None
    task_id: Optional[str] = None
    timestamp: str
    data: Dict[str, Any] = {}


class MobileBridge:
    """
    Bridges the TFNK™ desktop agent with connected mobile clients.
    - WebSocket for real-time bidirectional comms
    - Authorization queue for non-reversible actions
    - Push notifications to all connected mobile clients
    - Tailscale hostname detection
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._connected_clients: Set[WebSocket] = set()
        self._pending_auths: Dict[str, PendingAuthorization] = {}
        self._auth_futures: Dict[str, asyncio.Future] = {}
        self._paused_tasks: Dict[str, asyncio.Future] = {}
        self._tailscale_hostname: Optional[str] = None
        self._detect_tailscale()

    # ── WebSocket management ──────────────────────────────────────────────────

    async def connect(self, ws: WebSocket, token: str) -> bool:
        """
        Accept and authenticate a mobile WebSocket connection.
        Returns True if auth succeeds, False otherwise.
        """
        expected = self._settings.mobile_auth_token
        if token != expected:
            await ws.close(code=4001, reason="認證失敗")
            logger.warning("Mobile WS 認證失敗 (token 不匹配)")
            return False

        await ws.accept()
        self._connected_clients.add(ws)
        logger.info("Mobile 客戶端已連接 (共 %d 個)", len(self._connected_clients))

        # Send welcome message
        await self._send_to_ws(ws, {
            "type": "connected",
            "message": "TFNK™ 已連接",
            "server_time": datetime.utcnow().isoformat(),
            "pending_count": len([a for a in self._pending_auths.values() if not a.resolved]),
        })
        return True

    async def disconnect(self, ws: WebSocket) -> None:
        self._connected_clients.discard(ws)
        logger.info("Mobile 客戶端已斷開 (剩餘 %d 個)", len(self._connected_clients))

    async def handle_message(self, ws: WebSocket, raw: str) -> None:
        """Process incoming message from mobile client."""
        try:
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "authorize":
                auth_id = data.get("auth_id")
                approved = data.get("approved", False)
                await self.resolve_authorization(auth_id, approved)

            elif msg_type == "continue_task":
                task_id = data.get("task_id")
                await self.resolve_task_continue(task_id)

            elif msg_type == "ping":
                await self._send_to_ws(ws, {"type": "pong", "ts": datetime.utcnow().isoformat()})

            elif msg_type == "get_status":
                await self._send_to_ws(ws, {
                    "type": "status",
                    "connected_clients": len(self._connected_clients),
                    "pending_auths": len([a for a in self._pending_auths.values() if not a.resolved]),
                })

            else:
                logger.debug("未知 Mobile 消息類型: %s", msg_type)

        except json.JSONDecodeError:
            logger.warning("Mobile WS 收到無效 JSON")
        except Exception as exc:
            logger.error("Mobile WS 消息處理錯誤: %s", exc)

    # ── Push notifications ────────────────────────────────────────────────────

    async def send_notification(
        self,
        title: str,
        body: str,
        action_required: bool = False,
        auth_id: Optional[str] = None,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast a push notification to all connected mobile clients."""
        notification = MobilePushNotification(
            notification_id=str(uuid.uuid4()),
            title=title,
            body=body,
            action_required=action_required,
            auth_id=auth_id,
            task_id=task_id,
            timestamp=datetime.utcnow().isoformat(),
            data=data or {},
        )
        payload = {"type": "notification", **notification.model_dump()}
        await self._broadcast(payload)
        logger.debug("已推送通知: %s", title)

    # ── Authorization queue ───────────────────────────────────────────────────

    async def request_authorization(
        self,
        action_description: str,
        task_id: Optional[str] = None,
        timeout_seconds: float = 300.0,
    ) -> bool:
        """
        Request authorization from mobile for a non-reversible action.
        Blocks until mobile approves/denies or timeout.
        Returns True if approved, False if denied/timed out.
        """
        auth_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._auth_futures[auth_id] = fut

        auth = PendingAuthorization(
            auth_id=auth_id,
            action_description=action_description,
            task_id=task_id,
            requested_at=datetime.utcnow().isoformat(),
        )
        self._pending_auths[auth_id] = auth

        # Notify mobile clients
        await self.send_notification(
            title="需要授權",
            body=action_description,
            action_required=True,
            auth_id=auth_id,
            task_id=task_id,
        )

        try:
            result = await asyncio.wait_for(fut, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            logger.warning("授權請求超時: %s", auth_id)
            auth.resolved = True
            auth.approved = False
            return False
        finally:
            self._auth_futures.pop(auth_id, None)

    async def resolve_authorization(self, auth_id: str, approved: bool) -> None:
        """Called when mobile client approves or denies an action."""
        auth = self._pending_auths.get(auth_id)
        if auth:
            auth.resolved = True
            auth.approved = approved

        fut = self._auth_futures.get(auth_id)
        if fut and not fut.done():
            fut.set_result(approved)

        # Acknowledge to all clients
        await self._broadcast({
            "type": "auth_resolved",
            "auth_id": auth_id,
            "approved": approved,
        })
        logger.info("授權 %s: %s", auth_id, "批准" if approved else "拒絕")

    def get_pending_authorizations(self) -> List[Dict[str, Any]]:
        return [
            a.to_dict()
            for a in self._pending_auths.values()
            if not a.resolved
        ]

    def get_all_authorizations(self, limit: int = 50) -> List[Dict[str, Any]]:
        auths = sorted(
            self._pending_auths.values(),
            key=lambda a: a.requested_at,
            reverse=True,
        )
        return [a.to_dict() for a in auths[:limit]]

    # ── Task continuation ─────────────────────────────────────────────────────

    async def request_task_continue(
        self,
        task_id: str,
        reason: str = "任務需要繼續確認",
    ) -> bool:
        """
        Signal mobile that a paused task needs continuation approval.
        Returns True if mobile sends continue signal.
        """
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._paused_tasks[task_id] = fut

        await self.send_notification(
            title="任務暫停",
            body=reason,
            action_required=True,
            task_id=task_id,
        )

        try:
            return await asyncio.wait_for(fut, timeout=600.0)
        except asyncio.TimeoutError:
            return False
        finally:
            self._paused_tasks.pop(task_id, None)

    async def resolve_task_continue(self, task_id: str) -> None:
        """Called when mobile client sends continue signal for a paused task."""
        fut = self._paused_tasks.get(task_id)
        if fut and not fut.done():
            fut.set_result(True)
            logger.info("任務繼續信號已接收: %s", task_id)

        await self._broadcast({
            "type": "task_continued",
            "task_id": task_id,
        })

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected_clients": len(self._connected_clients),
            "pending_authorizations": len([a for a in self._pending_auths.values() if not a.resolved]),
            "paused_tasks": len(self._paused_tasks),
            "tailscale_hostname": self._tailscale_hostname,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        """Send a message to all connected mobile clients."""
        if not self._connected_clients:
            return
        message = json.dumps(payload, ensure_ascii=False)
        dead: Set[WebSocket] = set()
        for ws in list(self._connected_clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._connected_clients -= dead

    async def _send_to_ws(self, ws: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            logger.warning("Mobile WS 發送失敗: %s", exc)

    def _detect_tailscale(self) -> None:
        """Try to detect Tailscale hostname."""
        import subprocess
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                self._tailscale_hostname = result.stdout.strip()
                logger.info("Tailscale IP: %s", self._tailscale_hostname)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception as exc:
            logger.debug("Tailscale 偵測失敗: %s", exc)


# Global singleton
_mobile_bridge: Optional[MobileBridge] = None


def get_mobile_bridge() -> MobileBridge:
    global _mobile_bridge
    if _mobile_bridge is None:
        _mobile_bridge = MobileBridge()
    return _mobile_bridge
