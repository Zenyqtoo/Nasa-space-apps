"""PDF-план севооборота (A4, ru/kk). Шрифт DejaVu Sans — для казахских букв."""
from __future__ import annotations

import io
from datetime import date
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..data_sources.registry import source_catalog
from ..model.explain import NBSP, fmt_int, fmt_num, years_phrase
from ..model.rules import get_rules
from . import charts
from .fonts import FONT, FONT_BOLD, register_fonts

LOCALE_PATH = Path(__file__).resolve().parent.parent / "locales" / "report.yaml"
GREEN = colors.HexColor("#2f5d1e")
SOIL = colors.HexColor("#6b4f2a")
LIGHT = colors.HexColor("#eef3e8")
GRID = colors.HexColor("#b9c4ae")


@lru_cache
def _strings() -> dict:
    return yaml.safe_load(LOCALE_PATH.read_text(encoding="utf-8"))


def strings(lang: str) -> dict[str, str]:
    return {k: v[lang] for k, v in _strings().items()}


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=FONT, fontSize=9.5, leading=12.5, alignment=TA_LEFT)
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor("#444444")),
        "title": ParagraphStyle("title", parent=base, fontName=FONT_BOLD, fontSize=20, leading=24, textColor=GREEN),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10, textColor=SOIL),
        "h2": ParagraphStyle("h2", parent=base, fontName=FONT_BOLD, fontSize=12.5, leading=16, textColor=GREEN, spaceBefore=8, spaceAfter=4),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=10.5),
        "cellb": ParagraphStyle("cellb", parent=base, fontName=FONT_BOLD, fontSize=8.5, leading=10.5),
        "disclaimer": ParagraphStyle(
            "disclaimer", parent=base, fontName=FONT_BOLD, fontSize=9.5, leading=12.5, textColor=colors.HexColor("#7a3d00"),
            backColor=colors.HexColor("#fff4e0"), borderPadding=5, borderColor=colors.HexColor("#e0b070"), borderWidth=0.6,
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _table(rows: list[list], widths: list[float], header: bool = True, zebra: bool = True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONT", (0, 0), (-1, -1), FONT, 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("FONT", (0, 0), (-1, 0), FONT_BOLD, 8.5)]
    if zebra:
        for r in range(2 if header else 1, len(rows), 2):
            style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f8faf5")))
    t.setStyle(TableStyle(style))
    return t


def _variant_label(v: dict, lang: str, rules) -> str:
    chain = " → ".join(rules.crop_name(c, lang, short=True) for c in v["crops"])
    name = (v.get("name") or {}).get(lang) if isinstance(v.get("name"), dict) else v.get("name")
    return f"{name}: {chain}" if name else chain


def build_report(
    comparison: dict,
    analysis: dict,
    *,
    lang: str = "ru",
    selected_variant_id: str | None = None,
    farm_name: str = "",
    stress_year_index: int | None = None,
    today: date | None = None,
) -> bytes:
    register_fonts()
    rules = get_rules()
    t = strings(lang)
    st = _styles()
    today = today or date.today()
    variants = comparison["variants"]
    by_id = {v["id"]: v for v in variants}
    selected = by_id.get(selected_variant_id or "") or by_id[comparison["best_variant_id"]]
    n_years = comparison["horizon_years"]
    yp = years_phrase(n_years)[lang]
    field = analysis["field"]
    story: list = []

    # ---- шапка ----------------------------------------------------------------
    story += [
        _p(t["title"], st["title"]),
        _p(t["subtitle"], st["subtitle"]),
        Spacer(1, 3 * mm),
        _p(f"{t['date']}: {today.strftime('%d.%m.%Y')}", st["small"]),
        Spacer(1, 3 * mm),
        _p(t["disclaimer"], st["disclaimer"]),
        Spacer(1, 2 * mm),
    ]

    # ---- 1. поле ----------------------------------------------------------------
    hist = comparison.get("history") or []
    history_text = ", ".join(f"{h['year']}: {rules.crop_name(h['crop'], lang, short=True)}" for h in hist) or t["not_set"]
    c = field["centroid"]
    rows = [
        [t["farm"], farm_name or "—"],
        [t["area"], f"{fmt_num(field['area_ha'], 1)}{NBSP}{t['ha']}"],
        [t["region"], field["region_name"][lang]],
        [t["centroid"], f"{c['lat']:.5f}, {c['lon']:.5f}"],
        [t["history"], history_text],
        [t["priority"], comparison["priority_name"][lang]],
        [t["horizon"], yp],
    ]
    story += [_p(t["section_field"], st["h2"])]
    story.append(_table([[_p(a, st["cellb"]), _p(b, st["cell"])] for a, b in rows], [55 * mm, 120 * mm], header=False, zebra=False))
    if field.get("is_demo"):
        story += [Spacer(1, 1.5 * mm), _p(t["demo_history_note"], st["small"])]

    # ---- 2. данные поля -------------------------------------------------------
    d = analysis["drought"]
    win = d.get("window") or {}
    if d["dry_years"]:
        dry_text = t["dry_share_value"].format(
            n=len(d["dry_years"]), total=win.get("n_years"), from_year=win.get("from"), to_year=win.get("to"), nth=d["every_nth"]
        )
    else:
        dry_text = t["dry_share_none"].format(from_year=win.get("from"), to_year=win.get("to"))
    cond = comparison["conditions"]
    stock = analysis["soil_moisture"]["stock"]
    basis = t["stock_basis_smap"] if stock.get("uses_smap") else t["stock_basis_power"]
    soil = analysis["soil"]["summary"]
    if soil:
        top = soil["topsoil"]
        soil_text = t["soil_value"].format(
            humus=fmt_num(top["humus_pct"] or 0, 1), clay=fmt_num(top["clay_pct"] or 0, 0),
            sand=fmt_num(top["sand_pct"] or 0, 0), ph=fmt_num(top["ph"] or 0, 1), awc=fmt_num(soil["awc_mm"], 0),
        )
    else:
        soil_text = t["soil_missing"]
    trend = (analysis.get("ndvi") or {}).get("trend")
    if trend and trend.get("label") != "insufficient":
        ndvi_text = t["ndvi_value"].format(
            label=t[f"ndvi_{trend['label']}"], from_year=trend["from_year"], to_year=trend["to_year"], p=fmt_num(trend["p_value"], 3)
        )
    elif trend:
        ndvi_text = t["ndvi_insufficient"]
    else:
        ndvi_text = t["ndvi_missing"]
    data_rows = [
        [t["normal_precip"], f"{fmt_num(cond['p_season_normal'], 0)}{NBSP}{t['mm']}"],
        [t["dry_share"], dry_text],
        [t["stress_year"], t["stress_year_value"].format(year=cond["dry_year"], precip=fmt_num(cond["p_season_dry"], 0))],
        [t["stock"], f"{fmt_num(cond['stock_normal'], 0)}{NBSP}{t['mm']} ({basis})"],
        [t["soil"], soil_text],
        [t["ndvi"], ndvi_text],
    ]
    story += [_p(t["section_data"], st["h2"])]
    story.append(_table([[_p(a, st["cellb"]), _p(b, st["cell"])] for a, b in data_rows], [55 * mm, 120 * mm], header=False, zebra=False))

    # ---- 3. сравнение -------------------------------------------------------------
    labels = [_variant_label(v, lang, rules) for v in variants]
    head = [t["col_variant"], t["col_soil"], t["col_water"], t["col_income"], t["col_risk"], t["col_weighted"],
            t["col_income_total"].format(n=yp)]
    rows = [[_p(h, st["cellb"]) for h in head]]
    for v, label in zip(variants, labels):
        mark = "★ " if v["fits_priority"] else ""
        s = v["scores"]
        rows.append(
            [_p(mark + label, st["cellb"] if v["fits_priority"] else st["cell"])]
            + [fmt_num(s[k]["score"], 1) for k in ("soil", "water", "income", "risk")]
            + [fmt_num(v["weighted_score"], 2), fmt_int(v["totals"]["income_kzt_ha"])]
        )
    story += [_p(t["section_compare"], st["h2"]), _table(rows, [53 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 17 * mm, 37 * mm])]
    story += [Spacer(1, 1.5 * mm), _p(t["scores_note"], st["small"])]

    # ---- 4. прогноз ---------------------------------------------------------------
    short_labels = [f"{i + 1}. " + " → ".join(rules.crop_name(c, lang, short=True) for c in v["crops"]) for i, v in enumerate(variants)]
    png = charts.forecast_chart(variants, short_labels, t)
    story += [KeepTogether([_p(t["section_forecast"], st["h2"]), Image(io.BytesIO(png), width=178 * mm, height=72 * mm)])]

    # ---- 5. стресс-тест -----------------------------------------------------------
    # Если пользователь выбрал год плана — засуха ставится в этот год у всех вариантов.
    # Иначе у каждого варианта берётся его худший год (честнее, чем один номер года для всех:
    # у варианта с паром в «год пара» засуха ничего не меняет).
    def stress_idx(v: dict) -> int:
        i = stress_year_index or v["stress"]["worst_year_index"]
        return max(1, min(i, n_years))

    if stress_year_index:
        dry_col = t["col_dry_year"].format(year=selected["years"][stress_idx(selected) - 1]["year"])
    else:
        dry_col = t["col_dry_worst"]
    s_rows = [[_p(h, st["cellb"]) for h in (t["col_variant"], t["col_normal"], dry_col, t["col_loss"])]]
    for v, label in zip(variants, short_labels):
        i = stress_idx(v)
        normal = v["stress"]["total_normal_kzt_ha"]
        dry = v["stress"]["per_year"][i - 1]["total_if_dry_kzt_ha"]
        suffix = "" if stress_year_index else f" ({v['years'][i - 1]['year']})"
        s_rows.append([_p(label, st["cell"]), fmt_int(normal), fmt_int(dry) + suffix, fmt_int(dry - normal)])
    png = charts.stress_chart(variants, [str(i + 1) for i in range(len(variants))], [stress_idx(v) for v in variants], t)
    story += [
        KeepTogether(
            [
                _p(t["section_stress"], st["h2"]),
                _p(t["stress_intro"].format(year=cond["dry_year"]), st["small"]),
                Spacer(1, 1.5 * mm),
                _table(s_rows, [80 * mm, 30 * mm, 37 * mm, 28 * mm]),
                Spacer(1, 2 * mm),
                Image(io.BytesIO(png), width=178 * mm, height=56 * mm),
            ]
        )
    ]

    # ---- 6. выбранный вариант -----------------------------------------------------
    y_rows = [[_p(h, st["cellb"]) for h in (t["col_year"], t["col_crop"], t["col_yield"], t["col_income_year"], t["col_income_dry"], t["col_soil_index"])]]
    for y in selected["years"]:
        y_rows.append(
            [str(y["year"]), _p(rules.crop_name(y["crop"], lang), st["cell"]), fmt_num(y["yield_t_ha"], 2),
             fmt_int(y["income_kzt_ha"]), fmt_int(y["income_dry_kzt_ha"]), fmt_num(y["soil_index"], 1)]
        )
    block = [
        _p(t["section_selected"], st["h2"]),
        _p(_variant_label(selected, lang, rules), st["cellb"]),
        Spacer(1, 1.5 * mm),
        _table(y_rows, [16 * mm, 40 * mm, 27 * mm, 30 * mm, 37 * mm, 25 * mm]),
        Spacer(1, 1.5 * mm),
        _p(t["field_total"].format(n=yp, value=fmt_int(selected["totals"]["income_field_kzt"])), st["cell"]),
        Spacer(1, 2 * mm),
        _p(t["why"], st["cellb"]),
    ]
    story += [KeepTogether(block)]
    for line in selected.get("explanation", []):
        story.append(_p("• " + line[lang], st["cell"]))

    # ---- 7. источники ----------------------------------------------------------------
    story += [_p(t["section_sources"], st["h2"])]
    origins = {s["source"]: s.get("origin") for s in analysis.get("sources", [])}
    cat = source_catalog()
    for sid in ("power", "modis", "smap", "soilgrids"):
        meta = cat[sid]
        origin = origins.get(sid)
        origin_text = t.get(f"origin_{origin}") if origin else t["origin_none"]
        story.append(
            _p(f"• {meta['title']} ({origin_text}): {meta['spatial_resolution'][lang]} {meta['url']}", st["small"])
        )
    story.append(Spacer(1, 1.5 * mm))
    story.append(
        _p(t["assumptions_note"].format(n_assumptions=selected["assumptions_used"], n_params=selected["params_used"]), st["small"])
    )
    story += [Spacer(1, 2 * mm), _p(t["disclaimer"], st["disclaimer"])]

    # ---- подписи ----------------------------------------------------------------------
    sign = Table(
        [
            [_p(t["sign_farm"], st["cell"]), farm_name or ""],
            [_p(t["sign_farmer"], st["cell"]), ""],
            [_p(t["sign_date"], st["cell"]), ""],
        ],
        colWidths=[50 * mm, 125 * mm],
        rowHeights=[11 * mm] * 3,
    )
    sign.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), FONT, 9), ("LINEBELOW", (1, 0), (1, -1), 0.6, colors.black), ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    story += [KeepTogether([_p(t["section_sign"], st["h2"]), sign])]

    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(18 * mm, 10 * mm, t["subtitle"])
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{t['page']} {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=t["title"], author="Agro-Sevooborot", lang="kk-KZ" if lang == "kk" else "ru-RU",
        initialFontName=FONT, initialFontSize=9.5,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
