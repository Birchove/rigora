import pytest
from pydantic import ValidationError

from research_mentor.config import Settings
from research_mentor.setup_wizard.apply import build_updates, current_config
from research_mentor.setup_wizard.env_file import KEEP_SENTINEL
from research_mentor.setup_wizard.models import (
    EXCLUSIVE_AGENTS,
    OptionalConfig,
    PlanCheckPair,
    SaveRequest,
    SlotConfig,
)


def _slot(slot: str, **overrides) -> SlotConfig:
    payload = {
        "slot": slot,
        "api_key": "sk-test",
        "base_url": "https://api.example/v1",
        "model": f"{slot}-model",
        "api_style": "chat_completions",
    }
    payload.update(overrides)
    return SlotConfig(**payload)


def _all_to(slot: str) -> dict[str, list[str]]:
    return {agent: [slot] for agent in EXCLUSIVE_AGENTS}


def _pair(plan: str, check: str) -> PlanCheckPair:
    return PlanCheckPair(plan=plan, check=check)


def _request(*slots: str, pairs=None, **overrides) -> SaveRequest:
    first = slots[0]
    payload = {
        "slots": [_slot(name) for name in slots],
        "assignments": _all_to(first),
        "pairs": pairs if pairs is not None else [_pair(first, first)],
    }
    payload.update(overrides)
    return SaveRequest(**payload)


def test_single_slot_covers_every_agent():
    updates = build_updates(_request("qwen"), {})

    assert updates["QWEN_API_KEY"] == "sk-test"
    assert updates["QWEN_MODEL"] == "qwen-model"
    assert updates["MODEL_PROVIDER"] == "unset"
    assert set(updates["QWEN_AGENTS"].split(",")) == {
        "idea_review",
        "plan_loop",
        "key_insight_check",
        "working_qa",
        "complete",
    }
    assert updates["PLAN_CHECK_PAIRS"] == "qwen>qwen"


def test_updates_survive_a_settings_round_trip_with_full_coverage():
    updates = build_updates(_request("qwen"), {})

    settings = Settings(
        qwen_api_key=updates["QWEN_API_KEY"],
        qwen_base_url=updates["QWEN_BASE_URL"],
        qwen_model=updates["QWEN_MODEL"],
        qwen_api_style=updates["QWEN_API_STYLE"],
        qwen_agents=updates["QWEN_AGENTS"],
        plan_check_pairs_spec=updates["PLAN_CHECK_PAIRS"],
        plan_check_high_cross=updates["PLAN_CHECK_HIGH_CROSS"],
    )

    assert settings.unrouted_agents() == ()
    assert settings.configured_slots() == ("qwen",)
    assert settings.plan_check_pairs() == (("qwen-model", "qwen-model"),)


def test_two_pairs_default_to_dual_mode_without_a_crossed_third():
    request = _request(
        "qwen",
        "glm",
        "deepseek",
        "chatgpt",
        pairs=[_pair("qwen", "glm"), _pair("deepseek", "chatgpt")],
    )

    assert request.parallel_path_count() == 2
    assert request.available_modes() == ["low", "mid"]


def test_two_pairs_round_trip_into_three_runtime_paths():
    request = _request(
        "qwen",
        "glm",
        "deepseek",
        "chatgpt",
        pairs=[_pair("qwen", "glm"), _pair("deepseek", "chatgpt")],
        high_cross="ad",
    )
    updates = build_updates(request, {})

    assert updates["PLAN_CHECK_PAIRS"] == "qwen>glm,deepseek>chatgpt"
    assert request.parallel_path_count() == 3
    assert request.available_modes() == ["low", "mid", "high"]

    settings = Settings(
        **{
            f"{slot}_{field}": updates[f"{slot.upper()}_{field.upper()}"]
            for slot in ("qwen", "glm", "deepseek", "chatgpt")
            for field in ("api_key", "base_url", "model", "api_style", "agents")
        },
        plan_check_pairs_spec=updates["PLAN_CHECK_PAIRS"],
        plan_check_high_cross=updates["PLAN_CHECK_HIGH_CROSS"],
    )

    assert settings.plan_check_pairs() == (
        ("qwen-model", "glm-model"),
        ("deepseek-model", "chatgpt-model"),
        ("qwen-model", "chatgpt-model"),
    )


def test_one_pair_leaves_only_the_single_path_mode():
    request = _request("qwen", "glm", pairs=[_pair("qwen", "glm")])

    assert request.parallel_path_count() == 1
    assert request.available_modes() == ["low"]


def test_unselected_slot_stops_serving_agents_but_keeps_its_key():
    existing = {"GLM_API_KEY": "sk-old-glm", "GLM_AGENTS": "complete"}

    updates = build_updates(_request("qwen"), existing)

    assert updates["GLM_AGENTS"] is None
    assert "GLM_API_KEY" not in updates


def test_blank_key_reuses_stored_secret_via_sentinel():
    existing = {"QWEN_API_KEY": "sk-stored"}
    request = SaveRequest(
        slots=[_slot("qwen", api_key=KEEP_SENTINEL)],
        assignments=_all_to("qwen"),
        pairs=[_pair("qwen", "qwen")],
    )

    updates = build_updates(request, existing)

    assert updates["QWEN_API_KEY"] == "sk-stored"


def test_missing_key_is_rejected():
    request = SaveRequest(
        slots=[_slot("qwen", api_key="")],
        assignments=_all_to("qwen"),
        pairs=[_pair("qwen", "qwen")],
    )

    with pytest.raises(ValueError, match="缺少 API key"):
        build_updates(request, {})


