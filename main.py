from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
import json
from contextlib import asynccontextmanager
from enum import Enum
from io import BytesIO
from threading import Lock
from typing import Annotated, TypeVar

from dotenv import load_dotenv
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps

from gpt_agent.analyze import analyze_image_for_pipeline
from internal.auth import verify_telegram_init_data
from internal.config import load_internal_config
from internal.repository import InternalRepository
from internal.tokens import create_access_token, decode_access_token
from image_processor.pipeline import run_pipeline
from output_storage.local import OutputStorage
from presets.definitions import (
    BackgroundMode,
    CropMode,
    FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX,
    FurniturePortfolioOutputTarget,
    FurnitureScene,
    ImageType,
    OutputFormat,
    QualityLevel,
    StylePreset,
    get_preset,
)
from validator.checks import validate_output

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_APP_DESC = """Подготовка изображений для сайта: Vision (OpenAI) + пресеты product | category | banner | portfolio_interior | furniture_portfolio (нужны furniture_scene и output_target; см. docs/FURNITURE_PORTFOLIO_API.md).

**Пример curl (хост и путь к файлу подставьте свои):**
```bash
curl -s -X POST "http://127.0.0.1:8000/process-image" \\
  -F "image=@./photo.jpg" \\
  -F "type=product" \\
  -F "background=keep" \\
  -F "format=webp"
```

Веб-форма: **/ui** (или `/`). Интерактивная OpenAPI-схема: **/docs**.
"""


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if os.environ.get("REMBG_WARMUP", "").lower() in ("1", "true", "yes"):
        try:
            import numpy as np

            from image_processor.ops import _rembg_remove

            _rembg_remove(np.zeros((32, 32, 3), dtype=np.uint8))
            logger.info("rembg model warmup done")
        except Exception as exc:
            logger.warning("rembg warmup skipped: %s", exc)
    yield


