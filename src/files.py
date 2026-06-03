"""
TFNK™ File Manager
Locked-path enforcement, auto-backup before writes, watchdog monitoring,
safe read/write/delete with audit trail.
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Callable, List, Optional, Set

from src.config import get_settings

logger = logging.getLogger("tfnk.files")


class LockedPathError(PermissionError):
    """Raised when an operation targets a locked path."""


class FileManager:
    """
    Provides safe file I/O with:
    - Lock list enforcement (from config)
    - Auto-backup before any write or delete
    - Audit trail
    - Watchdog integration for external change detection
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._lock_set: Set[str] = set(self._settings.lock_list_parsed)
        self._mutex = Lock()
        self._audit_path = self._settings.get_log_dir() / "file_audit.jsonl"
        self._change_callbacks: List[Callable[[str, str], None]] = []
        self._observer: Optional[Any] = None

    # ── Lock management ───────────────────────────────────────────────────────

    def is_locked(self, path: str) -> bool:
        """
        Return True if path or any parent directory is in the lock list.
        Resolves symlinks before checking.
        """
        try:
            resolved = str(Path(path).resolve())
        except Exception:
            resolved = str(Path(path).absolute())

        with self._mutex:
            for locked in self._lock_set:
                try:
                    locked_resolved = str(Path(locked).resolve())
                except Exception:
                    locked_resolved = locked
                if resolved == locked_resolved or resolved.startswith(locked_resolved + "/"):
                    return True
        return False

    def add_lock(self, path: str) -> None:
        """Add a path to the lock list."""
        resolved = str(Path(path).resolve())
        with self._mutex:
            self._lock_set.add(resolved)
        self._persist_lock_list()
        self._audit("lock_added", {"path": resolved})
        logger.info("路徑已鎖定: %s", resolved)

    def remove_lock(self, path: str) -> None:
        """Remove a path from the lock list."""
        resolved = str(Path(path).resolve())
        with self._mutex:
            self._lock_set.discard(resolved)
        self._persist_lock_list()
        self._audit("lock_removed", {"path": resolved})
        logger.info("路徑已解鎖: %s", resolved)

    def list_locks(self) -> List[str]:
        with self._mutex:
            return sorted(self._lock_set)

    def _persist_lock_list(self) -> None:
        """Save current lock list to a JSON sidecar file."""
        lock_file = self._settings.get_memory_dir() / "lock_list.json"
        try:
            lock_file.write_text(
                json.dumps({"locks": self.list_locks()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("鎖定清單保存失敗: %s", exc)

    def load_persisted_locks(self) -> None:
        """Load lock list from persisted JSON (called on startup)."""
        lock_file = self._settings.get_memory_dir() / "lock_list.json"
        if not lock_file.exists():
            return
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8"))
            with self._mutex:
                self._lock_set.update(data.get("locks", []))
            logger.info("已載入 %d 個鎖定路徑", len(self._lock_set))
        except Exception as exc:
            logger.warning("鎖定清單載入失敗: %s", exc)

    # ── Safe I/O operations ───────────────────────────────────────────────────

    def safe_read(self, path: str) -> str:
        """Read a file, raising LockedPathError if path is locked."""
        if self.is_locked(path):
            raise LockedPathError(f"路徑已鎖定，拒絕讀取: {path}")
        try:
            content = Path(path).read_text(encoding="utf-8")
            self._audit("file_read", {"path": path, "size": len(content)})
            return content
        except LockedPathError:
            raise
        except Exception as exc:
            raise IOError(f"讀取文件失敗 {path}: {exc}") from exc

    def safe_read_bytes(self, path: str) -> bytes:
        """Read a binary file, raising LockedPathError if path is locked."""
        if self.is_locked(path):
            raise LockedPathError(f"路徑已鎖定，拒絕讀取: {path}")
        try:
            return Path(path).read_bytes()
        except Exception as exc:
            raise IOError(f"讀取文件失敗 {path}: {exc}") from exc

    def safe_write(self, path: str, content: str, encoding: str = "utf-8") -> None:
        """
        Write content to a file.
        - Raises LockedPathError if path is locked.
        - Automatically backs up the existing file before overwriting.
        """
        if self.is_locked(path):
            raise LockedPathError(f"路徑已鎖定，拒絕寫入: {path}")

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Auto-backup if file exists
        backup_path = None
        if target.exists():
            backup_path = self._backup_file(path)

        target.write_text(content, encoding=encoding)
        self._audit("file_written", {
            "path": path,
            "size": len(content),
            "backup": str(backup_path) if backup_path else None,
        })
        logger.debug("已寫入文件: %s", path)

    def safe_write_bytes(self, path: str, content: bytes) -> None:
        """Write binary content with lock check and backup."""
        if self.is_locked(path):
            raise LockedPathError(f"路徑已鎖定，拒絕寫入: {path}")

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            self._backup_file(path)

        target.write_bytes(content)
        self._audit("file_written_binary", {"path": path, "size": len(content)})

    def safe_delete(self, path: str, confirmed: bool = False) -> str:
        """
        Delete a file or directory.
        - Raises LockedPathError if path is locked.
        - Requires confirmed=True to proceed (non-reversible action guard).
        - Always backs up before deletion.
        Returns the backup path.
        """
        if self.is_locked(path):
            raise LockedPathError(f"路徑已鎖定，拒絕刪除: {path}")

        if not confirmed:
            raise ValueError(
                "刪除操作需要明確確認。請設置 confirmed=True 並由用戶批准。"
            )

        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        backup_path = self._backup_file(path)

        if target.is_dir():
            shutil.rmtree(str(target))
        else:
            target.unlink()

        self._audit("file_deleted", {"path": path, "backup": str(backup_path)})
        logger.warning("文件已刪除: %s (備份: %s)", path, backup_path)
        return str(backup_path)

    def safe_copy(self, src: str, dst: str) -> None:
        """Copy a file with lock checks."""
        if self.is_locked(src):
            raise LockedPathError(f"來源路徑已鎖定: {src}")
        if self.is_locked(dst):
            raise LockedPathError(f"目標路徑已鎖定: {dst}")
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self._audit("file_copied", {"src": src, "dst": dst})

    def safe_move(self, src: str, dst: str) -> None:
        """Move a file with lock checks and backup."""
        if self.is_locked(src):
            raise LockedPathError(f"來源路徑已鎖定: {src}")
        if self.is_locked(dst):
            raise LockedPathError(f"目標路徑已鎖定: {dst}")
        self._backup_file(src)
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        self._audit("file_moved", {"src": src, "dst": dst})

    # ── Backup ────────────────────────────────────────────────────────────────

    def _backup_file(self, path: str) -> Path:
        """Copy file to BACKUP_DIR with timestamp suffix."""
        backup_dir = self._settings.get_backup_dir()
        src = Path(path)
        if not src.exists():
            return backup_dir / "nonexistent"

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = str(src.absolute()).replace("/", "_").replace("\\", "_")
        backup_name = f"{stamp}_{safe_name[-80:]}"
        backup_path = backup_dir / backup_name

        try:
            if src.is_dir():
                shutil.copytree(str(src), str(backup_path), dirs_exist_ok=True)
            else:
                shutil.copy2(str(src), str(backup_path))
            logger.debug("已備份: %s -> %s", path, backup_path)
        except Exception as exc:
            logger.warning("備份失敗 %s: %s", path, exc)

        return backup_path

    # ── Watchdog monitoring ───────────────────────────────────────────────────

    def start_watching(self, path: str) -> None:
        """Start watchdog observer to detect external file changes."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def __init__(self, fm: FileManager) -> None:
                    self._fm = fm

                def on_modified(self, event: Any) -> None:
                    if not event.is_directory:
                        self._fm._on_file_changed(event.src_path, "modified")

                def on_created(self, event: Any) -> None:
                    if not event.is_directory:
                        self._fm._on_file_changed(event.src_path, "created")

                def on_deleted(self, event: Any) -> None:
                    self._fm._on_file_changed(event.src_path, "deleted")

            if self._observer:
                self._observer.stop()

            self._observer = Observer()
            self._observer.schedule(_Handler(self), path, recursive=True)
            self._observer.start()
            logger.info("文件監控已啟動: %s", path)
        except Exception as exc:
            logger.warning("文件監控啟動失敗: %s", exc)

    def stop_watching(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def on_change(self, callback: Callable[[str, str], None]) -> None:
        """Register callback(path, event_type) for file change events."""
        self._change_callbacks.append(callback)

    def _on_file_changed(self, path: str, event_type: str) -> None:
        for cb in self._change_callbacks:
            try:
                cb(path, event_type)
            except Exception as exc:
                logger.warning("文件變化回調錯誤: %s", exc)

    # ── Audit ─────────────────────────────────────────────────────────────────

    def _audit(self, event: str, data: dict) -> None:
        entry = {"ts": datetime.utcnow().isoformat(), "event": event, **data}
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("文件審計日誌失敗: %s", exc)


# Type placeholder
Any = type(None).__class__

# Global singleton
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
        _file_manager.load_persisted_locks()
    return _file_manager
