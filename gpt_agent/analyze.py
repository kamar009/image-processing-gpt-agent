from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from io import BytesIO

import httpx
from openai import OpenAI
from PIL import Image

from gpt_agent.schema import SafeAreaNormalized, VisionAnalysis
from presets.definitions import ImageType, StylePreset

logger = logging.getLogger(__name__)

_SBER_TLS_WARN_EMITTED = False


def _sber_httpx_verify() -> bool:
    """TLS verify for GigaChat/OAuth httpx clients. Disable only if MITM/proxy breaks the chain (CERTIFICATE_VERIFY_FAILED)."""
    global _SBER_TLS_WARN_EMITTED
    v = os.environ.get("SBER_HTTPX_VERIFY", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        if not _SBER_TLS_WARN_EMITTED:
            logger.warning(
                "SBER_HTTPX_VERIFY is off: TLS certificate verification disabled for Sber OAuth/GigaChat "
                "(use only if a corporate proxy causes SSL errors; prefer installing the proxy CA in the OS trust store)"
            )
            _SBER_TLS_WARN_EMITTED = True
        return False
    return True


@dataclass(frozen=True)
class VisionProviderConfig:
    provider: str
    api_key: str
    base_url: str | None
    model: str
    structured_parse: bool
    timeout: float
    auth_key: str
    oauth_url: str
    scope: str


def _image_to_base64_png(image: Image.Image) -> str:
    buf = BytesIO()
    rgb = image.convert("RGB") if image.mode not in ("RGB", "L") else image.convert("RGB")
    rgb.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _image_to_jpeg_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    rgb = image.convert("RGB")
    rgb.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _message_content_to_text(content: object) -> str:
    """Normalize chat message content (str or OpenAI-style list of parts) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _json_dict_from_llm_text(text: str) -> dict:
    """Parse JSON from model output; tolerate ```json fences and leading/trailing prose."""
    s = text.strip()
    if not s:
        raise ValueError("empty model content")
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    try:
        parsed: object = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(s[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("model JSON root must be an object")
    return parsed


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
    cfg = _load_provider_config(model=model, timeout=timeout)
    if cfg.provider == "fallback":
        logger.info("VISION_PROVIDER=fallback; using heuristic fallback analysis")
        return _fallback_analysis(image, image_type)
    if cfg.provider == "sber":
        if not (cfg.api_key or cfg.auth_key):
            logger.warning(
                "sber vision: set SBER_VISION_API_KEY or SBER_VISION_AUTH_KEY; using heuristic fallback"
            )
            return _fallback_analysis(image, image_type)
    elif not cfg.api_key:
        logger.warning("%s vision key missing; using heuristic fallback", cfg.provider)
        return _fallback_analysis(image, image_type)

    try:
        if cfg.provider == "sber":
            return _run_sber_vision(cfg, image=image, image_type=image_type, style=style)
        return _run_openai_compatible_vision(cfg, image=image, image_type=image_type, style=style)
    except Exception as e:
        logger.error("%s vision failed; using heuristic fallback: %s", cfg.provider, e, exc_info=True)
        return _fallback_analysis(image, image_type)


def _load_provider_config(*, model: str | None, timeout: float) -> VisionProviderConfig:
    provider = os.environ.get("VISION_PROVIDER", "openai").strip().lower()
    if provider not in ("openai", "sber", "yandex", "fallback"):
        logger.warning("Unknown VISION_PROVIDER=%s; fallback to openai", provider)
        provider = "openai"

    if provider == "fallback":
        return VisionProviderConfig(
            provider=provider,
            api_key="",
            base_url=None,
            model="",
            structured_parse=False,
            timeout=timeout,
            auth_key="",
            oauth_url="",
            scope="",
        )

    if provider == "openai":
        return VisionProviderConfig(
            provider=provider,
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or None,
            model=model or os.environ.get("OPENAI_MODEL", "gpt-4o"),
            structured_parse=os.environ.get("OPENAI_STRUCTURED_PARSE", "1").lower() in ("1", "true", "yes"),
            timeout=timeout,
            auth_key="",
            oauth_url="",
            scope="",
        )

    if provider == "sber":
        return VisionProviderConfig(
            provider=provider,
            api_key=os.environ.get("SBER_VISION_API_KEY", "").strip(),
            base_url=os.environ.get("SBER_VISION_BASE_URL", "").strip() or "https://gigachat.devices.sberbank.ru/api/v1",
            model=model or os.environ.get("SBER_VISION_MODEL", "GigaChat-2-Pro"),
            structured_parse=os.environ.get("SBER_STRUCTURED_PARSE", "0").lower() in ("1", "true", "yes"),
            timeout=timeout,
            auth_key=os.environ.get("SBER_VISION_AUTH_KEY", "").strip(),
            oauth_url=os.environ.get("SBER_OAUTH_URL", "").strip() or "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            scope=os.environ.get("SBER_SCOPE", "GIGACHAT_API_PERS").strip(),
        )

    folder_id = os.environ.get("YANDEX_FOLDER_ID", "").strip()
    y_model = (model or os.environ.get("YANDEX_VISION_MODEL", "yandexgpt") or "yandexgpt").strip()
    if folder_id and not y_model.startswith("gpt://"):
        if y_model in ("yandexgpt", "yandexgpt/latest"):
            y_model = f"gpt://{folder_id}/yandexgpt/latest"
        elif y_model.startswith("yandexgpt/"):
            y_model = f"gpt://{folder_id}/{y_model}"
        elif y_model.startswith("yandexgpt-lite"):
            y_model = f"gpt://{folder_id}/{y_model}"
        # Мультимодель (изображения): см. yandex-ai-studio-sdk examples/sync/chat/multimodal.py
        elif y_model in ("gemma-3-27b-it", "gemma-3-27b-it/latest"):
            y_model = f"gpt://{folder_id}/gemma-3-27b-it/latest"
        elif y_model.startswith("gemma-3-27b-it/"):
            y_model = f"gpt://{folder_id}/{y_model}"

    return VisionProviderConfig(
        provider="yandex",
        api_key=os.environ.get("YANDEX_VISION_API_KEY", "").strip(),
        base_url=os.environ.get("YANDEX_VISION_BASE_URL", "").strip() or None,
        model=y_model,
        structured_parse=os.environ.get("YANDEX_STRUCTURED_PARSE", "0").lower() in ("1", "true", "yes"),
        timeout=timeout,
        auth_key="",
        oauth_url="",
        scope="",
    )


def _resolve_sber_access_token(cfg: VisionProviderConfig) -> str:
    if cfg.api_key:
        return cfg.api_key
    if not cfg.auth_key:
        raise RuntimeError("SBER_VISION_API_KEY or SBER_VISION_AUTH_KEY is required")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {cfg.auth_key}",
    }
    with httpx.Client(timeout=cfg.timeout, verify=_sber_httpx_verify()) as client:
        resp = client.post(cfg.oauth_url, headers=headers, data={"scope": cfg.scope})
        resp.raise_for_status()
        data = resp.json()
    token = str(data.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("Sber oauth response does not contain access_token")
    return token


def _run_sber_vision(
    cfg: VisionProviderConfig,
    *,
    image: Image.Image,
    image_type: ImageType,
    style: StylePreset,
) -> VisionAnalysis:
    token = _resolve_sber_access_token(cfg)
    if not cfg.base_url:
        raise RuntimeError("SBER_VISION_BASE_URL is required")

    base_url = cfg.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    payload_text = (
        _build_system_prompt(image_type, style)
        + "\n\nAnalyze the attached image and output JSON only."
    )
    img_bytes = _image_to_jpeg_bytes(image)

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=cfg.timeout, verify=_sber_httpx_verify()) as client:
                files_resp = client.post(
                    f"{base_url}/files",
                    headers=headers,
                    files={"file": ("vision.jpg", img_bytes, "image/jpeg")},
                    data={"purpose": "general"},
                )
                try:
                    files_resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "sber /files attempt %s: HTTP %s body=%s",
                        attempt + 1,
                        e.response.status_code,
                        (e.response.text or "")[:800],
                    )
                    raise
                file_id = str(files_resp.json()["id"])

                # GigaChat не всегда принимает OpenAI-стиль response_format=json_object; промпт уже требует JSON.
                body = {
                    "model": cfg.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": payload_text,
                            "attachments": [file_id],
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048,
                }
                chat_resp = client.post(
                    f"{base_url}/chat/completions",
                    headers={**headers, "Content-Type": "application/json"},
                    json=body,
                )
                try:
                    chat_resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.warning(
                        "sber chat attempt %s: HTTP %s body=%s",
                        attempt + 1,
                        e.response.status_code,
                        (e.response.text or "")[:800],
                    )
                    raise
                raw_content = chat_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                text = _message_content_to_text(raw_content)
                data = _json_dict_from_llm_text(text)
            return VisionAnalysis.model_validate(data)
        except Exception as e:
            last_err = e
            logger.warning("sber vision attempt %s failed: %s", attempt + 1, e)
    if last_err is None:
        raise RuntimeError("sber vision failed after 3 attempts")
    raise RuntimeError(f"sber vision failed after 3 attempts: {last_err}") from last_err


def _run_openai_compatible_vision(
    cfg: VisionProviderConfig,
    *,
    image: Image.Image,
    image_type: ImageType,
    style: StylePreset,
) -> VisionAnalysis:
    # SDK: if base_url is omitted/None it reads OPENAI_BASE_URL from env; an empty
    # string there becomes the client base URL and httpx fails (UnsupportedProtocol),
    # surfaced as APIConnectionError → heuristic fallback.
    if cfg.provider == "yandex":
        openai_base = cfg.base_url or "https://llm.api.cloud.yandex.net/v1"
    else:
        openai_base = cfg.base_url or "https://api.openai.com/v1"
    client = OpenAI(api_key=cfg.api_key, base_url=openai_base, timeout=cfg.timeout)
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
            if cfg.structured_parse:
                try:
                    resp = client.beta.chat.completions.parse(
                        model=cfg.model,
                        messages=messages,
                        response_format=VisionAnalysis,
                        max_tokens=800,
                    )
                    choice = resp.choices[0]
                    msg = choice.message
                    if getattr(msg, "refusal", None):
                        logger.warning("%s vision refusal: %s", cfg.provider, msg.refusal)
                    elif msg.parsed is not None:
                        return msg.parsed
                except Exception as parse_err:
                    logger.warning("%s structured parse failed: %s", cfg.provider, parse_err)

            resp = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=800,
            )
            raw = resp.choices[0].message.content or "{}"
            data = _json_dict_from_llm_text(_message_content_to_text(raw))
            return VisionAnalysis.model_validate(data)
        except Exception as e:
            logger.warning("%s vision attempt %s failed: %s", cfg.provider, attempt + 1, e)
    raise RuntimeError(f"{cfg.provider} vision failed")


def _fallback_analysis(image: Image.Image, image_type: ImageType) -> VisionAnalysis:
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
