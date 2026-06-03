"""
TFNK™ Intelligence Center
Daily AI model comparison, news, free models, agent comparison, popular tools.
All data cached in memory/intel_cache.json, updated by scheduler daily.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.config import get_settings

logger = logging.getLogger("tfnk.intel")

CACHE_TTL_HOURS = 24


# ── Static reference data ─────────────────────────────────────────────────────

MODEL_REFERENCE: List[Dict[str, Any]] = [
    {
        "name": "claude-opus-4-5",
        "provider": "Anthropic",
        "context_window": 200_000,
        "pricing_in_per_1m": 15.0,
        "pricing_out_per_1m": 75.0,
        "strengths": ["推理", "長文本", "程式碼", "繁體中文", "分析"],
        "multimodal": True,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "claude-3-5-sonnet-20241022",
        "provider": "Anthropic",
        "context_window": 200_000,
        "pricing_in_per_1m": 3.0,
        "pricing_out_per_1m": 15.0,
        "strengths": ["程式碼", "推理", "速度", "多模態"],
        "multimodal": True,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "claude-3-haiku-20240307",
        "provider": "Anthropic",
        "context_window": 200_000,
        "pricing_in_per_1m": 0.25,
        "pricing_out_per_1m": 1.25,
        "strengths": ["速度", "低成本", "摘要"],
        "multimodal": True,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "gpt-4o",
        "provider": "OpenAI",
        "context_window": 128_000,
        "pricing_in_per_1m": 2.5,
        "pricing_out_per_1m": 10.0,
        "strengths": ["多模態", "推理", "程式碼", "工具使用"],
        "multimodal": True,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "gpt-4o-mini",
        "provider": "OpenAI",
        "context_window": 128_000,
        "pricing_in_per_1m": 0.15,
        "pricing_out_per_1m": 0.60,
        "strengths": ["速度", "低成本", "多模態"],
        "multimodal": True,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "gemini-1.5-pro",
        "provider": "Google",
        "context_window": 2_000_000,
        "pricing_in_per_1m": 1.25,
        "pricing_out_per_1m": 5.0,
        "strengths": ["超長上下文", "多模態", "程式碼"],
        "multimodal": True,
        "open_source": False,
        "available_free": True,
    },
    {
        "name": "gemini-2.0-flash",
        "provider": "Google",
        "context_window": 1_000_000,
        "pricing_in_per_1m": 0.075,
        "pricing_out_per_1m": 0.30,
        "strengths": ["速度", "低成本", "免費層"],
        "multimodal": True,
        "open_source": False,
        "available_free": True,
    },
    {
        "name": "llama-3.3-70b-versatile",
        "provider": "Meta / Groq",
        "context_window": 128_000,
        "pricing_in_per_1m": 0.59,
        "pricing_out_per_1m": 0.79,
        "strengths": ["開源", "本地部署", "速度", "免費API"],
        "multimodal": False,
        "open_source": True,
        "available_free": True,
    },
    {
        "name": "llama-3.1-8b-instant",
        "provider": "Meta / Groq",
        "context_window": 128_000,
        "pricing_in_per_1m": 0.05,
        "pricing_out_per_1m": 0.08,
        "strengths": ["超低成本", "開源", "快速"],
        "multimodal": False,
        "open_source": True,
        "available_free": True,
    },
    {
        "name": "mistral-large-2407",
        "provider": "Mistral AI",
        "context_window": 128_000,
        "pricing_in_per_1m": 2.0,
        "pricing_out_per_1m": 6.0,
        "strengths": ["歐洲AI", "程式碼", "多語言", "開源版本"],
        "multimodal": False,
        "open_source": False,
        "available_free": False,
    },
    {
        "name": "mixtral-8x7b-32768",
        "provider": "Mistral AI / Groq",
        "context_window": 32_768,
        "pricing_in_per_1m": 0.24,
        "pricing_out_per_1m": 0.24,
        "strengths": ["MoE架構", "開源", "免費API"],
        "multimodal": False,
        "open_source": True,
        "available_free": True,
    },
    {
        "name": "qwen2.5-72b-instruct",
        "provider": "Alibaba / OpenRouter",
        "context_window": 128_000,
        "pricing_in_per_1m": 0.35,
        "pricing_out_per_1m": 0.40,
        "strengths": ["中文", "程式碼", "開源", "長上下文"],
        "multimodal": False,
        "open_source": True,
        "available_free": True,
    },
    {
        "name": "deepseek-r1",
        "provider": "DeepSeek / OpenRouter",
        "context_window": 64_000,
        "pricing_in_per_1m": 0.55,
        "pricing_out_per_1m": 2.19,
        "strengths": ["推理", "開源", "數學", "低成本"],
        "multimodal": False,
        "open_source": True,
        "available_free": False,
    },
]

AGENT_COMPARISON: List[Dict[str, Any]] = [
    {
        "name": "TFNK™",
        "description": "自主代理桌面應用，繁體中文，Manus風格循環",
        "features": {
            "autonomous_loop": True,
            "voice_cantonese": True,
            "screen_translate": True,
            "skills_system": True,
            "mobile_bridge": True,
            "local_models": True,
            "finance_integration": True,
            "scheduler": True,
            "file_safety": True,
            "knowledge_graph": True,
        },
        "language": "繁體中文（廣東話）",
        "open_source": False,
    },
    {
        "name": "Manus",
        "description": "中國自主代理平台，多步驟任務執行",
        "features": {
            "autonomous_loop": True,
            "voice_cantonese": False,
            "screen_translate": False,
            "skills_system": True,
            "mobile_bridge": False,
            "local_models": False,
            "finance_integration": False,
            "scheduler": True,
            "file_safety": True,
            "knowledge_graph": False,
        },
        "language": "中文 / 英文",
        "open_source": False,
    },
    {
        "name": "Claude (Anthropic)",
        "description": "Anthropic的對話AI，工具使用",
        "features": {
            "autonomous_loop": False,
            "voice_cantonese": False,
            "screen_translate": False,
            "skills_system": False,
            "mobile_bridge": False,
            "local_models": False,
            "finance_integration": False,
            "scheduler": False,
            "file_safety": False,
            "knowledge_graph": False,
        },
        "language": "多語言",
        "open_source": False,
    },
    {
        "name": "OpenHands (OpenClaw)",
        "description": "開源代理框架，程式碼為主",
        "features": {
            "autonomous_loop": True,
            "voice_cantonese": False,
            "screen_translate": False,
            "skills_system": False,
            "mobile_bridge": False,
            "local_models": True,
            "finance_integration": False,
            "scheduler": False,
            "file_safety": True,
            "knowledge_graph": False,
        },
        "language": "英文",
        "open_source": True,
    },
    {
        "name": "Hermes",
        "description": "技能驅動代理，技能庫自動積累",
        "features": {
            "autonomous_loop": True,
            "voice_cantonese": False,
            "screen_translate": False,
            "skills_system": True,
            "mobile_bridge": False,
            "local_models": True,
            "finance_integration": False,
            "scheduler": False,
            "file_safety": False,
            "knowledge_graph": False,
        },
        "language": "英文",
        "open_source": True,
    },
]

POPULAR_TOOLS: List[Dict[str, Any]] = [
    # Video Generation
    {
        "name": "Sora",
        "category": "影片生成",
        "provider": "OpenAI",
        "description": "文字轉影片，高品質AI影片生成",
        "url": "https://sora.com",
        "free_tier": False,
        "trending": True,
    },
    {
        "name": "Runway Gen-4",
        "category": "影片生成",
        "provider": "Runway",
        "description": "專業AI影片生成與編輯",
        "url": "https://runwayml.com",
        "free_tier": True,
        "trending": True,
    },
    {
        "name": "Kling AI",
        "category": "影片生成",
        "provider": "Kuaishou",
        "description": "高品質文字/圖像轉影片",
        "url": "https://klingai.com",
        "free_tier": True,
        "trending": True,
    },
    # Image Generation
    {
        "name": "Midjourney",
        "category": "圖像生成",
        "provider": "Midjourney",
        "description": "藝術品質AI圖像生成",
        "url": "https://midjourney.com",
        "free_tier": False,
        "trending": True,
    },
    {
        "name": "FLUX.1",
        "category": "圖像生成",
        "provider": "Black Forest Labs",
        "description": "開源高品質圖像生成",
        "url": "https://blackforestlabs.ai",
        "free_tier": True,
        "trending": True,
    },
    {
        "name": "Stable Diffusion 3.5",
        "category": "圖像生成",
        "provider": "Stability AI",
        "description": "開源圖像生成，本地部署",
        "url": "https://stability.ai",
        "free_tier": True,
        "trending": False,
    },
    # Social / Trend
    {
        "name": "Perplexity AI",
        "category": "AI搜索",
        "provider": "Perplexity",
        "description": "AI驅動的實時網絡搜索引擎",
        "url": "https://perplexity.ai",
        "free_tier": True,
        "trending": True,
    },
    {
        "name": "NotebookLM",
        "category": "文件分析",
        "provider": "Google",
        "description": "AI文件理解和播客生成",
        "url": "https://notebooklm.google.com",
        "free_tier": True,
        "trending": True,
    },
    {
        "name": "Cursor",
        "category": "程式碼編輯器",
        "provider": "Anysphere",
        "description": "AI驅動的程式碼IDE",
        "url": "https://cursor.sh",
        "free_tier": True,
        "trending": True,
    },
    {
        "name": "ElevenLabs",
        "category": "語音合成",
        "provider": "ElevenLabs",
        "description": "高擬真AI語音克隆和合成",
        "url": "https://elevenlabs.io",
        "free_tier": True,
        "trending": True,
    },
]

FREE_MODELS_STATIC: List[Dict[str, Any]] = [
    {"name": "llama-3.3-70b-versatile", "provider": "Groq", "context": 128_000, "type": "text"},
    {"name": "llama-3.1-8b-instant", "provider": "Groq", "context": 128_000, "type": "text"},
    {"name": "mixtral-8x7b-32768", "provider": "Groq", "context": 32_768, "type": "text"},
    {"name": "gemma2-9b-it", "provider": "Groq", "context": 8_192, "type": "text"},
    {"name": "gemini-2.0-flash", "provider": "Google", "context": 1_000_000, "type": "text+vision"},
    {"name": "gemini-1.5-flash", "provider": "Google", "context": 1_000_000, "type": "text+vision"},
    {"name": "gemini-1.5-pro", "provider": "Google", "context": 2_000_000, "type": "text+vision"},
    {"name": "qwen/qwen-2.5-72b-instruct:free", "provider": "OpenRouter", "context": 128_000, "type": "text"},
    {"name": "meta-llama/llama-3.2-11b-vision-instruct:free", "provider": "OpenRouter", "context": 131_072, "type": "text+vision"},
    {"name": "deepseek/deepseek-r1:free", "provider": "OpenRouter", "context": 64_000, "type": "text"},
    {"name": "microsoft/phi-3-mini-128k-instruct:free", "provider": "OpenRouter", "context": 128_000, "type": "text"},
    {"name": "google/gemma-3-27b-it:free", "provider": "OpenRouter", "context": 131_072, "type": "text"},
]


class IntelManager:
    """
    AI Intelligence Center.
    Aggregates model comparisons, AI news, free models, agent comparison,
    and popular tools. Caches everything in memory/intel_cache.json.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache_file = self._settings.get_memory_dir() / "intel_cache.json"
        self._cache: Dict[str, Any] = {}
        self.last_updated: float = 0.0
        self._load_cache()
        import time
        self.last_updated = self._cache.get("updated_at", time.time())

    # ── Cache management ──────────────────────────────────────────────────────

    def _load_cache(self) -> None:
        if self._cache_file.exists():
            try:
                self._cache = json.loads(self._cache_file.read_text(encoding="utf-8"))
                logger.info("情報緩存已載入")
            except Exception as exc:
                logger.warning("情報緩存載入失敗: %s", exc)
                self._cache = {}

    def _save_cache(self) -> None:
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._cache_file.write_text(
                json.dumps(self._cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("情報緩存保存失敗: %s", exc)

    def _is_stale(self, key: str) -> bool:
        ts = self._cache.get(f"{key}_updated_at")
        if not ts:
            return True
        updated = datetime.fromisoformat(ts)
        return datetime.utcnow() - updated > timedelta(hours=CACHE_TTL_HOURS)

    # ── Main update ───────────────────────────────────────────────────────────

    async def update_all(self) -> None:
        """Update all intelligence data sources."""
        logger.info("開始更新情報中心...")
        try:
            self._update_model_comparison()
            await self._update_ai_news()
            await self._update_free_models()
            self._update_agent_comparison()
            self._update_popular_tools()
            self._cache["last_full_update"] = datetime.utcnow().isoformat()
            self._save_cache()
            logger.info("情報中心更新完成")
        except Exception as exc:
            logger.error("情報更新失敗: %s", exc)

    # ── Model comparison ──────────────────────────────────────────────────────

    def _update_model_comparison(self) -> None:
        self._cache["model_comparison"] = MODEL_REFERENCE
        self._cache["model_comparison_updated_at"] = datetime.utcnow().isoformat()

    def get_model_comparison(self) -> List[Dict[str, Any]]:
        return self._cache.get("model_comparison", MODEL_REFERENCE)

    # ── AI News ───────────────────────────────────────────────────────────────

    async def _update_ai_news(self) -> None:
        settings = self._settings
        news: List[Dict[str, Any]] = []

        if settings.google_api_key and settings.google_cse_id:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={
                            "key": settings.google_api_key,
                            "cx": settings.google_cse_id,
                            "q": "AI 人工智能 大型語言模型 新聞",
                            "sort": "date",
                            "num": 10,
                            "dateRestrict": "d1",
                        },
                    )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    for item in items:
                        news.append({
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": item.get("link", ""),
                            "source": item.get("displayLink", ""),
                            "published": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", ""),
                        })
            except Exception as exc:
                logger.warning("Google News 搜索失敗: %s", exc)

        # Fallback: static placeholder news
        if not news:
            news = [
                {
                    "title": "AI行業每日動態",
                    "snippet": "請配置 GOOGLE_API_KEY 和 GOOGLE_CSE_ID 以獲取實時新聞",
                    "url": "https://techcrunch.com/tag/artificial-intelligence/",
                    "source": "TechCrunch",
                    "published": datetime.utcnow().isoformat(),
                }
            ]

        self._cache["ai_news"] = news
        self._cache["ai_news_updated_at"] = datetime.utcnow().isoformat()

    def get_ai_news(self) -> List[Dict[str, Any]]:
        return self._cache.get("ai_news", [])

    # ── Free models ───────────────────────────────────────────────────────────

    async def _update_free_models(self) -> None:
        models = list(FREE_MODELS_STATIC)

        # Try to fetch live list from OpenRouter
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                headers = {}
                if self._settings.openrouter_api_key:
                    headers["Authorization"] = f"Bearer {self._settings.openrouter_api_key}"
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers,
                )
            if resp.status_code == 200:
                or_models = resp.json().get("data", [])
                for m in or_models:
                    pricing = m.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", "999"))
                    if prompt_price == 0:
                        models.append({
                            "name": m.get("id", ""),
                            "provider": "OpenRouter",
                            "context": m.get("context_length", 0),
                            "type": "text",
                            "description": m.get("description", ""),
                        })
        except Exception as exc:
            logger.debug("OpenRouter 免費模型獲取失敗: %s", exc)

        # Try Groq
        try:
            headers = {}
            if self._settings.groq_api_key:
                headers["Authorization"] = f"Bearer {self._settings.groq_api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
            if resp.status_code == 200:
                groq_models = resp.json().get("data", [])
                groq_names = {m["name"] for m in models if m.get("provider") == "Groq"}
                for m in groq_models:
                    if m.get("id") not in groq_names:
                        models.append({
                            "name": m.get("id", ""),
                            "provider": "Groq (免費)",
                            "context": m.get("context_window", 32768),
                            "type": "text",
                        })
        except Exception as exc:
            logger.debug("Groq 模型列表獲取失敗: %s", exc)

        # Deduplicate
        seen = set()
        unique = []
        for m in models:
            key = (m.get("name"), m.get("provider"))
            if key not in seen:
                seen.add(key)
                unique.append(m)

        self._cache["free_models"] = unique
        self._cache["free_models_updated_at"] = datetime.utcnow().isoformat()

    def get_free_models(self) -> List[Dict[str, Any]]:
        return self._cache.get("free_models", FREE_MODELS_STATIC)

    # ── Agent comparison ──────────────────────────────────────────────────────

    def _update_agent_comparison(self) -> None:
        self._cache["agent_comparison"] = AGENT_COMPARISON
        self._cache["agent_comparison_updated_at"] = datetime.utcnow().isoformat()

    def get_agent_comparison(self) -> List[Dict[str, Any]]:
        return self._cache.get("agent_comparison", AGENT_COMPARISON)

    # ── Popular tools ─────────────────────────────────────────────────────────

    def _update_popular_tools(self) -> None:
        self._cache["popular_tools"] = POPULAR_TOOLS
        self._cache["popular_tools_updated_at"] = datetime.utcnow().isoformat()

    def get_popular_tools(self) -> List[Dict[str, Any]]:
        return self._cache.get("popular_tools", POPULAR_TOOLS)

    # ── Summary ───────────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        return {
            "last_full_update": self._cache.get("last_full_update"),
            "model_count": len(self.get_model_comparison()),
            "news_count": len(self.get_ai_news()),
            "free_model_count": len(self.get_free_models()),
            "agent_count": len(self.get_agent_comparison()),
            "tool_count": len(self.get_popular_tools()),
        }


# Global singleton
_intel_manager: Optional[IntelManager] = None


def get_intel_manager() -> IntelManager:
    global _intel_manager
    if _intel_manager is None:
        _intel_manager = IntelManager()
    return _intel_manager
