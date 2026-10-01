"""Loads concept-group/weight and IPC-family scoring rules from YAML.

Moved out of scoring/keywords.py and scoring/ipc.py module constants per
docs/PIPELINE.md 단계 2 ("개념 그룹·가중치·IPC 규칙을 YAML 설정으로 분리") so
the rules can be tuned against the evaluation set without a code change.
Config files live in config/ at the repo root; set IPAUTO_CONFIG_DIR to point
at an alternate directory (used by tests).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR_ENV = "IPAUTO_CONFIG_DIR"
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def _config_dir() -> Path:
    override = os.getenv(CONFIG_DIR_ENV)
    return Path(override) if override else _DEFAULT_CONFIG_DIR


def _load_yaml(filename: str) -> dict:
    path = _config_dir() / filename
    with path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


@dataclass(frozen=True)
class ConceptRules:
    concept_groups: dict[str, tuple[str, ...]]
    title_weights: dict[str, int]
    abstract_weights: dict[str, int]
    core_both_bonus: int
    single_core_bonus: int
    vehicle_presence_bonus: int
    ipc_code_bonus: int
    primary_ipc_bonus: int
    generic_title_weight: int
    generic_abstract_weight: int
    generic_multi_keyword_bonus: int
    generic_ipc_weight: int
    concept_priority_high_min: float
    concept_priority_medium_min: float
    generic_priority_high_min: float
    generic_priority_medium_min: float


@dataclass(frozen=True)
class PrimarySignalRule:
    """A confirmed, precise IPC subgroup range tied to one concept.

    Subgroup digits after the slash compare as a decimal fraction (IPC's own
    ordering): "613" -> 0.613, so min/max_subgroup are also fractions.
    """

    family: str
    group: str
    min_subgroup: float
    max_subgroup: float
    concept: str

    def matches(self, family: str, group: str, subgroup_fraction: float) -> bool:
        if family != self.family or group != self.group:
            return False
        return self.min_subgroup <= subgroup_fraction <= self.max_subgroup


@dataclass(frozen=True)
class IpcRules:
    families: tuple[str, ...]
    concept_family_map: dict[str, str]
    primary_signals: tuple[PrimarySignalRule, ...]


@lru_cache(maxsize=1)
def get_concept_rules() -> ConceptRules:
    raw = _load_yaml("concepts.yaml")
    bonuses = raw["bonuses"]
    generic = raw["generic"]
    thresholds = raw["priority_thresholds"]
    concept_thresholds = thresholds["concept_mode"]
    generic_thresholds = thresholds["generic_mode"]
    return ConceptRules(
        concept_groups={key: tuple(values) for key, values in raw["concept_groups"].items()},
        title_weights=dict(raw["title_weights"]),
        abstract_weights=dict(raw["abstract_weights"]),
        core_both_bonus=bonuses["core_both"],
        single_core_bonus=bonuses["single_core"],
        vehicle_presence_bonus=bonuses["vehicle_presence"],
        ipc_code_bonus=bonuses["ipc_code"],
        primary_ipc_bonus=bonuses["primary_ipc"],
        generic_title_weight=generic["title_weight"],
        generic_abstract_weight=generic["abstract_weight"],
        generic_multi_keyword_bonus=generic["multi_keyword_bonus"],
        generic_ipc_weight=generic["ipc_weight"],
        concept_priority_high_min=concept_thresholds["high_min"],
        concept_priority_medium_min=concept_thresholds["medium_min"],
        generic_priority_high_min=generic_thresholds["high_min"],
        generic_priority_medium_min=generic_thresholds["medium_min"],
    )


@lru_cache(maxsize=1)
def get_ipc_rules() -> IpcRules:
    raw = _load_yaml("ipc_rules.yaml")
    primary_signals = tuple(
        PrimarySignalRule(
            family=item["family"],
            group=str(item["group"]),
            min_subgroup=float(item["min_subgroup"]),
            max_subgroup=float(item["max_subgroup"]),
            concept=item["concept"],
        )
        for item in raw.get("primary_signals", [])
    )
    return IpcRules(
        families=tuple(raw["families"]),
        concept_family_map=dict(raw["concept_family_map"]),
        primary_signals=primary_signals,
    )


def clear_cache() -> None:
    """Drop cached rules so a changed IPAUTO_CONFIG_DIR takes effect (tests only)."""
    get_concept_rules.cache_clear()
    get_ipc_rules.cache_clear()