def test_panel_does_not_accept_the_second_chatgpt_slot():
    with pytest.raises(ValidationError, match="面板不支持"):
        SaveRequest(
            slots=[_slot("chatgpt_2")],
            assignments=_all_to("chatgpt_2"),
            pairs=[_pair("chatgpt_2", "chatgpt_2")],
        )


def test_exclusive_agent_cannot_take_two_slots():
    assignments = _all_to("qwen")
    assignments["idea_review"] = ["qwen", "glm"]

    with pytest.raises(ValidationError, match="只能由一个供应商承担"):
        SaveRequest(
            slots=[_slot("qwen"), _slot("glm")],
            assignments=assignments,
            pairs=[_pair("qwen", "glm")],
        )


def test_unassigned_agent_is_rejected():
    assignments = _all_to("qwen")
    del assignments["complete"]

    with pytest.raises(ValidationError, match="未分配模型"):
        SaveRequest(
            slots=[_slot("qwen")],
            assignments=assignments,
            pairs=[_pair("qwen", "qwen")],
        )


def test_shared_agents_must_not_come_through_assignments():
    assignments = _all_to("qwen")
    assignments["plan_loop"] = ["qwen"]

    with pytest.raises(ValidationError, match="通过 pairs 配置"):
        SaveRequest(
            slots=[_slot("qwen")],
            assignments=assignments,
            pairs=[_pair("qwen", "qwen")],
        )


def test_assignment_to_unconfigured_slot_is_rejected():
    assignments = _all_to("qwen")
    assignments["complete"] = ["glm"]

    with pytest.raises(ValidationError, match="未配置的供应商"):
        SaveRequest(
            slots=[_slot("qwen")],
            assignments=assignments,
            pairs=[_pair("qwen", "qwen")],
        )


def test_pair_to_unconfigured_slot_is_rejected():
    with pytest.raises(ValidationError, match="配对引用了未配置的供应商"):
        SaveRequest(
            slots=[_slot("qwen")],
            assignments=_all_to("qwen"),
            pairs=[_pair("qwen", "glm")],
        )


def test_duplicate_pair_is_rejected():
    with pytest.raises(ValidationError, match="重复"):
        SaveRequest(
            slots=[_slot("qwen"), _slot("glm")],
            assignments=_all_to("qwen"),
            pairs=[_pair("qwen", "glm"), _pair("qwen", "glm")],
        )


def test_more_than_three_pairs_is_rejected():
    with pytest.raises(ValidationError):
        SaveRequest(
            slots=[_slot("qwen"), _slot("glm")],
            assignments=_all_to("qwen"),
            pairs=[
                _pair("qwen", "glm"),
                _pair("glm", "qwen"),
                _pair("qwen", "qwen"),
                _pair("glm", "glm"),
            ],
        )


def test_pairs_drive_the_shared_agent_assignments():
    request = _request(
        "qwen", "glm", pairs=[_pair("qwen", "glm"), _pair("glm", "qwen")]
    )

    agents = request.slot_agents()

    assert set(agents["qwen"]) >= {"plan_loop", "key_insight_check"}
    assert set(agents["glm"]) == {"plan_loop", "key_insight_check"}
    # 顺序按 ALL_AGENTS 归一，落库后 Settings 才好读。
    assert agents["glm"] == ["plan_loop", "key_insight_check"]


def test_current_config_masks_every_secret(tmp_path):
    path = tmp_path / ".env"
    existing = {
        "QWEN_API_KEY": "sk-abcdefghijklmnop",
        "QWEN_AGENTS": "idea_review, plan_loop",
        "OPENALEX_API_KEY": "oa-abcdefghijklmnop",
        "HF_TOKEN": "hf-abcdefghijklmnop",
        "DATABASE_URL": "postgresql+asyncpg://user:secretpw@host/db",
        "PLAN_CHECK_PAIRS": "qwen>glm",
        "PLAN_CHECK_HIGH_CROSS": "bc",
    }

    snapshot = current_config(existing, path)
    serialized = snapshot.model_dump_json()

    for secret in ("sk-abcdefghijklmnop", "oa-abcdefghijklmnop", "hf-abcdefghijklmnop"):
        assert secret not in serialized
    assert "secretpw" not in serialized

    qwen = next(item for item in snapshot.slots if item.slot == "qwen")
    assert qwen.has_key is True
    assert qwen.agents == ["idea_review", "plan_loop"]
    assert snapshot.optional.openalex_has_key is True
    assert snapshot.pairs == [PlanCheckPair(plan="qwen", check="glm")]
    assert snapshot.high_cross == "bc"
    assert snapshot.env_exists is False


def test_current_config_drops_pairs_the_panel_cannot_render(tmp_path):
    snapshot = current_config(
        {"PLAN_CHECK_PAIRS": "chatgpt>chatgpt_2,qwen>glm"}, tmp_path / ".env"
    )

    assert snapshot.pairs == [PlanCheckPair(plan="qwen", check="glm")]


def test_current_config_survives_a_malformed_pair_spec(tmp_path):
    snapshot = current_config({"PLAN_CHECK_PAIRS": "nonsense"}, tmp_path / ".env")

    assert snapshot.pairs == []


def test_optional_secrets_default_to_removal():
    request = _request("qwen", optional=OptionalConfig())

    updates = build_updates(request, {})

    assert updates["OPENALEX_API_KEY"] is None
    assert updates["HF_TOKEN"] is None
    assert updates["DATABASE_URL"] is None
    assert updates["RERANKER_BACKEND"] == "auto"
    # demo 预置项已经从面板移除，不再由 wizard 改写。
    assert "DEMO_MODE" not in updates
