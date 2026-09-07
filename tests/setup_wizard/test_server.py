import json
import threading
import urllib.error
import urllib.request

import pytest

from research_mentor.config import ALL_AGENTS, PANEL_SLOTS
from research_mentor.setup_wizard.models import EXCLUSIVE_AGENTS
from research_mentor.setup_wizard.server import (
    app_styles,
    build_server,
    new_state,
)


@pytest.fixture
def panel(tmp_path):
    target = tmp_path / ".env"
    target.write_text("RESEARCH_MENTOR_UPLOAD_ROOT=./data/uploads\n", encoding="utf-8")

    # 目标文件必须显式注入，handler 不允许自行解析仓库路径。
    state = new_state(env_file=target)
    server = build_server(state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield {
            "state": state,
            "base": f"http://127.0.0.1:{port}",
            "token": state.token,
            "env": target,
            "port": port,
        }
    finally:
        server.shutdown()
        server.server_close()


def _request(panel, path, *, method="GET", body=None, headers=None, token=True):
    url = f"{panel['base']}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("X-Rigora-Setup-Token", panel["token"])
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, {"raw": raw}


def _payload(slot="qwen"):
    return {
        "slots": [
            {
                "slot": slot,
                "api_key": "sk-panel-test",
                "base_url": "https://api.example/v1",
                "model": "qwen3-coder-plus",
                "api_style": "chat_completions",
            }
        ],
        "assignments": {agent: [slot] for agent in EXCLUSIVE_AGENTS},
        "pairs": [{"plan": slot, "check": slot}],
        "high_cross": "ad",
        "optional": {
            "openalex_api_key": "oa-panel-test",
            "hf_token": "",
            "hf_endpoint": "mirror",
            "database_url": "",
            "reranker_backend": "auto",
        },
    }


def test_requests_without_token_are_refused(panel):
    status, body = _request(panel, "/api/catalog", token=False)

    assert status == 403
    assert "token" in body["error"]


def test_wrong_token_is_refused(panel):
    status, _ = _request(
        panel,
        "/api/catalog",
        headers={"X-Rigora-Setup-Token": "not-the-token"},
        token=False,
    )

    assert status == 403


def test_foreign_host_header_is_refused(panel):
    status, body = _request(panel, "/api/catalog", headers={"Host": "evil.example"})

    assert status == 400
    assert body["error"] == "非法 Host"


def test_cross_site_origin_is_refused_on_post(panel):
    status, body = _request(
        panel,
        "/api/save",
        method="POST",
        body=_payload(),
        headers={"Origin": "https://evil.example"},
    )

    assert status == 403
    assert body["error"] == "非法 Origin"
    assert "sk-panel-test" not in panel["env"].read_text(encoding="utf-8")


def test_catalog_exposes_agents_vendors_and_optional_dependencies(panel):
    status, body = _request(panel, "/api/catalog")

    assert status == 200
    assert [item["name"] for item in body["agents"]] == list(ALL_AGENTS)
    assert body["agent_order"] == list(ALL_AGENTS)
    assert {item["slot"] for item in body["vendors"]} == set(PANEL_SLOTS)
    assert {item["key"] for item in body["optional"]} == {
        "openalex",
        "reranker",
        "hf_token",
        "database",
    }
    assert [mode["paths"] for mode in body["plan_modes"]] == [1, 2, 3]
    assert body["max_pairs"] == 3
    for vendor in body["vendors"]:
        assert vendor["default_model"]
        assert vendor["default_base_url"].startswith("http")
    for agent in body["agents"]:
        assert "qwen3.8-max" not in agent["recommended"]
        assert "gpt-5.6-sol" not in agent["recommended"]


def test_current_never_returns_stored_secrets_in_clear_text(panel):
    panel["env"].write_text(
        "RESEARCH_MENTOR_QWEN_API_KEY=sk-should-stay-hidden\n",
        encoding="utf-8",
    )

    status, body = _request(panel, "/api/current")

    assert status == 200
    assert "sk-should-stay-hidden" not in json.dumps(body, ensure_ascii=False)
    qwen = next(item for item in body["slots"] if item["slot"] == "qwen")
    assert qwen["has_key"] is True
    assert qwen["masked_key"]


def test_save_writes_env_merges_and_finishes(panel):
    status, body = _request(panel, "/api/save", method="POST", body=_payload())

    assert status == 200
    assert body["parallel_paths"] == 1
    text = panel["env"].read_text(encoding="utf-8")
    assert "RESEARCH_MENTOR_QWEN_API_KEY=sk-panel-test" in text
    assert "RESEARCH_MENTOR_MODEL_PROVIDER=unset" in text
    assert "RESEARCH_MENTOR_UPLOAD_ROOT=./data/uploads" in text
    assert set(
        text.split("RESEARCH_MENTOR_QWEN_AGENTS=")[1].splitlines()[0].split(",")
    ) == set(ALL_AGENTS)
    assert "RESEARCH_MENTOR_PLAN_CHECK_PAIRS=qwen>qwen" in text
    assert "sk-panel-test" not in json.dumps(body, ensure_ascii=False)
    assert panel["state"].finished.wait(timeout=5) is True


def test_save_rejects_incomplete_agent_coverage(panel):
    payload = _payload()
    del payload["assignments"]["complete"]

    status, body = _request(panel, "/api/save", method="POST", body=payload)

    assert status == 400
    assert "未分配模型" in body["error"]
    assert "sk-panel-test" not in panel["env"].read_text(encoding="utf-8")
    assert panel["state"].finished.is_set() is False


def test_save_requires_at_least_one_provider(panel):
    payload = _payload()
    payload["slots"] = []

    status, body = _request(panel, "/api/save", method="POST", body=payload)

    assert status == 400
    assert panel["state"].finished.is_set() is False


def test_unknown_paths_and_asset_traversal_are_refused(panel):
    assert _request(panel, "/api/nope")[0] == 404
    assert _request(panel, "/assets/..%2Fserver.py")[0] in {400, 404}


def test_panel_page_and_assets_are_served_with_no_store(panel):
    url = f"{panel['base']}/?t={panel['token']}"
    with urllib.request.urlopen(url, timeout=10) as response:
        html = response.read().decode("utf-8")
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    assert panel["token"] in html
    assert "__SETUP_TOKEN__" not in html

    for asset in ("panel.css", "panel.js", "app.css"):
        with urllib.request.urlopen(
            f"{panel['base']}/assets/{asset}?t={panel['token']}", timeout=10
        ) as response:
            assert response.status == 200
            assert response.read()


def test_app_styles_reuse_frontend_tokens():
    styles = app_styles()

    assert "--accent" in styles
    assert 'html[data-theme="dark"]' in styles
