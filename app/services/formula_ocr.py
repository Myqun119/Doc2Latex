from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image


@dataclass
class OCRResult:
    latex: str
    confidence: float
    engine: str


class FormulaOCR:
    def __init__(self) -> None:
        self._pix2tex_model = None
        self._pix2tex_available = False
        try:
            from pix2tex.cli import LatexOCR  # type: ignore

            self._pix2tex_model = LatexOCR()
            self._pix2tex_available = True
        except Exception:
            self._pix2tex_available = False

    def is_formula_like_image(self, image_path: Path) -> bool:
        try:
            img = Image.open(image_path)
            width, height = img.size
            if width < 24 or height < 12:
                return False
            ratio = width / max(height, 1)
            return 1.2 <= ratio <= 18
        except Exception:
            return False

    def extract_latex(self, image_path: Path) -> Optional[OCRResult]:
        if self._pix2tex_available and self._pix2tex_model is not None:
            try:
                pred = self._pix2tex_model(str(image_path))
                latex = self._cleanup_latex(pred)
                if latex:
                    return OCRResult(latex=latex, confidence=0.9, engine="pix2tex")
            except Exception:
                pass

        latex = self._tesseract_fallback(image_path)
        if latex:
            return OCRResult(latex=latex, confidence=0.45, engine="tesseract")
        return None

    def _tesseract_fallback(self, image_path: Path) -> str:
        try:
            img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if img is None:
                return ""
            blur = cv2.GaussianBlur(img, (3, 3), 0)
            thresh = cv2.adaptiveThreshold(
                blur,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                35,
                11,
            )
            text = pytesseract.image_to_string(
                thresh,
                config="--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+-=*/()[]{}^_\\. ",
            )
            return self._cleanup_latex(text)
        except Exception:
            return ""

    def _cleanup_latex(self, text: str) -> str:
        if not text:
            return ""
        normalized = " ".join(text.replace("\n", " ").split()).strip()
        normalized = normalized.strip("$")
        if not normalized:
            return ""
        likely_formula_chars = set("=+-*/^_\\{}[]()")
        char_hits = sum(1 for c in normalized if c in likely_formula_chars)
        if char_hits == 0 and not any(ch.isdigit() for ch in normalized):
            return ""
        return normalized
