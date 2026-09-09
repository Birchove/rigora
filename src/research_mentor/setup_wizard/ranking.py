"""Load the onboarding model ranking list.

The JSON next to this module is the source of truth for Agent 推荐型号.
Edit that file when the public ranking changes; do not hard-code picks here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RANKING_PATH = Path(__file__).with_name("model_ranking.json")


def load_ranking() -> dict[str, Any]:
    return json.loads(RANKING_PATH.read_text(encoding="utf-8"))


def recommended_models(agent: str) -> list[dict[str, Any]]:
    data = load_ranking()
    by_id = {item["id"]: item for item in data["models"] if item.get("id")}
    picks = data["agent_picks"].get(agent)
    if not picks:
        raise KeyError(f"model_ranking.json 缺少 {agent} 的推荐")
    resolved: list[dict[str, Any]] = []
    for model_id in picks:
        item = by_id.get(model_id)
        if item is None:
            raise KeyError(f"model_ranking.json 的 {agent} 引用了未知 id: {model_id}")
        resolved.append(
            {
                "id": item["id"],
                "label": item["name"],
                "score": item["score"],
                "org": item["org"],
            }
        )
    return resolved
