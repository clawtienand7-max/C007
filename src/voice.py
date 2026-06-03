"""
TFNK™ Voice Manager
Cantonese STT (faster-whisper) + TTS (edge-tts zh-HK-HiuMaanNeural).
Push-to-talk, always-on, wake-word detection, WebSocket streaming.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import queue
import threading
import time
import wave
from typing import Any, Callable, Optional

logger = logging.getLogger("tfnk.voice")

WAKE_WORDS = {"聽", "tfnk", "TFNK", "天飛", "天風"}
TTS_VOICE = "zh-HK-HiuMaanNeural"
WHISPER_MODEL = "base"
WHISPER_LANG = "zh"


class VoiceManager:
    """
    Unified voice module for TFNK™.
    - STT  : faster-whisper (Cantonese, language='zh')
    - TTS  : edge-tts zh-HK-HiuMaanNeural (female, magnetic)
    - Modes: push-to-talk | always-on
    - Wake word: 聽 / TFNK triggers callback
    """

    def __init__(self) -> None:
        self._whisper_model: Any = None
        self._whisper_lock = asyncio.Lock()
        self._always_on = False
        self._ptt_active = False
        self._stop_listen = threading.Event()
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._ws_clients: list[Any] = []  # WebSocket connections for streaming

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_whisper(self) -> Any:
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                self._whisper_model = WhisperModel(
                    WHISPER_MODEL,
                    device="cpu",
                    compute_type="int8",
                )
                logger.info("Whisper 模型已載入: %s", WHISPER_MODEL)
            except Exception as exc:
                logger.error("Whisper 模型載入失敗: %s", exc)
                raise
        return self._whisper_model

    # ── STT ───────────────────────────────────────────────────────────────────

    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """
        Convert raw audio bytes (WAV/PCM) to Cantonese text.
        Returns transcription string (Traditional Chinese).
        """
        async with self._whisper_lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._transcribe_sync, audio_bytes)

    def _transcribe_sync(self, audio_bytes: bytes) -> str:
        model = self._load_whisper()
        audio_file = io.BytesIO(audio_bytes)
        try:
            segments, info = model.transcribe(
                audio_file,
                language=WHISPER_LANG,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
            raw = " ".join(text_parts)
            logger.debug("STT 識別結果: %s (語言: %s, 信心: %.2f)",
                         raw, info.language, info.language_probability)
            return raw
        except Exception as exc:
            logger.error("STT 轉錄失敗: %s", exc)
            return ""

    # ── Wake word detection ───────────────────────────────────────────────────

    async def listen_for_wake_word(self, callback: Callable[[str], Any]) -> None:
        """
        Continuously listen for wake words (聽 / TFNK).
        On detection, calls callback(transcript) asynchronously.
        Non-blocking: runs in background thread.
        """
        self._stop_listen.clear()
        loop = asyncio.get_event_loop()
        logger.info("喚醒詞偵測已啟動 (監聽: %s)", WAKE_WORDS)

        def _listen_thread() -> None:
            try:
                import pyaudio  # type: ignore
                pa = pyaudio.PyAudio()
                CHUNK = 1024
                RATE = 16000
                CHANNELS = 1
                FORMAT = pyaudio.paInt16
                WINDOW_SECONDS = 2

                stream = pa.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                )
                frames_per_window = int(RATE / CHUNK * WINDOW_SECONDS)
                buffer: list[bytes] = []

                while not self._stop_listen.is_set():
                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                        buffer.append(data)
                        if len(buffer) >= frames_per_window:
                            audio_bytes = _frames_to_wav(buffer, RATE, CHANNELS)
                            buffer = buffer[frames_per_window // 2:]  # 50% overlap

                            # Transcribe in thread executor via run_coroutine_threadsafe
                            future = asyncio.run_coroutine_threadsafe(
                                self.transcribe_audio(audio_bytes), loop
                            )
                            try:
                                text = future.result(timeout=5)
                            except Exception:
                                text = ""

                            if text:
                                text_lower = text.lower().strip()
                                if any(w.lower() in text_lower for w in WAKE_WORDS):
                                    logger.info("喚醒詞偵測到: %s", text)
                                    asyncio.run_coroutine_threadsafe(
                                        _async_callback(callback, text), loop
                                    )
                    except Exception as read_exc:
                        logger.warning("音頻讀取錯誤: %s", read_exc)
                        time.sleep(0.1)

                stream.stop_stream()
                stream.close()
                pa.terminate()
            except Exception as exc:
                logger.error("喚醒詞監聽線程錯誤: %s", exc)

        t = threading.Thread(target=_listen_thread, daemon=True)
        t.start()

    def stop_listening(self) -> None:
        """Stop wake word detection thread."""
        self._stop_listen.set()
        logger.info("喚醒詞偵測已停止")

    # ── Push-to-talk ──────────────────────────────────────────────────────────

    async def start_ptt_recording(self) -> None:
        """Begin push-to-talk recording session."""
        self._ptt_active = True
        self._ptt_frames: list[bytes] = []
        logger.debug("PTT 錄音開始")

    async def stop_ptt_recording(self) -> str:
        """Stop PTT recording and return transcription."""
        self._ptt_active = False
        if not hasattr(self, "_ptt_frames") or not self._ptt_frames:
            return ""
        audio_bytes = _frames_to_wav(self._ptt_frames, 16000, 1)
        text = await self.transcribe_audio(audio_bytes)
        logger.debug("PTT 轉錄: %s", text)

        # Apply text correction
        from src.text_fix import TextFixer
        fixer = TextFixer()
        corrected, _ = fixer.fix(text)
        return corrected

    def push_ptt_chunk(self, chunk: bytes) -> None:
        """Append audio chunk during PTT session."""
        if self._ptt_active:
            if not hasattr(self, "_ptt_frames"):
                self._ptt_frames = []
            self._ptt_frames.append(chunk)

    # ── TTS ───────────────────────────────────────────────────────────────────

    async def speak(self, text: str) -> bytes:
        """
        Convert text to speech using edge-tts zh-HK-HiuMaanNeural.
        Returns MP3 audio bytes.
        """
        import edge_tts

        if not text.strip():
            return b""

        communicate = edge_tts.Communicate(text, voice=TTS_VOICE)
        audio_chunks: list[bytes] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        audio_bytes = b"".join(audio_chunks)
        logger.debug("TTS 生成完成: %d 字元 -> %d bytes", len(text), len(audio_bytes))
        return audio_bytes

    async def speak_streaming(self, text: str, ws_send: Callable[[bytes], Any]) -> None:
        """
        Stream TTS audio in real-time to a WebSocket callback.
        Useful for low-latency voice responses.
        """
        import edge_tts

        if not text.strip():
            return

        communicate = edge_tts.Communicate(text, voice=TTS_VOICE)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await ws_send(chunk["data"])

    # ── Text correction pipeline ──────────────────────────────────────────────

    async def transcribe_and_fix(self, audio_bytes: bytes) -> tuple[str, str]:
        """
        Transcribe audio and apply Cantonese text correction.
        Returns (corrected_text, original_text).
        """
        original = await self.transcribe_audio(audio_bytes)
        if not original:
            return "", ""

        from src.text_fix import TextFixer
        fixer = TextFixer()
        corrected, diff = fixer.fix(original)
        return corrected, original

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        mode = "always" if self._always_on else ("ptt" if self._ptt_active else "off")
        return {
            "voice_mode": mode,          # frontend alias: off / ptt / always
            "wake_word": list(WAKE_WORDS)[0] if WAKE_WORDS else "嘿 TFNK",
            "whisper_loaded": self._whisper_model is not None,
            "whisper_model": WHISPER_MODEL,
            "tts_voice": TTS_VOICE,
            "always_on": self._always_on,
            "ptt_active": self._ptt_active,
            "wake_words": list(WAKE_WORDS),
            "listening": not self._stop_listen.is_set(),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _frames_to_wav(frames: list[bytes], rate: int, channels: int) -> bytes:
    """Pack raw PCM frames into WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    return buf.getvalue()


async def _async_callback(callback: Callable, text: str) -> None:
    try:
        result = callback(text)
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:
        logger.error("喚醒詞回調錯誤: %s", exc)


# Global singleton
_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager
