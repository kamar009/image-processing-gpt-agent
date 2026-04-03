from __future__ import annotations

import logging
import time

from PIL import Image

from gpt_agent.analyze import analyze_image_for_pipeline
from image_processor.pipeline import run_pipeline
from internal.config import load_internal_config
from internal.repository import InternalRepository
from output_storage.local import OutputStorage
from presets.definitions import ImageType, StylePreset, get_preset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


def _parse_image_type(raw: str) -> ImageType:
    try:
        return ImageType(raw)
    except ValueError:
        return ImageType.product


def _parse_style(raw: str) -> StylePreset:
    try:
        return StylePreset(raw)
    except ValueError:
        return StylePreset.neutral


def _process_job(repo: InternalRepository, storage: OutputStorage, job: dict) -> None:
    job_id = str(job["id"])
    user_id = str(job.get("user_id", ""))
    preset_key = str(job.get("preset_key", ""))
    t0 = time.perf_counter()

    row = repo.get_preset_row(preset_key)
    if not row:
        repo.mark_job_failed(job_id, f"unknown preset: {preset_key}")
        logger.warning(
            "job_failed event=preset_missing job_id=%s user_id=%s preset_key=%s",
            job_id,
            user_id,
            preset_key,
        )
        return
    image_type = _parse_image_type(str(row["image_type"]))
    style = _parse_style(str(row["style"]))
    preset_cfg = get_preset(image_type)

    input_path = storage.path_for(job["input_file_id"], ".png")
    if not input_path.exists():
        repo.mark_job_failed(job_id, "input file not found")
        logger.warning(
            "job_failed event=input_missing job_id=%s user_id=%s input_file_id=%s",
            job_id,
            user_id,
            job["input_file_id"],
        )
        return
    try:
        pil = Image.open(input_path)
        pil.load()
        t_after_load = time.perf_counter()
        vision = analyze_image_for_pipeline(pil, image_type, style)
        t_after_vision = time.perf_counter()
        result = run_pipeline(
            pil,
            image_type,
            preset_cfg.default_background,
            preset_cfg.default_format,
            preset_cfg.default_crop,
            preset_cfg.default_quality,
            style,
            vision,
            preset_cfg,
        )
        ext = f".{preset_cfg.default_format.value}"
        output_file_id, output_path = storage.new_file_id(ext)
        output_path.write_bytes(result.data)
        repo.mark_job_done(job_id, output_file_id)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        vision_ms = round((t_after_vision - t_after_load) * 1000, 1)
        pipe_ms = round((time.perf_counter() - t_after_vision) * 1000, 1)
        logger.info(
            "job_done job_id=%s user_id=%s preset_key=%s image_type=%s output_file_id=%s "
            "elapsed_ms=%s vision_ms=%s pipeline_wall_ms=%s pipeline_body_ms=%s encode_ms=%s",
            job_id,
            user_id,
            preset_key,
            image_type.value,
            output_file_id,
            elapsed_ms,
            vision_ms,
            pipe_ms,
            result.timing_ms.get("pipeline_body_ms"),
            result.timing_ms.get("encode_ms"),
        )
    except Exception as exc:
        repo.mark_job_failed(job_id, str(exc))
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.exception(
            "job_failed job_id=%s user_id=%s preset_key=%s elapsed_ms=%s",
            job_id,
            user_id,
            preset_key,
            elapsed_ms,
        )


def main() -> None:
    cfg = load_internal_config()
    repo = InternalRepository(cfg.db_path)
    storage = OutputStorage()
    logger.info(
        "worker_started poll_seconds=%s db_path=%s output_dir=%s",
        cfg.worker_poll_seconds,
        cfg.db_path,
        storage.root(),
    )
    while True:
        job = repo.pop_queued_job()
        if job is None:
            time.sleep(cfg.worker_poll_seconds)
            continue
        _process_job(repo, storage, job)


if __name__ == "__main__":
    main()
