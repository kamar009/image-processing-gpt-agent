from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from internal.preset_seed import GENERATION_PRESET_ROWS
from internal.repository import InternalRepository


def _missing_keys(db_path: Path) -> list[str]:
    if not db_path.is_file():
        return [row[0] for row in GENERATION_PRESET_ROWS]
    conn = sqlite3.connect(db_path)
    try:
        try:
            existing = {r[0] for r in conn.execute("select key from generation_presets")}
        except sqlite3.OperationalError:
            return [row[0] for row in GENERATION_PRESET_ROWS]
        return [row[0] for row in GENERATION_PRESET_ROWS if row[0] not in existing]
    finally:
        conn.close()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Ensure bundled generation_presets rows exist (insert missing keys). "
        "Uses the same schema init as the API/worker.",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("INTERNAL_DB_PATH", "./outputs/internal.db"),
        help="Path to internal SQLite DB (default: INTERNAL_DB_PATH or ./outputs/internal.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list preset keys that are missing; do not write",
    )
    args = parser.parse_args()
    db_path = Path(args.db)

    if args.dry_run:
        missing = _missing_keys(db_path)
        if not missing:
            print("No missing presets.")
            return 0
        print(f"Would insert {len(missing)} preset(s):")
        titles = {row[0]: row[1] for row in GENERATION_PRESET_ROWS}
        for key in missing:
            print(f"  + {key} — {titles.get(key, '')}")
        return 0

    before = set(_missing_keys(db_path))
    InternalRepository(str(db_path))
    after = set(_missing_keys(db_path))
    added = sorted(before - after)
    if added:
        print(f"Added preset key(s): {', '.join(added)}")
    else:
        print("generation_presets already contained all bundled keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
