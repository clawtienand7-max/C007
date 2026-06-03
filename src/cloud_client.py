"""
TFNK™ Cloud Client
Unified interface for Ollama, OpenRouter, Groq, Gemini, Anthropic,
YouTube Data API v3, Google Custom Search, and image generation.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger("tfnk.cloud")


class CloudClient:
    """
    Aggregated cloud service client for TFNK™.
    All methods are async and production-ready.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Ollama ────────────────────────────────────────────────────────────────

    async def ollama_list_models(self) -> List[Dict[str, Any]]:
        """List all locally available Ollama models."""
        base = self._settings.ollama_base_url
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base}/api/tags")
            resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        return [
            {
                "name": m.get("name"),
                "size": m.get("size"),
                "modified_at": m.get("modified_at"),
                "digest": m.get("digest"),
                "provider": "Ollama (本地)",
            }
            for m in models
        ]

    async def ollama_get_model_info(self, model: str) -> Dict[str, Any]:
        """Get detailed info about a specific Ollama model."""
        base = self._settings.ollama_base_url
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{base}/api/show", json={"name": model})
            resp.raise_for_status()
        return resp.json()

    async def ollama_chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream chat completion from Ollama."""
        base = self._settings.ollama_base_url
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{base}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            pass

    # ── OpenRouter ────────────────────────────────────────────────────────────

    async def openrouter_list_free_models(self) -> List[Dict[str, Any]]:
        """Fetch all models from OpenRouter, filter to free tier."""
        key = self._settings.openrouter_api_key
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
            )
            resp.raise_for_status()
        data = resp.json().get("data", [])
        free_models = []
        for m in data:
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "1"))
            if prompt_price == 0:
                free_models.append({
                    "id": m.get("id"),
                    "name": m.get("name"),
                    "context_length": m.get("context_length"),
                    "description": m.get("description", ""),
                    "provider": "OpenRouter (免費)",
                })
        return free_models

    async def openrouter_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> str:
        """Chat via OpenRouter API."""
        key = self._settings.openrouter_api_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY 未設置")

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "https://tfnk.app",
                    "X-Title": "TFNK™",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": all_messages,
                    "max_tokens": max_tokens,
                    "stream": stream,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ── Groq ──────────────────────────────────────────────────────────────────

    async def groq_chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream chat completion from Groq."""
        key = self._settings.groq_api_key
        if not key:
            raise ValueError("GROQ_API_KEY 未設置")

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": all_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(payload)
                            delta = data["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

    # ── Gemini ────────────────────────────────────────────────────────────────

    async def gemini_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> str:
        """Chat via Google Gemini API."""
        key = self._settings.gemini_api_key
        if not key:
            raise ValueError("GEMINI_API_KEY 未設置")

        # Build Gemini content format
        contents = []
        if system:
            # Gemini uses system_instruction at model level
            pass
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                params={"key": key},
                json=body,
            )
            resp.raise_for_status()
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Gemini 回應格式錯誤: {data}") from exc

    # ── Anthropic ─────────────────────────────────────────────────────────────

    async def anthropic_chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
        use_cache: bool = True,
    ) -> AsyncIterator[str]:
        """
        Stream chat from Anthropic Claude with prompt caching enabled.
        System prompt is cached using cache_control for efficiency.
        """
        key = self._settings.anthropic_api_key
        if not key:
            raise ValueError("ANTHROPIC_API_KEY 未設置")

        import anthropic as anthropic_sdk

        client = anthropic_sdk.AsyncAnthropic(api_key=key)

        # Build system with cache control for large prompts
        sys_content: Any = system or "你是 TFNK™ 智能助理，請用繁體中文回答。"
        if use_cache and isinstance(sys_content, str) and len(sys_content) > 500:
            sys_content = [
                {
                    "type": "text",
                    "text": sys_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=sys_content,
            messages=messages,
        ) as stream:
            async for text_chunk in stream.text_stream:
                yield text_chunk

    async def anthropic_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming Anthropic chat."""
        key = self._settings.anthropic_api_key
        if not key:
            raise ValueError("ANTHROPIC_API_KEY 未設置")

        import anthropic as anthropic_sdk

        client = anthropic_sdk.AsyncAnthropic(api_key=key)
        msg = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "你是 TFNK™ 智能助理，請用繁體中文回答。",
            messages=messages,
        )
        return msg.content[0].text

    # ── YouTube Data API v3 ───────────────────────────────────────────────────

    async def youtube_search(
        self,
        query: str,
        max_results: int = 10,
        order: str = "relevance",
    ) -> List[Dict[str, Any]]:
        """Search YouTube videos."""
        key = self._settings.youtube_api_key
        if not key:
            raise ValueError("YOUTUBE_API_KEY 未設置")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": query,
                    "maxResults": max_results,
                    "order": order,
                    "type": "video",
                    "key": key,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", []):
            snip = item.get("snippet", {})
            vid_id = item.get("id", {}).get("videoId", "")
            results.append({
                "video_id": vid_id,
                "title": snip.get("title", ""),
                "description": snip.get("description", ""),
                "channel": snip.get("channelTitle", ""),
                "published_at": snip.get("publishedAt", ""),
                "thumbnail": snip.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            })
        return results

    async def youtube_get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Get detailed info for a YouTube video."""
        key = self._settings.youtube_api_key
        if not key:
            raise ValueError("YOUTUBE_API_KEY 未設置")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": video_id,
                    "key": key,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            raise ValueError(f"影片不存在: {video_id}")
        item = items[0]
        snip = item.get("snippet", {})
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {})
        return {
            "video_id": video_id,
            "title": snip.get("title", ""),
            "description": snip.get("description", ""),
            "channel": snip.get("channelTitle", ""),
            "published_at": snip.get("publishedAt", ""),
            "duration": details.get("duration", ""),
            "views": stats.get("viewCount", "0"),
            "likes": stats.get("likeCount", "0"),
            "comments": stats.get("commentCount", "0"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }

    async def youtube_list_uploads(
        self, channel_id: str, max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent uploads from a YouTube channel."""
        key = self._settings.youtube_api_key
        if not key:
            raise ValueError("YOUTUBE_API_KEY 未設置")

        # First get uploads playlist ID
        async with httpx.AsyncClient(timeout=15) as client:
            ch_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "contentDetails",
                    "id": channel_id,
                    "key": key,
                },
            )
            ch_resp.raise_for_status()
        ch_data = ch_resp.json()
        ch_items = ch_data.get("items", [])
        if not ch_items:
            raise ValueError(f"頻道不存在: {channel_id}")
        uploads_playlist = ch_items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Get uploads
        async with httpx.AsyncClient(timeout=15) as client:
            pl_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/playlistItems",
                params={
                    "part": "snippet",
                    "playlistId": uploads_playlist,
                    "maxResults": max_results,
                    "key": key,
                },
            )
            pl_resp.raise_for_status()
        pl_data = pl_resp.json()
        videos = []
        for item in pl_data.get("items", []):
            snip = item.get("snippet", {})
            vid_id = snip.get("resourceId", {}).get("videoId", "")
            videos.append({
                "video_id": vid_id,
                "title": snip.get("title", ""),
                "published_at": snip.get("publishedAt", ""),
                "thumbnail": snip.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={vid_id}",
            })
        return videos

    # ── Google Custom Search ──────────────────────────────────────────────────

    async def google_search(
        self, query: str, num: int = 10, safe: str = "off"
    ) -> List[Dict[str, Any]]:
        """Perform Google Custom Search."""
        settings = self._settings
        if not settings.google_api_key or not settings.google_cse_id:
            raise ValueError("GOOGLE_API_KEY 和 GOOGLE_CSE_ID 未設置")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": settings.google_api_key,
                    "cx": settings.google_cse_id,
                    "q": query,
                    "num": min(num, 10),
                    "safe": safe,
                },
            )
            resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "display_url": item.get("displayLink", ""),
                "image": item.get("pagemap", {}).get("cse_image", [{}])[0].get("src", ""),
            })
        return results

    # ── Image Generation ──────────────────────────────────────────────────────

    async def generate_image_flux(
        self, prompt: str, width: int = 1024, height: int = 1024
    ) -> bytes:
        """Generate image via FLUX.1-schnell on HuggingFace."""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
                headers={"Content-Type": "application/json"},
                json={"inputs": prompt, "parameters": {"width": width, "height": height}},
            )
            resp.raise_for_status()
        return resp.content

    async def generate_image_sdxl(self, prompt: str) -> bytes:
        """Generate image via Stable Diffusion XL on HuggingFace."""
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
                headers={"Content-Type": "application/json"},
                json={"inputs": prompt},
            )
            resp.raise_for_status()
        return resp.content

    # ── YouTube Download (yt-dlp) ─────────────────────────────────────────────

    async def youtube_download(
        self,
        url: str,
        output_dir: str = "/tmp",
        format: str = "best[ext=mp4]",
        audio_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Download YouTube video using yt-dlp.
        Returns metadata about the downloaded file.
        """
        import yt_dlp  # type: ignore
        import asyncio

        ydl_opts: Dict[str, Any] = {
            "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
        }

        if audio_only:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            ydl_opts["format"] = format

        result: Dict[str, Any] = {}

        def _download() -> None:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    result["title"] = info.get("title", "")
                    result["duration"] = info.get("duration", 0)
                    result["uploader"] = info.get("uploader", "")
                    result["ext"] = info.get("ext", "mp4")
                    result["filepath"] = ydl.prepare_filename(info)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _download)
        return result

    # ── Universal chat dispatcher ─────────────────────────────────────────────

    async def chat(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        stream: bool = False,
    ) -> Any:
        """
        Unified chat interface. Routes to the appropriate provider.
        provider: anthropic | openai | openrouter | groq | gemini | ollama
        """
        if provider == "anthropic":
            if stream:
                return self.anthropic_chat_stream(model, messages, system, max_tokens)
            return await self.anthropic_chat(model, messages, system, max_tokens)

        elif provider == "groq":
            if stream:
                return self.groq_chat_stream(model, messages, system, max_tokens)
            chunks: List[str] = []
            async for chunk in self.groq_chat_stream(model, messages, system, max_tokens):
                chunks.append(chunk)
            return "".join(chunks)

        elif provider == "openrouter":
            return await self.openrouter_chat(model, messages, system, max_tokens)

        elif provider == "gemini":
            return await self.gemini_chat(model, messages, system, max_tokens)

        elif provider == "ollama":
            if stream:
                return self.ollama_chat_stream(model, messages, system)
            chunks = []
            async for chunk in self.ollama_chat_stream(model, messages, system):
                chunks.append(chunk)
            return "".join(chunks)

        else:
            raise ValueError(f"不支援的提供商: {provider}")


# Global singleton
_cloud_client: Optional[CloudClient] = None


def get_cloud_client() -> CloudClient:
    global _cloud_client
    if _cloud_client is None:
        _cloud_client = CloudClient()
    return _cloud_client
