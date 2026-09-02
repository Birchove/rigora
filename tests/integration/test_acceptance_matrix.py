"""规格 1–34 验收矩阵：绑定真实测试节点，并核对本轮 JUnit PASS 证据。"""

from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
JUNIT_PATH = ROOT / "test-results" / "acceptance-pytest.xml"

# 每个场景至少一个真实 pytest 节点。节点必须能被本测试实际执行。
SCENARIOS: dict[int, tuple[str, ...]] = {
    1: ("tests/application/test_production_journey.py::test_submit_idea_through_worker_reaches_working",),
    2: ("tests/harness/test_orchestrator_idea_review_v1.py::test_range_clarification_can_be_resubmitted",),
    3: ("tests/harness/test_orchestrator_idea_review_v1.py::test_non_cs_domain_returns_refinement_without_model",),
    4: ("tests/integration/test_forward_stages.py::test_each_forward_stage_skips_plan_loop_and_enters_working",),
    5: ("tests/harness/test_orchestrator_completion_v1.py::test_record_main_result_confirms_task_and_forward_runs_complete",),
    6: ("tests/harness/test_scoring.py::test_scoring_passes_high_total_even_when_one_dimension_is_low",),
    7: ("tests/harness/test_orchestrator_plan_loop_v1.py::test_candidate_key_insight_override_is_audited",),
    8: ("tests/harness/test_working_context.py::test_successful_low_rank_is_diagnostic_only",),
    9: ("tests/harness/test_working_context.py::test_rank_unavailable_does_not_decline_question",),
    10: ("tests/api/test_documents.py::test_upload_list_get_and_project_isolation",),
    11: ("tests/api/test_documents.py::test_failed_retry_new_attempt_and_delete_rules",),
    12: ("tests/integration/test_validation_workflow.py::test_candidates_are_offered_and_selected_by_rank",),
    13: ("tests/harness/test_orchestrator_completion_v1.py::test_validation_queue_selects_by_rank_and_preserves_skip_reasons",),
    14: ("tests/harness/test_orchestrator_completion_v1.py::test_validation_results_preserve_outcome_and_return_completing",),
    15: ("tests/harness/test_orchestrator_completion_v1.py::test_invalidating_validation_complete_interrupts_pending_queue",),
    16: ("tests/harness/test_validation_queue.py::test_skipping_critical_candidate_preserves_rationale_and_user_reason",),
    17: ("tests/harness/test_orchestrator_completion_v1.py::test_record_main_result_confirms_task_and_forward_runs_complete",),
    18: ("tests/application/test_journal.py::test_journal_json_is_authoritative_and_markdown_is_deterministic",),
    19: ("tests/application/test_recovery.py::test_recovery_only_requeues_expired_running_lease",),
    20: ("tests/application/test_command_bus.py::test_same_command_id_returns_original_receipt_without_reinvoking_handler",),
    21: ("tests/api/test_commands.py::test_command_conflicts_and_validation_use_stable_errors",),
    22: ("tests/api/test_events.py::test_cursor_uses_larger_header_or_query",),
    23: ("tests/application/test_demo.py::test_demo_seed_creates_three_real_schema_projects",),
    24: ("tests/adapters/llm/test_openai_responses.py::test_responses_adapter_returns_parsed_model",),
    25: ("tests/integration/test_forward_stages.py::test_each_forward_stage_skips_plan_loop_and_enters_working",),
    26: ("tests/application/test_run_worker.py::test_running_agent_uses_frozen_input_snapshot",),
    27: ("tests/application/test_allowed_commands.py::test_illegal_phase_is_rejected_by_server_authority",),
    28: ("tests/application/test_command_bus.py::test_restart_archives_cycle_by_switching_active_session_and_queues_review",),
    29: ("tests/harness/test_orchestrator_idea_review_v1.py::test_non_cs_domain_returns_refinement_without_model",),
    30: ("tests/test_architecture_boundaries.py::test_architecture_import_boundaries",),
    31: ("tests/harness/test_orchestrator_plan_loop_v1.py::test_plan_mode_creates_isolated_candidate_paths",),
    32: ("tests/harness/test_orchestrator_plan_loop_v1.py::test_exhausted_candidate_requires_explicit_override",),
    33: ("tests/harness/test_routing.py::test_working_success_requires_result_record",),
    34: ("tests/agents/test_prompt_contracts.py::test_prompt_builders_preserve_exact_instruction_and_data_boundaries",),
}


def _node_function(nodeid: str) -> str:
    return nodeid.rsplit("::", 1)[-1]


def _passed_names(junit_path: Path) -> set[str]:
    tree = ET.parse(junit_path)
    passed: set[str] = set()
    for case in tree.iter("testcase"):
        if any(child.tag in {"failure", "error", "skipped"} for child in case):
            continue
        name = case.attrib.get("name", "")
        passed.add(name.split("[", 1)[0])
    return passed


def test_acceptance_scenarios_are_complete_and_have_pass_evidence() -> None:
    assert set(SCENARIOS) == set(range(1, 35))
    unique_nodes = sorted({node for nodes in SCENARIOS.values() for node in nodes})
    collect = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *unique_nodes,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert collect.returncode == 0, collect.stdout + collect.stderr

    JUNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    evidence = Path(os.environ.get("ACCEPTANCE_JUNIT", str(JUNIT_PATH)))
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={evidence}",
            *unique_nodes,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert evidence.is_file(), "missing pytest JUnit evidence"
    passed = _passed_names(evidence)
    missing: list[str] = []
    for number, nodes in SCENARIOS.items():
        for node in nodes:
            function_name = _node_function(node)
            if function_name not in passed:
                missing.append(f"{number}:{node}")
    assert missing == [], missing
