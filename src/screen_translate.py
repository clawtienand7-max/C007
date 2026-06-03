"""
TFNK™ Screen Translator
In-place image translation: OCR -> detect language -> translate to Traditional Chinese
-> redraw text on original image preserving font size, color, and position.
"""
from __future__ import annotations

import io
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont  # type: ignore
import pytesseract  # type: ignore

from src.config import get_settings

logger = logging.getLogger("tfnk.screen_translate")

# Tesseract language codes for OCR
TESSERACT_LANGS = "chi_tra+chi_sim+eng+jpn+kor"
# Output font to use for translated Chinese text
DEFAULT_FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
FALLBACK_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@dataclass
class TextRegion:
    text: str
    x: int
    y: int
    w: int
    h: int
    confidence: float
    font_size: int
    bg_color: Tuple[int, int, int]
    text_color: Tuple[int, int, int]
    translated: str = ""


class ScreenTranslator:
    """
    Translates all text in an image in-place.
    Detects source language, translates to Traditional Chinese (繁體中文),
    and redraws text at the same position with matching visual style.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._font_cache: Dict[int, Any] = {}
        self._translator: Any = None

    def _get_translator(self) -> Any:
        if self._translator is None:
            try:
                from googletrans import Translator  # type: ignore
                self._translator = Translator()
            except Exception as exc:
                logger.error("翻譯器初始化失敗: %s", exc)
                raise
        return self._translator

    def _get_font(self, size: int) -> Any:
        if size in self._font_cache:
            return self._font_cache[size]
        for font_path in [DEFAULT_FONT_PATH, FALLBACK_FONT_PATH]:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, size)
                    self._font_cache[size] = font
                    return font
                except Exception:
                    pass
        # Last resort: default PIL font
        font = ImageFont.load_default()
        self._font_cache[size] = font
        return font

    # ── Main API ──────────────────────────────────────────────────────────────

    def translate_image(
        self,
        image_path: str,
        target_lang: str = "zh-TW",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Translate all text in the image in-place.
        Returns the output file path.
        """
        input_path = Path(image_path)
        if not input_path.exists():
            raise FileNotFoundError(f"圖像文件不存在: {image_path}")

        image = Image.open(str(input_path)).convert("RGBA")

        # Step 1: OCR to get text regions
        regions = self._extract_text_regions(image)
        if not regions:
            logger.info("圖像中未找到文字")
            if output_path:
                image.save(output_path)
                return output_path
            return image_path

        # Step 2: Detect source language from all text combined
        all_text = " ".join(r.text for r in regions if r.text.strip())
        source_lang = self._detect_language(all_text)
        logger.info("偵測到語言: %s, 共 %d 個文字區域", source_lang, len(regions))

        # If already Traditional Chinese, return as-is
        if source_lang in ("zh-tw", "zh-TW") and target_lang in ("zh-TW", "zh-tw"):
            if output_path:
                image.save(output_path)
                return output_path
            return image_path

        # Step 3: Translate all regions
        regions = self._translate_regions(regions, source_lang, target_lang)

        # Step 4: Redraw translated text on image
        result_image = self._redraw_text(image, regions)

        # Step 5: Save output
        if output_path is None:
            stem = input_path.stem
            output_path = str(input_path.parent / f"{stem}_translated{input_path.suffix}")

        if output_path.lower().endswith(".png") or output_path.lower().endswith(".webp"):
            result_image.save(output_path)
        else:
            # Convert RGBA to RGB for JPEG
            rgb = result_image.convert("RGB")
            rgb.save(output_path, quality=95)

        logger.info("翻譯圖像已保存: %s", output_path)
        return output_path

    # ── OCR ───────────────────────────────────────────────────────────────────

    def _extract_text_regions(self, image: Image.Image) -> List[TextRegion]:
        """Use pytesseract to extract text regions with bounding boxes."""
        regions: List[TextRegion] = []
        try:
            # Get detailed OCR data
            data = pytesseract.image_to_data(
                image,
                lang=TESSERACT_LANGS,
                output_type=pytesseract.Output.DICT,
                config="--oem 3 --psm 11",
            )

            n = len(data["text"])
            for i in range(n):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])
                if not text or conf < 40:
                    continue

                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])

                if w < 5 or h < 5:
                    continue

                # Estimate font size from bounding box height
                font_size = max(8, int(h * 0.75))

                # Sample background and text colors
                bg_color = self._sample_background_color(image, x, y, w, h)
                text_color = self._sample_text_color(image, x, y, w, h, bg_color)

                regions.append(TextRegion(
                    text=text,
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    confidence=conf,
                    font_size=font_size,
                    bg_color=bg_color,
                    text_color=text_color,
                ))

        except Exception as exc:
            logger.error("OCR 提取失敗: %s", exc)

        return regions

    @staticmethod
    def _sample_background_color(
        image: Image.Image, x: int, y: int, w: int, h: int
    ) -> Tuple[int, int, int]:
        """Sample the most common color in the border of a bounding box."""
        try:
            # Sample corners
            pixels = []
            for dx, dy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
                px = min(x + dx, image.width - 1)
                py = min(y + dy, image.height - 1)
                color = image.getpixel((px, py))
                pixels.append(color[:3] if len(color) > 3 else color)

            # Average
            r = sum(p[0] for p in pixels) // len(pixels)
            g = sum(p[1] for p in pixels) // len(pixels)
            b = sum(p[2] for p in pixels) // len(pixels)
            return (r, g, b)
        except Exception:
            return (255, 255, 255)

    @staticmethod
    def _sample_text_color(
        image: Image.Image,
        x: int,
        y: int,
        w: int,
        h: int,
        bg: Tuple[int, int, int],
    ) -> Tuple[int, int, int]:
        """Estimate text color as the complement of background color."""
        # Sample center pixels
        try:
            cx = min(x + w // 2, image.width - 1)
            cy = min(y + h // 2, image.height - 1)
            center = image.getpixel((cx, cy))
            r, g, b = center[:3]
            # If center is similar to bg, invert
            diff = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            if diff < 60:
                # Use contrasting dark/light
                brightness = (bg[0] * 299 + bg[1] * 587 + bg[2] * 114) // 1000
                return (0, 0, 0) if brightness > 128 else (255, 255, 255)
            return (r, g, b)
        except Exception:
            return (0, 0, 0)

    # ── Translation ───────────────────────────────────────────────────────────

    def _detect_language(self, text: str) -> str:
        if not text.strip():
            return "en"
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            # Heuristic: count CJK chars
            cjk = sum(1 for c in text if "一" <= c <= "鿿")
            return "zh" if cjk > len(text) * 0.3 else "en"

    def _translate_regions(
        self,
        regions: List[TextRegion],
        source_lang: str,
        target_lang: str,
    ) -> List[TextRegion]:
        """Translate all region texts in batches."""
        translator = self._get_translator()
        texts = [r.text for r in regions]

        # Batch translate (googletrans supports list input)
        try:
            # Translate in chunks of 50 to avoid API limits
            chunk_size = 50
            translated: List[str] = []
            for i in range(0, len(texts), chunk_size):
                chunk = texts[i: i + chunk_size]
                results = translator.translate(chunk, src=source_lang, dest="zh-tw")
                if isinstance(results, list):
                    translated.extend(r.text for r in results)
                else:
                    translated.append(results.text)
                time.sleep(0.1)  # Rate limiting

            for region, tr_text in zip(regions, translated):
                region.translated = tr_text

        except Exception as exc:
            logger.error("批量翻譯失敗: %s，嘗試逐個翻譯", exc)
            for region in regions:
                try:
                    result = translator.translate(region.text, dest="zh-tw")
                    region.translated = result.text
                    time.sleep(0.05)
                except Exception as e2:
                    logger.warning("翻譯失敗 '%s': %s", region.text[:20], e2)
                    region.translated = region.text

        return regions

    # ── Redraw ────────────────────────────────────────────────────────────────

    def _redraw_text(
        self, image: Image.Image, regions: List[TextRegion]
    ) -> Image.Image:
        """
        Cover original text with background color rectangle,
        then draw translated text in the same position.
        """
        draw = ImageDraw.Draw(image)

        for region in regions:
            if not region.translated or not region.translated.strip():
                continue

            # 1. Fill over original text with background color
            draw.rectangle(
                [region.x, region.y, region.x + region.w, region.y + region.h],
                fill=region.bg_color + (255,),  # RGBA
            )

            # 2. Fit translated text into the bounding box
            font_size = region.font_size
            font = self._get_font(font_size)

            # Auto-shrink font to fit width
            translated = region.translated
            for attempt in range(10):
                bbox = draw.textbbox((0, 0), translated, font=font)
                text_w = bbox[2] - bbox[0]
                if text_w <= region.w or font_size <= 6:
                    break
                font_size = max(6, font_size - 2)
                font = self._get_font(font_size)

            # 3. Draw text
            draw.text(
                (region.x + 1, region.y + 1),
                translated,
                fill=region.text_color + (255,),
                font=font,
            )

        return image

    # ── Convenience ───────────────────────────────────────────────────────────

    def translate_image_bytes(
        self, image_bytes: bytes, filename: str = "input.png"
    ) -> bytes:
        """Translate image from bytes and return bytes."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp_in:
            tmp_in.write(image_bytes)
            tmp_in_path = tmp_in.name

        try:
            output_path = tmp_in_path + "_out" + Path(filename).suffix
            self.translate_image(tmp_in_path, output_path=output_path)
            result = Path(output_path).read_bytes()
            Path(output_path).unlink(missing_ok=True)
            return result
        finally:
            Path(tmp_in_path).unlink(missing_ok=True)


# Global singleton
_translator: Optional[ScreenTranslator] = None


def get_screen_translator() -> ScreenTranslator:
    global _translator
    if _translator is None:
        _translator = ScreenTranslator()
    return _translator
