"""
TFNK™ Text Fixer
Cantonese STT error correction, OCR artifact cleanup,
Traditional Chinese normalization via OpenCC.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("tfnk.text_fix")


# ── Cantonese STT confusion pairs ────────────────────────────────────────────
# Maps (wrong, correct) pairs for common Cantonese ASR errors.
# These are real Cantonese acoustic confusions, NOT Mandarin→Cantonese transforms.

STT_CORRECTIONS: Dict[str, str] = {
    # 係/是 — keep Cantonese 係 for copula
    # 既/嘅 — 嘅 is Cantonese possessive/aspect; 既 is literary
    "既然係": "既然係",          # context: keep correct
    "我既": "我嘅",
    "你既": "你嘅",
    "佢既": "佢嘅",
    "我地既": "我哋嘅",
    "你地既": "你哋嘅",
    "佢地既": "佢哋嘅",
    "係既": "係嘅",
    "係咁": "係咁",             # keep
    "而家既": "而家嘅",
    "今日既": "今日嘅",
    "個既": "個嘅",
    "件既": "件嘅",
    "樣既": "樣嘅",
    # 唔/不 — keep Cantonese 唔
    "不係": "唔係",
    "不知": "唔知",
    "不要": "唔要",
    "不好": "唔好",
    "不得": "唔得",
    "不使": "唔使",
    # 點/怎 — keep Cantonese 點
    "怎樣": "點樣",
    "怎麼": "點解",
    # 咁/這樣 — 咁 is the correct Cantonese form
    "這樣": "咁樣",
    "這麼": "咁",
    # Common STT confusion: similar sounding characters
    "一齊": "一齊",             # correct
    "一起": "一齊",             # Mandarin form -> Cantonese
    "喺度": "喺度",             # correct
    "在這裡": "喺度",
    "在那裡": "喺嗰度",
    "嗰度": "嗰度",             # correct
    "那邊": "嗰邊",
    "這邊": "呢邊",
    "什麼": "咩",
    "為甚麼": "點解",
    "為什麼": "點解",
    # Particle confusion (STT often picks wrong final particle)
    "喇 嘛": "喇",
    "囉 嘛": "囉",
    "咋 嘛": "咋",
    # Number STT errors
    "一零": "十",
    "二零": "二十",
    # Common phonetic confusions in HK Cantonese STT
    "傾": "傾",                 # correct (tilt / chat)
    "請": "請",                 # correct
    "清": "清",                 # correct
    # 哋/們 — keep Cantonese 哋
    "我們": "我哋",
    "你們": "你哋",
    "他們": "佢哋",
    "她們": "佢哋",
    # OCR artifacts from image translation
    "l ": "l",                  # trailing space in OCR
    "Il": "ll",
    # Common voice command misrecognitions
    "停止": "停止",
    "開始": "開始",
    "幫我": "幫我",
    "可以": "可以",
}

# Context-window rules: (left_context_pattern, match, right_context_pattern, replacement)
CONTEXT_RULES: List[Tuple[Optional[str], str, Optional[str], str]] = [
    # 嘅 vs 既: after pronoun/noun + possessive context -> 嘅
    (r"[我你佢]", "既", None, "嘅"),
    (r"[點噉咁]", "既", None, "嘅"),
    # 係 as copula (correct), 是 -> 係 in Cantonese
    (None, "是", r"[咪唔]", "係"),
    # 咁 in measure/comparison context
    (r"[唔好唔係]", "那樣", None, "咁"),
]

# OpenCC converter config
OPENCC_CONFIG = "t2hk"   # Traditional -> Hong Kong traditional


@dataclass
class FixResult:
    original: str
    corrected: str
    changes: List[Dict[str, str]] = field(default_factory=list)

    @property
    def diff_summary(self) -> str:
        if not self.changes:
            return "無修正"
        lines = [f"- {c['from']} -> {c['to']}" for c in self.changes]
        return "\n".join(lines)


class TextFixer:
    """
    Applies Cantonese STT corrections, OCR cleanup, and Traditional Chinese
    normalization to input text.  Returns (corrected_text, list_of_changes).
    """

    def __init__(self) -> None:
        self._opencc = self._load_opencc()

    @staticmethod
    def _load_opencc() -> Optional[Any]:
        try:
            import opencc  # type: ignore
            return opencc.OpenCC(OPENCC_CONFIG)
        except Exception as exc:
            logger.warning("OpenCC 載入失敗（跳過正規化）: %s", exc)
            return None

    def fix(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Main entry point.
        Returns (corrected_text, changes) where changes is a list of dicts
        with keys 'from', 'to', 'position'.
        """
        if not text or not text.strip():
            return text, []

        changes: List[Dict[str, str]] = []
        current = text

        # Step 1: Direct replacement corrections
        current, c1 = self._apply_direct_corrections(current)
        changes.extend(c1)

        # Step 2: Context-aware corrections using sliding window
        current, c2 = self._apply_context_rules(current)
        changes.extend(c2)

        # Step 3: Cleanup whitespace artifacts
        current = self._cleanup_whitespace(current)

        # Step 4: OpenCC normalization (Simplified -> Traditional HK)
        if self._opencc:
            normalized = self._opencc.convert(current)
            if normalized != current:
                changes.append({"from": "(簡體正規化)", "to": "(繁體香港)", "position": -1})
                current = normalized

        # Step 5: Final punctuation cleanup
        current = self._fix_punctuation(current)

        return current, changes

    def _apply_direct_corrections(
        self, text: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        changes: List[Dict[str, str]] = []
        for wrong, correct in STT_CORRECTIONS.items():
            if wrong == correct:
                continue
            if wrong in text:
                before = text
                text = text.replace(wrong, correct)
                if text != before:
                    changes.append({"from": wrong, "to": correct, "position": before.find(wrong)})
        return text, changes

    def _apply_context_rules(
        self, text: str
    ) -> Tuple[str, List[Dict[str, str]]]:
        changes: List[Dict[str, str]] = []
        for left_pat, match, right_pat, replacement in CONTEXT_RULES:
            if match not in text:
                continue
            for m in re.finditer(re.escape(match), text):
                pos = m.start()
                left_ctx = text[max(0, pos - 5): pos]
                right_ctx = text[pos + len(match): pos + len(match) + 5]

                left_ok = (left_pat is None) or bool(re.search(left_pat, left_ctx))
                right_ok = (right_pat is None) or bool(re.search(right_pat, right_ctx))

                if left_ok and right_ok:
                    if replacement != match:
                        text = text[:pos] + replacement + text[pos + len(match):]
                        changes.append({"from": match, "to": replacement, "position": pos})
                        break  # restart after modification to avoid position drift
        return text, changes

    @staticmethod
    def _cleanup_whitespace(text: str) -> str:
        # Collapse multiple spaces/newlines
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove space before Chinese punctuation
        text = re.sub(r" ([，。！？；：、…])", r"\1", text)
        return text.strip()

    @staticmethod
    def _fix_punctuation(text: str) -> str:
        # Normalize Western punctuation to Chinese equivalents in Chinese context
        # Only if surrounded by Chinese characters
        cjk = r"[一-鿿㐀-䶿]"
        text = re.sub(rf"({cjk}),({cjk})", r"\1，\2", text)
        text = re.sub(rf"({cjk})\.({cjk})", r"\1。\2", text)
        text = re.sub(rf"({cjk})!({cjk})", r"\1！\2", text)
        text = re.sub(rf"({cjk})\?({cjk})", r"\1？\2", text)
        return text

    def fix_ocr(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Additional corrections specifically for OCR output
        (handles character segmentation artifacts).
        """
        changes: List[Dict[str, str]] = []
        # Remove spurious single characters that are common OCR artifacts
        # between Chinese text spans
        cleaned = re.sub(r"(?<=[一-鿿])\s([a-zA-Z])\s(?=[一-鿿])", " ", text)
        if cleaned != text:
            changes.append({"from": "(OCR空格)", "to": "(清理)", "position": -1})
            text = cleaned

        # Fix common OCR character confusions
        ocr_map = {
            "0": "O",   # only in pure Chinese context -> skip (ambiguous)
            "l": "l",   # keep
            "ﬁ": "fi",
            "ﬂ": "fl",
            " ": " ",  # non-breaking space -> regular space
        }
        for wrong, correct in ocr_map.items():
            if wrong in text and wrong != correct:
                text = text.replace(wrong, correct)
                changes.append({"from": wrong, "to": correct, "position": -1})

        corrected, more = self.fix(text)
        changes.extend(more)
        return corrected, changes

    def detect_language(self, text: str) -> str:
        """Detect the primary language of the text."""
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            cjk_count = sum(1 for c in text if "一" <= c <= "鿿")
            return "zh-tw" if cjk_count > len(text) * 0.3 else "en"


# Global singleton
_text_fixer: Optional[TextFixer] = None


def get_text_fixer() -> TextFixer:
    global _text_fixer
    if _text_fixer is None:
        _text_fixer = TextFixer()
    return _text_fixer


# Type alias for Optional[Any]
Any = type(None).__class__
