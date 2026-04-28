"""B1: отдельный system prompt для furniture_portfolio."""

from gpt_agent.analyze import _build_system_prompt
from presets.definitions import ImageType, StylePreset


def test_furniture_portfolio_prompt_lists_people_detected_and_furniture_rules():
    p = _build_system_prompt(ImageType.furniture_portfolio, StylePreset.neutral)
    assert '"people_detected": boolean' in p
    assert "people_detected" in p
    assert "office furniture" in p.lower()
    assert "geometry" in p.lower() or "hardware" in p.lower()


def test_furniture_portfolio_enhanced_prompt_includes_retoucher_goals():
    p = _build_system_prompt(
        ImageType.furniture_portfolio, StylePreset.neutral, furniture_enhanced=True
    )
    assert "ретушёр" in p or "ретушер" in p
    assert "пайплайн" in p.lower()
    assert '"people_detected": boolean' in p
    assert "office furniture" in p.lower()


def test_portfolio_interior_prompt_has_no_people_detected_field_in_schema():
    p = _build_system_prompt(ImageType.portfolio_interior, StylePreset.neutral)
    assert '"people_detected"' not in p


def test_vision_analysis_accepts_people_detected_json():
    from gpt_agent.schema import VisionAnalysis

    v = VisionAnalysis.model_validate({"scene_description": "x", "people_detected": True})
    assert v.people_detected is True
    v2 = VisionAnalysis.model_validate({"scene_description": "x"})
    assert v2.people_detected is False
