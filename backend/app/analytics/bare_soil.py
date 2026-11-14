"""«Часы голой почвы»: суточные условия и помесячные показатели. Чистые функции без сети и файлов.

Все пороги берутся из ``rules/erosion.yaml`` (аргумент ``e`` — ``Rules.erosion``); числовых порогов здесь нет.
Константы ниже описывают формат данных (шаг композитов MOD13Q1, коды качества), а не пороги.

Суточный ряд (``daily_conditions``):
  * снег — POWER (FRSNO и SNODP одновременно) или снежный композит MODIS; снежный день никогда не «без покрова»;
  * NDVI — квантиль NDVI по годным пикселям поля на уровне ``bare_soil.min_field_fraction``: он ниже порога
    ровно тогда, когда ниже порога не меньше этой доли пикселей. Внутри 16-дневного окна композита — его значение,
    между серединами двух годных композитов — линейная интерполяция, если разрыв не длиннее
    ``ndvi_daily.max_interp_gap_days`` и между ними нет снежных дней. Остальные дни неизвестны (NA);
  * ветер — ``erosive_wind.power_parameter`` (WS2M_MAX) не меньше ``erosive_wind.speed_ms``;
  * сухость — SMAP ниже порога, а в дни без SMAP — POWER GWETTOP ниже порога, подобранного по SMAP.

Месяц (``month_summary``): ``known_days`` — дни, когда известны все три условия; ``exposure = joint_days / known_days``.
"""
from __future__ import annotations

import calendar
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from ..data_sources.modis import COMPOSITE_STEP, QUANTILE_LEVELS, SEASON_DOY, shoulder_windows

#: окно одного композита MOD13Q1 — 16 дней от даты начала; середина — через 8 дней
COMPOSITE_DAYS = COMPOSITE_STEP
COMPOSITE_MID = COMPOSITE_STEP // 2

MOISTURE_LABEL = {"smap": "smap", "gwettop": "power_gwettop"}
#: порядок, в котором выбирается главная причина «неизвестных» дней месяца
UNKNOWN_CAUSES = ("future", "no_weather", "ndvi_pending_fetch", "ndvi_gap", "ndvi_not_covered", "no_moisture")


def v(e: dict, group: str, key: str) -> Any:
    """Значение правила erosion.yaml."""
    return e[group][key].value


# ---------------------------------------------------------------- композиты NDVI
@dataclass
class Composite:
    start: date
    value: float | None  # квантиль NDVI поля на уровне min_field_fraction (или среднее — proxy)
    valid: bool
    snow: bool
    proxy: bool  # значение — среднее NDVI поля, а не квантиль (старые демо-данные)

    @property
    def end(self) -> date:
        return min(self.start + timedelta(days=COMPOSITE_DAYS - 1), date(self.start.year, 12, 31))

    @property
    def mid(self) -> date:
        return self.start + timedelta(days=COMPOSITE_MID)


def _field_quantile(entry: dict, modis: dict, level: float) -> tuple[float | None, bool]:
    """Квантиль NDVI поля: из ndvi_q, из пиксельного растра или (proxy) среднее по полю."""
    q = entry.get("ndvi_q")
    if q:
        levels = modis.get("quantile_levels") or list(QUANTILE_LEVELS)
        return float(np.interp(level, levels, q)), False
    raster = (modis.get("rasters") or {}).get(entry["date"])
    mask = modis.get("field_mask")
    if raster is not None and mask is not None and len(raster) == len(mask):
        scale = float(modis.get("ndvi_scale") or 1.0)
        vals = [x * scale for x, m in zip(raster, mask) if m and x is not None]
        if vals:
            return float(np.quantile(vals, level)), False
    if entry.get("ndvi") is not None:
        return float(entry["ndvi"]), True
    return None, False


