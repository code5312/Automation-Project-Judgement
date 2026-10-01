"""Tests for the YAML-backed scoring rules loader (docs/PIPELINE.md 단계 2)."""

from __future__ import annotations

from pathlib import Path

from ipauto.scoring import rules

REPO_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def test_default_config_dir_points_at_repo_config():
    assert rules._config_dir() == REPO_CONFIG_DIR


def test_get_concept_rules_loads_repo_yaml():
    concept_rules = rules.get_concept_rules()

    assert concept_rules.concept_groups["battery"] == ("배터리",)
    assert concept_rules.title_weights["cooling"] == 6
    assert concept_rules.core_both_bonus == 65
    assert concept_rules.generic_multi_keyword_bonus == 3
    assert concept_rules.primary_ipc_bonus == 15
    assert concept_rules.concept_priority_high_min == 70
    assert concept_rules.generic_priority_medium_min == 40


def test_get_ipc_rules_loads_repo_yaml():
    ipc_rules = rules.get_ipc_rules()

    assert ipc_rules.families == ("H01M", "B60L")
    assert ipc_rules.concept_family_map["battery"] == "H01M"


def test_config_dir_env_override_is_respected(tmp_path, monkeypatch):
    (tmp_path / "concepts.yaml").write_text(
        "concept_groups:\n"
        "  widget: ['위젯']\n"
        "title_weights:\n"
        "  widget: 9\n"
        "abstract_weights:\n"
        "  widget: 1\n"
        "bonuses:\n"
        "  core_both: 1\n"
        "  single_core: 1\n"
        "  vehicle_presence: 1\n"
        "  ipc_code: 1\n"
        "  primary_ipc: 1\n"
        "generic:\n"
        "  title_weight: 1\n"
        "  abstract_weight: 1\n"
        "  multi_keyword_bonus: 1\n"
        "  ipc_weight: 1\n"
        "priority_thresholds:\n"
        "  concept_mode:\n"
        "    high_min: 50\n"
        "    medium_min: 20\n"
        "  generic_mode:\n"
        "    high_min: 60\n"
        "    medium_min: 30\n",
        encoding="utf-8",
    )
    (tmp_path / "ipc_rules.yaml").write_text(
        "families: ['X99']\nconcept_family_map:\n  widget: X99\n", encoding="utf-8"
    )
    monkeypatch.setenv(rules.CONFIG_DIR_ENV, str(tmp_path))
    rules.clear_cache()
    try:
        assert rules._config_dir() == tmp_path
        concept_rules = rules.get_concept_rules()
        assert concept_rules.title_weights == {"widget": 9}
        assert concept_rules.concept_priority_high_min == 50
        assert concept_rules.generic_priority_high_min == 60
        assert rules.get_ipc_rules().families == ("X99",)
    finally:
        rules.clear_cache()
