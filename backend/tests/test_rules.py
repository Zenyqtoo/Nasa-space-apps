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


def test_task_statement_anchors_are_recorded_as_such(rules):
    """Опоры из постановки: пшеница 65–70 тыс. тенге/т, лён и рапс от 200 тыс."""
    wheat = rules.crop("wheat")["price_kzt_t"]
    assert 65000 <= wheat.value <= 70000 and wheat.source_id == "task_statement"
    for cid in ("flax", "rapeseed"):
        p = rules.crop(cid)["price_kzt_t"]
        assert p.value >= 200000 and p.source_id == "task_statement"


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
    (d / "crops.yaml").write_text(text.replace("source: task_statement, status: assumption", "status: assumption", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="missing fields"):
        load_rules(d)


def test_loader_rejects_unknown_source_and_status(tmp_path):
    d = _copy_rules(tmp_path)
    text = (d / "crops.yaml").read_text(encoding="utf-8")
    (d / "crops.yaml").write_text(text.replace("source: task_statement", "source: made_up", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="unknown source"):
        load_rules(d)
    (d / "crops.yaml").write_text(text.replace("source: stat_gov_kz, status: assumption", "source: stat_gov_kz, status: sure", 1), encoding="utf-8")
    with pytest.raises(RulesError, match="status"):
        load_rules(d)