def composites(modis_datasets: list[dict], e: dict) -> list[Composite]:
    """Композиты из одного или нескольких ответов MODIS (сезон и межсезонье), по дате начала."""
    level = float(v(e, "bare_soil", "min_field_fraction"))
    snow_code = str(v(e, "snow", "modis_reliability_snow"))
    snow_min = float(v(e, "snow", "modis_min_field_fraction"))
    min_valid = float(v(e, "ndvi_daily", "min_valid_fraction"))
    out: dict[date, Composite] = {}
    for modis in modis_datasets:
        for entry in modis.get("series", []):
            start = date.fromisoformat(entry["date"])
            counts = entry.get("reliability_counts")
            snow = False
            if counts:
                total = sum(counts.values())
                snow = total > 0 and counts.get(snow_code, 0) / total >= snow_min
            value, proxy = _field_quantile(entry, modis, level)
            valid = (not snow and value is not None
                     and float(entry.get("valid_fraction") or 0.0) >= min_valid)
            out[start] = Composite(start, value, valid, snow, proxy and valid)
    return [out[k] for k in sorted(out)]


def ndvi_coverage(day: date) -> str | None:
    """Каким запросом MODIS покрыт день: ``main`` (DOY 129–288), ``shoulder`` или ``None`` (зима)."""
    doy = day.timetuple().tm_yday
    if SEASON_DOY[0] <= doy < SEASON_DOY[1] + COMPOSITE_DAYS:
        return "main"
    if any(a <= doy < b + COMPOSITE_DAYS for a, b in shoulder_windows()):
        return "shoulder"
    return None


# ---------------------------------------------------------------- суточный ряд
def power_frame(power: dict) -> pd.DataFrame:
    df = pd.DataFrame(power["daily"])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def smap_days(*datasets: dict | None) -> pd.Series:
    """Влажность SMAP (центральная ячейка) по датам; несколько ответов объединяются."""
    values: dict[pd.Timestamp, float] = {}
    for d in datasets:
        for r in (d or {}).get("daily", []):
            if r.get("sm") is not None:
                values[pd.Timestamp(r["date"])] = float(r["sm"])
    return pd.Series(values, dtype=float).sort_index()


def power_snow(df: pd.DataFrame, e: dict) -> pd.Series:
    if "FRSNO" not in df or "SNODP" not in df:
        return pd.Series(False, index=df.index)
    fr = df["FRSNO"].astype(float) >= float(v(e, "snow", "power_frsno_min"))
    dp = df["SNODP"].astype(float) >= float(v(e, "snow", "power_snodp_min_cm"))
    return (fr & dp).fillna(False)


def gwettop_threshold(df: pd.DataFrame, sm: pd.Series, smap_thr: float, snow: pd.Series, e: dict) -> dict:
    """Порог GWETTOP для поля: доля дней GWETTOP < порога равна доле дней SMAP < smap_thr
    на общих бесснежных днях (сопоставление распределений). Мало общих дней — gwettop_fallback."""
    gw = df["GWETTOP"].astype(float) if "GWETTOP" in df else pd.Series(dtype=float)
    common = sm.index.intersection(gw.dropna().index)
    common = common[~snow.reindex(common, fill_value=False).to_numpy(dtype=bool)]
    n = len(common)
    if n < int(v(e, "dry_topsoil", "gwettop_min_pairs")):
        return {"value": float(v(e, "dry_topsoil", "gwettop_fallback")), "basis": "fallback", "pairs": n}
    p = float((sm.loc[common] < smap_thr).mean())
    g = gw.loc[common].to_numpy()
    thr = float(np.min(g)) if p <= 0 else float(np.quantile(g, p))
    return {"value": round(thr, 4), "basis": "cdf_match", "pairs": n, "smap_dry_share": round(p, 3)}


