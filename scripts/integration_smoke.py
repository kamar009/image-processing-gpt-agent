from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

CASES = [
    ("product", "keep"),
    ("category", "keep"),
    ("banner", "keep"),
    ("portfolio_interior", "keep"),
]


def run_case(base_url: str, image_path: Path, image_type: str, background: str) -> dict:
    with image_path.open("rb") as f:
        resp = requests.post(
            f"{base_url.rstrip('/')}/process-image",
            files={"image": (image_path.name, f, "image/png")},
            data={"type": image_type, "background": background, "format": "webp"},
            timeout=180,
        )
    payload: dict = {}
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text[:400]}
    return {"status": resp.status_code, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Integration smoke runner (4 types, one image)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True, help="Path to image for smoke calls")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any case status is not 200",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Do not call GET /health before cases",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}")

    if not args.skip_health:
        try:
            h = requests.get(f"{base}/health", timeout=10)
            if h.status_code != 200:
                print(f"warning: /health returned {h.status_code}", file=sys.stderr)
        except Exception as exc:
            print(f"warning: /health failed: {exc}", file=sys.stderr)

    results: dict[str, dict] = {}
    failures = 0
    for image_type, background in CASES:
        key = f"{image_type}:{background}"
        results[key] = run_case(base, image_path, image_type, background)
        st = results[key]["status"]
        if st != 200:
            failures += 1
        pay = results[key].get("payload") or {}
        vok = pay.get("validation_ok")
        print(f"{key}: HTTP {st}, validation_ok={vok}")

    print(json.dumps(results, ensure_ascii=False, indent=2))

    if args.strict and failures:
        raise SystemExit(f"smoke failed: {failures}/{len(CASES)} cases not HTTP 200")


if __name__ == "__main__":
    main()