app = FastAPI(
    title="Site image processing MVP",
    version="0.1.0",
    description=_APP_DESC,
    lifespan=_lifespan,
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/ui")
def ui_redirect() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/index.html")


storage = OutputStorage()
internal_cfg = load_internal_config()
internal_repo = InternalRepository(internal_cfg.db_path)

for admin_id in internal_cfg.admin_ids:
    internal_repo.allow_user(admin_id, "env admin")


def _bearer_sub(request: Request) -> str:
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authorization bearer token required")
    raw = auth[7:].strip()
    if not internal_cfg.jwt_secret:
        raise HTTPException(status_code=500, detail="internal jwt secret not configured")
    try:
        payload = decode_access_token(internal_cfg.jwt_secret, raw)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token") from None
    return str(payload["sub"])


def _resolve_job_owner_user_id(
    request: Request,
    *,
    query_user_id: str | None,
    body_user_id: str | None,
) -> str:
    if internal_cfg.jwt_secret:
        return _bearer_sub(request)
    uid = (query_user_id or body_user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="user_id is required")
    return uid


if internal_cfg.enabled and internal_cfg.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(internal_cfg.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )

_MINIAPP_DIR = Path(__file__).resolve().parent / "static" / "miniapp"
if _MINIAPP_DIR.is_dir():
    app.mount("/miniapp", StaticFiles(directory=str(_MINIAPP_DIR), html=True), name="miniapp")

_metrics_lock = Lock()
_metrics = {
    "requests_total": 0,
    "status_2xx": 0,
    "status_4xx": 0,
    "status_5xx": 0,
    "process_image_count": 0,
    "process_image_total_ms": 0.0,
}


def _bump_metric(key: str, value: float = 1) -> None:
    with _metrics_lock:
        _metrics[key] = _metrics.get(key, 0) + value


def _error_response(status_code: int, detail: str, request_id: str | None = None) -> JSONResponse:
    body: dict[str, str] = {"detail": detail}
    if request_id:
        body["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=body)


def _max_upload_bytes() -> int:
    try:
        mb = float(os.environ.get("MAX_UPLOAD_MB", "25"))
    except ValueError:
        mb = 25.0
    mb = max(1.0, min(mb, 100.0))
    return int(mb * 1024 * 1024)


def _disk_usage_for_path(root: Path) -> dict[str, float]:
    """Usage of the filesystem that contains OUTPUT_DIR (same volume as uploads)."""
    try:
        root.mkdir(parents=True, exist_ok=True)
        u = shutil.disk_usage(root)
        if u.total <= 0:
            return {"disk_volume_used_pct": -1.0, "disk_volume_free_gb": 0.0, "disk_volume_total_gb": 0.0}
        used_pct = round((u.used / u.total) * 100.0, 2)
        return {
            "disk_volume_used_pct": used_pct,
            "disk_volume_free_gb": round(u.free / (1024**3), 3),
            "disk_volume_total_gb": round(u.total / (1024**3), 3),
        }
    except OSError:
        return {"disk_volume_used_pct": -1.0, "disk_volume_free_gb": 0.0, "disk_volume_total_gb": 0.0}


def _disk_thresholds() -> tuple[float, float]:
    try:
        warn = float(os.environ.get("DISK_USAGE_WARN_PCT", "85"))
    except ValueError:
        warn = 85.0
    try:
        crit = float(os.environ.get("DISK_USAGE_CRITICAL_PCT", "95"))
    except ValueError:
        crit = 95.0
    return max(0.0, min(warn, 100.0)), max(0.0, min(crit, 100.0))


_E = TypeVar("_E", bound=Enum)
_ALLOWED_MAX_OUTPUT_KB = {150, 200, 250, 300, 350, 400, 450, 500}
_ALLOWED_VISION_PROVIDERS = {"openai", "sber", "fallback"}
_ALLOWED_SBER_MODELS = {"GigaChat-2-Max", "GigaChat-2-Pro"}


def _parse_enum(raw: str | None, cls: type[_E], default: _E) -> _E:
    if raw is None or raw == "":
        return default
    try:
        return cls(raw)
    except ValueError:
        try:
            return cls[raw]
        except Exception:
            raise HTTPException(status_code=400, detail=f"invalid value for {cls.__name__}: {raw}") from None


def _parse_enhanced_flag(raw: str | None) -> bool:
    """FURNITURE_PORTFOLIO_API §2: on only for 1, true, on (case-insensitive)."""
    if raw is None or str(raw).strip() == "":
        return False
    return str(raw).strip().lower() in ("1", "true", "on")


def _parse_furniture_enum_or_422(raw: str | None, *, cls: type[_E], field_label: str) -> _E:
    if raw is None or str(raw).strip() == "":
        raise HTTPException(
            status_code=422,
            detail=f"{field_label} is required when type=furniture_portfolio",
        )
    key = str(raw).strip()
    try:
        return cls(key)
    except ValueError:
        allowed = ", ".join(sorted(e.value for e in cls))
        raise HTTPException(
            status_code=422,
            detail=f"invalid {field_label}: {key!r}; expected one of: {allowed}",
        ) from None


def _parse_max_output_kb(raw: str | None, default_kb: int) -> int:
    if raw is None or raw == "":
        return default_kb
    try:
        value = int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="max_output_kb must be an integer") from exc
    if value not in _ALLOWED_MAX_OUTPUT_KB:
        allowed = ", ".join(str(v) for v in sorted(_ALLOWED_MAX_OUTPUT_KB))
        raise HTTPException(status_code=422, detail=f"max_output_kb must be one of: {allowed}")
    return value


def _resolve_vision_provider_and_model(
    provider_raw: str | None,
    model_raw: str | None,
) -> tuple[str, str | None]:
    default_provider = os.environ.get("VISION_PROVIDER", "openai").strip().lower()
    provider = (provider_raw or default_provider or "openai").strip().lower()
    if provider not in _ALLOWED_VISION_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_VISION_PROVIDERS))
        raise HTTPException(status_code=422, detail=f"vision_provider must be one of: {allowed}")

    model = (model_raw or "").strip() or None
    if provider == "sber":
        if model is None:
            model = os.environ.get("SBER_VISION_MODEL", "GigaChat-2-Pro").strip() or "GigaChat-2-Pro"
        if model not in _ALLOWED_SBER_MODELS:
            allowed = ", ".join(sorted(_ALLOWED_SBER_MODELS))
            raise HTTPException(status_code=422, detail=f"vision_model for sber must be one of: {allowed}")
        return provider, model

    if provider == "fallback":
        # Explicitly no external vision model: only heuristic/software analysis path.
        return provider, None

    if model is None:
        model = os.environ.get("OPENAI_MODEL", "gpt-4o").strip() or "gpt-4o"
    return provider, model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/health")