def daily_conditions(
    df: pd.DataFrame, comps: list[Composite], sm: pd.Series, smap_thr: float, gw_thr: float,
    e: dict, start: date, end: date,
) -> pd.DataFrame:
    """Суточная таблица с ``start`` по ``end``: snow, ndvi, ndvi_proxy, bare, windy, dry, moisture."""
    idx = pd.date_range(start, end, freq="D")
    power = df.reindex(idx)
    n = len(idx)
    pos = {d.date(): i for i, d in enumerate(idx)}

    snow = power_snow(power, e).to_numpy(dtype=bool).copy()
    for c in comps:
        if c.snow:
            for k in range((c.end - c.start).days + 1):
                i = pos.get(c.start + timedelta(days=k))
                if i is not None:
                    snow[i] = True

    ndvi = np.full(n, np.nan)
    proxy = np.zeros(n, dtype=bool)
    valid = [c for c in comps if c.valid]
    for c in valid:  # внутри окна композита — его значение
        for k in range((c.end - c.start).days + 1):
            i = pos.get(c.start + timedelta(days=k))
            if i is not None:
                ndvi[i], proxy[i] = c.value, c.proxy
    max_gap = int(v(e, "ndvi_daily", "max_interp_gap_days"))
    snow_dates = {idx[i].date() for i in np.flatnonzero(snow)}
    for a, b in zip(valid, valid[1:]):  # между серединами — интерполяция
        gap = (b.mid - a.mid).days
        if gap > max_gap or any(a.mid + timedelta(days=k) in snow_dates for k in range(1, gap)):
            continue
        for k in range(gap + 1):
            i = pos.get(a.mid + timedelta(days=k))
            if i is not None:
                ndvi[i] = a.value + (b.value - a.value) * k / gap
                proxy[i] = a.proxy or b.proxy

    bare = pd.array([pd.NA] * n, dtype="boolean")
    known_ndvi = ~np.isnan(ndvi)
    bare[known_ndvi] = ndvi[known_ndvi] < float(v(e, "bare_soil", "ndvi_max"))
    bare[snow] = False

    wind_col = e["erosive_wind"]["power_parameter"]
    wind = power[wind_col].astype(float) if wind_col in power else pd.Series(np.nan, index=idx)
    windy = pd.array([pd.NA] * n, dtype="boolean")
    wk = wind.notna().to_numpy()
    windy[wk] = wind.to_numpy()[wk] >= float(v(e, "erosive_wind", "speed_ms"))

    smv = sm.reindex(idx).to_numpy(dtype=float)
    gw = power["GWETTOP"].astype(float).to_numpy() if "GWETTOP" in power else np.full(n, np.nan)
    dry = pd.array([pd.NA] * n, dtype="boolean")
    moisture = np.array([None] * n, dtype=object)
    has_sm, has_gw = ~np.isnan(smv), np.isnan(smv) & ~np.isnan(gw)
    dry[has_sm] = smv[has_sm] < smap_thr
    dry[has_gw] = gw[has_gw] < gw_thr
    moisture[has_sm], moisture[has_gw] = "smap", "gwettop"

    out = pd.DataFrame({"snow": snow, "ndvi": ndvi, "ndvi_proxy": proxy, "bare": bare, "windy": windy, "dry": dry,
                        "moisture": moisture}, index=idx)
    out["weather"] = power[wind_col].notna().to_numpy() if wind_col in power else False
    return out


# ---------------------------------------------------------------- месяц
def _unknown_cause(day: pd.Timestamp, row: pd.Series, last_weather: date | None, ndvi_ready: dict[str, bool]) -> str:
    if last_weather is None or day.date() > last_weather:
        return "future"
    if pd.isna(row["windy"]):
        return "no_weather"
    if pd.isna(row["bare"]):
        cov = ndvi_coverage(day.date())
        if cov is None:
            return "ndvi_not_covered"
        return "ndvi_gap" if ndvi_ready.get(cov, False) else "ndvi_pending_fetch"
    return "no_moisture"


