from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from presets.definitions import OutputFormat, PresetConfig


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _laplacian_variance(path: Path) -> float | None:
    try:
        with Image.open(path) as im:
            gray = np.array(im.convert("L"))
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except Exception:
        return None


def _highlight_clip_fraction(path: Path) -> float | None:
    try:
        with Image.open(path) as im:
            rgb = np.array(im.convert("RGB"))
        near_white = (rgb[:, :, 0] > 248) & (rgb[:, :, 1] > 248) & (rgb[:, :, 2] > 248)
        return float(near_white.mean())
    except Exception:
        return None


def _sharpness_warn_threshold(width: int, height: int) -> float:
    # Wider outputs (banner/interior) often have smoother gradients; use a softer threshold.
    return 18.0 if width >= 1600 or height >= 900 else 25.0


def _highlight_warn_threshold(width: int, height: int) -> float:
    # Product/category shots usually contain more bright background; tolerate slightly more clipping.
    return 0.20 if width <= 1200 else 0.14


def validate_output(
    file_path: Path,
    preset: PresetConfig,
    fmt: OutputFormat,
    max_kb: int,
) -> ValidationResult:
    r = ValidationResult(ok=True)
    if not file_path.is_file():
        r.add("output file missing")
        return r
    size_kb = file_path.stat().st_size / 1024.0
    if size_kb > max_kb + 0.5:
        r.add(f"file size {size_kb:.1f} KB exceeds max {max_kb} KB")
    elif size_kb >= max_kb * 0.92:
        r.warn(f"file size {size_kb:.1f} KB is near limit {max_kb} KB (quality headroom low)")

    try:
        with Image.open(file_path) as im:
            w, h = im.size
            if w != preset.width or h != preset.height:
                r.add(f"dimensions {w}x{h} expected {preset.width}x{preset.height}")
            detected = im.format
            if fmt == OutputFormat.webp and detected != "WEBP":
                r.add(f"format expected WEBP got {detected}")
            elif fmt == OutputFormat.jpeg and detected not in ("JPEG", "JPG"):
                r.add(f"format expected JPEG got {detected}")
            elif fmt == OutputFormat.png and detected != "PNG":
                r.add(f"format expected PNG got {detected}")
    except Exception as e:
        r.add(f"cannot read output image: {e}")
        return r

    if not r.errors:
        lv = _laplacian_variance(file_path)
        sharpness_threshold = _sharpness_warn_threshold(preset.width, preset.height)
        if lv is not None and lv < sharpness_threshold:
            r.warn(f"low_sharpness_heuristic (laplacian_var={lv:.1f})")
        hf = _highlight_clip_fraction(file_path)
        highlight_threshold = _highlight_warn_threshold(preset.width, preset.height)
        if hf is not None and hf > highlight_threshold:
            r.warn(f"possible_highlight_clipping (near_white_fraction={hf:.2f})")

    strict = os.environ.get("VALIDATION_WARNINGS_AS_ERRORS", "").lower() in ("1", "true", "yes")
    if strict and r.warnings:
        for w in r.warnings:
            r.add(w)
        r.warnings.clear()

    return r
