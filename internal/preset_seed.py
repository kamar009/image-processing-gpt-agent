"""Canonical list of bundled internal generation presets (SQLite generation_presets)."""

from __future__ import annotations

import sqlite3

# (key, title, image_type, style)
GENERATION_PRESET_ROWS: list[tuple[str, str, str, str]] = [
    ("promo_flyer", "Реклама и флаеры", "banner", "neutral"),
    ("staff_portrait", "Проф. фото сотрудников", "product", "neutral"),
    ("work_portfolio", "Проф. фото работ", "portfolio_interior", "neutral"),
    ("hair_style_ai", "ИИ подбор прически", "category", "creative"),
    ("catalog_showcase", "Витрина каталога", "category", "neutral"),
    ("hero_slide", "Слайд главной (герой)", "banner", "neutral"),
    ("interior_wide", "Интерьер широкий кадр", "portfolio_interior", "neutral"),
    ("product_white_bg", "Товар на белом фоне", "product", "premium"),
]


def apply_preset_seed(conn: sqlite3.Connection) -> int:
    """insert or ignore each bundled row. Returns number of rows actually inserted."""
    inserted = 0
    for row in GENERATION_PRESET_ROWS:
        cur = conn.execute(
            "insert or ignore into generation_presets(key,title,image_type,style,enabled) values(?,?,?,?,1)",
            row,
        )
        inserted += cur.rowcount
    return inserted
