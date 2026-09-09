from research_mentor.config import ALL_AGENTS
from research_mentor.setup_wizard.ranking import load_ranking, recommended_models


def test_ranking_file_covers_every_agent_with_known_ids():
    data = load_ranking()
    by_id = {item["id"] for item in data["models"] if item.get("id")}

    assert data["as_of"]
    assert set(data["agent_picks"]) == set(ALL_AGENTS)
    for agent, picks in data["agent_picks"].items():
        assert len(picks) == 3
        assert set(picks) <= by_id
        assert recommended_models(agent)[0]["id"] == picks[0]


def test_high_thinking_agents_prefer_stronger_models():
    plan = {item["id"] for item in recommended_models("plan_loop")}
    check = {item["id"] for item in recommended_models("key_insight_check")}
    qa = {item["id"] for item in recommended_models("working_qa")}

    assert "claude-fable-5.1" in plan
    assert "gpt-5.6-sol" in check
    assert "gpt-5.6-luna" in qa
    assert plan.isdisjoint(check)
