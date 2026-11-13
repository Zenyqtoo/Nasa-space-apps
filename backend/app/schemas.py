"""Схемы запросов API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Lang = Literal["ru", "kk", "en"]


class HistoryItem(BaseModel):
    year: int = Field(ge=1990, le=2100)
    crop: str


class VariantIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: dict[str, str] | None = None
    crops: list[str] = Field(min_length=1, max_length=5)
    custom: bool = False


class FieldRequest(BaseModel):
    geometry: dict[str, Any]
    region: str
    history: list[HistoryItem] = Field(default_factory=list, max_length=10)
    priority: str = "max_income"
    horizon_years: int = Field(default=4, ge=3, le=5)

    @field_validator("history")
    @classmethod
    def unique_years(cls, v: list[HistoryItem]) -> list[HistoryItem]:
        years = [h.year for h in v]
        if len(set(years)) != len(years):
            raise ValueError("history contains duplicate years")
        return v

    def history_crops(self) -> list[str]:
        """Культуры по возрастанию года; последняя — предшественник первого года плана."""
        return [h.crop for h in sorted(self.history, key=lambda h: h.year)]


class CompareRequest(FieldRequest):
    variants: list[VariantIn] | None = Field(default=None, max_length=6)
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    #: веса оценок {soil, water, income, risk}, заданные фермером; нормируются к сумме 1
    weights: dict[str, float] | None = None
    #: исторический засушливый год для стресс-теста (должен быть засушливым по данным поля)
    stress_year: int | None = Field(default=None, ge=1981, le=2100)


class ReportRequest(CompareRequest):
    lang: Lang = "ru"
    selected_variant_id: str | None = None
    farm_name: str = Field(default="", max_length=120)
    stress_year_index: int | None = Field(default=None, ge=1, le=5)


class RetroSubmission(BaseModel):
    farm_name: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=3, max_length=160)
    region: str
    geometry: dict[str, Any] | None = None
    history: list[HistoryItem] = Field(min_length=2, max_length=30)
    evidence: str = Field(default="", max_length=2000)
    consent: bool


# ---------------------------------------------------------------- учётные записи и поля
class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    name: str = Field(default="", max_length=120)
    farm_name: str = Field(default="", max_length=160)
    lang: Lang = "ru"


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


class ProfileIn(BaseModel):
    name: str = Field(default="", max_length=120)
    farm_name: str = Field(default="", max_length=160)
    lang: Lang = "ru"


class SoilInfo(BaseModel):
    """Сведения о почве, которые вносит фермер (например, из агрохимического обследования)."""

    humus_pct: float | None = Field(default=None, ge=0, le=20)
    ph: float | None = Field(default=None, ge=3, le=11)
    texture: Literal["sand", "sandy_loam", "loam", "clay_loam", "clay"] | None = None
    soil_type: str = Field(default="", max_length=120)
    survey_year: int | None = Field(default=None, ge=1950, le=2100)
    notes: str = Field(default="", max_length=1000)


class FieldIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    region: str
    geometry: dict[str, Any]
    history: list[HistoryItem] = Field(default_factory=list, max_length=10)
    history_is_scenario: bool = False
    soil: SoilInfo = Field(default_factory=SoilInfo)
    notes: str = Field(default="", max_length=4000)

    @field_validator("history")
    @classmethod
    def unique_years(cls, v: list[HistoryItem]) -> list[HistoryItem]:
        years = [h.year for h in v]
        if len(set(years)) != len(years):
            raise ValueError("history contains duplicate years")
        return sorted(v, key=lambda h: h.year)


class AnalysisIn(BaseModel):
    title: str = Field(default="", max_length=120)
    priority: str = "max_income"
    weights: dict[str, float] | None = None
    horizon_years: int = Field(default=4, ge=3, le=5)
    variants: list[VariantIn] | None = Field(default=None, max_length=6)
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    stress_year: int | None = Field(default=None, ge=1981, le=2100)
