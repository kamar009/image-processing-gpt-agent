from __future__ import annotations

import time
from io import BytesIO
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from gpt_agent.schema import VisionAnalysis


def now_ok(deadline: float | None) -> bool:
    return deadline is None or time.monotonic() < deadline


def normalize_exposure_rgb(im: Image.Image, strength: float = 0.35) -> Image.Image:
    """Gentle auto-contrast on luminance via grayscale blend."""
    if im.mode != "RGB":
        im = im.convert("RGB")
    gray = ImageOps.grayscale(im)
    lo, hi = np.percentile(np.array(gray), (2, 98))
    if hi <= lo:
        return im
    arr = np.array(im, dtype=np.float32)
    g = np.array(gray, dtype=np.float32)
    g = np.clip((g - lo) / (hi - lo), 0, 1)
    for c in range(3):
        ch = arr[:, :, c]
        arr[:, :, c] = ch * (1 - strength) + (g * 255.0) * strength
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


def unsharp(im: Image.Image, radius: float = 1.2, percent: int = 130, threshold: int = 3) -> Image.Image:
    return im.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def denoise_color(im: Image.Image, h: int = 6) -> Image.Image:
    rgb = np.array(im.convert("RGB"))
    den = cv2.fastNlMeansDenoisingColored(rgb, None, h, h, 7, 21)
    return Image.fromarray(den, mode="RGB")


def _rembg_remove(arr: np.ndarray) -> np.ndarray:
    from rembg import remove

    return remove(arr)


def remove_background_rgba(im: Image.Image) -> Image.Image:
    arr = np.array(im.convert("RGB"))
    out = _rembg_remove(arr)
    return Image.fromarray(out).convert("RGBA")


def composite_white(rgba: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, rgba.convert("RGBA")).convert("RGB")


def crop_to_aspect(
    im: Image.Image,
    aspect_w: int,
    aspect_h: int,
    cx: float,
    cy: float,
) -> Image.Image:
    iw, ih = im.size
    if iw <= 0 or ih <= 0:
        return im
    target_ar = aspect_w / aspect_h
    img_ar = iw / ih
    cx_pix = max(0.0, min(1.0, cx)) * iw
    cy_pix = max(0.0, min(1.0, cy)) * ih
    if img_ar > target_ar:
        nw = int(round(ih * target_ar))
        nh = ih
        x0 = int(round(cx_pix - nw / 2))
        x0 = max(0, min(x0, iw - nw))
        y0 = 0
    else:
        nw = iw
        nh = int(round(iw / target_ar))
        x0 = 0
        y0 = int(round(cy_pix - nh / 2))
        y0 = max(0, min(y0, ih - nh))
    return im.crop((x0, y0, x0 + nw, y0 + nh))


def resize_exact(im: Image.Image, w: int, h: int) -> Image.Image:
    if im.size == (w, h):
        return im
    return im.resize((w, h), Image.Resampling.LANCZOS)


