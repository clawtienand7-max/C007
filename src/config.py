"""
TFNK™ Configuration
Pydantic Settings with full .env support.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AI API Keys ──────────────────────────────────────────────────────────
    anthropic_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    google_cse_id: Optional[str] = Field(default=None)
    openrouter_api_key: Optional[str] = Field(default=None)
    groq_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)

    # ── Finance ───────────────────────────────────────────────────────────────
    longbridge_app_key: Optional[str] = Field(default=None)
    longbridge_app_secret: Optional[str] = Field(default=None)
    longbridge_access_token: Optional[str] = Field(default=None)
    alpha_vantage_api_key: Optional[str] = Field(default=None)
    finnhub_api_key: Optional[str] = Field(default=None)

    # ── Media ─────────────────────────────────────────────────────────────────
    youtube_api_key: Optional[str] = Field(default=None)

    # ── Network / Mobile ─────────────────────────────────────────────────────
    tailscale_auth_key: Optional[str] = Field(default=None)
    mobile_auth_token: Optional[str] = Field(default="tfnk-mobile-token-change-me")

    # ── Directories ───────────────────────────────────────────────────────────
    backup_dir: str = Field(default="./backups")
    log_dir: str = Field(default="./logs")
    memory_dir: str = Field(default="./memory")
    skills_dir: str = Field(default="./skills")

    # ── Agent Behaviour ───────────────────────────────────────────────────────
    agent_mode: str = Field(default="basic")  # basic | thinking | collaborative

    lock_list: str = Field(default="")  # comma-separated absolute paths

    # Tool policies: allow | deny | confirm
    tool_policy_web_search: str = Field(default="allow")
    tool_policy_read_file: str = Field(default="allow")
    tool_policy_write_file: str = Field(default="confirm")
    tool_policy_delete_file: str = Field(default="confirm")
    tool_policy_run_code: str = Field(default="confirm")
    tool_policy_system_command: str = Field(default="confirm")
    tool_policy_browser_action: str = Field(default="allow")

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434")

    # ── Server ────────────────────────────────────────────────────────────────
    server_host: str = Field(default="0.0.0.0")
    server_port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # ── Derived properties ────────────────────────────────────────────────────
    @property
    def lock_list_parsed(self) -> List[str]:
        """Return the lock list as a Python list of strings."""
        if not self.lock_list:
            return []
        return [p.strip() for p in self.lock_list.split(",") if p.strip()]

    @property
    def tool_policies(self) -> dict[str, str]:
        return {
            "web_search": self.tool_policy_web_search,
            "read_file": self.tool_policy_read_file,
            "write_file": self.tool_policy_write_file,
            "delete_file": self.tool_policy_delete_file,
            "run_code": self.tool_policy_run_code,
            "system_command": self.tool_policy_system_command,
            "browser_action": self.tool_policy_browser_action,
        }

    def get_backup_dir(self) -> Path:
        p = Path(self.backup_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_log_dir(self) -> Path:
        p = Path(self.log_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_memory_dir(self) -> Path:
        p = Path(self.memory_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_skills_dir(self) -> Path:
        p = Path(self.skills_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def model_for_mode(self) -> str:
        """Return the primary model name based on agent mode."""
        mapping = {
            "basic": "claude-3-haiku-20240307",
            "thinking": "claude-3-5-sonnet-20241022",
            "collaborative": "claude-3-5-sonnet-20241022",
        }
        return mapping.get(self.agent_mode, "claude-3-haiku-20240307")


# Singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()
    return _settings
