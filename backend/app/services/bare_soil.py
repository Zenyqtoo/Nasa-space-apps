"""«Часы голой почвы»: месяц за месяцем — доля дней, когда на поле одновременно открытая почва,
эрозионный ветер и сухой верхний слой почвы.

Сейчас это КАРКАС: заполняются только годы, месяцы и число дней в месяце. Остальные числа — ``None``,
состояние месяца — ``missing``, итоговый статус — ``missing``. Расчёт по данным (MODIS, POWER, SMAP) — в задаче 4.
Каркас не ходит в сеть и не запускает фоновых загрузок: источники только описываются, а их ``origin``
определяется по демо-данным и кэшу (``read_cached``).

Форма ответа — docs/contracts/bare_soil.example.json; менять можно только добавлением необязательных полей.
"""
from __future__ import annotations

import calendar
from datetime import date

from ..data_sources.registry import SOURCES
from ..geometry import parse_field
from ..schemas import BareSoilOut
from .analysis import MODIS_START, POWER_START, SMAP_START
from .monitoring import source_meta

#: MOD13Q1 начинается 18.02.2000, поэтому 2000 год неполный; расчёт — с 2001 года.
MIN_YEAR = 2001
#: SMAP SPL3SMP_E доступен с 2015 года — разумное начало периода по умолчанию.
DEFAULT_START_YEAR = 2015

#: определение показателя; казахский текст требует вычитки носителем языка (как и весь интерфейс на kk)
DEFINITION = {
    "exposure": {
        "ru": "Доля дней месяца, когда одновременно: почва открыта, ветер эрозионный и верхний слой сухой.",
        "kk": "Айдағы күндердің үлесі: топырақ ашық, жел эрозиялық және беткі қабат құрғақ.",
        "en": "Share of days in the month that are bare AND have erosive wind AND dry topsoil on the same day.",
    }
}


def resolve_period(start_year: int | None, end_year: int | None, today: date | None = None) -> tuple[int, int]:
    """Период по умолчанию 2015…текущий год; допустимо MIN_YEAR…текущий год, иначе ``ValueError`` (422)."""
    current = (today or date.today()).year
    start = DEFAULT_START_YEAR if start_year is None else start_year
    end = current if end_year is None else end_year
    for name, v in (("start_year", start), ("end_year", end)):
        if not MIN_YEAR <= v <= current:
            raise ValueError(f"{name} must be in {MIN_YEAR}..{current}")
    if start > end:
        raise ValueError("start_year must not exceed end_year")
    return start, end


def month_grid(start_year: int, end_year: int) -> list[dict]:
    """Все 12 месяцев каждого года периода; числа ещё не посчитаны."""
    return [
        {
            "year": y,
            "months": [
                {
                    "month": m,
                    "state": "missing",
                    "bare_days": None,
                    "erosive_wind_days": None,
                    "dry_days": None,
                    "joint_days": None,
                    "days_in_month": calendar.monthrange(y, m)[1],
                    "exposure": None,
                    "moisture_source": None,
                    "quality": "missing",
                }
                for m in range(1, 13)
            ],
        }
        for y in range(start_year, end_year + 1)
    ]


def _sources(geometry: dict) -> list[dict]:
    """Источники расчёта с их текущим происхождением данных (демо / кэш / нет), без сетевых запросов."""
    field = parse_field(geometry)
    today = date.today()
    out = []
    for sid, start in (("power", POWER_START), ("modis", MODIS_START), ("smap", SMAP_START)):
        hit = SOURCES[sid].read_cached(field, start, today)
        out.append(source_meta(sid, hit.origin if hit else None))
    return out


def bare_soil(field_id: int, geometry: dict, start_year: int | None, end_year: int | None) -> dict:
    start, end = resolve_period(start_year, end_year)
    body = {
        "field_id": field_id,
        "period": {"start_year": start, "end_year": end},
        "status": "missing",
        "jobs": [],
        "headline": {"top_months": [], "max_median_exposure": None},
        "definition": DEFINITION,
        "thresholds": [],
        "years": month_grid(start, end),
        "climatology": [],
        "cover_crop_windows": [],
        "sources": _sources(geometry),
        "warnings": [{"code": "bare_soil_not_computed", "source": "bare_soil", "params": {}}],
    }
    return BareSoilOut.model_validate(body).model_dump(mode="json")
