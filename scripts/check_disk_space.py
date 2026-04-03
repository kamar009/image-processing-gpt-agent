from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Check disk usage for output storage")
    parser.add_argument("--path", default="outputs", help="Path on target volume")
    parser.add_argument("--warn-usage-pct", type=float, default=85.0)
    parser.add_argument("--critical-usage-pct", type=float, default=95.0)
    args = parser.parse_args()

    p = Path(args.path)
    if not p.exists():
        raise SystemExit(f"path does not exist: {p}")

    usage = shutil.disk_usage(p)
    used_pct = (usage.used / usage.total) * 100.0
    free_gb = usage.free / (1024**3)

    msg = f"disk usage {used_pct:.1f}% free={free_gb:.2f}GB path={p.resolve()}"
    if used_pct >= args.critical_usage_pct:
        print(f"CRITICAL: {msg}")
        raise SystemExit(2)
    if used_pct >= args.warn_usage_pct:
        print(f"WARNING: {msg}")
        raise SystemExit(1)
    print(f"OK: {msg}")


if __name__ == "__main__":
    main()
