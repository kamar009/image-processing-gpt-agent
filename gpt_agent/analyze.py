from __future__ import annotations

import base64
import json
import logging
import os
from io import BytesIO

from openai import OpenAI
from PIL import Image

from gpt_agent.schema import SafeAreaNormalized, VisionAnalysis
from presets.definitions import ImageType, StylePreset

logger = logging.getLogger(__name__)


def _image_to_base64_png(image: Image.Image) -> str:
    buf = BytesIO()
    rgb = image.convert("RGB") if image.mode not in ("RGB", "L") else image.convert("RGB")
    rgb.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _build_system_prompt(image_type: ImageType, style: StylePreset) -> str:
    base = f"""You analyze images for automated web publishing. Image use case: {image_type.value}.
Style hint: {style.value}.

Respond ONLY with JSON matching this exact shape (no markdown):
{{
  "scene_description": string,
  "focal_center_x": number 0-1,
  "focal_center_y": number 0-1,
  "suggested_crop": null or {{"x":0-1,"y":0-1,"width":0-1,"height":0-1}},
  "safe_area": null or {{"left":0-1,"top":0-1,"right":0-1,"bottom":0-1}},
  "preserve_realistic_colors": boolean,
  "avoid_heavy_saturation": boolean,
  "vertical_lines_need_correction": boolean,
  "perspective_strength": "none"|"light"|"moderate",
  "notes_for_crop": string,
  "content_tight_box": null or {{"x","y","width","height"}} in 0-1
}}

Rules:
- focal_center is the main subject or hook for composition.
- For banner, safe_area is where headline/subcopy must stay clear; prefer lower_center-ish safe zone if unclear.
- For product: content_tight_box should bound the main object (rough).
- For portfolio_interior: preserve_realistic_colors=true, avoid_heavy_saturation=true, perspective_strength usually light; do not suggest removing architecture.
"""
    if image_type == ImageType.portfolio_interior:
        base += "\nInterior: never suggest cropping away dominant furniture or key walls; focal_center on strongest design read."
    if image_type == ImageType.banner:
        base += "\nBanner: safe_area must leave ~top 25% clearer for text unless image has strong negative space there."
    return base


def analyze_image_for_pipeline(
    image: Image.Image,
    image_type: ImageType,
    style: StylePreset = StylePreset.neutral,
    *,
    model: str | None = None,
    timeout: float = 60.0,
) -> VisionAnalysis:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY missing; using heuristic fallback analysis")
        return _fallback_analysis(image, image_type)

    client = OpenAI(api_key=api_key, timeout=timeout)
    use_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
    b64 = _image_to_base64_png(image)
    system = _build_system_prompt(image_type, style)
    user_content = [
        {"type": "text", "text": "Analyze this image and output the JSON object only."},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        },
    ]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    for attempt in range(3):
        try:
            if os.environ.get("OPENAI_STRUCTURED_PARSE", "1").lower() in ("1", "true", "yes"):
                try:
                    resp = client.beta.chat.completions.parse(
                        model=use_model,
                        messages=messages,
                        response_format=VisionAnalysis,
                        max_tokens=800,
                    )
                    choice = resp.choices[0]
                    msg = choice.message
                    if getattr(msg, "refusal", None):
                        logger.warning("Vision refusal: %s", msg.refusal)
                    elif msg.parsed is not None:
                        return msg.parsed
                except Exception as parse_err:
                    logger.warning("Structured parse attempt failed: %s", parse_err)

            resp = client.chat.completions.create(
                model=use_model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=800,
            )
            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)
            return VisionAnalysis.model_validate(data)
        except Exception as e:
            logger.warning("Vision attempt %s failed: %s", attempt + 1, e)
    logger.error("Vision failed after retries; fallback")
    return _fallback_analysis(image, image_type)


def _fallback_analysis(image: Image.Image, image_type: ImageType) -> VisionAnalysis:
    w, h = image.size
    default_safe = SafeAreaNormalized(left=0.08, top=0.1, right=0.92, bottom=0.75)
    if image_type == ImageType.banner:
        return VisionAnalysis(
            scene_description="fallback",
            focal_center_x=0.5,
            focal_center_y=0.45,
            safe_area=default_safe,
            preserve_realistic_colors=True,
            vertical_lines_need_correction=False,
            perspective_strength="light",
        )
    if image_type == ImageType.product:
        return VisionAnalysis(
            scene_description="fallback",
            focal_center_x=0.5,
            focal_center_y=0.5,
            perspective_strength="none",
            preserve_realistic_colors=True,
            content_tight_box=None,
        )
    if image_type == ImageType.portfolio_interior:
        return VisionAnalysis(
            scene_description="fallback interior",
            focal_center_x=0.5,
            focal_center_y=0.5,
            preserve_realistic_colors=True,
            avoid_heavy_saturation=True,
            vertical_lines_need_correction=True,
            perspective_strength="light",
        )
    return VisionAnalysis(
        scene_description="fallback",
        focal_center_x=0.5,
        focal_center_y=0.5,
        perspective_strength="none",
    )