def internal_health() -> dict[str, str | bool | float]:
    if not internal_cfg.enabled:
        return {"status": "ok", "internal_mode": False}
    db_ok = internal_repo.ping()
    try:
        root = storage.root()
        outputs_writable = root.is_dir() and os.access(root, os.W_OK)
    except OSError:
        outputs_writable = False
    disk = _disk_usage_for_path(storage.root())
    warn_p, crit_p = _disk_thresholds()
    pct = disk["disk_volume_used_pct"]
    if pct < 0:
        disk_status = "unknown"
        disk_critical = False
    elif pct >= crit_p:
        disk_status = "critical"
        disk_critical = True
    elif pct >= warn_p:
        disk_status = "warn"
        disk_critical = False
    else:
        disk_status = "ok"
        disk_critical = False
    status = "ok" if db_ok and outputs_writable and not disk_critical else "degraded"
    return {
        "status": status,
        "internal_mode": True,
        "db_ok": db_ok,
        "outputs_writable": outputs_writable,
        "disk_status": disk_status,
        **disk,
    }


@app.get("/metrics")
def metrics() -> dict[str, float | int]:
    with _metrics_lock:
        avg_ms = (
            _metrics["process_image_total_ms"] / _metrics["process_image_count"]
            if _metrics["process_image_count"]
            else 0.0
        )
        disk = _disk_usage_for_path(storage.root())
        return {**_metrics, "process_image_avg_ms": round(avg_ms, 2), **disk}


