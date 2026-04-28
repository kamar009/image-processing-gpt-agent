import pytest

from presets.definitions import (
    FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX,
    FurniturePortfolioOutputTarget,
    ImageType,
    get_preset,
)


def test_preset_dimensions_and_limits():
    p = get_preset(ImageType.product)
    assert p.width == 800 and p.height == 800 and p.max_kb == 200
    c = get_preset(ImageType.category)
    assert c.width == 1200 and c.height == 800 and c.max_kb == 250
    b = get_preset(ImageType.banner)
    assert b.width == 1920 and b.height == 900 and b.max_kb == 400
    assert b.safe_area is not None
    i = get_preset(ImageType.portfolio_interior)
    assert i.width == 1600 and i.height == 900 and i.max_kb == 350


@pytest.mark.parametrize(
    ("target", "exp_w", "exp_h", "exp_kb"),
    [
        (FurniturePortfolioOutputTarget.site, 1600, 900, 400),
        (FurniturePortfolioOutputTarget.banner, 1920, 900, 450),
        (FurniturePortfolioOutputTarget.social_vk, 1080, 1080, 350),
        (FurniturePortfolioOutputTarget.social_telegram, 1280, 720, 300),
        (FurniturePortfolioOutputTarget.social_max, 1080, 1350, 350),
    ],
)
def test_furniture_portfolio_preset_matrix(target, exp_w, exp_h, exp_kb):
    p = get_preset(ImageType.furniture_portfolio, furniture_output_target=target)
    assert p.width == exp_w and p.height == exp_h and p.max_kb == exp_kb
    assert p.default_background.value == "keep"
    assert p.default_format.value == "webp"
    assert p.safe_area is None


def test_get_preset_furniture_requires_output_target():
    with pytest.raises(ValueError, match="furniture_output_target is required"):
        get_preset(ImageType.furniture_portfolio)


def test_get_preset_rejects_furniture_target_for_other_types():
    with pytest.raises(ValueError, match="only valid for image_type=furniture_portfolio"):
        get_preset(ImageType.product, furniture_output_target=FurniturePortfolioOutputTarget.site)


def test_furniture_portfolio_min_input_long_side_constant():
    assert FURNITURE_PORTFOLIO_MIN_INPUT_LONG_SIDE_PX == 1200
