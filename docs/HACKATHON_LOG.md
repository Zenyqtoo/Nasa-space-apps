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
| 3. Пороги эрозии | `rules/erosion.yaml`: NDVI < 0,30 (нет зелёного покрова — открытая почва или стерня), ветер ≥ 5 м/с на 2 м по POWER `WS2M_MAX` (RWEQ), сухо — SMAP ниже влажности завядания 0–5 см (Chepil 1956), GWETTOP — порог по распределению SMAP для поля (Reichle & Koster 2004), снег — MOD13Q1 код 2 или POWER FRSNO ≥ 0,5 и SNODP ≥ 2,54 см; 12 источников в `sources.yaml`; загрузчик проверяет группы, диапазоны, высоту ветра; `make audit` показывает «Часы» при NDVI 0,25 и 0,30 | `backend/app/rules/erosion.yaml`, `rules/sources.yaml`, `model/rules.py`, `services/bare_soil.py`, `tests/test_rules.py`, `scripts/audit_model.py`, `docs/contracts/README.md`, `docs/LIMITATIONS.md` | ветка `hackathon/task3-erosion-rules` |

## To verify on full text

В контейнере хакатона полные тексты статей были недоступны (сайты издателей и репозиториев закрыты сетевой политикой), поэтому источники порогов
эрозии проверены **только по выдержкам из поисковой выдачи**. У каждого такого источника в `backend/app/rules/sources.yaml` стоит
note «Проверено только по выдержке, полный текст не прочитан», и ни одно правило на них не имеет `status: verified`.
После сверки по полному тексту: убрать эту пометку из note и, если значение применимо к Северному Казахстану, поднять `evidence`.

| Приоритет | Источник (id) | Что сверить | Где в правилах |
|---|---|---|---|
| 1 | RWEQ, Fryrear et al. 1998, Technical Bulletin No. 1 (`rweq_1998`) | порог 5 м/с именно на высоте 2 м и к какой скорости он относится (часовая, мгновенная); снежный покров > 25,4 мм как защитный | `erosive_wind.speed_ms`, `snow.power_snodp_min_cm` |
| 2 | Chepil 1956, SSSA Proc. 20:288–292 (`chepil_1956`) | эродируемость ≈ 0 при влажности завядания (15 атм) и почти без изменений ниже ~1/3 её | `dry_topsoil.smap_wilting_point_factor` |
| 3 | Sobrino et al. 2004, RSE 90:434–440 (`sobrino_2004`) | NDVI < 0,2 — открытая почва, > 0,5 — сплошная растительность | `bare_soil.ndvi_max` (range) |
| 4 | Lamb et al. 2022, Remote Sensing 14:6128 (`lamb_2022`) | выборка NDVI < 0,3 для сцен без заметной зелени | `bare_soil.ndvi_max` |
| 5 | Dvorakova et al. 2021, Remote Sensing 13:1791 (`dvorakova_2021`) | порог NDVI < 0,25 и точное название статьи | `bare_soil.ndvi_max` (range) |
| 6 | Reichle & Koster 2004, GRL 31 (`reichle_koster_2004`) | метод сопоставления распределений (CDF matching) | `dry_topsoil.gwettop_min_pairs` |
| 7 | Fécan et al. 1999, Ann. Geophys. 17:149–157 (`fecan_1999`) | коэффициенты w′ = 0,0014·глина² + 0,17·глина | note к `dry_topsoil.smap_wilting_point_factor` |
| 8 | Daughtry et al. 2004, RSE (`daughtry_residue`) | NDVI не связан с покрытием остатками; том и страницы | комментарий к `bare_soil` |
| 9 | Bilbro & Fryrear 1994, Agron. J. (`bilbro_fryrear_1994`) | снижение потерь почвы стоящей стерней; DOI | комментарий к `bare_soil` |
| 10 | GMAO MERRA-2 FAQ (`gmao_merra2_faq`) | SFMC = пористость × GWETTOP; SNODP — в заснеженной части ячейки | `snow.power_frsno_min`, комментарий к `dry_topsoil` |
| 11 | MOD13 User Guide C6.1 (`mod13_user_guide`) | таблица pixel_reliability: 2 — снег/лёд | `snow.modis_reliability_snow` |
| — | А. А. Зайцева (через ru-ecology.info), первоисточник не установлен | найти первоисточник: 6 м/с (лёгкие) и ≥ 10 м/с (тяжёлые почвы) на высоте флюгера, Северный Казахстан | только note к `erosive_wind.speed_ms` |
