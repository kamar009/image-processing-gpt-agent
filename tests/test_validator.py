from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from presets.definitions import ImageType, OutputFormat, get_preset
from validator.checks import validate_output


def test_validate_ok_webp(tmp_path: Path):
    preset = get_preset(ImageType.product)
    p = tmp_path / "out.webp"
    im = Image.new("RGB", (preset.width, preset.height), (128, 128, 128))
    im.save(p, format="WEBP", quality=80)
    r = validate_output(p, preset, OutputFormat.webp, preset.max_kb)
    assert r.ok, r.errors


def test_validate_wrong_size(tmp_path: Path):
    preset = get_preset(ImageType.product)
    p = tmp_path / "bad.webp"
    Image.new("RGB", (100, 100), (0, 0, 0)).save(p, format="WEBP", quality=80)
    r = validate_output(p, preset, OutputFormat.webp, preset.max_kb)
    assert not r.ok
    assert any("dimensions" in e for e in r.errors)


def test_validate_near_limit_warning(tmp_path: Path):
    preset = get_preset(ImageType.product)
    p = tmp_path / "x.webp"
    arr = np.random.default_rng(42).integers(0, 256, (preset.height, preset.width, 3), dtype=np.uint8)
    Image.fromarray(arr, mode="RGB").save(p, format="WEBP", quality=88, method=6)
    kb = p.stat().st_size / 1024.0
    max_kb_ = int(kb // 0.92)
    assert kb < max_kb_ + 0.5
    assert kb >= max_kb_ * 0.92 - 1e-6

    r = validate_output(p, preset, OutputFormat.webp, max_kb_)
    assert r.ok, r.errors
    assert any("near limit" in w.lower() for w in r.warnings)
