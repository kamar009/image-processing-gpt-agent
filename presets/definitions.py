from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ImageType(str, Enum):
    product = "product"
    category = "category"
    banner = "banner"
    portfolio_interior = "portfolio_interior"


class BackgroundMode(str, Enum):
    keep = "keep"
    white = "white"
    transparent = "transparent"
    clean = "clean"


class OutputFormat(str, Enum):
    webp = "webp"
    jpeg = "jpeg"
    png = "png"


class CropMode(str, Enum):
    center = "center"
    smart = "smart"


class QualityLevel(str, Enum):
    standard = "standard"
    high = "high"


class StylePreset(str, Enum):
    neutral = "neutral"
    premium = "premium"
    light = "light"
    creative = "creative"


@dataclass(frozen=True)
class SafeAreaFractions:
    """Normalized margins from each edge (0–1) for banner text safe zone."""

    left: float = 0.08
    top: float = 0.12
    right: float = 0.92
    bottom: float = 0.78


@dataclass(frozen=True)
class PresetConfig:
    width: int
    height: int
    max_kb: int
    default_background: BackgroundMode
    default_format: OutputFormat
    default_crop: CropMode
    default_quality: QualityLevel
    safe_area: SafeAreaFractions | None = None


_PRESETS: dict[ImageType, PresetConfig] = {
    ImageType.product: PresetConfig(
        width=800,
        height=800,
        max_kb=150,
        default_background=BackgroundMode.white,
        default_format=OutputFormat.webp,
        default_crop=CropMode.smart,
        default_quality=QualityLevel.high,
    ),
    ImageType.category: PresetConfig(
        width=1200,
        height=800,
        max_kb=250,
        default_background=BackgroundMode.keep,
        default_format=OutputFormat.webp,
        default_crop=CropMode.smart,
        default_quality=QualityLevel.high,
    ),
    ImageType.banner: PresetConfig(
        width=1920,
        height=900,
        max_kb=400,
        default_background=BackgroundMode.keep,
        default_format=OutputFormat.webp,
        default_crop=CropMode.smart,
        default_quality=QualityLevel.high,
        safe_area=SafeAreaFractions(),
    ),
    ImageType.portfolio_interior: PresetConfig(
        width=1600,
        height=900,
        max_kb=350,
        default_background=BackgroundMode.keep,
        default_format=OutputFormat.webp,
        default_crop=CropMode.smart,
        default_quality=QualityLevel.high,
    ),
}


def get_preset(image_type: ImageType) -> PresetConfig:
    return _PRESETS[image_type]
