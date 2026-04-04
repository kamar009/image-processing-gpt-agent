"""Проверка доступности API после деплоя (чеклист приёмки).

Использование:
  set BASE_URL=https://api.example.com
  python scripts/acceptance_remote_smoke.py

Опционально с заголовком Authorization для проверки /internal/presets:
  set INTERNAL_BEARER=eyJ...
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "").rstrip("/"), help="Например https://api.example.com")
    args = parser.parse_args()
    base = (args.base_url or "").rstrip("/")
    if not base:
        print("Задайте --base-url или переменную окружения BASE_URL")
        return 2

    bearer = os.environ.get("INTERNAL_BEARER", "").strip()

    def get(path: str, need_internal: bool = False) -> tuple[int, str]:
        req = urllib.request.Request(f"{base}{path}", method="GET")
        if need_internal and bearer:
            req.add_header("Authorization", f"Bearer {bearer}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, (resp.read(512) or b"").decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, (e.read(512) or b"").decode("utf-8", errors="replace")
        except Exception as exc:
            return -1, str(exc)

    ok = True
    print(f"BASE_URL={base}")

    for path, label in (("/health", "GET /health"), ("/internal/health", "GET /internal/health")):
        code, body = get(path)
        if code == 200:
            print(f"OK  {label}")
        else:
            print(f"FAIL {label} -> {code} {body[:200]}")
            ok = False

    if bearer:
        code, body = get("/internal/presets", need_internal=True)
        if code == 200:
            print("OK  GET /internal/presets (с Bearer)")
        else:
            print(f"FAIL GET /internal/presets -> {code} {body[:200]}")
            ok = False
    else:
        print("SKIP GET /internal/presets (задайте INTERNAL_BEARER для проверки с токеном)")

    if ok:
        print("Итог: базовые проверки пройдены. Дополнительно вручную: DEPLOYMENT_CHECKLIST, INTERNAL_MVP_CHECKLIST.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
