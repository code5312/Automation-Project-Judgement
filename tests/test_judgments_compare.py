"""Tests for comparing a current record against a judgment's stored premises.

IPC and 출원인 are set comparisons (order-insensitive); everything else is a
normalized string comparison.
"""

from __future__ import annotations

from ipauto.judgments.compare import compare_with_premises


def _premise(check_key: str, expected_value: str) -> dict[str, str]:
    return {"check_key": check_key, "expected_value": expected_value}


def test_no_premises_means_no_differences():
    assert compare_with_premises({"등록상태": "공개(샘플)"}, []) == []


def test_matching_values_report_no_difference():
    premises = [_premise("등록상태", "공개(샘플)")]
    current = {"등록상태": "공개(샘플)"}
    assert compare_with_premises(current, premises) == []


def test_changed_scalar_value_is_reported():
    premises = [_premise("등록상태", "공개(샘플)")]
    current = {"등록상태": "소멸(샘플)"}
    assert compare_with_premises(current, premises) == [("등록상태", "공개(샘플)", "소멸(샘플)")]


def test_ipc_reordered_but_same_set_is_not_a_difference():
    premises = [_premise("IPC", "H01M 10/613|H01M 10/625")]
    current = {"IPC": "H01M 10/625|H01M 10/613"}
    assert compare_with_premises(current, premises) == []


def test_ipc_with_a_removed_code_is_a_difference():
    premises = [_premise("IPC", "H01M 10/613|H01M 10/625")]
    current = {"IPC": "H01M 10/613"}
    differences = compare_with_premises(current, premises)
    assert len(differences) == 1
    assert differences[0][0] == "IPC"


def test_applicant_set_comparison_ignores_order():
    premises = [_premise("출원인", "샘플대학교,샘플 주식회사")]
    current = {"출원인": "샘플 주식회사,샘플대학교"}
    assert compare_with_premises(current, premises) == []
