from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from gpt_agent.schema import VisionAnalysis
from image_processor import crop_geometry, ops
from presets.definitions import (
    BackgroundMode,
    CropMode,
    ImageType,
    OutputFormat,
    PresetConfig,
    QualityLevel,
    StylePreset,
)


@dataclass
class ProcessResult:
    data: bytes
    operations: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    format: str = ""
    size_kb: float = 0.0
    background: str = ""
    timing_ms: dict[str, float] = field(default_factory=dict)


def _deadline_from_env() -> float | None:
    import os

    try:
        sec = float(os.environ.get("MAX_PROCESS_SECONDS", "10"))
    except ValueError:
        sec = 10.0
    return time.monotonic() + sec


def _quality_range(level: QualityLevel, fmt: OutputFormat) -> tuple[int, int]:
    if fmt == OutputFormat.png:
        return 95, 75
    if level == QualityLevel.high:
        return 92, 55
    return 85, 45


def _fmt_name(fmt: OutputFormat) -> str:
    return fmt.value


def _exposure_strength(base: float, style: StylePreset) -> float:
    if style == StylePreset.light:
        return base * 0.78
    if style == StylePreset.premium:
        return base * 1.1
    return base


def _focal_center(vision: VisionAnalysis) -> tuple[float, float]:
    sc = vision.suggested_crop
    if sc and sc.width > 0 and sc.height > 0:
        cx = sc.x + sc.width / 2
        cy = sc.y + sc.height / 2
        return (max(0, min(1, cx)), max(0, min(1, cy)))
    b = vision.content_tight_box
    if b and b.width > 0 and b.height > 0:
        cx = b.x + b.width / 2
        cy = b.y + b.height / 2
        return (max(0, min(1, cx)), max(0, min(1, cy)))
    return ops.focal_from_vision(vision)


def _pad_rgba_square(rgba: Image.Image, margin: float = 0.08) -> Image.Image:
    rgba = rgba.convert("RGBA")
    a = np.array(rgba.split()[-1])
    ys, xs = np.where(a > 8)
    if len(xs) == 0:
        return rgba
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    bw, bh = x1 - x0, y1 - y0
    side = int(max(bw, bh) * (1 + 2 * margin))
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    half = side // 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(rgba, (half - cx, half - cy))
    return canvas


