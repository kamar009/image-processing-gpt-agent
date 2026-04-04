from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt


def create_access_token(
    *,
    secret: str,
    user_id: str,
    telegram_id: int,
    role: str,
    exp_hours: int,
) -> str:
    if not secret:
        raise ValueError("jwt secret required")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tid": telegram_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=max(1, min(exp_hours, 24 * 30))),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(secret: str, token: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"])
