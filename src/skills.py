"""
TFNK™ Skills Manager
Hermes-style skills: auto-generate SKILL.md after multi-step tasks,
FTS search with Whoosh, find/save/list skills.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_settings

logger = logging.getLogger("tfnk.skills")


@dataclass
class Skill:
    name: str
    description: str
    steps: List[str]
    result_summary: str
    tags: List[str] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    last_used: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            f"# 技能: {self.name}",
            f"",
            f"**技能ID**: {self.skill_id}",
            f"**描述**: {self.description}",
            f"**標籤**: {', '.join(self.tags)}",
            f"**成功次數**: {self.success_count}",
            f"**失敗次數**: {self.fail_count}",
            f"**最後使用**: {self.last_used or '從未'}",
            f"**創建時間**: {self.created_at}",
            f"",
            f"## 執行步驟",
            f"",
        ]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")
        lines += [
            f"",
            f"## 結果摘要",
            f"",
            self.result_summary,
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, content: str, file_path: Optional[str] = None) -> "Skill":
        """Parse a SKILL.md file back into a Skill object."""
        name = ""
        description = ""
        tags: List[str] = []
        steps: List[str] = []
        result_summary = ""
        success_count = 0
        fail_count = 0
        last_used = None
        created_at = datetime.utcnow().isoformat()
        skill_id = str(uuid.uuid4())

        lines = content.splitlines()
        section = None

        for line in lines:
            if line.startswith("# 技能:"):
                name = line.replace("# 技能:", "").strip()
            elif line.startswith("**技能ID**:"):
                skill_id = line.split(":", 1)[1].strip()
            elif line.startswith("**描述**:"):
                description = line.split(":", 1)[1].strip()
            elif line.startswith("**標籤**:"):
                tag_str = line.split(":", 1)[1].strip()
                tags = [t.strip() for t in tag_str.split(",") if t.strip()]
            elif line.startswith("**成功次數**:"):
                try:
                    success_count = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**失敗次數**:"):
                try:
                    fail_count = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("**最後使用**:"):
                val = line.split(":", 1)[1].strip()
                last_used = None if val == "從未" else val
            elif line.startswith("**創建時間**:"):
                created_at = line.split(":", 1)[1].strip()
            elif line.strip() == "## 執行步驟":
                section = "steps"
            elif line.strip() == "## 結果摘要":
                section = "result"
            elif section == "steps" and re.match(r"^\d+\.", line.strip()):
                step = re.sub(r"^\d+\.\s*", "", line.strip())
                if step:
                    steps.append(step)
            elif section == "result" and line.strip():
                result_summary += line + "\n"

        return cls(
            name=name or "未命名技能",
            description=description,
            tags=tags,
            steps=steps,
            result_summary=result_summary.strip(),
            success_count=success_count,
            fail_count=fail_count,
            last_used=last_used,
            created_at=created_at,
            skill_id=skill_id,
            file_path=file_path,
        )


class SkillsManager:
    """
    Hermes-style skills system.
    Auto-generates SKILL.md files, searches with Whoosh FTS,
    tracks usage statistics, and provides semantic skill matching.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._skills_dir = self._settings.get_skills_dir()
        self._index_dir = self._skills_dir / ".whoosh_index"
        self._ix: Any = None
        self._skills_cache: Dict[str, Skill] = {}
        self._ensure_index()

    # ── Index management ──────────────────────────────────────────────────────

    def _ensure_index(self) -> None:
        """Create or open the Whoosh FTS index."""
        try:
            from whoosh import index as whoosh_index
            from whoosh.fields import Schema, TEXT, ID, NUMERIC, STORED

            self._schema = Schema(
                skill_id=ID(stored=True, unique=True),
                name=TEXT(stored=True),
                description=TEXT(stored=True),
                steps=TEXT(stored=True),
                result_summary=TEXT(stored=True),
                tags=TEXT(stored=True),
                success_count=NUMERIC(stored=True),
                file_path=STORED,
            )

            self._index_dir.mkdir(parents=True, exist_ok=True)

            if whoosh_index.exists_in(str(self._index_dir)):
                self._ix = whoosh_index.open_dir(str(self._index_dir))
            else:
                self._ix = whoosh_index.create_in(str(self._index_dir), self._schema)
                self._reindex_all()

        except Exception as exc:
            logger.warning("Whoosh 索引初始化失敗（將使用純文本搜索）: %s", exc)
            self._ix = None

    def _reindex_all(self) -> None:
        """Re-scan skills/ directory and rebuild the index."""
        if self._ix is None:
            return
        try:
            writer = self._ix.writer()
            for md_file in self._skills_dir.glob("*.md"):
                skill = self._load_skill_file(md_file)
                if skill:
                    self._index_skill(writer, skill)
            writer.commit()
        except Exception as exc:
            logger.error("技能重新索引失敗: %s", exc)

    def _index_skill(self, writer: Any, skill: Skill) -> None:
        writer.update_document(
            skill_id=skill.skill_id,
            name=skill.name,
            description=skill.description,
            steps=" ".join(skill.steps),
            result_summary=skill.result_summary,
            tags=" ".join(skill.tags),
            success_count=skill.success_count,
            file_path=skill.file_path or "",
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def save_skill(
        self,
        name: str,
        steps: List[str],
        result: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Skill:
        """
        Create and persist a new skill.
        Called automatically after completing a multi-step task.
        """
        if not tags:
            tags = self._auto_tags(name, description, steps)

        skill = Skill(
            name=name,
            description=description or name,
            steps=steps,
            result_summary=result,
            tags=tags,
            success_count=1,
            last_used=datetime.utcnow().isoformat(),
        )

        safe_name = re.sub(r"[^\w\-]", "_", name)[:60]
        file_path = self._skills_dir / f"{safe_name}.md"
        skill.file_path = str(file_path)

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(skill.to_markdown(), encoding="utf-8")

        self._skills_cache[skill.skill_id] = skill
        self._update_index(skill)

        logger.info("技能已保存: %s -> %s", name, file_path)
        return skill

    def update_skill_stats(self, skill_id: str, success: bool) -> None:
        """Increment success/fail count for a skill."""
        skill = self._skills_cache.get(skill_id)
        if not skill and skill_id in [s.skill_id for s in self._load_all()]:
            skill = next((s for s in self._load_all() if s.skill_id == skill_id), None)
        if not skill:
            return
        if success:
            skill.success_count += 1
        else:
            skill.fail_count += 1
        skill.last_used = datetime.utcnow().isoformat()
        if skill.file_path:
            Path(skill.file_path).write_text(skill.to_markdown(), encoding="utf-8")
        self._update_index(skill)

    def _update_index(self, skill: Skill) -> None:
        if self._ix is None:
            return
        try:
            writer = self._ix.writer()
            self._index_skill(writer, skill)
            writer.commit()
        except Exception as exc:
            logger.warning("技能索引更新失敗: %s", exc)

    # ── Search ────────────────────────────────────────────────────────────────

    def find_relevant_skill(self, task_description: str) -> Optional[Skill]:
        """
        Find the best matching skill for a task description.
        Uses Whoosh FTS if available, falls back to keyword matching.
        """
        results = self.search_skills(task_description, limit=1)
        if results:
            return results[0]
        return None

    def search_skills(self, query: str, limit: int = 10) -> List[Skill]:
        """Full-text search across all skill files."""
        if self._ix is not None:
            return self._whoosh_search(query, limit)
        return self._keyword_search(query, limit)

    def _whoosh_search(self, query_str: str, limit: int) -> List[Skill]:
        try:
            from whoosh.qparser import MultifieldParser, OrGroup
            from whoosh import scoring

            with self._ix.searcher(weighting=scoring.BM25F()) as searcher:
                parser = MultifieldParser(
                    ["name", "description", "steps", "result_summary", "tags"],
                    schema=self._schema,
                    group=OrGroup,
                )
                query = parser.parse(query_str)
                results = searcher.search(query, limit=limit)
                skills: List[Skill] = []
                for hit in results:
                    fp = hit.get("file_path")
                    if fp and Path(fp).exists():
                        skill = self._load_skill_file(Path(fp))
                        if skill:
                            skills.append(skill)
                return skills
        except Exception as exc:
            logger.warning("Whoosh 搜索失敗，退回關鍵詞搜索: %s", exc)
            return self._keyword_search(query_str, limit)

    def _keyword_search(self, query: str, limit: int) -> List[Skill]:
        keywords = set(query.lower().split())
        scored: List[tuple[int, Skill]] = []
        for skill in self._load_all():
            content = f"{skill.name} {skill.description} {' '.join(skill.steps)} {' '.join(skill.tags)}".lower()
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda x: (-x[0], -x[1].success_count))
        return [s for _, s in scored[:limit]]

    def list_skills(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._load_all()]

    # ── File loading ──────────────────────────────────────────────────────────

    def _load_all(self) -> List[Skill]:
        skills: List[Skill] = []
        for md_file in self._skills_dir.glob("*.md"):
            skill = self._load_skill_file(md_file)
            if skill:
                skills.append(skill)
        return skills

    def _load_skill_file(self, path: Path) -> Optional[Skill]:
        try:
            content = path.read_text(encoding="utf-8")
            skill = Skill.from_markdown(content, file_path=str(path))
            self._skills_cache[skill.skill_id] = skill
            return skill
        except Exception as exc:
            logger.warning("技能文件解析失敗 %s: %s", path, exc)
            return None

    # ── Tag extraction ────────────────────────────────────────────────────────

    @staticmethod
    def _auto_tags(name: str, description: str, steps: List[str]) -> List[str]:
        """Auto-extract tags from task content."""
        combined = f"{name} {description} {' '.join(steps)}".lower()
        keywords = {
            "搜索": "搜索", "文件": "文件", "代碼": "程式", "系統": "系統",
            "分析": "分析", "下載": "下載", "翻譯": "翻譯", "圖像": "圖像",
            "網絡": "網絡", "數據": "數據", "金融": "金融", "股票": "金融",
            "video": "影片", "youtube": "影片", "search": "搜索",
            "file": "文件", "code": "程式", "system": "系統",
        }
        tags = set()
        for kw, tag in keywords.items():
            if kw in combined:
                tags.add(tag)
        return list(tags)[:8]


# Global singleton
_skills_manager: Optional[SkillsManager] = None


def get_skills_manager() -> SkillsManager:
    global _skills_manager
    if _skills_manager is None:
        _skills_manager = SkillsManager()
    return _skills_manager