@app.middleware("http")
async def request_context_logging(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    _bump_metric("requests_total", 1)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        _bump_metric("status_5xx", 1)
        logger.exception(
            "request_fail method=%s path=%s request_id=%s elapsed_ms=%s",
            request.method,
            request.url.path,
            request_id,
            elapsed_ms,
        )
        raise
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    response.headers["x-request-id"] = request_id
    sc = response.status_code
    if 200 <= sc < 300:
        _bump_metric("status_2xx", 1)
    elif 400 <= sc < 500:
        _bump_metric("status_4xx", 1)
    elif sc >= 500:
        _bump_metric("status_5xx", 1)
    logger.info(
        "request_done method=%s path=%s status=%s request_id=%s elapsed_ms=%s",
        request.method,
        request.url.path,
        sc,
        request_id,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    request_id = getattr(request.state, "request_id", None)
    return _error_response(exc.status_code, detail, request_id=request_id)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    detail = "; ".join(err.get("msg", "validation error") for err in exc.errors())
    return _error_response(422, detail, request_id=request_id)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("unhandled_error request_id=%s", request_id)
    return _error_response(500, f"internal server error: {exc}", request_id=request_id)


@app.get("/outputs/{file_id}")
def download_output(file_id: str):
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        p = storage.path_for(file_id, ext)
        if p.is_file():
            media = {
                ".webp": "image/webp",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
            }.get(ext, "application/octet-stream")
            return FileResponse(path=p, media_type=media, filename=p.name)
    raise HTTPException(status_code=404, detail="file not found")


@app.post("/internal/auth/telegram")
async def internal_auth_telegram(payload: dict):
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    init_data = str(payload.get("init_data", ""))
    parsed = verify_telegram_init_data(init_data, internal_cfg.telegram_bot_token)
    if parsed is None:
        raise HTTPException(status_code=401, detail="invalid init_data")
    user_raw = parsed.get("user", "")
    try:
        user_obj = json.loads(user_raw) if user_raw else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid user payload") from exc
    telegram_id = int(user_obj.get("id", 0))
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="telegram id missing")
    if not internal_repo.is_allowed(telegram_id):
        raise HTTPException(status_code=403, detail="user is not in whitelist")
    full_name = " ".join(x for x in [user_obj.get("first_name", ""), user_obj.get("last_name", "")] if x).strip() or None
    role = "admin" if telegram_id in internal_cfg.admin_ids else "user"
    user = internal_repo.upsert_user(
        telegram_id=telegram_id,
        username=user_obj.get("username"),
        full_name=full_name,
        role=role,
    )
    out: dict = {
        "ok": True,
        "user": {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
        },
    }
    if internal_cfg.jwt_secret:
        out["access_token"] = create_access_token(
            secret=internal_cfg.jwt_secret,
            user_id=user.id,
            telegram_id=user.telegram_id,
            role=user.role,
            exp_hours=internal_cfg.jwt_exp_hours,
        )
        out["token_type"] = "bearer"
        out["expires_in_hours"] = internal_cfg.jwt_exp_hours
    return out


@app.post("/internal/admin/allow-user")
async def allow_user(payload: dict):
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    telegram_id = int(payload.get("telegram_id", 0))
    if telegram_id <= 0:
        raise HTTPException(status_code=400, detail="telegram_id is required")
    comment = str(payload.get("comment", "manual add"))[:120]
    internal_repo.allow_user(telegram_id, comment)
    return {"ok": True, "telegram_id": telegram_id}


@app.get("/internal/client-config")
def internal_client_config():
    """Публичные лимиты для Mini App (без секретов)."""
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    try:
        mb = float(os.environ.get("MAX_UPLOAD_MB", "25"))
    except ValueError:
        mb = 25.0
    mb = max(1.0, min(mb, 100.0))
    return {
        "max_upload_mb": mb,
        "max_upload_bytes": int(mb * 1024 * 1024),
        "max_concurrent_jobs_per_user": internal_cfg.max_concurrent_jobs_per_user,
        "jwt_required": bool(internal_cfg.jwt_secret),
        "presets_count_hint": len(internal_repo.list_presets()),
    }


@app.get("/internal/presets")
def list_internal_presets():
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    return {"items": internal_repo.list_presets()}


@app.post("/internal/jobs")
async def create_internal_job(request: Request, payload: dict):
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    request_id = getattr(request.state, "request_id", None)
    preset_key = str(payload.get("preset_key", "")).strip()
    image_b64 = str(payload.get("image_base64", "")).strip()
    user_id = _resolve_job_owner_user_id(
        request,
        query_user_id=None,
        body_user_id=str(payload.get("user_id", "")).strip() or None,
    )
    if internal_cfg.jwt_secret and (payload.get("user_id")):
        logger.warning("internal_job ignored body user_id when JWT mode is enabled")
    if not preset_key or not image_b64:
        raise HTTPException(status_code=400, detail="preset_key, image_base64 are required")
    if not internal_repo.get_preset_row(preset_key):
        raise HTTPException(status_code=400, detail="unknown or disabled preset_key")
    active = internal_repo.count_active_jobs_for_user(user_id)
    if active >= internal_cfg.max_concurrent_jobs_per_user:
        raise HTTPException(
            status_code=429,
            detail=f"too many active jobs ({active}), max {internal_cfg.max_concurrent_jobs_per_user}",
        )
    try:
        import base64

        data = base64.b64decode(image_b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid image_base64") from exc
    max_bytes = _max_upload_bytes()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"image too large: {len(data)} bytes (max {max_bytes}, MAX_UPLOAD_MB)",
        )
    if not data:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        pil = Image.open(BytesIO(data))
        pil.load()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"cannot decode image: {exc}") from exc
    if pil.format not in (None, "JPEG", "PNG", "WEBP", "MPO"):
        raise HTTPException(status_code=400, detail="unsupported image type (use JPEG, PNG, or WebP)")
    input_file_id, input_path = storage.new_file_id(".png")
    rgb = pil.convert("RGB") if pil.mode not in ("RGB", "L") else pil.convert("RGB")
    rgb.save(input_path, format="PNG")
    job_id = internal_repo.create_job(user_id=user_id, preset_key=preset_key, input_file_id=input_file_id)
    logger.info(
        "internal_job_queued request_id=%s job_id=%s user_id=%s preset_key=%s input_file_id=%s input_bytes=%s",
        request_id,
        job_id,
        user_id,
        preset_key,
        input_file_id,
        len(data),
    )
    return {"id": job_id, "status": "queued"}


