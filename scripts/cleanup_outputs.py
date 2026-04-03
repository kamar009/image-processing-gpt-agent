from __future__ import annotations

import argparse
import time
from pathlib import Path


def cleanup_outputs(dir_path: Path, max_age_hours: float, dry_run: bool) -> tuple[int, int]:
    now = time.time()
    deleted = 0
    kept = 0
    for p in dir_path.glob("*"):
        if not p.is_file():
            continue
        age_hours = (now - p.stat().st_mtime) / 3600.0
        if age_hours > max_age_hours:
            if dry_run:
                print(f"[dry-run] delete {p.name} (age={age_hours:.1f}h)")
            else:
                p.unlink(missing_ok=True)
                print(f"deleted {p.name} (age={age_hours:.1f}h)")
            deleted += 1
        else:
            kept += 1
    return deleted, kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup old files in outputs/")
    parser.add_argument("--dir", default="outputs", help="Outputs directory")
    parser.add_argument("--max-age-hours", type=float, default=72.0, help="Delete files older than this")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted")
    args = parser.parse_args()

    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    deleted, kept = cleanup_outputs(out, args.max_age_hours, args.dry_run)
    print(f"done: deleted={deleted}, kept={kept}, dir={out.resolve()}")


if __name__ == "__main__":
    main()
