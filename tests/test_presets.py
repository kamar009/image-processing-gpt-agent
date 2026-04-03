from presets.definitions import ImageType, get_preset


def test_preset_dimensions_and_limits():
    p = get_preset(ImageType.product)
    assert p.width == 800 and p.height == 800 and p.max_kb == 150
    c = get_preset(ImageType.category)
    assert c.width == 1200 and c.height == 800 and c.max_kb == 250
    b = get_preset(ImageType.banner)
    assert b.width == 1920 and b.height == 900 and b.max_kb == 400
    assert b.safe_area is not None
    i = get_preset(ImageType.portfolio_interior)
    assert i.width == 1600 and i.height == 900 and i.max_kb == 350
