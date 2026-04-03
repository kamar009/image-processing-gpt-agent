from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup internal sqlite DB file")
    parser.add_argument("--db", default="./outputs/internal.db", help="Path to sqlite DB")
    parser.add_argument("--out-dir", default="./reports/backups", help="Output backup directory")
    args = parser.parse_args()

    src = Path(args.db)
    if not src.exists():
        print(f"DB not found: {src}")
        return 1
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dst = out_dir / f"internal-{ts}.db"
    shutil.copy2(src, dst)
    print(f"Backup created: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