@app.get("/internal/jobs")
def list_internal_jobs(request: Request, user_id: str | None = None, limit: int = 50):
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    uid = _resolve_job_owner_user_id(request, query_user_id=user_id, body_user_id=None)
    items = internal_repo.list_jobs_for_user(uid, limit=limit)
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    for j in items:
        if j.get("output_file_id"):
            j["download_url"] = (
                f"{base}/outputs/{j['output_file_id']}" if base else f"/outputs/{j['output_file_id']}"
            )
    return {"items": items}


@app.get("/internal/jobs/{job_id}")
def get_internal_job(request: Request, job_id: str, user_id: str | None = None):
    if not internal_cfg.enabled:
        raise HTTPException(status_code=404, detail="internal mode disabled")
    uid = _resolve_job_owner_user_id(request, query_user_id=user_id, body_user_id=None)
    job = internal_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("user_id") != uid:
        raise HTTPException(status_code=403, detail="job does not belong to this user")
    if job.get("output_file_id"):
        base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        job["download_url"] = f"{base}/outputs/{job['output_file_id']}" if base else f"/outputs/{job['output_file_id']}"
    return job


@app.post("/process-image")
async def process_image(
    request: Request,
    image: Annotated[UploadFile, File(...)],
    type: Annotated[str, Form(...)],
    background: Annotated[str | None, Form()] = None,
    output_format: Annotated[str | None, Form(alias="format")] = None,
    style: Annotated[str | None, Form()] = None,
    crop_mode: Annotated[str | None, Form()] = None,
    quality_level: Annotated[str | None, Form()] = None,
    max_output_kb: Annotated[str | None, Form()] = None,
    vision_provider: Annotated[str | None, Form()] = None,
    vision_model: Annotated[str | None, Form()] = None,
    furniture_scene: Annotated[str | None, Form()] = None,
    output_target: Annotated[str | None, Form()] = None,
    enhanced: Annotated[str | None, Form()] = None,
):
    try:
        image_type = ImageType(type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid type: {type}") from e

    furniture_scene_e: FurnitureScene | None = None
    furniture_output_target_e: FurniturePortfolioOutputTarget | None = None
    enhanced_requested = _parse_enhanced_flag(enhanced)

    if image_type == ImageType.furniture_portfolio:
        furniture_scene_e = _parse_furniture_enum_or_422(
            furniture_scene, cls=FurnitureScene, field_label="furniture_scene"
        )
        furniture_output_target_e = _parse_furniture_enum_or_422(
            output_target, cls=FurniturePortfolioOutputTarget, field_label="output_target"
        )
        preset = get_preset(
            image_type,
            furniture_output_target=furniture_output_target_e,
        )
    else:
        preset = get_preset(image_type)
    bg_mode = _parse_enum(background, BackgroundMode, preset.default_background)
    out_fmt = _parse_enum(output_format, OutputFormat, preset.default_format)
    sty = _parse_enum(style, StylePreset, StylePreset.neutral)
    crop = _parse_enum(crop_mode, CropMode, preset.default_crop)
    qual = _parse_enum(quality_level, QualityLevel, preset.default_quality)
    effective_max_output_kb = _parse_max_output_kb(max_output_kb, preset.max_kb)
    effective_vision_provider, effective_vision_model = _resolve_vision_provider_and_model(vision_provider, vision_model)

    max_bytes = _max_upload_bytes()
    raw = await image.read()
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"image too large: {len(raw)} bytes (max {max_bytes} bytes, set MAX_UPLOAD_MB)",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="empty image")
    try:
        pil = Image.open(BytesIO(raw))
        pil.load()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"cannot decode image: {e}") from e

    if image_type == ImageType.furniture_portfolio:
        pil = ImageOps.exif_transpose(pil)
        iw, ih = pil.size
        long_side = max(iw, ih)
        if long_side < FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"input image longest side is {long_side}px after EXIF orientation; "
                    f"furniture_portfolio requires at least {FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX}px"
                ),
            )

    t_all = time.perf_counter()
    try:
        vision = analyze_image_for_pipeline(
            pil,
            image_type,
            sty,
            provider=effective_vision_provider,
            model=effective_vision_model,
            furniture_enhanced=(
                image_type == ImageType.furniture_portfolio and enhanced_requested
            ),
        )
    except Exception as e:
        logger.exception(
            "vision_failed request_id=%s type=%s",
            getattr(request.state, "request_id", None),
            image_type.value,
        )
        raise HTTPException(
            status_code=502,
            detail=f"vision/analysis failed: {e}",
        ) from e
    t_after_vision = time.perf_counter()
    pil_for_pipe = pil.copy()

    furniture_enhanced_run = (
        image_type == ImageType.furniture_portfolio and enhanced_requested
    )
    try:
        result = run_pipeline(
            pil_for_pipe,
            image_type,
            bg_mode,
            out_fmt,
            crop,
            qual,
            sty,
            vision,
            preset,
            max_output_kb=effective_max_output_kb,
            furniture_enhanced=furniture_enhanced_run,
        )
    except Exception as e:
        logger.exception("pipeline failed")
        raise HTTPException(status_code=500, detail=f"processing failed: {e}") from e
    t_done = time.perf_counter()
    vision_ms = round((t_after_vision - t_all) * 1000, 1)
    pipeline_wall_ms = round((t_done - t_after_vision) * 1000, 1)
    elapsed_ms = round((t_done - t_all) * 1000, 1)
    _bump_metric("process_image_count", 1)
    _bump_metric("process_image_total_ms", elapsed_ms)
    try:
        max_sec = float(os.environ.get("MAX_PROCESS_SECONDS", "10"))
    except ValueError:
        max_sec = 10.0
    if elapsed_ms > max_sec * 1000:
        logger.warning("process-image exceeded budget: %sms (limit %sms)", elapsed_ms, max_sec * 1000)

    ext = {OutputFormat.webp: ".webp", OutputFormat.jpeg: ".jpg", OutputFormat.png: ".png"}[out_fmt]
    file_id, out_path = storage.new_file_id(ext)
    out_path.write_bytes(result.data)

    v = validate_output(out_path, preset, out_fmt, effective_max_output_kb)
    response_warnings = list(v.warnings)
    if image_type == ImageType.furniture_portfolio and vision.people_detected:
        response_warnings.append(
            "В кадре видны люди (оценка Vision); проверьте кадр перед публикацией."
        )
    if (
        image_type == ImageType.furniture_portfolio
        and enhanced_requested
        and vision.people_detected
    ):
        response_warnings.append(
            "Усиленный режим не удаляет людей автоматически — при необходимости обработайте кадр вручную."
        )
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    download_url = f"{base}/outputs/{file_id}" if base else f"/outputs/{file_id}"

    body: dict[str, object] = {
        "file_id": file_id,
        "download_url": download_url,
        "type": image_type.value,
        "width": result.width,
        "height": result.height,
        "format": result.format,
        "size_kb": round(result.size_kb, 2),
        "max_output_kb": effective_max_output_kb,
        "background": result.background,
        "operations": result.operations,
        "validation_ok": v.ok,
        "validation_errors": v.errors,
        "validation_warnings": response_warnings,
        "processing_time_ms": elapsed_ms,
        "vision_ms": vision_ms,
        "vision_provider": effective_vision_provider,
        "vision_model": effective_vision_model,
        "vision_fallback_code": getattr(vision, "fallback_code", "") or "",
        "vision_fallback_message": getattr(vision, "fallback_message", "") or "",
        "pipeline_wall_ms": pipeline_wall_ms,
        "vision_scene": vision.scene_description[:200],
        **result.timing_ms,
    }
    if image_type == ImageType.furniture_portfolio:
        assert furniture_scene_e is not None and furniture_output_target_e is not None
        body["furniture_scene"] = furniture_scene_e.value
        body["output_target"] = furniture_output_target_e.value
        body["enhanced_requested"] = enhanced_requested
        body["enhanced_applied"] = bool(enhanced_requested)
        body["people_detected"] = vision.people_detected
    rid = getattr(request.state, "request_id", None)
    logger.info(
        "process_image_done request_id=%s file_id=%s type=%s vision_ms=%s pipeline_wall_ms=%s "
        "pipeline_body_ms=%s encode_ms=%s size_kb=%s validation_ok=%s",
        rid,
        file_id,
        image_type.value,
        vision_ms,
        pipeline_wall_ms,
        result.timing_ms.get("pipeline_body_ms"),
        result.timing_ms.get("encode_ms"),
        round(result.size_kb, 2),
        v.ok,
    )
    status = 200 if v.ok else 422
    return JSONResponse(content=body, status_code=status)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
