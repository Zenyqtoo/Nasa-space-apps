#!/usr/bin/env python
"""Собирает данные демо-поля в data/demo/ — после этого демо работает без интернета.

Что сохраняется:
    field.json      контур, область, история (демо-сценарий), приоритет
    power.json      NASA POWER, суточный ряд с 1981 г.
    modis.json      MODIS MOD13Q1: ряд NDVI по полю и пиксельные растры
    soilgrids.json  ISRIC SoilGrids: почва по слоям до 1 м
    smap.json       SMAP SPL3SMP_E: влажность почвы в апреле–мае (нужен EARTHDATA_TOKEN)

Запуск (нужен интернет):
    cd backend && .venv/bin/python ../scripts/build_demo.py [--only power,modis,soilgrids,smap]

Если какой-то источник недоступен, уже сохранённый файл не трогается.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings
from app.data_sources.registry import SOURCES
from app.geometry import parse_field
from app.services.analysis import MODIS_START, POWER_START, SMAP_START

# Демо-поле: два смежных участка пашни в Шортандинском районе Акмолинской области,
# между полевой дорогой (север) и ручьём (юг), ~9 км западнее п. Шортанды.
# Контур снят вручную по спутниковому снимку Esri World Imagery (следы уборки, границы полей),
# с отступом ~30 м внутрь от видимых границ. Это НЕ кадастровая граница.
DEMO_FIELD = {
    "id": "demo-akmola-shortandy",
    "name": {"ru": "Демо-поле, Шортандинский район", "kk": "Демо-егістік, Шортанды ауданы"},
    "region": "akmola",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [70.9186, 51.6916],
                [70.9465, 51.6935],
                [70.9475, 51.6808],
                [70.9300, 51.6781],
                [70.9138, 51.6802],
                [70.9186, 51.6916],
            ]
        ],
    },
    # Демо-СЦЕНАРИЙ из постановки задачи: «пшеница 10 лет подряд».
    # Фактическая история культур на этом поле нам неизвестна и не подтверждена.
    "history": [{"year": y, "crop": "wheat"} for y in range(2022, 2027)],
    "history_is_scenario": True,
    "history_note": {
        "ru": "История культур — учебный сценарий «пшеница много лет подряд». Что на самом деле сеяли на этом поле, не проверялось.",
        "kk": "Дақылдар тарихы — «қатарынан көп жыл бидай» оқу сценарийі. Бұл егістікке іс жүзінде не себілгені тексерілмеген.",
    },
    "priority": "max_income",
    "horizon_years": 4,
    "contour_source": "Esri World Imagery, ручная оцифровка 12.11.2026",
}

PERIODS = {"power": POWER_START, "soilgrids": POWER_START, "modis": MODIS_START, "smap": SMAP_START}


def progress_printer(name: str):
    def cb(done: int, total: int) -> None:
        if done == total or done % 10 == 0:
            print(f"  {name}: {done}/{total}", flush=True)

    return cb


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="power,soilgrids,modis,smap")
    args = parser.parse_args()
    wanted = [s.strip() for s in args.only.split(",") if s.strip()]

    settings = get_settings()
    demo_dir = settings.demo_dir
    demo_dir.mkdir(parents=True, exist_ok=True)
    field = parse_field(DEMO_FIELD["geometry"])
    record = {
        **DEMO_FIELD,
        "area_ha": round(field.area_ha, 1),
        "centroid": {"lat": round(field.centroid_lat, 5), "lon": round(field.centroid_lon, 5)},
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (demo_dir / "field.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Демо-поле: {record['area_ha']} га, центр {record['centroid']}")

    today = date.today()
    failed = []
    for sid in wanted:
        src = SOURCES[sid]
        if not src.enabled:
            print(f"{sid}: пропущен — источник не настроен (для SMAP нужен EARTHDATA_TOKEN)")
            failed.append(sid)
            continue
        print(f"{sid}: загрузка…", flush=True)
        try:
            # _fetch_live, а не fetch: нужны свежие данные, а не уже сохранённое демо
            data = await src._fetch_live(field, PERIODS[sid], today, progress_printer(sid))
        except Exception as exc:  # noqa: BLE001
            print(f"{sid}: НЕ УДАЛОСЬ ({type(exc).__name__}: {str(exc)[:160]}); прежний файл оставлен как есть")
            failed.append(sid)
            continue
        data.pop("partial", None)
        out = {"cached_at": datetime.now(UTC).isoformat(timespec="seconds"), "demo": True, **data}
        path = demo_dir / f"{sid}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{sid}: сохранено {path.name}, {path.stat().st_size / 1024:.0f} КБ")
    if failed:
        print("Не обновлены:", ", ".join(failed))
        sys.exit(1)
    print("Готово: демо-данные собраны.")


if __name__ == "__main__":
    asyncio.run(main())
