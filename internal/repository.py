from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from internal.preset_seed import apply_preset_seed


@dataclass(frozen=True)
class InternalUser:
    id: str
    telegram_id: int
    username: str | None
    full_name: str | None
    role: str


class InternalRepository:
    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("select 1").fetchone()
            return True
        except OSError:
            return False
        except sqlite3.Error:
            return False

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists users (
                  id text primary key,
                  telegram_id integer unique not null,
                  username text,
                  full_name text,
                  role text not null default 'user',
                  created_at text not null default current_timestamp
                );
                create table if not exists allowed_users (
                  telegram_id integer primary key,
                  comment text,
                  created_at text not null default current_timestamp
                );
                create table if not exists generation_presets (
                  key text primary key,
                  title text not null,
                  image_type text not null,
                  style text not null default 'neutral',
                  enabled integer not null default 1
                );
                create table if not exists generation_jobs (
                  id text primary key,
                  user_id text not null,
                  preset_key text not null,
                  status text not null,
                  input_file_id text not null,
                  output_file_id text,
                  error_message text,
                  created_at text not null default current_timestamp,
                  started_at text,
                  finished_at text
                );
                """
            )
            apply_preset_seed(conn)

    def allow_user(self, telegram_id: int, comment: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "insert or ignore into allowed_users(telegram_id, comment) values(?, ?)",
                (telegram_id, comment),
            )

    def is_allowed(self, telegram_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "select 1 from allowed_users where telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            return row is not None

    def upsert_user(self, telegram_id: int, username: str | None, full_name: str | None, role: str = "user") -> InternalUser:
        with self._connect() as conn:
            row = conn.execute(
                "select id, role from users where telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            user_id = row["id"] if row else str(uuid.uuid4())
            user_role = role if not row else row["role"]
            conn.execute(
                """
                insert into users(id, telegram_id, username, full_name, role)
                values(?,?,?,?,?)
                on conflict(telegram_id) do update set
                  username=excluded.username,
                  full_name=excluded.full_name
                """,
                (user_id, telegram_id, username, full_name, user_role),
            )
            return InternalUser(id=user_id, telegram_id=telegram_id, username=username, full_name=full_name, role=user_role)

    def list_presets(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select key, title, image_type, style from generation_presets where enabled = 1 order by title"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_preset_row(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select key, title, image_type, style from generation_presets where key = ? and enabled = 1",
                (key,),
            ).fetchone()
            return dict(row) if row else None

    def count_active_jobs_for_user(self, user_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                select count(*) as c from generation_jobs
                where user_id = ? and status in ('queued', 'processing')
                """,
                (user_id,),
            ).fetchone()
            return int(row["c"]) if row else 0

    def list_jobs_for_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                select * from generation_jobs
                where user_id = ?
                order by created_at desc
                limit ?
                """,
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_job(self, user_id: str, preset_key: str, input_file_id: str) -> str:
        job_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                insert into generation_jobs(id, user_id, preset_key, status, input_file_id)
                values(?, ?, ?, 'queued', ?)
                """,
                (job_id, user_id, preset_key, input_file_id),
            )
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from generation_jobs where id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def pop_queued_job(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "select * from generation_jobs where status = 'queued' order by created_at asc limit 1"
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "update generation_jobs set status='processing', started_at=current_timestamp where id = ?",
                (row["id"],),
            )
            row = conn.execute("select * from generation_jobs where id = ?", (row["id"],)).fetchone()
            return dict(row) if row else None

    def mark_job_done(self, job_id: str, output_file_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update generation_jobs
                set status='done', output_file_id=?, finished_at=current_timestamp, error_message=null
                where id=?
                """,
                (output_file_id, job_id),
            )

    def mark_job_failed(self, job_id: str, error_message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update generation_jobs
                set status='failed', error_message=?, finished_at=current_timestamp
                where id=?
                """,
                (error_message[:500], job_id),
            )
