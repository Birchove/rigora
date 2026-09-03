import pytest

from research_mentor.application.production import resolve_working_query
from research_mentor.errors import InvariantViolationError
from research_mentor.harness.session_slices import PendingWorkingClarification


PENDING = PendingWorkingClarification(
    original_question="如果恢复 exact-match 掉了 3 个点，原因是什么？",
    clarify_reply="请补充是否已有 actual_result。",
)


def test_new_working_question_keeps_the_question_as_retrieval_query() -> None:
    question, clarification = resolve_working_query(
        {"question": "主实验第一步怎么卡死变量？"},
        None,
    )

    assert question == "主实验第一步怎么卡死变量？"
    assert clarification is None


def test_clarification_reuses_original_question_instead_of_the_followup() -> None:
    question, clarification = resolve_working_query(
        {"clarification": "目前还没跑完，没有 actual_result。"},
        PENDING,
    )

    assert question == PENDING.original_question
    assert clarification == "目前还没跑完，没有 actual_result。"


def test_clarification_without_pending_turn_is_rejected() -> None:
    with pytest.raises(InvariantViolationError):
        resolve_working_query({"clarification": "补一句"}, None)
