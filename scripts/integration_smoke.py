from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import requests

CASES = [
    ("product", "keep"),
    ("category", "keep"),
    ("banner", "keep"),
    ("portfolio_interior", "keep"),
]


def _furniture_min_png_bytes() -> bytes:
    from PIL import Image

    buf = BytesIO()
    # Long edge = minimum for furniture_portfolio (see FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX)
    Image.new("RGB", (1200, 900), (50, 55, 60)).save(buf, format="PNG")
    return buf.getvalue()


def run_case(
    base_url: str,
    *,
    filename: str,
    raw: bytes,
    mime: str,
    image_type: str,
    background: str,
    extra_form: dict | None = None,
) -> dict:
    data: dict = {"type": image_type, "background": background, "format": "webp"}
    if extra_form:
        data.update(extra_form)
    resp = requests.post(
        f"{base_url.rstrip('/')}/process-image",
        files={"image": (filename, raw, mime)},
        data=data,
        timeout=180,
    )
    payload: dict = {}
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text[:400]}
    return {"status": resp.status_code, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Integration smoke (4 base types; optional furniture_portfolio)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True, help="Path to image for product/category/banner/portfolio calls")
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
    parser.add_argument(
        "--include-furniture",
        action="store_true",
        help="Also POST furniture_portfolio with synthetic 1600x900 PNG and vision_provider=fallback",
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

    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    with image_path.open("rb") as f:
        user_bytes = f.read()

    results: dict[str, dict] = {}
    failures = 0
    for image_type, background in CASES:
        key = f"{image_type}:{background}"
        results[key] = run_case(
            base,
            filename=image_path.name,
            raw=user_bytes,
            mime=mime,
            image_type=image_type,
            background=background,
        )
        st = results[key]["status"]
        if st != 200:
            failures += 1
        pay = results[key].get("payload") or {}
        vok = pay.get("validation_ok")
        print(f"{key}: HTTP {st}, validation_ok={vok}")

    if args.include_furniture:
        key = "furniture_portfolio:meeting_room+site"
        png = _furniture_min_png_bytes()
        results[key] = run_case(
            base,
            filename="smoke_furniture_min.png",
            raw=png,
            mime="image/png",
            image_type="furniture_portfolio",
            background="keep",
            extra_form={
                "furniture_scene": "meeting_room",
                "output_target": "site",
                "vision_provider": "fallback",
            },
        )
        st = results[key]["status"]
        if st != 200:
            failures += 1
        pay = results[key].get("payload") or {}
        vok = pay.get("validation_ok")
        print(f"{key}: HTTP {st}, validation_ok={vok}")

    print(json.dumps(results, ensure_ascii=False, indent=2))

    total = len(CASES) + (1 if args.include_furniture else 0)
    if args.strict and failures:
        raise SystemExit(f"smoke failed: {failures}/{total} cases not HTTP 200")


if __name__ == "__main__":
    main()
