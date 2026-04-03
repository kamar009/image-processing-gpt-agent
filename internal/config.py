from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class InternalConfig:
    enabled: bool
    db_path: str
    admin_ids: set[int]
    telegram_bot_token: str
    worker_poll_seconds: float
    max_concurrent_jobs_per_user: int


def load_internal_config() -> InternalConfig:
    admin_raw = os.environ.get("INTERNAL_ADMIN_IDS", "")
    admin_ids: set[int] = set()
    for part in admin_raw.split(","):
        part = part.strip()
        if part.isdigit():
            admin_ids.add(int(part))
    try:
        max_jobs = int(os.environ.get("INTERNAL_MAX_CONCURRENT_JOBS_PER_USER", "3"))
    except ValueError:
        max_jobs = 3
    max_jobs = max(1, min(max_jobs, 20))
    return InternalConfig(
        enabled=os.environ.get("INTERNAL_MODE", "0").lower() in ("1", "true", "yes"),
        db_path=os.environ.get("INTERNAL_DB_PATH", "./outputs/internal.db"),
        admin_ids=admin_ids,
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        worker_poll_seconds=float(os.environ.get("WORKER_POLL_SECONDS", "3")),
        max_concurrent_jobs_per_user=max_jobs,
    )