def run_pipeline(
    image: Image.Image,
    image_type: ImageType,
    background: BackgroundMode,
    output_format: OutputFormat,
    crop_mode: CropMode,
    quality_level: QualityLevel,
    style: StylePreset,
    vision: VisionAnalysis,
    preset: PresetConfig,
    max_output_kb: int | None = None,
    deadline: float | None = None,
) -> ProcessResult:
    if deadline is None:
        deadline = _deadline_from_env()
    t_body_start = time.perf_counter()
    ops_list: list[str] = []
    tw, th = preset.width, preset.height
    ar_w, ar_h = tw, th

    working = image.copy()
    orig_w, orig_h = working.size
    working, vmeta = crop_geometry.pre_constrain_to_vision_region(working, vision, crop_mode)
    if vmeta:
        ops_list.append("vision_region_precrop")

    cx, cy = (0.5, 0.5)
    if crop_mode == CropMode.smart:
        cx, cy = _focal_center(vision)
    if image_type == ImageType.banner:
        cx, cy = ops.banner_focal(vision)
    cx, cy = crop_geometry.remap_normalized_focal(cx, cy, vmeta, orig_w, orig_h)

    def _tag_vision_suggested() -> None:
        if vision.suggested_crop and crop_mode == CropMode.smart:
            ops_list.append("vision_suggested_crop")

    if image_type == ImageType.product:
        ops_list.append("analyze_preset_product")
        _tag_vision_suggested()
        if background == BackgroundMode.keep:
            working = working.convert("RGB")
            ops_list.append("background_keep")
        else:
            working = ops.remove_background_rgba(working)
            ops_list.append("background_removal")
            if background in (BackgroundMode.white, BackgroundMode.clean):
                working = ops.composite_white(working)
                working = working.convert("RGB")
                ops_list.append("background_white")
                working = ops.product_pad_square_content(working)
                ops_list.append("padding_subject")
            elif background == BackgroundMode.transparent:
                working = _pad_rgba_square(working)
                ops_list.append("padding_subject_alpha")
        if working.mode == "RGB":
            working = ops.normalize_exposure_rgb(
                working,
                _exposure_strength(0.28 if style != StylePreset.light else 0.18, style),
            )
            ops_list.append("exposure_normalize")
            working = ops.crop_to_aspect(working, ar_w, ar_h, cx, cy)
            ops_list.append("crop_aspect")
            working = ops.resize_exact(working, tw, th)
            ops_list.append("resize")
            working = ops.unsharp(working, radius=1.0, percent=125, threshold=2)
            ops_list.append("sharpness")
        else:
            working = working.convert("RGBA")
            working = ops.crop_to_aspect(working, ar_w, ar_h, cx, cy)
            ops_list.append("crop_aspect")
            working = ops.resize_exact(working, tw, th)
            ops_list.append("resize")
            r, g, b, a = working.split()
            rgb_only = Image.merge("RGB", (r, g, b))
            rgb_only = ops.normalize_exposure_rgb(rgb_only, _exposure_strength(0.2, style))
            r2, g2, b2 = rgb_only.split()
            working = Image.merge("RGBA", (r2, g2, b2, a))
            ops_list.append("exposure_normalize_rgb")
            rgb_u = Image.merge("RGB", (r2, g2, b2))
            rgb_u = ops.unsharp(rgb_u, radius=1.0, percent=120, threshold=2)
            ru, gu, bu = rgb_u.split()
            working = Image.merge("RGBA", (ru, gu, bu, a))
            ops_list.append("sharpness")

    elif image_type == ImageType.category:
        ops_list.append("analyze_preset_category")
        _tag_vision_suggested()
        working = working.convert("RGB")
        h_cat = 4
        if not ops.now_ok(deadline):
            h_cat = 2
            ops_list.append("deadline_denoise_light")
        working = ops.denoise_color(working, h=h_cat)
        ops_list.append("noise_reduction")
        working = ops.crop_to_aspect(working, ar_w, ar_h, cx, cy)
        ops_list.append("smart_crop" if crop_mode == CropMode.smart else "center_crop")
        working = ops.resize_exact(working, tw, th)
        ops_list.append("resize")
        working = ops.normalize_exposure_rgb(working, _exposure_strength(0.3, style))
        ops_list.append("exposure_normalize")
        working = ops.category_grade(working)
        ops_list.append("color_correction")

    elif image_type == ImageType.banner:
        ops_list.append("analyze_preset_banner")
        _tag_vision_suggested()
        working = working.convert("RGBA")
        iw, ih = working.size
        target_ar = ar_w / ar_h
        need_compose = abs((iw / max(ih, 1)) - target_ar) > 0.12
        if need_compose:
            working = ops.blur_fill_compose(working, tw, th)
            ops_list.append("wide_format_adapt_blur_fill")
        else:
            rgb = working.convert("RGB")
            working = ops.crop_to_aspect(rgb, ar_w, ar_h, cx, cy)
            ops_list.append("crop_aspect")
            working = ops.resize_exact(working, tw, th)
            ops_list.append("resize")
        working = ops.normalize_exposure_rgb(working, _exposure_strength(0.25, style))
        ops_list.append("exposure_normalize")
        working = ops.cinematic_banner(working)
        ops_list.append("cinematic_tone")

    elif image_type == ImageType.portfolio_interior:
        ops_list.append("analyze_preset_portfolio")
        _tag_vision_suggested()
        working = working.convert("RGB")
        if vision.vertical_lines_need_correction:
            working = ops.slight_rotation_fix(working, max_deg=1.1)
            ops_list.append("vertical_alignment_light")
        h_pf = 5 if quality_level == QualityLevel.high else 4
        if not ops.now_ok(deadline):
            h_pf = min(h_pf, 2)
            ops_list.append("deadline_denoise_light")
        working = ops.denoise_color(working, h=h_pf)
        ops_list.append("noise_reduction")
        working = ops.crop_to_aspect(working, ar_w, ar_h, cx, cy)
        ops_list.append("smart_crop" if crop_mode == CropMode.smart else "center_crop")
        working = ops.resize_exact(working, tw, th)
        ops_list.append("resize")
        strength = 0.22 if vision.preserve_realistic_colors else 0.35
        if style == StylePreset.premium and image_type == ImageType.portfolio_interior:
            strength = min(strength * 1.05, 0.32)
        working = ops.normalize_exposure_rgb(working, _exposure_strength(strength, style))
        ops_list.append("exposure_normalize")
        if vision.avoid_heavy_saturation:
            from PIL import ImageEnhance

            working = ImageEnhance.Color(working).enhance(0.98)
            ops_list.append("desaturate_slight")
        working = ops.unsharp(working, radius=0.9, percent=115, threshold=3)
        ops_list.append("sharpness")

    effective_max_kb = max_output_kb if max_output_kb is not None else preset.max_kb
    max_bytes = effective_max_kb * 1024
    qh, ql = _quality_range(quality_level, output_format)
    fmt = _fmt_name(output_format)

    img_out = working
    preserve_alpha = (
        img_out.mode == "RGBA"
        and background == BackgroundMode.transparent
        and output_format in (OutputFormat.webp, OutputFormat.png)
    )
    if preserve_alpha:
        pass
    elif img_out.mode == "RGBA":
        bg = Image.new("RGB", img_out.size, (255, 255, 255))
        bg.paste(img_out, mask=img_out.split()[-1])
        img_out = bg
    elif img_out.mode != "RGB":
        img_out = img_out.convert("RGB")

    if output_format == OutputFormat.jpeg and img_out.mode == "RGBA":
        bg = Image.new("RGB", img_out.size, (255, 255, 255))
        bg.paste(img_out, mask=img_out.split()[-1])
        img_out = bg

    t_pre_encode = time.perf_counter()
    data, _q = ops.encode_under_budget(
        img_out,
        fmt,
        max_bytes,
        qh,
        ql,
        deadline,
    )
    t_end = time.perf_counter()
    timing_ms = {
        "pipeline_body_ms": round((t_pre_encode - t_body_start) * 1000, 1),
        "encode_ms": round((t_end - t_pre_encode) * 1000, 1),
    }
    ops_list.append("compression")
    ops_list.append(f"format_conversion_{fmt}")

    size_kb = len(data) / 1024.0
    return ProcessResult(
        data=data,
        operations=ops_list + ["encode_quality_search"],
        width=tw,
        height=th,
        format=output_format.value,
        size_kb=size_kb,
        background=background.value,
        timing_ms=timing_ms,
    )
