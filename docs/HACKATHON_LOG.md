# Журнал хакатона NASA Space Apps 2026 — «Агро-Севооборот»

Задача: Field Shift: Adapting Farms with NASA Data. Соревновательные дни: 14–15 ноября 2026.
Каждый коммит, сделанный в эти дни, начинается с `[hackathon]` — по ним можно отделить новое от прежнего.

## Что существовало до хакатона (по README.md)

| Область | Что было |
|---|---|
| Аккаунты и поля | регистрация, вход, демо-песочница `/demo`; поля на карте (рисование, GeoJSON/KML), история культур, почвенное обследование; изоляция по владельцу (чужое поле → 404) |
| Данные по полю | NASA POWER (климат), MODIS NDVI, SMAP (влажность почвы, нужен Earthdata), SoilGrids (почва); файловый кэш, демо-данные в `data/demo`, `OFFLINE=1` |
| Мониторинг и риски | помесячный климат и аномалии, NDVI, влажность SMAP, история сезонов, риски сезона, пригодность культур, слои карты |
| Планировщик | сравнение 2–4 севооборотов по почве, воде, доходу и риску на 3–5 лет, экономика, стресс-тест засухой, объяснения по шаблонам |
| Отчёты | PDF и XLSX на ru/kk/en |
| Качество | 109 тестов, аудит модели (`docs/MODEL_AUDIT.md`, `docs/audit/PARAMETERS.md`), все параметры модели в `backend/app/rules/*.yaml` |
| Демо без сети | `/demo` с двумя реальными полями (Шортанды, Костанай), `make offline-check` |

## Built during the hackathon (14–15 Nov 2026)

| Задача | Что сделано | Файлы | Коммит |
|---|---|---|---|
| 1. Проверка проекта | `make test` (109), `lint`, `build`, `offline-check` проходят; живой запрос для точки 52.3/68.5: POWER, SoilGrids — OK, MODIS — медленно, SMAP — не проверен (в контейнере нет токена и закрыт `urs.earthdata.nasa.gov`) | `docs/HACKATHON_LOG.md`, `docs/contracts/bare_soil.example.json` | ветка `hackathon/task1-log-and-contract` |
| 2. Каркас `/bare-soil` | эндпоинт по контракту, проверка владельца, период 2001…текущий год; числа пока `null`, `status: missing` | `backend/app/schemas.py`, `services/bare_soil.py`, `api/accounts.py`, `tests/test_bare_soil.py`, `docs/contracts/README.md`, `README.md` | ветка `hackathon/task2-bare-soil-endpoint` |
