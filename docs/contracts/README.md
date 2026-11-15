# Контракты API

Файлы `*.example.json` — **согласованная с фронтендом форма ответа**. Значения в примерах иллюстративные, не результаты.
Менять форму можно только добавлением необязательных полей; переименовывать и удалять поля нельзя.

## `bare_soil.example.json` — `GET /api/fields/{id}/bare-soil?start_year=&end_year=`

Реализация: `backend/app/services/bare_soil.py`, схемы — `BareSoilOut` в `backend/app/schemas.py`.
Тесты сверяют ответ со схемой и с ключами примера (`backend/tests/test_bare_soil.py`).

### Определение показателя

`exposure` — доля **известных** дней месяца, когда в один и тот же день:

1. **нет зелёного покрова (открытая почва или стерня)** — NDVI MOD13Q1 ниже порога;
2. **эрозионный ветер** — максимальная часовая скорость ветра на 2 м (POWER `WS2M_MAX`) не ниже порога;
3. **сухой верхний слой** — SMAP ниже влажности завядания слоя 0–5 см, или GWETTOP ниже порога, подобранного по SMAP.

`exposure = joint_days / known_days`, где `known_days` — дни месяца, когда известны **все три** условия
(день с неизвестным условием не входит ни в `joint_days`, ни в `known_days`). Месяц считается (`state: ok`), если
`known_days / days_in_month ≥ month.min_known_fraction` (0,5 в `erosion.yaml`). Деление на известные дни, а не на
все дни месяца: иначе частично известные весенние и осенние месяцы — самые опасные — выглядели бы безопаснее.
Снежный день известен и не бывает «без покрова».

NDVI не отличает стерню от открытой почвы. Поэтому там, где стерня оставлена стоять, `exposure` — **верхняя оценка
риска**: стоящие остатки сильно снижают выдувание. Поле `bare_days` означает дни без зелёного покрова (открытая почва
или стерня); имя поля не меняется. Пороги, единицы и источники — `backend/app/rules/erosion.yaml`; в ответе они
приходят в `thresholds` (id `ndvi_bare`, `erosive_wind_ms`, `dry_topsoil`, соответствие — `contract_thresholds` в YAML).

### Параметры

| Параметр | По умолчанию | Допустимо |
|---|---|---|
| `start_year` | 2015 (начало ряда SMAP) | 2001 … текущий год |
| `end_year` | текущий год | 2001 … текущий год, не меньше `start_year` |

Вне диапазона — `422`. Год 2000 исключён: он неполный (MOD13Q1 начинается 18.02.2000). Чужое поле — `404`.

### Верхнеуровневый `status`

Это уточнение к примеру, форму оно не меняет.

| Значение | Смысл |
|---|---|
| `ok` | всё посчитано |
| `partial` | посчитана часть месяцев: есть пропуски или ещё идут фоновые загрузки |
| `loading` | пока ничего не посчитано, фоновые загрузки идут |
| `missing` | посчитать нельзя (нет данных) |

Будущие месяцы (`missing_reason: future`) на статус не влияют.

### Состояние месяца

- `state`: `ok` — посчитан; `snow` — снежный покров не меньше половины дней месяца, эрозия не оценивается; `missing` — нет данных
  (известных дней меньше `month.min_known_fraction`). У `missing` числа — `null`, **не 0**.
- `known_days` *(добавлено в задаче 4)* — дни, когда известны все три условия; знаменатель `exposure`.
- `missing_reason` *(добавлено в задаче 4, только при `state: missing`)*: `future` — после последнего дня POWER;
  `no_weather` — нет ветра POWER; `ndvi_pending_fetch` — нужный ряд MODIS (сезон или межсезонье) ещё не загружен;
  `ndvi_gap` — ряд загружен, но годного композита нет (облака, длинный разрыв); `ndvi_not_covered` — зима вне окон
  MODIS без снежного покрова; `no_moisture` — нет ни SMAP, ни GWETTOP.
- `moisture_source`: `smap` | `power_gwettop` | `mixed` (в одни дни месяца SMAP, в другие GWETTOP).
- `quality: partial` ставится и тогда, когда сухость верхнего слоя определялась по POWER GWETTOP, а не по SMAP (`moisture_source: power_gwettop`).
- `quality`: `ok` | `partial` | `missing`. `partial` — также когда известны не все дни месяца или «нет покрова»
  решено по среднему NDVI поля (предупреждение `ndvi_field_mean_proxy`).
- `bare_days`, `erosive_wind_days`, `dry_days`, `joint_days`, `exposure`, `moisture_source` могут быть `null`.
- `days_in_month` есть всегда, в високосные годы февраль — 29.

### Остальное

- `sources` — список в форме `monitoring.source_meta` (не словарь, как в `/monitoring`).
- `warnings` — `{code, source, params}`, как `DataWarning`.
- `jobs` — `{source, status, job}`, где `job` — состояние фоновой задачи (как в `/api/jobs/{id}`). Только реально
  запущенные загрузки: `modis`, `modis_shoulder`, `smap_season`; недоступность без задачи (нет сети, нет токена) — в `warnings`.
- `effective_thresholds` *(добавлено в задаче 4, необязательное)* — пороги, фактически применённые к полю: θ_wp слоя
  0–5 см из SoilGrids, порог GWETTOP (`cdf_match` по SMAP или `fallback`), медианы дат заморозков, типичное окончание уборки в области (`harvest_end`).
- `headline.top_months` — до `headline.top_n` месяцев с наибольшей медианой exposure (> 0), по убыванию.
- `cover_crop_windows[].needs_review` *(добавлено в задаче 4)* — языки текста `basis`, требующие вычитки (`["kk"]`).
  `uncertainty`: `low` | `medium` | `high` по числу лет и доле частичных месяцев (`cover_crop` в `erosion.yaml`).
  Окно только после уборки: `start` не раньше `cover_crop.harvest_end` области поля (`effective_thresholds.harvest_end`,
  «ММ-ДД») и не позже, чем за `min_frost_free_days` до медианы первого осеннего заморозка.
- `cover_crop_note` *(добавлено после задачи 4, необязательное)* — почему окон нет: `{reason, basis, needs_review}`;
  `null`, если окна есть или расчёт не выполнялся. `reason`: `no_harvest_date` (для области нет даты уборки),
  `no_frost_data`, `no_risky_months`, `risk_before_harvest_only` (опасные месяцы только между севом и уборкой),
  `frost_before_establishment` (после уборки до заморозка слишком мало дней). `basis` называет исключённые месяцы.
- Коды `warnings`: `cell_larger_than_field` (POWER, SMAP), `smap_before_2015_unavailable`, `moisture_fallback_gwettop`,
  `gwettop_threshold_fallback`, `smap_threshold_fallback`, `ndvi_field_mean_proxy`, `ndvi_pending_fetch`,
  `offline_no_cache`, `source_unavailable`, `smap_not_configured`, `power_without_wind`, `bare_soil_no_weather`.
- Казахские тексты требуют вычитки носителем языка.
