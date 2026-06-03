"""
TFNK™ System Controller
Screen capture, application control, keyboard/mouse automation via pyautogui.
Includes safety checks and failsafe enforcement.
"""
from __future__ import annotations

import io
import logging
import platform
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

import psutil  # type: ignore

logger = logging.getLogger("tfnk.controller")

# Safety: these characters are never typed without explicit confirmation
_DANGEROUS_SEQUENCES = (
    "rm -rf",
    "format",
    "del /f",
    "DROP TABLE",
    ":(){:|:&};:",  # fork bomb
)


class SystemController:
    """
    Safe interface for OS-level automation:
    - System stats (CPU/RAM/GPU/disk/network)
    - Screenshots
    - Application launching
    - Keyboard + mouse automation (with safety checks)
    """

    def __init__(self, failsafe: bool = True) -> None:
        self._failsafe_enabled = failsafe
        self._pyautogui: Optional[Any] = None
        self._initialized = False

    @property
    def failsafe_enabled(self) -> bool:
        return self._failsafe_enabled

    @failsafe_enabled.setter
    def failsafe_enabled(self, value: bool) -> None:
        self._failsafe_enabled = value
        if self._pyautogui:
            self._pyautogui.FAILSAFE = value

    def _get_pyautogui(self) -> Any:
        if self._pyautogui is None:
            try:
                import pyautogui  # type: ignore
                pyautogui.FAILSAFE = self._failsafe_enabled
                pyautogui.PAUSE = 0.05
                self._pyautogui = pyautogui
                self._initialized = True
                logger.info("pyautogui 已初始化 (failsafe=%s)", self._failsafe_enabled)
            except Exception as exc:
                logger.error("pyautogui 初始化失敗: %s", exc)
                raise
        return self._pyautogui

    # ── System stats ──────────────────────────────────────────────────────────

    def get_system_stats(self) -> Dict[str, Any]:
        """Return current system resource utilization."""
        stats: Dict[str, Any] = {}

        # CPU
        cpu_pct = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        stats["cpu"] = {
            "percent": cpu_pct,
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
            "freq_mhz": cpu_freq.current if cpu_freq else None,
        }

        # RAM
        ram = psutil.virtual_memory()
        stats["ram"] = {
            "total_gb": round(ram.total / 1e9, 2),
            "used_gb": round(ram.used / 1e9, 2),
            "available_gb": round(ram.available / 1e9, 2),
            "percent": ram.percent,
        }

        # Swap
        swap = psutil.swap_memory()
        stats["swap"] = {
            "total_gb": round(swap.total / 1e9, 2),
            "used_gb": round(swap.used / 1e9, 2),
            "percent": swap.percent,
        }

        # Disk
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        stats["disk"] = {
            "total_gb": round(disk.total / 1e9, 2),
            "used_gb": round(disk.used / 1e9, 2),
            "free_gb": round(disk.free / 1e9, 2),
            "percent": disk.percent,
            "read_mb_s": round(disk_io.read_bytes / 1e6, 2) if disk_io else None,
            "write_mb_s": round(disk_io.write_bytes / 1e6, 2) if disk_io else None,
        }

        # Network
        net_io = psutil.net_io_counters()
        stats["network"] = {
            "bytes_sent_mb": round(net_io.bytes_sent / 1e6, 2),
            "bytes_recv_mb": round(net_io.bytes_recv / 1e6, 2),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }

        # GPU (try nvidia-smi)
        stats["gpu"] = self._get_gpu_stats()

        # Processes
        stats["process_count"] = len(psutil.pids())

        # Platform
        stats["platform"] = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        }

        # Tokens/second placeholder (populated by agent runtime)
        stats["tokens_per_second"] = None

        return stats

    def _get_gpu_stats(self) -> Dict[str, Any]:
        """Try to get NVIDIA GPU stats via nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                gpus = []
                for line in lines:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        try:
                            gpus.append({
                                "name": parts[0],
                                "temperature_c": int(parts[1]),
                                "utilization_percent": int(parts[2]),
                                "vram_used_mb": int(parts[3]),
                                "vram_total_mb": int(parts[4]),
                                "vram_percent": round(int(parts[3]) / max(int(parts[4]), 1) * 100, 1),
                            })
                        except (ValueError, IndexError):
                            pass
                return {"gpus": gpus, "available": True}
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.debug("nvidia-smi 查詢失敗: %s", exc)

        # Try rocm-smi for AMD
        try:
            result = subprocess.run(
                ["rocm-smi", "--showuse", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return {"gpus": [data], "available": True, "vendor": "AMD"}
        except Exception:
            pass

        return {"gpus": [], "available": False}

    # ── Screenshot ────────────────────────────────────────────────────────────

    def take_screenshot(self) -> bytes:
        """Capture a full-screen screenshot and return PNG bytes."""
        try:
            pag = self._get_pyautogui()
            screenshot = pag.screenshot()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.error("截圖失敗: %s", exc)
            # Return empty 1x1 PNG
            from PIL import Image as PILImage
            img = PILImage.new("RGB", (1, 1), color=(0, 0, 0))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    def take_region_screenshot(
        self, x: int, y: int, width: int, height: int
    ) -> bytes:
        """Capture a specific screen region."""
        pag = self._get_pyautogui()
        screenshot = pag.screenshot(region=(x, y, width, height))
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return buf.getvalue()

    # ── Application control ───────────────────────────────────────────────────

    def open_application(self, name: str) -> bool:
        """
        Open an application by name.
        Platform-aware: uses xdg-open on Linux, open on macOS, start on Windows.
        """
        system = platform.system()
        logger.info("開啟應用程式: %s (系統: %s)", name, system)

        try:
            if system == "Linux":
                subprocess.Popen(
                    ["xdg-open", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif system == "Darwin":
                subprocess.Popen(
                    ["open", "-a", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            elif system == "Windows":
                subprocess.Popen(
                    ["start", "", name],
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    [name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            return True
        except Exception as exc:
            logger.error("開啟應用程式失敗 '%s': %s", name, exc)
            return False

    def list_running_apps(self) -> list:
        """Return list of running process names."""
        apps = []
        for proc in psutil.process_iter(["pid", "name", "status"]):
            try:
                apps.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "status": proc.info["status"],
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return apps

    # ── Keyboard / Mouse ──────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.02) -> None:
        """
        Type text using pyautogui with safety checks.
        Raises ValueError for dangerous sequences.
        """
        self._check_text_safety(text)
        pag = self._get_pyautogui()
        pag.typewrite(text, interval=interval)
        logger.debug("已輸入文字: %s...", text[:20])

    def press_key(self, key: str) -> None:
        """Press a keyboard key."""
        pag = self._get_pyautogui()
        pag.press(key)

    def hotkey(self, *keys: str) -> None:
        """Press a keyboard shortcut combination."""
        pag = self._get_pyautogui()
        pag.hotkey(*keys)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        """
        Click at screen coordinates with safety check.
        Failsafe: move mouse to top-left corner to abort.
        """
        screen_w, screen_h = self._get_screen_size()
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            raise ValueError(f"點擊座標超出螢幕範圍: ({x}, {y})")

        pag = self._get_pyautogui()
        pag.click(x, y, button=button, clicks=clicks)
        logger.debug("已點擊: (%d, %d) [%s]", x, y, button)

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def double_click(self, x: int, y: int) -> None:
        self.click(x, y, clicks=2)

    def move_mouse(self, x: int, y: int, duration: float = 0.1) -> None:
        """Move mouse to coordinates."""
        pag = self._get_pyautogui()
        pag.moveTo(x, y, duration=duration)

    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.3,
    ) -> None:
        """Click and drag from start to end coordinates."""
        pag = self._get_pyautogui()
        pag.drag(start_x, start_y, end_x, end_y, duration=duration)

    def scroll(self, x: int, y: int, clicks: int = 3) -> None:
        """Scroll at coordinates. Positive = up, negative = down."""
        pag = self._get_pyautogui()
        pag.scroll(clicks, x=x, y=y)

    def get_mouse_position(self) -> Tuple[int, int]:
        """Return current mouse (x, y) position."""
        pag = self._get_pyautogui()
        pos = pag.position()
        return (pos.x, pos.y)

    def _get_screen_size(self) -> Tuple[int, int]:
        try:
            pag = self._get_pyautogui()
            return pag.size()
        except Exception:
            return (1920, 1080)

    @staticmethod
    def _check_text_safety(text: str) -> None:
        """Raise ValueError if text contains dangerous sequences."""
        for seq in _DANGEROUS_SEQUENCES:
            if seq.lower() in text.lower():
                raise ValueError(
                    f"輸入文字包含危險序列，已阻止: '{seq}'"
                )

    # ── Window management ─────────────────────────────────────────────────────

    def list_windows(self) -> list:
        """Return list of open windows (Linux/macOS/Windows)."""
        windows = []
        try:
            import pygetwindow as gw  # type: ignore
            for win in gw.getAllWindows():
                windows.append({
                    "title": win.title,
                    "left": win.left,
                    "top": win.top,
                    "width": win.width,
                    "height": win.height,
                    "is_active": win.isActive,
                })
        except Exception as exc:
            logger.warning("視窗列表獲取失敗: %s", exc)
        return windows

    def focus_window(self, title: str) -> bool:
        """Bring window with given title to focus."""
        try:
            import pygetwindow as gw  # type: ignore
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                time.sleep(0.2)
                return True
        except Exception as exc:
            logger.warning("視窗聚焦失敗 '%s': %s", title, exc)
        return False


# Global singleton
_controller: Optional[SystemController] = None


def get_controller() -> SystemController:
    global _controller
    if _controller is None:
        _controller = SystemController(failsafe=True)
    return _controller
