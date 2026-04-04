"""Проверка переменных окружения для internal MVP (опционально --strict)."""

from __future__ import annotations

import argparse
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Считать ошибкой отсутствие JWT и OPENAI_API_KEY при INTERNAL_MODE=1",
    )
    args = parser.parse_args()

    internal = os.environ.get("INTERNAL_MODE", "").lower() in ("1", "true", "yes")
    errors: list[str] = []
    warns: list[str] = []

    if not internal:
        print("INTERNAL_MODE выключен — проверка internal пропущена.")
        return 0

    if not (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip():
        errors.append("TELEGRAM_BOT_TOKEN пуст при INTERNAL_MODE=1")

    admin = os.environ.get("INTERNAL_ADMIN_IDS", "").strip()
    if not admin:
        warns.append("INTERNAL_ADMIN_IDS пуст — добавьте хотя бы одного админа")

    jwt = os.environ.get("INTERNAL_JWT_SECRET", "").strip()
    if args.strict and len(jwt) < 32:
        errors.append("INTERNAL_JWT_SECRET должен быть не короче 32 символов (--strict)")
    elif len(jwt) > 0 and len(jwt) < 32:
        warns.append("INTERNAL_JWT_SECRET короче 32 символов (рекомендация RFC)")

    if args.strict and not (os.environ.get("OPENAI_API_KEY") or "").strip():
        errors.append("OPENAI_API_KEY пуст (--strict, worker вызывает Vision)")

    cors = os.environ.get("INTERNAL_CORS_ORIGINS", "").strip()
    if cors:
        print("INTERNAL_CORS_ORIGINS:", cors)
    for w in warns:
        print("WARN:", w)
    for e in errors:
        print("ERROR:", e)
    if errors:
        return 1
    print("OK: ключевые переменные для internal проверены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
