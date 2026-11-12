"""Загрузка и проверка YAML-правил.

Каждое числовое правило — это ``Param``: значение, единица, источник (название + ссылка)
и статус ``verified`` / ``assumption``. Загрузчик отказывается работать с правилом
без источника или статуса: так нельзя случайно добавить «голую» цифру.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
STATUSES = {"verified", "assumption"}
GROUPS = {"cereal", "legume", "oilseed", "fallow"}


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Param:
    path: str
    value: Any
    unit: str
    source_id: str
    source_name: str
    source_url: str
    status: str
    note: str = ""

    @property
    def is_assumption(self) -> bool:
        return self.status == "assumption"

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "value": self.value,
            "unit": self.unit,
            "source": {"id": self.source_id, "name": self.source_name, "url": self.source_url},
            "status": self.status,
            "note": self.note,
        }

    def ref(self) -> dict:
        """Короткая ссылка на правило для подсказок интерфейса."""
        return {
            "path": self.path,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "source": self.source_name,
            "url": self.source_url,
        }


def _is_param(node: Any) -> bool:
    return isinstance(node, dict) and "value" in node and ("status" in node or "source" in node)


def _convert(node: Any, path: str, sources: dict[str, dict]) -> Any:
    if _is_param(node):
        missing = {"value", "unit", "source", "status"} - set(node)
        if missing:
            raise RulesError(f"{path}: missing fields {sorted(missing)}")
        if node["status"] not in STATUSES:
            raise RulesError(f"{path}: status must be one of {sorted(STATUSES)}")
        src = sources.get(node["source"])
        if src is None:
            raise RulesError(f"{path}: unknown source id '{node['source']}'")
        return Param(
            path=path,
            value=node["value"],
            unit=str(node["unit"]),
            source_id=node["source"],
            source_name=src["name"],
            source_url=src["url"],
            status=node["status"],
            note=str(node.get("note", "")),
        )
    if isinstance(node, dict):
        return {k: _convert(v, f"{path}.{k}" if path else str(k), sources) for k, v in node.items()}
    if isinstance(node, list):
        out = []
        for i, v in enumerate(node):
            key = v.get("id", i) if isinstance(v, dict) else i
            out.append(_convert(v, f"{path}.{key}", sources))
        return out
    return node


def _walk(node: Any) -> Iterator[Param]:
    if isinstance(node, Param):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


@dataclass(frozen=True)
class Rules:
    sources: dict[str, dict]
    crops: dict[str, dict]
    predecessors: list[dict]
    regions: dict[str, dict]
    model: dict[str, Any]

    # ---- культуры --------------------------------------------------------
    def crop(self, crop_id: str) -> dict:
        try:
            return self.crops[crop_id]
        except KeyError as exc:
            raise RulesError(f"unknown crop '{crop_id}'") from exc

    def group(self, crop_id: str) -> str:
        return self.crop(crop_id)["group"]

    def crop_name(self, crop_id: str, lang: str = "ru", short: bool = False) -> str:
        c = self.crop(crop_id)
        return c["short" if short else "name"].get(lang) or c["name"]["ru"]

    def region(self, region_id: str) -> dict:
        try:
            return self.regions[region_id]
        except KeyError as exc:
            raise RulesError(f"unknown region '{region_id}'") from exc

    # ---- предшественники -------------------------------------------------
    def predecessor_effect(self, predecessor: str | None, crop: str) -> tuple[float, dict | None]:
        """(эффект в %, сработавшее правило). Самое конкретное правило побеждает."""
        if predecessor is None or self.group(crop) == "fallow":
            return 0.0, None
        pg, cg = self.group(predecessor), self.group(crop)

        def match(pattern: str, crop_id: str, group: str) -> int:
            if pattern == crop_id:
                return 2
            if pattern == f"group:{group}":
                return 1
            return 0 if pattern == "any" else -1

        best: tuple[int, dict] | None = None
        for rule in self.predecessors:
            mp, mc = match(rule["predecessor"], predecessor, pg), match(rule["crop"], crop, cg)
            if mp < 0 or mc < 0:
                continue
            if rule.get("same") and predecessor != crop:
                continue
            score = mp * 4 + mc * 2 + (1 if rule.get("same") else 0)
            if best is None or score > best[0]:
                best = (score, rule)
        if best is None:
            return 0.0, None
        return float(best[1]["yield_effect_pct"].value), best[1]

    # ---- сервис -----------------------------------------------------------
    def all_params(self) -> list[Param]:
        return [*_walk(self.crops), *_walk(self.predecessors), *_walk(self.regions), *_walk(self.model)]

    def todo_sources(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self.sources.items() if str(v.get("url", "")).startswith("TODO")]


def load_rules(directory: Path | None = None) -> Rules:
    d = directory or RULES_DIR

    def read(name: str) -> Any:
        return yaml.safe_load((d / name).read_text(encoding="utf-8"))

    sources = read("sources.yaml")
    for sid, src in sources.items():
        if not src.get("name") or not src.get("url"):
            raise RulesError(f"sources.{sid}: name and url are required (use 'TODO: ссылка' if unknown)")
    crops = _convert(read("crops.yaml")["crops"], "crops", sources)
    preds = _convert(read("predecessors.yaml")["effects"], "predecessors", sources)
    regions = _convert(read("regions.yaml")["regions"], "regions", sources)
    model = _convert(read("model.yaml"), "model", sources)

    required = (
        "base_yield_t_ha",
        "price_kzt_t",
        "cost_kzt_ha",
        "water_need_mm",
        "ky",
        "nitrogen_balance_kg_ha",
        "humus_balance_t_ha",
    )
    for cid, crop in crops.items():
        if crop.get("group") not in GROUPS:
            raise RulesError(f"crops.{cid}: group must be one of {sorted(GROUPS)}")
        for key in required:
            if not isinstance(crop.get(key), Param):
                raise RulesError(f"crops.{cid}.{key}: must be a rule with value/unit/source/status")
    rules = Rules(sources=sources, crops=crops, predecessors=preds, regions=regions, model=model)
    for rule in preds:
        for side in ("predecessor", "crop"):
            pat = rule[side]
            if pat != "any" and not pat.startswith("group:") and pat not in crops:
                raise RulesError(f"predecessors.{rule.get('id')}: unknown crop '{pat}'")
    for variant in model["default_variants"]:
        for cid in variant["crops"]:
            rules.crop(cid)
    for pid, pr in model["priorities"].items():
        total = sum(pr["weights"].value.values())
        if abs(total - 1.0) > 1e-6:
            raise RulesError(f"model.priorities.{pid}: weights must sum to 1 (got {total})")
    return rules


@lru_cache
def get_rules() -> Rules:
    return load_rules()
