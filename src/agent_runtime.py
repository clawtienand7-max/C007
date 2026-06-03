"""
TFNK™ Agent Runtime
Manus-style analyze → plan → execute → observe autonomous loop.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import textwrap
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger("tfnk.agent")


# ─── Enums ───────────────────────────────────────────────────────────────────

class TaskState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentMode(str, Enum):
    BASIC = "basic"
    THINKING = "thinking"
    COLLABORATIVE = "collaborative"


# ─── Models ──────────────────────────────────────────────────────────────────

class AgentTask:
    def __init__(
        self,
        task_id: str,
        description: str,
        parent_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.description = description
        self.parent_id = parent_id
        self.state = TaskState.PENDING
        self.steps: List[Dict[str, Any]] = []
        self.result: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.progress: float = 0.0  # 0–100
        self.sub_tasks: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "parent_id": self.parent_id,
            "state": self.state.value,
            "steps": self.steps,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "sub_tasks": self.sub_tasks,
        }


# ─── Agent Runtime ────────────────────────────────────────────────────────────

class AgentRuntime:
    """
    Autonomous agent following the analyze → plan → execute → observe loop.
    All responses and reasoning are in Traditional Chinese (繁體中文).
    """

    MAX_STEPS = 30
    STEP_DELAY = 0.1  # seconds between steps

    def __init__(self):
        self._settings = get_settings()
        self._tasks: Dict[str, AgentTask] = {}
        self._stop_flag = False
        self._mode = AgentMode(self._settings.agent_mode)
        self._audit_path = self._settings.get_log_dir() / "audit.jsonl"
        self._memory_dir = self._settings.get_memory_dir()
        self._skills_dir = self._settings.get_skills_dir()
        self._confirmation_callbacks: Dict[str, asyncio.Future] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    async def create_task(
        self,
        description: str,
        parent_id: Optional[str] = None,
    ) -> AgentTask:
        task_id = str(uuid.uuid4())
        task = AgentTask(task_id, description, parent_id)
        self._tasks[task_id] = task
        self._audit("task_created", {"task_id": task_id, "description": description})
        return task

    async def start_task(self, task_id: str) -> None:
        task = self._get_task(task_id)
        if task.state not in (TaskState.PENDING, TaskState.PAUSED):
            raise ValueError(f"任務狀態不允許啟動: {task.state}")
        task.state = TaskState.RUNNING
        task.started_at = datetime.utcnow().isoformat()
        self._audit("task_started", {"task_id": task_id})
        coro = self._run_loop(task)
        at = asyncio.create_task(coro)
        self._active_tasks[task_id] = at

    async def pause_task(self, task_id: str) -> None:
        task = self._get_task(task_id)
        task.state = TaskState.PAUSED
        self._audit("task_paused", {"task_id": task_id})
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()

    async def cancel_task(self, task_id: str) -> None:
        task = self._get_task(task_id)
        task.state = TaskState.FAILED
        task.error = "已取消"
        task.completed_at = datetime.utcnow().isoformat()
        self._audit("task_cancelled", {"task_id": task_id})
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            del self._active_tasks[task_id]

    def emergency_stop(self) -> None:
        self._stop_flag = True
        for at in self._active_tasks.values():
            at.cancel()
        self._active_tasks.clear()
        self._audit("emergency_stop", {})
        logger.warning("緊急停止已觸發 - 所有任務已停止")

    def resume_after_stop(self) -> None:
        self._stop_flag = False

    async def confirm_action(self, confirmation_id: str, approved: bool) -> None:
        fut = self._confirmation_callbacks.get(confirmation_id)
        if fut and not fut.done():
            fut.set_result(approved)

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tasks.values()]

    def set_mode(self, mode: str) -> None:
        self._mode = AgentMode(mode)
        self._settings.agent_mode = mode

    # ── Autonomous Loop ───────────────────────────────────────────────────────

    async def _run_loop(self, task: AgentTask) -> None:
        try:
            # 1. Search skills for matching pattern
            skill_match = await self._find_skill(task.description)
            if skill_match:
                self._log_step(task, "技能匹配", f"找到相關技能: {skill_match['name']}")

            # 2. Analyze phase
            plan = await self._analyze_and_plan(task, skill_match)
            self._log_step(task, "分析與規劃", plan)
            task.progress = 10.0

            # 3. Execute each step
            steps = self._parse_plan_steps(plan)
            total = max(len(steps), 1)

            for idx, step in enumerate(steps):
                if self._stop_flag or task.state == TaskState.PAUSED:
                    return

                self._log_step(task, f"執行步驟 {idx+1}/{total}", step)
                observation = await self._execute_step(task, step)
                self._log_step(task, f"觀察 {idx+1}/{total}", observation)
                task.progress = 10.0 + (80.0 * (idx + 1) / total)
                await asyncio.sleep(self.STEP_DELAY)

            # 4. Final summary
            summary = await self._summarize(task)
            task.result = summary
            task.state = TaskState.COMPLETED
            task.completed_at = datetime.utcnow().isoformat()
            task.progress = 100.0
            self._audit("task_completed", {"task_id": task.task_id, "result": summary[:200]})

            # 5. Auto-save skill if multi-step
            if len(steps) >= 3:
                await self._auto_save_skill(task, steps)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            task.state = TaskState.FAILED
            task.error = str(exc)
            task.completed_at = datetime.utcnow().isoformat()
            self._audit("task_failed", {"task_id": task.task_id, "error": str(exc)})
            logger.exception(f"任務 {task.task_id} 執行失敗: {exc}")

    async def _analyze_and_plan(
        self, task: AgentTask, skill: Optional[Dict]
    ) -> str:
        """Call LLM to analyze the task and produce a numbered plan."""
        skill_context = ""
        if skill:
            skill_context = f"\n\n可用技能:\n{skill['content']}"

        memory_context = await self._load_relevant_memory(task.description)

        system_prompt = textwrap.dedent("""
            你是 TFNK™ 智能代理人。請用繁體中文回答。
            分析用戶任務並制定詳細的逐步執行計劃。
            格式: 每個步驟以 "步驟N: 動作描述" 的格式列出。
            考慮安全性、可逆性和效率。
        """).strip()

        user_msg = f"任務: {task.description}{skill_context}\n\n相關記憶:\n{memory_context}"

        try:
            plan = await self._llm_call(system_prompt, user_msg)
        except Exception as exc:
            logger.warning(f"LLM 規劃失敗, 使用預設計劃: {exc}")
            plan = f"步驟1: 分析任務需求\n步驟2: 執行 {task.description}\n步驟3: 驗證結果"

        return plan

    async def _execute_step(self, task: AgentTask, step: str) -> str:
        """Parse the step and dispatch to the appropriate tool."""
        step_lower = step.lower()

        tool = self._detect_tool(step_lower)
        policy = self._settings.tool_policies.get(tool, "allow")

        if policy == "deny":
            return f"工具 {tool} 已被策略禁止"

        if policy == "confirm":
            conf_id = str(uuid.uuid4())
            approved = await self._request_confirmation(
                conf_id, f"任務 {task.task_id}: {step}"
            )
            if not approved:
                return "用戶拒絕執行此步驟"

        # Dispatch
        try:
            if tool == "web_search":
                query = self._extract_query(step)
                return await self._tool_web_search(query)
            elif tool == "read_file":
                path = self._extract_path(step)
                return await self._tool_read_file(path)
            elif tool == "write_file":
                path, content = self._extract_path_content(step)
                return await self._tool_write_file(path, content)
            elif tool == "run_code":
                code = self._extract_code(step)
                return await self._tool_run_code(code)
            elif tool == "system_command":
                cmd = self._extract_command(step)
                return await self._tool_system_command(cmd)
            elif tool == "browser_action":
                url = self._extract_url(step)
                return await self._tool_browser_fetch(url)
            else:
                return await self._tool_llm_step(task.description, step)
        except Exception as exc:
            return f"步驟執行錯誤: {exc}"

    async def _summarize(self, task: AgentTask) -> str:
        steps_text = "\n".join(
            f"- {s.get('phase')}: {str(s.get('content', ''))[:100]}"
            for s in task.steps[-10:]
        )
        system_prompt = "你是 TFNK™ 智能代理人。用繁體中文為用戶總結已完成的任務。"
        user_msg = f"任務: {task.description}\n\n執行步驟摘要:\n{steps_text}\n\n請提供完整的完成報告。"
        try:
            return await self._llm_call(system_prompt, user_msg)
        except Exception:
            return f"任務「{task.description}」已完成，共執行 {len(task.steps)} 個步驟。"

    # ── Tools ─────────────────────────────────────────────────────────────────

    async def _tool_web_search(self, query: str) -> str:
        settings = self._settings
        if not settings.google_api_key or not settings.google_cse_id:
            return f"網絡搜索（無API金鑰）: {query}"
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.google_api_key,
            "cx": settings.google_cse_id,
            "q": query,
            "num": 5,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        items = data.get("items", [])
        if not items:
            return f"搜索「{query}」無結果"
        results = []
        for item in items[:5]:
            results.append(f"標題: {item.get('title')}\n摘要: {item.get('snippet')}\n連結: {item.get('link')}")
        return "\n\n".join(results)

    async def _tool_read_file(self, path: str) -> str:
        from src.files import FileManager
        fm = FileManager()
        return fm.safe_read(path)

    async def _tool_write_file(self, path: str, content: str) -> str:
        from src.files import FileManager
        fm = FileManager()
        fm.safe_write(path, content)
        self._audit("file_written", {"path": path})
        return f"已寫入文件: {path}"

    async def _tool_run_code(self, code: str) -> str:
        self._audit("code_executed", {"code_preview": code[:100]})
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout or result.stderr
            return output[:2000] if output else "（無輸出）"
        except subprocess.TimeoutExpired:
            return "代碼執行超時（30秒限制）"
        except Exception as exc:
            return f"代碼執行錯誤: {exc}"

    async def _tool_system_command(self, cmd: str) -> str:
        self._audit("system_command", {"cmd": cmd})
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout or result.stderr
            return output[:2000] if output else "（命令執行完成，無輸出）"
        except subprocess.TimeoutExpired:
            return "命令執行超時（60秒限制）"
        except Exception as exc:
            return f"命令執行錯誤: {exc}"

    async def _tool_browser_fetch(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "TFNK/1.0"})
            resp.raise_for_status()
            text = resp.text[:3000]
        return f"網頁內容 ({url}):\n{text}"

    async def _tool_llm_step(self, task_desc: str, step: str) -> str:
        system_prompt = "你是 TFNK™ 智能代理人。用繁體中文執行以下任務步驟並回報結果。"
        user_msg = f"總體任務: {task_desc}\n\n當前步驟: {step}\n\n請執行並報告結果。"
        return await self._llm_call(system_prompt, user_msg)

    # ── LLM Call ──────────────────────────────────────────────────────────────

    async def _llm_call(self, system: str, user: str) -> str:
        settings = self._settings
        model = settings.model_for_mode()

        if settings.anthropic_api_key:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            msg = await client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text

        # Fallback: Ollama
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": "llama3",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    # ── Skill helpers ─────────────────────────────────────────────────────────

    async def _find_skill(self, description: str) -> Optional[Dict[str, Any]]:
        skills_dir = self._skills_dir
        if not skills_dir.exists():
            return None
        best: Optional[Dict[str, Any]] = None
        best_score = 0
        keywords = set(description.lower().split())
        for skill_file in skills_dir.glob("*.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
                score = sum(1 for kw in keywords if kw in content.lower())
                if score > best_score:
                    best_score = score
                    best = {"name": skill_file.stem, "content": content}
            except Exception:
                pass
        return best if best_score >= 2 else None

    async def _auto_save_skill(self, task: AgentTask, steps: List[str]) -> None:
        skills_dir = self._skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        name = task.description[:40].replace(" ", "_").replace("/", "_")
        skill_path = skills_dir / f"{name}.md"
        content = f"# 技能: {task.description}\n\n"
        content += f"**創建時間**: {task.completed_at}\n\n"
        content += "## 執行步驟\n\n"
        for i, step in enumerate(steps, 1):
            content += f"{i}. {step}\n"
        content += f"\n## 結果\n\n{task.result or '完成'}\n"
        skill_path.write_text(content, encoding="utf-8")
        self._audit("skill_saved", {"name": name, "task_id": task.task_id})

    # ── Memory ────────────────────────────────────────────────────────────────

    async def _load_relevant_memory(self, description: str) -> str:
        mem_file = self._memory_dir / "long_term.json"
        if not mem_file.exists():
            return "（無相關記憶）"
        try:
            data = json.loads(mem_file.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
            keywords = set(description.lower().split())
            relevant = [
                e for e in entries
                if any(kw in e.get("content", "").lower() for kw in keywords)
            ]
            if not relevant:
                return "（無相關記憶）"
            return "\n".join(e["content"] for e in relevant[:3])
        except Exception:
            return "（記憶載入失敗）"

    async def write_memory(self, key: str, content: str) -> None:
        mem_file = self._memory_dir / "long_term.json"
        data: Dict[str, Any] = {}
        if mem_file.exists():
            try:
                data = json.loads(mem_file.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        entries: List[Dict[str, Any]] = data.get("entries", [])
        entries.append({
            "key": key,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        data["entries"] = entries[-500:]  # keep last 500
        mem_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_memory(self) -> List[Dict[str, Any]]:
        mem_file = self._memory_dir / "long_term.json"
        if not mem_file.exists():
            return []
        try:
            data = json.loads(mem_file.read_text(encoding="utf-8"))
            return data.get("entries", [])
        except Exception:
            return []

    # ── Confirmation ──────────────────────────────────────────────────────────

    async def _request_confirmation(self, conf_id: str, description: str) -> bool:
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        self._confirmation_callbacks[conf_id] = fut
        self._audit("confirmation_requested", {"id": conf_id, "description": description})
        try:
            result = await asyncio.wait_for(fut, timeout=300.0)
            return result
        except asyncio.TimeoutError:
            return False
        finally:
            self._confirmation_callbacks.pop(conf_id, None)

    def list_pending_confirmations(self) -> List[Dict[str, Any]]:
        return [
            {"id": cid, "pending": not fut.done()}
            for cid, fut in self._confirmation_callbacks.items()
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_task(self, task_id: str) -> AgentTask:
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"任務不存在: {task_id}")
        return task

    def _log_step(self, task: AgentTask, phase: str, content: str) -> None:
        step = {
            "phase": phase,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        task.steps.append(step)
        logger.debug(f"[{task.task_id}] {phase}: {content[:80]}")

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "event": event,
            **data,
        }
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning(f"審計日誌寫入失敗: {exc}")

    @staticmethod
    def _detect_tool(step: str) -> str:
        if any(kw in step for kw in ["搜索", "搜尋", "search", "google", "網路", "網絡"]):
            return "web_search"
        if any(kw in step for kw in ["讀取", "讀文件", "read file", "open file"]):
            return "read_file"
        if any(kw in step for kw in ["寫入", "寫文件", "write file", "save file", "創建文件"]):
            return "write_file"
        if any(kw in step for kw in ["執行代碼", "run code", "python", "script"]):
            return "run_code"
        if any(kw in step for kw in ["命令", "terminal", "bash", "shell", "系統命令"]):
            return "system_command"
        if any(kw in step for kw in ["瀏覽", "browser", "url", "http", "網頁"]):
            return "browser_action"
        return "llm_step"

    @staticmethod
    def _parse_plan_steps(plan: str) -> List[str]:
        lines = plan.strip().splitlines()
        steps = []
        for line in lines:
            line = line.strip()
            if line and (line.startswith("步驟") or (len(line) > 3 and line[0].isdigit())):
                steps.append(line)
        return steps if steps else [plan]

    @staticmethod
    def _extract_query(step: str) -> str:
        for marker in ["搜索 ", "搜尋 ", "search for ", "search "]:
            if marker in step:
                return step.split(marker, 1)[1].strip()
        return step

    @staticmethod
    def _extract_path(step: str) -> str:
        import re
        m = re.search(r"['\"]([^'\"]+)['\"]", step)
        return m.group(1) if m else "/tmp/unknown"

    @staticmethod
    def _extract_path_content(step: str) -> tuple[str, str]:
        import re
        paths = re.findall(r"['\"]([^'\"]+)['\"]", step)
        path = paths[0] if paths else "/tmp/output.txt"
        content = paths[1] if len(paths) > 1 else step
        return path, content

    @staticmethod
    def _extract_code(step: str) -> str:
        import re
        m = re.search(r"```(?:python)?\n(.*?)```", step, re.DOTALL)
        if m:
            return m.group(1)
        return step

    @staticmethod
    def _extract_command(step: str) -> str:
        import re
        m = re.search(r"`([^`]+)`", step)
        return m.group(1) if m else step

    @staticmethod
    def _extract_url(step: str) -> str:
        import re
        m = re.search(r"https?://\S+", step)
        return m.group(0) if m else "https://example.com"


# Global singleton
_runtime: Optional[AgentRuntime] = None


def get_agent_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime
