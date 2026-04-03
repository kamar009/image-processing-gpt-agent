from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

TYPES = ["product", "category", "banner", "portfolio_interior"]

# Расширенный набор образцов skimage (первые N при запуске по умолчанию)
DEFAULT_SAMPLE_NAMES = [
    "astronaut.png",
    "coffee.png",
    "camera.png",
    "chelsea.png",
    "coins.png",
    "brick.png",
    "grass.png",
    "gravel.png",
    "cell.png",
    "horse.png",
    "moon.png",
    "color.png",
]

IMAGE_GLOB = ("*.png", "*.jpg", "*.jpeg", "*.webp")


def _default_skimage_dir() -> Path | None:
    try:
        import skimage.data as skd  # type: ignore[import-untyped]

        return Path(skd.__file__).resolve().parent
    except Exception:
        return None


def _collect_images(image_dir: Path, names: list[str] | None, max_count: int) -> list[Path]:
    paths: list[Path] = []
    if names:
        for n in names:
            p = image_dir / n
            if p.is_file():
                paths.append(p)
            else:
                print(f"warning: missing {p}", file=sys.stderr)
    else:
        for pattern in IMAGE_GLOB:
            paths.extend(sorted(image_dir.glob(pattern)))
        paths = sorted({p.resolve() for p in paths}, key=lambda x: x.name.lower())
    return paths[:max_count]


def run(base_url: str, files: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for i, path in enumerate(files):
        image_type = TYPES[i % len(TYPES)]
        with path.open("rb") as f:
            r = requests.post(
                f"{base_url.rstrip('/')}/process-image",
                files={"image": (path.name, f, "application/octet-stream")},
                data={"type": image_type, "background": "keep", "format": "webp"},
                timeout=180,
            )
        item: dict = {"image": path.name, "type": image_type, "status": r.status_code}
        try:
            d = r.json()
            item.update(
                {
                    "file_id": d.get("file_id"),
                    "width": d.get("width"),
                    "height": d.get("height"),
                    "size_kb": d.get("size_kb"),
                    "validation_ok": d.get("validation_ok"),
                    "warnings": d.get("validation_warnings") or [],
                    "errors": d.get("validation_errors") or [],
                }
            )
        except Exception:
            item["raw"] = r.text[:300]
        rows.append(item)
    return rows


def write_reports(rows: list[dict], meta: dict) -> None:
    out = Path("reports")
    out.mkdir(exist_ok=True)
    payload = {"meta": meta, "rows": rows}
    (out / "real_batch_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Real batch report",
        "",
        f"_Generated: {meta.get('source', 'unknown')}, count={len(rows)}_",
        "",
        "| image | type | status | dims | size_kb | validation_ok | warnings |",
        "|---|---|---:|---|---:|---|---|",
    ]
    for x in rows:
        dims = f"{x.get('width')}x{x.get('height')}" if x.get("width") else "-"
        warns = "; ".join(x.get("warnings", [])) if x.get("warnings") else ""
        lines.append(
            f"| {x['image']} | {x['type']} | {x['status']} | {dims} | {x.get('size_kb','-')} | {x.get('validation_ok','-')} | {warns} |"
        )
    (out / "real_batch_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch POST /process-image and write reports/")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=None,
        help="Directory with images (default: skimage.data folder if available)",
    )
    parser.add_argument(
        "--image",
        action="append",
        dest="images",
        help="Concrete filename inside --image-dir (repeatable)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=12,
        help="Max number of images to process (default 12)",
    )
    parser.add_argument(
        "--all-in-dir",
        action="store_true",
        help="Take first --count images from directory via glob (default: built-in skimage sample names)",
    )
    args = parser.parse_args()

    img_dir = args.image_dir
    if img_dir is None:
        img_dir = _default_skimage_dir()
    if img_dir is None:
        raise SystemExit("No --image-dir and skimage not installed; exit")
    img_dir = img_dir.resolve()
    if not img_dir.is_dir():
        raise SystemExit(f"Not a directory: {img_dir}")

    if args.images:
        files = _collect_images(img_dir, args.images, args.count)
    elif args.all_in_dir:
        files = _collect_images(img_dir, None, args.count)
    else:
        names = DEFAULT_SAMPLE_NAMES[: max(1, args.count)]
        files = _collect_images(img_dir, names, len(names))

    if not files:
        raise SystemExit(f"No images found in {img_dir}")

    rows = run(args.base_url, files)
    meta = {
        "source": str(img_dir),
        "base_url": args.base_url,
        "count": len(rows),
    }
    write_reports(rows, meta)
    print(f"saved reports/real_batch_report.md and reports/real_batch_report.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