def month_summary(daily: pd.DataFrame, year: int, month: int, e: dict, *, last_weather: date | None,
                  ndvi_ready: dict[str, bool]) -> dict:
    """Показатели месяца по контракту (плюс known_days и missing_reason, служебное _flags)."""
    n_days = calendar.monthrange(year, month)[1]
    d = daily[(daily.index.year == year) & (daily.index.month == month)]
    base = {"month": month, "state": "missing", "bare_days": None, "erosive_wind_days": None, "dry_days": None,
            "joint_days": None, "days_in_month": n_days, "known_days": 0, "exposure": None, "moisture_source": None,
            "quality": "missing", "missing_reason": None, "_flags": {}}
    if len(d) == 0:
        return {**base, "missing_reason": "future"}
    known = (d["bare"].notna() & d["windy"].notna() & d["dry"].notna()).to_numpy()
    known_days = int(known.sum())
    wind_days = int(d["windy"].fillna(False).sum()) if d["windy"].notna().any() else None
    snow_days = int(d["snow"].sum())
    base.update(known_days=known_days, erosive_wind_days=wind_days)

    if snow_days >= float(v(e, "snow", "month_snow_day_fraction")) * n_days:
        complete = len(d) == n_days and bool(d["weather"].all())
        return {**base, "state": "snow", "quality": "ok" if complete else "partial"}

    if known_days < float(v(e, "month", "min_known_fraction")) * n_days:
        causes = Counter(_unknown_cause(day, row, last_weather, ndvi_ready)
                         for day, row in d[~known].iterrows())
        causes["future"] += n_days - len(d)
        reason = max(UNKNOWN_CAUSES, key=lambda c: (causes[c], -UNKNOWN_CAUSES.index(c)))
        return {**base, "missing_reason": reason}

    kd = d[known]
    joint = int((kd["bare"] & kd["windy"] & kd["dry"]).sum())
    sources = set(kd["moisture"]) - {None}
    label = MOISTURE_LABEL[sources.pop()] if len(sources) == 1 else "mixed"
    used_gwettop = "gwettop" in set(kd["moisture"])
    used_proxy = bool((kd["ndvi_proxy"] & ~kd["snow"]).any())
    partial = known_days < n_days or used_proxy or (
        used_gwettop and e["dry_topsoil"]["gwettop_month_quality"] == "partial")
    return {**base, "state": "ok", "bare_days": int(d["bare"].fillna(False).sum()),
            "dry_days": int(d["dry"].fillna(False).sum()), "joint_days": joint,
            "exposure": round(joint / known_days, 4), "moisture_source": label,
            "quality": "partial" if partial else "ok",
            "_flags": {"gwettop": used_gwettop, "ndvi_proxy": used_proxy, "smap": "smap" in set(kd["moisture"])}}


# ---------------------------------------------------------------- многолетняя сводка
def climatology(years: list[dict], e: dict) -> list[dict]:
    min_years = int(v(e, "climatology", "min_years"))
    out = []
    for m in range(1, 13):
        ex = [mo["exposure"] for y in years for mo in y["months"] if mo["month"] == m and mo["state"] == "ok"]
        enough = len(ex) >= min_years
        out.append({"month": m, "n_years": len(ex),
                    "exposure_median": round(float(np.median(ex)), 4) if enough else None,
                    "exposure_p90": round(float(np.percentile(ex, 90)), 4) if enough else None})
    return out


def headline(clim: list[dict], e: dict) -> dict:
    ranked = sorted((c for c in clim if c["exposure_median"] is not None and c["exposure_median"] > 0),
                    key=lambda c: (-c["exposure_median"], c["month"]))
    top = ranked[: int(v(e, "headline", "top_n"))]
    return {"top_months": [c["month"] for c in top],
            "max_median_exposure": top[0]["exposure_median"] if top else None}


# ---------------------------------------------------------------- заморозки и окна покровных культур
REF_YEAR = 2001  # невисокосный год для дат «ММ-ДД»


def _ref_doy(d: date) -> int:
    """Номер дня в невисокосном году: в високосном с 1 марта сдвигаем на день назад."""
    leap_shift = int(calendar.isleap(d.year) and d >= date(d.year, 3, 1))
    return (d - date(d.year, 1, 1)).days + 1 - leap_shift


def frost_dates(df: pd.DataFrame, e: dict, years: range) -> dict:
    """Медианы дат последнего весеннего и первого осеннего заморозка (POWER T2M_MIN) по годам периода."""
    thr = float(v(e, "cover_crop", "frost_t2m_min_c"))
    split = int(e["cover_crop"]["season_split_month"])
    tmin = df["T2M_MIN"].astype(float) if "T2M_MIN" in df else pd.Series(dtype=float)
    spring, autumn = [], []
    for y in years:
        t = tmin[tmin.index.year == y]
        if t.notna().sum() < (date(y, 12, 31) - date(y, 1, 1)).days + 1:  # только полные годы
            continue
        frost = t[t < thr]
        sp, au = frost[frost.index.month <= split], frost[frost.index.month > split]
        if len(sp) and len(au):
            spring.append(_ref_doy(sp.index[-1].date()))
            autumn.append(_ref_doy(au.index[0].date()))
    if not spring:
        return {"n_years": 0, "last_spring": None, "first_autumn": None}

    def to_date(doy: float) -> date:
        return date(REF_YEAR, 1, 1) + timedelta(days=int(round(doy)) - 1)

    return {"n_years": len(spring), "last_spring": to_date(float(np.median(spring))),
            "first_autumn": to_date(float(np.median(autumn)))}


