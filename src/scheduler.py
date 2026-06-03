"""
TFNK™ Task Scheduler
APScheduler-based scheduler with visual Gantt data, priority queue,
cross-restart persistence, mobile trigger support, and audit logging.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import get_settings

logger = logging.getLogger("tfnk.scheduler")

TASK_TYPE_ONCE = "once"
TASK_TYPE_RECURRING = "recurring"
TASK_TYPE_CRON = "cron"

PRIORITY_HIGH = 1
PRIORITY_NORMAL = 2
PRIORITY_LOW = 3


class ScheduledTask:
    def __init__(
        self,
        task_id: str,
        name: str,
        task_type: str,
        callback_name: str,
        priority: int = PRIORITY_NORMAL,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        run_at: Optional[datetime] = None,
        description: str = "",
        estimated_duration_seconds: int = 60,
    ) -> None:
        self.task_id = task_id
        self.name = name
        self.task_type = task_type
        self.callback_name = callback_name
        self.priority = priority
        self.interval_seconds = interval_seconds
        self.cron_expression = cron_expression
        self.run_at = run_at
        self.description = description
        self.estimated_duration_seconds = estimated_duration_seconds

        self.state = "pending"  # pending | running | paused | completed | failed
        self.progress: float = 0.0
        self.created_at = datetime.utcnow().isoformat()
        self.last_run: Optional[str] = None
        self.next_run: Optional[str] = None
        self.run_count: int = 0
        self.error: Optional[str] = None
        self.estimated_completion: Optional[str] = None
        self.apscheduler_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "callback_name": self.callback_name,
            "priority": self.priority,
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "description": self.description,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "state": self.state,
            "progress": self.progress,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "error": self.error,
            "estimated_completion": self.estimated_completion,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        run_at = None
        if data.get("run_at"):
            run_at = datetime.fromisoformat(data["run_at"])
        t = cls(
            task_id=data["task_id"],
            name=data["name"],
            task_type=data["task_type"],
            callback_name=data["callback_name"],
            priority=data.get("priority", PRIORITY_NORMAL),
            interval_seconds=data.get("interval_seconds"),
            cron_expression=data.get("cron_expression"),
            run_at=run_at,
            description=data.get("description", ""),
            estimated_duration_seconds=data.get("estimated_duration_seconds", 60),
        )
        t.state = data.get("state", "pending")
        t.run_count = data.get("run_count", 0)
        t.last_run = data.get("last_run")
        t.next_run = data.get("next_run")
        return t


class TaskScheduler:
    """
    Full-featured task scheduler for TFNK™.
    Supports one-shot, recurring, cron tasks with priority queue,
    visual Gantt data, state persistence, and mobile trigger support.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._scheduler = AsyncIOScheduler(timezone="Asia/Hong_Kong")
        self._tasks: Dict[str, ScheduledTask] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._state_file = self._settings.get_memory_dir() / "scheduler_state.json"
        self._audit_path = self._settings.get_log_dir() / "scheduler_audit.jsonl"
        self._register_builtin_callbacks()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the APScheduler and register all background jobs."""
        self._scheduler.start()
        self._load_state()
        self._register_background_jobs()
        logger.info("任務調度器已啟動")

    def stop(self) -> None:
        """Stop the scheduler and persist state."""
        self._save_state()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        logger.info("任務調度器已停止")

    # ── Task management ───────────────────────────────────────────────────────

    def add_task(
        self,
        name: str,
        callback_name: str = "run_agent_task",
        task_type: str = TASK_TYPE_ONCE,
        priority: int = PRIORITY_NORMAL,
        interval_seconds: Optional[int] = None,
        cron_expression: Optional[str] = None,
        run_at: Optional[datetime] = None,
        description: str = "",
        estimated_duration_seconds: int = 60,
    ) -> ScheduledTask:
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            task_type=task_type,
            callback_name=callback_name,
            priority=priority,
            interval_seconds=interval_seconds,
            cron_expression=cron_expression,
            run_at=run_at,
            description=description,
            estimated_duration_seconds=estimated_duration_seconds,
        )
        self._tasks[task_id] = task
        self._schedule_apscheduler(task)
        self._audit("task_added", {"task_id": task_id, "name": name})
        self._save_state()
        return task

    def remove_task(self, task_id: str) -> None:
        task = self._tasks.pop(task_id, None)
        if task and task.apscheduler_id:
            try:
                self._scheduler.remove_job(task.apscheduler_id)
            except Exception:
                pass
        self._audit("task_removed", {"task_id": task_id})
        self._save_state()

    def pause_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"任務不存在: {task_id}")
        task.state = "paused"
        if task.apscheduler_id:
            try:
                self._scheduler.pause_job(task.apscheduler_id)
            except Exception:
                pass
        self._audit("task_paused", {"task_id": task_id})
        self._save_state()

    def resume_task(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"任務不存在: {task_id}")
        task.state = "pending"
        if task.apscheduler_id:
            try:
                self._scheduler.resume_job(task.apscheduler_id)
            except Exception:
                pass
        self._audit("task_resumed", {"task_id": task_id})
        self._save_state()

    def trigger_task(self, task_id: str) -> None:
        """Immediately trigger a task (used by mobile bridge)."""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"任務不存在: {task_id}")
        if task.apscheduler_id:
            try:
                self._scheduler.get_job(task.apscheduler_id).modify(
                    next_run_time=datetime.utcnow()
                )
            except Exception:
                pass
        self._audit("task_triggered", {"task_id": task_id, "source": "mobile"})

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        tasks = sorted(
            self._tasks.values(),
            key=lambda t: (t.priority, t.created_at),
        )
        return [t.to_dict() for t in tasks]

    # ── Visual data ───────────────────────────────────────────────────────────

    def get_gantt_data(self) -> List[Dict[str, Any]]:
        """Return Gantt chart compatible data for the frontend."""
        now = datetime.utcnow()
        gantt = []
        for task in self._tasks.values():
            start = task.last_run or task.created_at
            if task.estimated_completion:
                end = task.estimated_completion
            else:
                est_end = now + timedelta(seconds=task.estimated_duration_seconds)
                end = est_end.isoformat()
            gantt.append({
                "id": task.task_id,
                "name": task.name,
                "start": start,
                "end": end,
                "progress": task.progress,
                "state": task.state,
                "priority": task.priority,
                "type": task.task_type,
            })
        return gantt

    def get_queue(self) -> List[Dict[str, Any]]:
        """Return pending tasks ordered by priority for the queue view."""
        pending = [
            t for t in self._tasks.values()
            if t.state in ("pending", "paused")
        ]
        pending.sort(key=lambda t: (t.priority, t.created_at))
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "priority": t.priority,
                "estimated_duration_seconds": t.estimated_duration_seconds,
                "state": t.state,
                "next_run": t.next_run,
            }
            for t in pending
        ]

    # ── Callback registry ─────────────────────────────────────────────────────

    def register_callback(self, name: str, fn: Callable) -> None:
        self._callbacks[name] = fn

    # ── Internal scheduling ───────────────────────────────────────────────────

    def _schedule_apscheduler(self, task: ScheduledTask) -> None:
        callback = self._callbacks.get(task.callback_name)
        if not callback:
            logger.warning("未找到回調: %s，使用空操作", task.callback_name)
            callback = _noop

        job_id = f"task_{task.task_id}"

        if task.task_type == TASK_TYPE_ONCE:
            run_at = task.run_at or (datetime.utcnow() + timedelta(seconds=1))
            job = self._scheduler.add_job(
                self._wrap_callback(task, callback),
                trigger=DateTrigger(run_date=run_at),
                id=job_id,
                replace_existing=True,
            )
        elif task.task_type == TASK_TYPE_RECURRING:
            seconds = task.interval_seconds or 3600
            job = self._scheduler.add_job(
                self._wrap_callback(task, callback),
                trigger=IntervalTrigger(seconds=seconds),
                id=job_id,
                replace_existing=True,
            )
        elif task.task_type == TASK_TYPE_CRON and task.cron_expression:
            parts = task.cron_expression.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
            else:
                minute, hour, day, month, day_of_week = "0", "2", "*", "*", "*"
            job = self._scheduler.add_job(
                self._wrap_callback(task, callback),
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                ),
                id=job_id,
                replace_existing=True,
            )
        else:
            logger.warning("無效的任務類型: %s", task.task_type)
            return

        task.apscheduler_id = job_id
        next_run = self._scheduler.get_job(job_id)
        if next_run and hasattr(next_run, "next_run_time") and next_run.next_run_time:
            task.next_run = next_run.next_run_time.isoformat()

    def _wrap_callback(self, task: ScheduledTask, callback: Callable) -> Callable:
        async def _wrapped() -> None:
            task.state = "running"
            task.last_run = datetime.utcnow().isoformat()
            task.run_count += 1
            task.progress = 0.0
            est = datetime.utcnow() + timedelta(seconds=task.estimated_duration_seconds)
            task.estimated_completion = est.isoformat()
            self._audit("task_run_started", {"task_id": task.task_id, "run_count": task.run_count})
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
                task.state = "completed" if task.task_type == TASK_TYPE_ONCE else "pending"
                task.progress = 100.0
                self._audit("task_run_completed", {"task_id": task.task_id})
            except Exception as exc:
                task.state = "failed"
                task.error = str(exc)
                logger.error("任務執行失敗 %s: %s", task.task_id, exc)
                self._audit("task_run_failed", {"task_id": task.task_id, "error": str(exc)})
            finally:
                self._save_state()

        return _wrapped

    # ── Built-in background jobs ──────────────────────────────────────────────

    def _register_builtin_callbacks(self) -> None:
        self._callbacks.update({
            "daily_intel_update": self._job_daily_intel,
            "model_health_check": self._job_model_health,
            "auto_backup": self._job_auto_backup,
            "noop": _noop,
        })

    def _register_background_jobs(self) -> None:
        """Register the always-running background maintenance jobs."""
        # Daily intel update at 06:00 HKT
        if "builtin_intel" not in self._tasks:
            self.add_task(
                name="每日AI情報更新",
                callback_name="daily_intel_update",
                task_type=TASK_TYPE_CRON,
                cron_expression="0 6 * * *",
                description="每日自動更新AI模型比較、新聞和免費模型清單",
                estimated_duration_seconds=120,
            )

        # Model health check every 5 minutes
        if "builtin_health" not in self._tasks:
            self.add_task(
                name="模型健康檢查",
                callback_name="model_health_check",
                task_type=TASK_TYPE_RECURRING,
                interval_seconds=300,
                description="每5分鐘檢查所有AI服務連接狀態",
                estimated_duration_seconds=30,
            )

        # Auto-backup every 6 hours
        if "builtin_backup" not in self._tasks:
            self.add_task(
                name="自動備份",
                callback_name="auto_backup",
                task_type=TASK_TYPE_CRON,
                cron_expression="0 */6 * * *",
                description="每6小時自動備份記憶和設定",
                estimated_duration_seconds=60,
            )

    async def _job_daily_intel(self) -> None:
        try:
            from src.intel import get_intel_manager
            intel = get_intel_manager()
            await intel.update_all()
            logger.info("每日情報更新完成")
        except Exception as exc:
            logger.error("每日情報更新失敗: %s", exc)

    async def _job_model_health(self) -> None:
        try:
            from src.connections import get_connection_monitor
            monitor = get_connection_monitor()
            await monitor.check_all()
            logger.debug("模型健康檢查完成")
        except Exception as exc:
            logger.error("模型健康檢查失敗: %s", exc)

    async def _job_auto_backup(self) -> None:
        settings = get_settings()
        backup_dir = settings.get_backup_dir()
        memory_dir = settings.get_memory_dir()
        import shutil
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"memory_backup_{stamp}"
        try:
            shutil.copytree(str(memory_dir), str(dest), dirs_exist_ok=True)
            logger.info("自動備份完成: %s", dest)
        except Exception as exc:
            logger.error("自動備份失敗: %s", exc)

    # ── State persistence ─────────────────────────────────────────────────────

    def _save_state(self) -> None:
        try:
            state = {
                "saved_at": datetime.utcnow().isoformat(),
                "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
            }
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            self._state_file.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("調度器狀態保存失敗: %s", exc)

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            state = json.loads(self._state_file.read_text(encoding="utf-8"))
            for tid, tdata in state.get("tasks", {}).items():
                # Skip built-in tasks — they re-register themselves
                if tdata.get("callback_name", "").startswith("daily_") or \
                   tdata.get("callback_name") in ("model_health_check", "auto_backup"):
                    continue
                task = ScheduledTask.from_dict(tdata)
                self._tasks[tid] = task
                self._schedule_apscheduler(task)
            logger.info("已恢復 %d 個調度任務", len(self._tasks))
        except Exception as exc:
            logger.error("調度器狀態恢復失敗: %s", exc)

    # ── Audit ─────────────────────────────────────────────────────────────────

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        entry = {"ts": datetime.utcnow().isoformat(), "event": event, **data}
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("調度審計日誌失敗: %s", exc)


def _noop() -> None:
    pass


# Global singleton
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler
