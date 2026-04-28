from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImageType(str, Enum):
    product = "product"
    category = "category"
    banner = "banner"
    portfolio_interior = "portfolio_interior"
    furniture_portfolio = "furniture_portfolio"


class FurnitureScene(str, Enum):
    """§3 FURNITURE_PORTFOLIO_API — подтип помещения (валидация формы — шаг A3)."""

    executive_office = "executive_office"
    meeting_room = "meeting_room"
    reception_waiting = "reception_waiting"
    open_workspace = "open_workspace"
    retail_counters = "retail_counters"
    archive_library = "archive_library"
    lounge = "lounge"


class FurniturePortfolioOutputTarget(str, Enum):
    """§4 FURNITURE_PORTFOLIO_API — цель вывода (не путать с ImageType.banner)."""

    site = "site"
    banner = "banner"  # баннер на сайте по §4, не пресет product/category/banner
    social_vk = "social_vk"
    social_telegram = "social_telegram"
    social_max = "social_max"


# §9 FURNITURE_PORTFOLIO_API — минимальная длинная сторона входа (px) после EXIF; шаг A4.
FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX = 1200


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
        max_kb=200,
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

_FP_DEFAULT_BG = BackgroundMode.keep
_FP_DEFAULT_FMT = OutputFormat.webp
_FP_DEFAULT_CROP = CropMode.smart
_FP_DEFAULT_QUALITY = QualityLevel.high

_FURNITURE_PORTFOLIO_PRESETS: dict[FurniturePortfolioOutputTarget, PresetConfig] = {
    FurniturePortfolioOutputTarget.site: PresetConfig(
        width=1600,
        height=900,
        max_kb=400,
        default_background=_FP_DEFAULT_BG,
        default_format=_FP_DEFAULT_FMT,
        default_crop=_FP_DEFAULT_CROP,
        default_quality=_FP_DEFAULT_QUALITY,
    ),
    FurniturePortfolioOutputTarget.banner: PresetConfig(
        width=1920,
        height=900,
        max_kb=450,
        default_background=_FP_DEFAULT_BG,
        default_format=_FP_DEFAULT_FMT,
        default_crop=_FP_DEFAULT_CROP,
        default_quality=_FP_DEFAULT_QUALITY,
    ),
    FurniturePortfolioOutputTarget.social_vk: PresetConfig(
        width=1080,
        height=1080,
        max_kb=350,
        default_background=_FP_DEFAULT_BG,
        default_format=_FP_DEFAULT_FMT,
        default_crop=_FP_DEFAULT_CROP,
        default_quality=_FP_DEFAULT_QUALITY,
    ),
    FurniturePortfolioOutputTarget.social_telegram: PresetConfig(
        width=1280,
        height=720,
        max_kb=300,
        default_background=_FP_DEFAULT_BG,
        default_format=_FP_DEFAULT_FMT,
        default_crop=_FP_DEFAULT_CROP,
        default_quality=_FP_DEFAULT_QUALITY,
    ),
    FurniturePortfolioOutputTarget.social_max: PresetConfig(
        width=1080,
        height=1350,
        max_kb=350,
        default_background=_FP_DEFAULT_BG,
        default_format=_FP_DEFAULT_FMT,
        default_crop=_FP_DEFAULT_CROP,
        default_quality=_FP_DEFAULT_QUALITY,
    ),
}


def get_preset(
    image_type: ImageType,
    *,
    furniture_output_target: FurniturePortfolioOutputTarget | None = None,
) -> PresetConfig:
    if image_type == ImageType.furniture_portfolio:
        if furniture_output_target is None:
            raise ValueError("furniture_output_target is required for image_type=furniture_portfolio")
        return _FURNITURE_PORTFOLIO_PRESETS[furniture_output_target]
    if furniture_output_target is not None:
        raise ValueError("furniture_output_target is only valid for image_type=furniture_portfolio")
    return _PRESETS[image_type]
