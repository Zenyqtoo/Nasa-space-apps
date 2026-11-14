"""GET /api/fields/{id}/bare-soil: каркас ответа по контракту docs/contracts/bare_soil.example.json."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data_sources.base import demo_field_record
from app.main import app
from app.schemas import BareSoilOut
from app.services.bare_soil import DEFAULT_START_YEAR, MIN_YEAR, resolve_period

pytestmark = pytest.mark.skipif(demo_field_record() is None, reason="нет data/demo")
H = {"X-Requested-With": "agro"}
CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "bare_soil.example.json"
CURRENT_YEAR = date.today().year


def _contract() -> dict:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return data


def _shape(obj):
    """Вложенная структура ключей; у списков — по первому элементу, у пустых — None."""
    if isinstance(obj, dict):
        return {k: _shape(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_shape(obj[0])] if obj else None
    return None


def _same_keys(actual, expected, path="$"):
    """Ключи ответа совпадают с контрактом везде, где оба списка непусты."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), f"{path}: {sorted(actual)} != {sorted(expected)}"
        for k in expected:
            _same_keys(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list) and actual:
        _same_keys(actual[0], expected[0], f"{path}[0]")


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    s = get_settings()
    old = (s.db_path, s.offline)
    s.db_path = tmp_path_factory.mktemp("db") / "t.db"
    s.offline = True
    with TestClient(app) as c, TestClient(app) as other:
        c.post("/api/auth/register", json={"email": "bs@example.org", "password": "password-123"}, headers=H)
        other.post("/api/auth/register", json={"email": "bs2@example.org", "password": "password-123"}, headers=H)
        demo = demo_field_record()
        f = c.post("/api/fields", json={"name": "Демо", "region": "akmola", "geometry": demo["geometry"],
                                        "history": demo["history"]}, headers=H).json()
        yield c, other, f["id"]
    s.db_path, s.offline = old


def test_schema_accepts_the_contract_example():
    BareSoilOut.model_validate(_contract())


def test_response_matches_schema_and_contract_shape(ctx):
    c, _, fid = ctx
    r = c.get(f"/api/fields/{fid}/bare-soil")
    assert r.status_code == 200
    body = r.json()
    BareSoilOut.model_validate(body)
    _same_keys(body, _shape(_contract()))
    assert body["field_id"] == fid


def test_skeleton_defaults_and_values(ctx):
    c, _, fid = ctx
    body = c.get(f"/api/fields/{fid}/bare-soil").json()
    assert body["period"] == {"start_year": DEFAULT_START_YEAR, "end_year": CURRENT_YEAR}
    assert body["status"] == "missing" and body["jobs"] == []
    assert [y["year"] for y in body["years"]] == list(range(DEFAULT_START_YEAR, CURRENT_YEAR + 1))
    for y in body["years"]:
        assert [m["month"] for m in y["months"]] == list(range(1, 13))
        for m in y["months"]:
            assert m["state"] == "missing" and m["quality"] == "missing"
            assert m["erosive_wind_days"] is None and m["exposure"] is None and m["joint_days"] is None
    feb = {y["year"]: y["months"][1]["days_in_month"] for y in body["years"]}
    assert feb[2016] == 29 and feb[2017] == 28
    assert {s["id"] for s in body["sources"]} == {"power", "modis", "smap"}
    assert [w["code"] for w in body["warnings"]] == ["bare_soil_not_computed"]
    assert set(body["definition"]["exposure"]) == {"ru", "kk", "en"}


def test_explicit_period(ctx):
    c, _, fid = ctx
    body = c.get(f"/api/fields/{fid}/bare-soil", params={"start_year": 2020, "end_year": 2022}).json()
    assert body["period"] == {"start_year": 2020, "end_year": 2022}
    assert [y["year"] for y in body["years"]] == [2020, 2021, 2022]


def test_demo_field_sources_come_from_demo_data_offline(ctx):
    """OFFLINE=1 на демо-поле: сеть не нужна, происхождение данных — демо."""
    c, _, fid = ctx
    assert get_settings().offline
    origins = {s["id"]: s["origin"] for s in c.get(f"/api/fields/{fid}/bare-soil").json()["sources"]}
    assert "demo" in origins.values()


@pytest.mark.parametrize("params", [
    {"start_year": MIN_YEAR - 1},
    {"end_year": CURRENT_YEAR + 1},
    {"start_year": 2020, "end_year": 2019},
    {"start_year": "abc"},
])
def test_out_of_range_is_422(ctx, params):
    c, _, fid = ctx
    assert c.get(f"/api/fields/{fid}/bare-soil", params=params).status_code == 422


def test_range_bounds_are_inclusive(ctx):
    c, _, fid = ctx
    r = c.get(f"/api/fields/{fid}/bare-soil", params={"start_year": MIN_YEAR, "end_year": CURRENT_YEAR})
    assert r.status_code == 200 and len(r.json()["years"]) == CURRENT_YEAR - MIN_YEAR + 1


def test_foreign_field_is_404(ctx):
    _, other, fid = ctx
    assert other.get(f"/api/fields/{fid}/bare-soil").status_code == 404
    assert other.get("/api/fields/99999/bare-soil").status_code == 404


def test_requires_login():
    with TestClient(app) as anon:
        assert anon.get("/api/fields/1/bare-soil").status_code in (401, 403)


def test_resolve_period_uses_given_today():
    assert resolve_period(None, None, date(2027, 3, 1)) == (2015, 2027)
    with pytest.raises(ValueError):
        resolve_period(2000, None, date(2027, 3, 1))