MONTHS = {
    "ru": ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь",
           "декабрь"],
    "kk": ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан", "қараша",
           "желтоқсан"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}
KK_REVIEW = " (ана тілінде тексеру қажет)"


def _num(x: float, lang: str) -> str:
    s = f"{x:.2f}"
    return s if lang == "en" else s.replace(".", ",")


def _basis(months: list[int], med: float, p90: float, n_years: int, frost: date, days: int) -> dict:
    names = {lang: "–".join(dict.fromkeys(MONTHS[lang][m - 1] for m in (months[0], months[-1]))) for lang in MONTHS}
    fr = frost.strftime("%d.%m")
    return {
        "ru": f"{names['ru'].capitalize()}: медиана доли опасных дней {_num(med, 'ru')} (P90 {_num(p90, 'ru')}, "
              f"{n_years} лет). От начала окна до медианной даты первого осеннего заморозка ({fr}) — {days} дн. "
              "Совместимость со сроками сева и уборки основной культуры не оценивалась.",
        "kk": f"{names['kk'].capitalize()}: қауіпті күндер үлесінің медианасы {_num(med, 'kk')} (P90 {_num(p90, 'kk')}, "
              f"{n_years} жыл). Терезе басынан алғашқы күзгі үсіктің медиана күніне ({fr}) дейін {days} күн. "
              "Негізгі дақылдың себу және жинау мерзімдерімен үйлесімі бағаланбаған." + KK_REVIEW,
        "en": f"{names['en']}: median share of risky days {_num(med, 'en')} (P90 {_num(p90, 'en')}, {n_years} years). "
              f"{days} days from the window start to the median first autumn frost ({frost.strftime('%d %b')}). "
              "Fit with the main crop's sowing and harvest dates was not assessed.",
    }


def cover_crop_windows(clim: list[dict], years: list[dict], frost: dict, e: dict) -> list[dict]:
    """Периоды с высокой медианой exposure, от начала которых до первого осеннего заморозка достаточно дней."""
    cc = e["cover_crop"]
    if frost["first_autumn"] is None:
        return []
    min_years = int(v(e, "climatology", "min_years"))
    hot = [c["month"] for c in clim if c["exposure_median"] is not None and c["n_years"] >= min_years
           and c["exposure_median"] >= float(cc["min_median_exposure"].value)]
    runs: list[list[int]] = []
    for m in hot:
        if runs and m == runs[-1][-1] + 1:
            runs[-1].append(m)
        else:
            runs.append([m])
    by_month = {c["month"]: c for c in clim}
    out = []
    for run in runs:
        first = date(REF_YEAR, run[0], 1)
        last = date(REF_YEAR, run[-1], calendar.monthrange(REF_YEAR, run[-1])[1])
        start = max(first, frost["last_spring"] + timedelta(days=1))
        end = min(last, frost["first_autumn"] - timedelta(days=1))
        remaining = (frost["first_autumn"] - start).days
        if start > end or remaining < int(cc["min_frost_free_days"].value):
            continue
        med = max(by_month[m]["exposure_median"] for m in run)
        p90 = max(by_month[m]["exposure_p90"] for m in run)
        n_years = min(by_month[m]["n_years"] for m in run)
        ok_months = [mo for y in years for mo in y["months"] if mo["month"] in run and mo["state"] == "ok"]
        partial_share = sum(mo["quality"] == "partial" for mo in ok_months) / len(ok_months) if ok_months else 1.0
        if n_years < int(cc["min_years_medium_uncertainty"].value):
            unc = "high"
        elif n_years >= int(cc["min_years_low_uncertainty"].value) and \
                partial_share <= float(cc["max_partial_share_low_uncertainty"].value):
            unc = "low"
        else:
            unc = "medium"
        out.append({"start": start.strftime("%m-%d"), "end": end.strftime("%m-%d"),
                    "basis": _basis(run, med, p90, n_years, frost["first_autumn"], remaining),
                    "uncertainty": unc, "needs_review": ["kk"]})
    return out
