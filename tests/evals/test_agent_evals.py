from pathlib import Path

import pytest

from research_mentor.evals.runner import (
    EvalSuite,
    build_demo_agents,
    evaluate_retrieval,
    load_suite,
    run_all_evals,
)


@pytest.mark.parametrize("dataset", sorted(Path("evals").glob("*_cases.json")))
def test_eval_dataset_is_versioned_and_has_metadata(dataset):
    suite = EvalSuite.model_validate_json(dataset.read_text(encoding="utf-8"))
    assert suite.version == "1.0"
    assert suite.prompt_version and suite.domain == "computer_science"


def test_idea_review_has_at_least_twenty_labeled_cases():
    suite = load_suite("evals/idea_review_cases.json")
    assert len(suite.cases) >= 20
    assert {case.expected_idea_type for case in suite.cases} == {
        "opinion",
        "range",
        "forward",
    }


def test_retrieval_threshold_is_calibrated_at_point_three():
    report = evaluate_retrieval(
        load_suite("evals/retrieval_relevance_cases.json"), threshold=0.3
    )
    assert report.threshold == 0.3 and report.labeled_case_count >= 20


def test_demo_model_passes_required_eval_thresholds():
    report = run_all_evals(build_demo_agents())
    assert report.contract_pass_rate == 1.0
    assert report.behavior_pass_rate >= 0.90
    assert report.metadata.prompt_versions
    assert report.metadata.model_profiles
    assert report.metadata.repetitions >= 1
    assert report.metadata.run_at.tzinfo is not None
