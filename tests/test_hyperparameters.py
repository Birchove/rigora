from research_mentor.hyperparameters import (
    CHECK_DIMENSION_FLOORS,
    CHECK_PASS_SCORE,
    SCORE_WEIGHTS,
    SCORING_RULE_VERSION,
    run_config_snapshot,
)


def test_run_config_snapshot_includes_check_floors() -> None:
    snapshot = run_config_snapshot()
    assert snapshot["scoring_rule_version"] == SCORING_RULE_VERSION
    assert snapshot["check_pass_score"] == CHECK_PASS_SCORE
    assert snapshot["check_dimension_floors"] == CHECK_DIMENSION_FLOORS
    assert snapshot["score_weights"] == SCORE_WEIGHTS
    assert snapshot["score_weights"] == {
        "research_fit": 0.30,
        "novelty": 0.30,
        "research_value": 0.20,
        "testability_feasibility": 0.10,
        "evidence_support": 0.10,
    }


def test_dimension_floors_match_requested_check_bounds() -> None:
    assert CHECK_DIMENSION_FLOORS == {
        "research_fit": 3.5,
        "novelty": 3.0,
        "research_value": 3.0,
        "testability_feasibility": 3.0,
        "evidence_support": 2.5,
    }
