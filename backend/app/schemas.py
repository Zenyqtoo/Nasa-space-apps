"""Схемы запросов API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Lang = Literal["ru", "kk"]


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