def blur_fill_compose(fg: Image.Image, tw: int, th: int) -> Image.Image:
    """Wide banner feel: blurred cover layer + centered fitted sharp layer."""
    fg = fg.convert("RGBA")
    iw, ih = fg.size
    if iw <= 0 or ih <= 0:
        return Image.new("RGB", (tw, th), (32, 32, 32))
    scale_cover = max(tw / iw, th / ih)
    cover = fg.resize((max(1, int(iw * scale_cover)), max(1, int(ih * scale_cover))), Image.Resampling.LANCZOS)
    lx = (cover.width - tw) // 2
    ly = (cover.height - th) // 2
    slab = cover.crop((lx, ly, lx + tw, ly + th)).convert("RGB")
    blur_r = max(8, min(tw, th) // 40)
    bg = slab.filter(ImageFilter.GaussianBlur(radius=blur_r))

    scale_fit = min(tw / iw, th / ih)
    fw = max(1, int(iw * scale_fit))
    fh = max(1, int(ih * scale_fit))
    fit = fg.resize((fw, fh), Image.Resampling.LANCZOS)
    out = bg.copy()
    ox = (tw - fw) // 2
    oy = (th - fh) // 2
    out.paste(fit.convert("RGB"), (ox, oy), fit.split()[-1] if fit.mode == "RGBA" else None)
    return out


def cinematic_banner(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(1.06)
    im = ImageEnhance.Color(im).enhance(1.04)
    im = ImageEnhance.Brightness(im).enhance(0.98)
    return im


def category_grade(im: Image.Image) -> Image.Image:
    im = im.convert("RGB")
    im = ImageEnhance.Color(im).enhance(1.06)
    im = ImageEnhance.Contrast(im).enhance(1.05)
    return im


def slight_rotation_fix(im: Image.Image, max_deg: float = 1.2) -> Image.Image:
    """Very light deskew using OpenCV minAreaRect on edges — cheap heuristic."""
    gray = np.array(ImageOps.grayscale(im))
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150)
    pts = cv2.findNonZero(edges)
    if pts is None or len(pts) < 50:
        return im
    rect = cv2.minAreaRect(pts)
    ang = rect[-1]
    if ang < -45:
        ang = 90 + ang
    if abs(ang) > max_deg or abs(ang) < 0.05:
        return im
    w, h = im.size
    m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    arr = np.array(im.convert("RGB"))
    rot = cv2.warpAffine(arr, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(rot, mode="RGB")


def product_pad_square_content(im_rgb: Image.Image, tight_margin: float = 0.06) -> Image.Image:
    """Expand canvas so subject has breathing room before square crop (uses bbox of non-white if no alpha)."""
    im_rgb = im_rgb.convert("RGB")
    arr = np.array(im_rgb)
    mask = np.any(arr < 250, axis=2)
    if not mask.any():
        return im_rgb
    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    bw, bh = x1 - x0, y1 - y0
    pad = int(max(bw, bh) * tight_margin)
    nw = max(bw + 2 * pad, bh + 2 * pad)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    half = nw // 2
    canvas = Image.new("RGB", (nw, nw), (255, 255, 255))
    paste_x = half - cx
    paste_y = half - cy
    canvas.paste(im_rgb, (paste_x, paste_y))
    return canvas


def focal_from_vision(vision: VisionAnalysis, default_cx: float = 0.5, default_cy: float = 0.5) -> tuple[float, float]:
    return (vision.focal_center_x, vision.focal_center_y)


def banner_focal(vision: VisionAnalysis) -> tuple[float, float]:
    cx, cy = vision.focal_center_x, vision.focal_center_y
    if vision.safe_area:
        sa = vision.safe_area
        sx = (sa.left + sa.right) / 2
        sy = (sa.top + sa.bottom) / 2
        # Anchor slightly below safe-area vertical center so top stays freer for headline
        cy_anchor = sa.top + (sa.bottom - sa.top) * 0.58
        cx = 0.42 * cx + 0.58 * sx
        cy = 0.38 * cy + 0.37 * sy + 0.25 * cy_anchor
    return (max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy)))


def encode_under_budget(
    im: Image.Image,
    fmt: str,
    max_bytes: int,
    quality_high: int,
    quality_low: int,
    deadline: float | None,
    check: Callable[[], bool] | None = None,
) -> tuple[bytes, int]:
    """Return (bytes, final_quality)."""
    if fmt == "png":
        buf = BytesIO()
        im.save(buf, format="PNG", optimize=True, compress_level=9)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            return data, 95
        if im.mode == "RGBA":
            flat = Image.new("RGB", im.size, (255, 255, 255))
            flat.paste(im, mask=im.split()[-1])
            rgb = flat
        else:
            rgb = im.convert("RGB")
        qimg = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        b2 = BytesIO()
        qimg.save(b2, format="PNG", optimize=True, compress_level=9)
        return b2.getvalue(), 256

    step = max(2, (quality_high - quality_low) // 25 or 1)
    last_buf = b""
    last_q = quality_low
    for q in range(quality_high, quality_low - 1, -step):
        if deadline is not None and time.monotonic() >= deadline:
            break
        if check and not check():
            break
        buf = BytesIO()
        if fmt == "webp":
            im.save(buf, format="WEBP", quality=q, method=6)
        elif fmt == "jpeg":
            im.save(buf, format="JPEG", quality=q, optimize=True)
        else:
            break
        last_buf = buf.getvalue()
        last_q = q
        if len(last_buf) <= max_bytes:
            return last_buf, last_q
    if last_buf and len(last_buf) <= max_bytes:
        return last_buf, last_q
    # Binary search fallback for webp/jpeg
    lo, hi = quality_low, quality_high
    best = last_buf
    best_q = last_q
    for _ in range(12):
        if deadline is not None and time.monotonic() >= deadline:
            break
        mid = (lo + hi) // 2
        buf = BytesIO()
        if fmt == "webp":
            im.save(buf, format="WEBP", quality=mid, method=6)
        elif fmt == "jpeg":
            im.save(buf, format="JPEG", quality=mid, optimize=True)
        else:
            break
        b = buf.getvalue()
        if len(b) <= max_bytes:
            best, best_q = b, mid
            lo = mid + 1
        else:
            hi = mid - 1
        if lo > hi:
            break
    return best or last_buf, best_q
