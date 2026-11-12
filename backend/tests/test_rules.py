"""Правила: у каждой цифры есть источник и статус."""
from __future__ import annotations

import shutil

import pytest

from app.model.rules import RULES_DIR, RulesError, load_rules

REQUIRED_CROPS = {"wheat", "lentil", "pea", "chickpea", "flax", "rapeseed", "sunflower", "fallow"}


def test_every_param_has_source_and_status(rules):
    params = rules.all_params()
    assert len(params) > 60
    for p in params:
        assert p.status in ("verified", "assumption"), p.path
        assert p.source_name and p.source_url, p.path
        assert p.unit != "", p.path
        if p.status == "assumption":
            assert p.note, f"{p.path}: у допущения должно быть пояснение"


def test_required_crops_regions_and_variants(rules):
    assert REQUIRED_CROPS <= set(rules.crops)
    assert set(rules.regions) == {"akmola", "kostanay", "north_kazakhstan"}
    assert [v["crops"] for v in rules.model["default_variants"]] == [
        ["wheat", "wheat", "wheat", "wheat"],
        ["wheat", "lentil", "wheat", "flax"],
        ["wheat", "pea", "rapeseed", "fallow"],
        ["wheat", "chickpea", "sunflower", "wheat"],
    ]
    assert set(rules.model["priorities"]) == {"max_income", "save_moisture", "restore_soil"}
    for crop in rules.crops.values():
        assert crop["name"]["ru"] and crop["name"]["kk"]
    for cid in ("lentil", "pea", "chickpea"):
        assert rules.crops[cid]["nitrogen_fixing"] is True
    assert rules.crops["wheat"]["nitrogen_fixing"] is False


def test_prices_come_from_one_document_and_date(rules):
    """Аудит: цены нельзя смешивать из разных источников и дат — это искажает сравнение культур.
    Все культуры, для которых есть цена в рекомендациях МСХ РК от 27.07.2026, берут её оттуда."""
    for cid in ("wheat", "lentil", "pea", "flax", "rapeseed", "sunflower"):
        p = rules.crop(cid)["price_kzt_t"]
        assert p.source_id == "moa_prices_2026" and p.status == "verified", cid
    assert rules.crop("wheat")["price_kzt_t"].value == 104000  # 3 класс, клейковина до 25 %


def test_every_param_has_evidence_class(rules):
    from app.model.rules import EVIDENCE

    for p in rules.all_params():
        assert p.evidence in EVIDENCE, p.path
        if p.status == "verified":
            assert p.evidence in ("literature", "definition"), p.path
        if p.evidence == "preliminary":
            assert p.status == "assumption", p.path


def test_fao_ky_values_match_fao56_table24(rules):
    # FAO-56, табл. 24 (сверено с текстом FAO): Spring wheat 1.15, Peas 1.15, Sunflower 0.95;
    # для культур без данных FAO рекомендует Ky = 1
    expected = {"wheat": 1.15, "pea": 1.15, "sunflower": 0.95, "lentil": 1.0, "chickpea": 1.0, "flax": 1.0, "rapeseed": 1.0}
    for cid, ky in expected.items():
        assert rules.crop(cid)["ky"].value == ky, cid


def test_region_reference_is_computed_from_power(rules):
    for rid, region in rules.regions.items():
        ref = region["reference_season_precip_mm"]
        assert ref.value is not None and 80 < ref.value < 400, rid
        assert ref.source_id == "nasa_power"


def test_predecessor_lookup_prefers_specific_rule(rules):
    assert rules.predecessor_effect("pea", "wheat")[0] == 26
    assert rules.predecessor_effect("lentil", "wheat")[0] == 18
    assert rules.predecessor_effect("wheat", "wheat")[0] == 0
    assert rules.predecessor_effect("sunflower", "wheat")[0] == -10  # конкретное правило сильнее группового
    assert rules.predecessor_effect("flax", "wheat")[0] == 10
    assert rules.predecessor_effect("pea", "pea")[0] == -15
    assert rules.predecessor_effect("pea", "lentil")[0] == -10
    assert rules.predecessor_effect(None, "wheat") == (0.0, None)
    assert rules.predecessor_effect("wheat", "fallow") == (0.0, None)


def _copy_rules(tmp_path):
    for f in RULES_DIR.glob("*.yaml"):
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def test_loader_rejects_number_without_source(tmp_path):
    d = _copy_rules(tmp_path)
    text = (d / "crops.yaml").read_text(encoding="utf-8")
    (d / "crops.yaml").write_text(text.replace("source: expert_guess, status: assumption", "status: assumption", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="missing fields"):
        load_rules(d)


def test_loader_rejects_missing_evidence(tmp_path):
    d = _copy_rules(tmp_path)
    text = (d / "crops.yaml").read_text(encoding="utf-8")
    (d / "crops.yaml").write_text(text.replace(" evidence: preliminary,", "", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="evidence"):
        load_rules(d)


def test_loader_rejects_unknown_source_and_status(tmp_path):
    d = _copy_rules(tmp_path)
    text = (d / "crops.yaml").read_text(encoding="utf-8")
    (d / "crops.yaml").write_text(text.replace("source: expert_guess", "source: made_up", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="unknown source"):
        load_rules(d)
    (d / "crops.yaml").write_text(text.replace("source: stat_gov_kz, status: assumption", "source: stat_gov_kz, status: sure", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="status"):
        load_rules(d)
