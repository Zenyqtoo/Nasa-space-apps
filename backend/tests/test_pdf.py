"""PDF-план: казахские буквы без «квадратиков»."""
from __future__ import annotations

import io

import pytest
import yaml
from pypdf import PdfReader

from app.model import explain, rotation
from app.report import pdf as pdf_mod
from app.report.fonts import FONT, KAZAKH_LETTERS, missing_glyphs

ALL_KK = set("әғқңөұүһі")


def _comparison(rules, cond):
    variants = [{"id": v["id"], "name": v["name"], "crops": list(v["crops"])} for v in rules.model["default_variants"]]
    res = rotation.compare(rules, cond, variants, ["wheat"] * 5, 4, "max_income", start_year=2027)
    explain.attach_explanations(rules, res)
    res["priority_name"] = rules.model["priorities"]["max_income"]["name"]
    res["history"] = [{"year": y, "crop": "wheat"} for y in range(2022, 2027)]
    return res


def _analysis(rules, cond):
    """Минимальная сводка анализа (синтетическая, только для проверки вёрстки)."""
    return {
        "field": {
            "area_ha": cond.area_ha,
            "centroid": {"lat": 51.68, "lon": 70.93},
            "region_name": rules.region(cond.region)["name"],
            "is_demo": False,
        },
        "drought": {"dry_years": [2010, 2012, 2023], "every_nth": 8, "window": {"from": 2002, "to": 2026, "n_years": 25}},
        "soil_moisture": {"stock": {"uses_smap": True}},
        "soil": {"summary": {"awc_mm": 160, "topsoil": {"humus_pct": 4.1, "clay_pct": 28, "sand_pct": 39, "ph": 7.0}}},
        "ndvi": {"trend": {"label": "stable", "from_year": 2000, "to_year": 2026, "p_value": 0.41}},
        "sources": [{"source": s, "origin": "cache"} for s in ("power", "modis", "smap", "soilgrids")],
    }


@pytest.mark.parametrize("lang", ["ru", "kk"])
def test_pdf_builds_and_contains_text(rules, cond, lang):
    data = pdf_mod.build_report(_comparison(rules, cond), _analysis(rules, cond), lang=lang, farm_name="ТОО «Қызылжар»")
    assert data.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 2
    text = "".join(p.extract_text() for p in reader.pages)
    assert pdf_mod.strings(lang)["title"] in text
    assert "Қызылжар" in text  # казахские буквы в пользовательском вводе
    if lang == "kk":
        found = ALL_KK & set(text.lower())
        assert len(found) >= 7, f"в PDF найдены не все казахские буквы: {sorted(found)}"
    fonts = set()
    for page in reader.pages:
        for f in (page["/Resources"].get("/Font") or {}).values():
            fonts.add(str(f.get_object()["/BaseFont"]))
    assert fonts and all("DejaVu" in f for f in fonts), fonts


def test_font_has_all_kazakh_letters():
    assert missing_glyphs(KAZAKH_LETTERS) == set()


def test_all_pdf_and_explanation_strings_have_glyphs():
    texts = []
    for path in (pdf_mod.LOCALE_PATH, explain.TEMPLATES_PATH):
        for entry in yaml.safe_load(path.read_text(encoding="utf-8")).values():
            texts += [entry["ru"], entry["kk"]]
    assert missing_glyphs("".join(texts) + "★→•−≈–—«»№", FONT) == set()


def test_builtin_pdf_font_cannot_render_kazakh():
    """Почему нужен TTF: во встроенной Helvetica нет казахских букв."""
    from reportlab.pdfbase import pdfmetrics

    widths = pdfmetrics.getFont("Helvetica").widths
    assert len(widths) == 256  # однобайтовая кодировка — ә (U+04D9) в неё не входит
