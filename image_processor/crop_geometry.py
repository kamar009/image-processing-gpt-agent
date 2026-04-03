"""Pre-crop to Vision boxes (normalized 0–1) before aspect crop."""

from __future__ import annotations

from PIL import Image

from gpt_agent.schema import VisionAnalysis
from presets.definitions import CropMode


def pre_constrain_to_vision_region(
    im: Image.Image,
    vision: VisionAnalysis,
    crop_mode: CropMode,
    *,
    margin_frac: float = 0.04,
) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """
    Smart mode only: crop to expanded suggested_crop or content_tight_box in pixel space.
    Returns (image, (ox, oy, sw, sh)) in original pixel coords, or (im, None) if skipped.
    """
    if crop_mode != CropMode.smart:
        return im, None
    box = vision.suggested_crop
    if box is None or box.width <= 0 or box.height <= 0:
        box = vision.content_tight_box
    if box is None or box.width <= 0 or box.height <= 0:
        return im, None
    W, H = im.size
    if W < 2 or H < 2:
        return im, None
    pad_x = margin_frac * W
    pad_y = margin_frac * H
    fx0 = box.x * W - pad_x
    fy0 = box.y * H - pad_y
    fx1 = (box.x + box.width) * W + pad_x
    fy1 = (box.y + box.height) * H + pad_y
    x0 = int(max(0, min(W - 1, fx0)))
    y0 = int(max(0, min(H - 1, fy0)))
    x1 = int(max(x0 + 1, min(W, fx1)))
    y1 = int(max(y0 + 1, min(H, fy1)))
    sw, sh = x1 - x0, y1 - y0
    min_side = max(32, min(W, H) // 25)
    if sw < min_side or sh < min_side:
        return im, None
    sub = im.crop((x0, y0, x1, y1))
    return sub, (x0, y0, sw, sh)


def remap_normalized_focal(
    cx: float,
    cy: float,
    meta: tuple[int, int, int, int] | None,
    orig_w: int,
    orig_h: int,
) -> tuple[float, float]:
    """Map focal (0–1 on full image) to 0–1 on pre-cropped subimage."""
    if meta is None:
        return cx, cy
    ox, oy, sw, sh = meta
    if sw <= 0 or sh <= 0:
        return cx, cy
    gcx, gcy = cx * orig_w, cy * orig_h
    ncx = (gcx - ox) / sw
    ncy = (gcy - oy) / sh
    return (max(0.0, min(1.0, ncx)), max(0.0, min(1.0, ncy)))
