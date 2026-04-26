from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizedBox(BaseModel):
    """All values in 0–1 relative to image width/height."""

    model_config = ConfigDict(extra="ignore")

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class SafeAreaNormalized(BaseModel):
    """Rectangle for banner text; values 0–1 (left, top, right, bottom as fractions)."""

    model_config = ConfigDict(extra="ignore")

    left: float = Field(ge=0, le=1)
    top: float = Field(ge=0, le=1)
    right: float = Field(ge=0, le=1)
    bottom: float = Field(ge=0, le=1)


class VisionAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_description: str = ""
    fallback_code: str = ""
    fallback_message: str = ""
    focal_center_x: float = Field(default=0.5, ge=0, le=1)
    focal_center_y: float = Field(default=0.5, ge=0, le=1)
    suggested_crop: NormalizedBox | None = None
    safe_area: SafeAreaNormalized | None = None
    preserve_realistic_colors: bool = True
    avoid_heavy_saturation: bool = True
    vertical_lines_need_correction: bool = False
    perspective_strength: Literal["none", "light", "moderate"] = "light"
    notes_for_crop: str = ""
    content_tight_box: NormalizedBox | None = None

    @field_validator("perspective_strength", mode="before")
    @classmethod
    def _coerce_perspective(cls, v: object):
        ok = ("none", "light", "moderate")
        if isinstance(v, str) and v in ok:
            return v
        return "light"
