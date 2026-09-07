import httpx

from research_mentor.setup_wizard.models import ProbeRequest
from research_mentor.setup_wizard.probe import probe_slot


class _FailingClient:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def post(self, *_args, **_kwargs):
        raise httpx.ConnectError(
            "[WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。"
        )


def test_probe_explains_windows_socket_access_denied(monkeypatch):
    monkeypatch.setattr(
        "research_mentor.setup_wizard.probe._http_client",
        lambda **_kwargs: _FailingClient(),
    )

    result = probe_slot(
        ProbeRequest(
            slot="qwen",
            api_key="sk-test",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen3-coder-plus",
            api_style="chat_completions",
        ),
        api_key="sk-test",
    )

    assert result.ok is False
    assert "WinError 10013" in result.message
    assert "HTTP_PROXY" in result.message
    assert "sk-test" not in result.message


def test_probe_claude_sends_anthropic_headers(monkeypatch):
    seen = {}

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, headers, json):
            seen["url"] = url
            seen["headers"] = headers
            request = httpx.Request("POST", url)
            return httpx.Response(200, json={"id": "ok"}, request=request)

    monkeypatch.setattr(
        "research_mentor.setup_wizard.probe._http_client",
        lambda **_kwargs: _Client(),
    )

    result = probe_slot(
        ProbeRequest(
            slot="claude",
            api_key="sk-ant-test",
            base_url="https://api.anthropic.com/v1",
            model="claude-haiku-4.5",
            api_style="chat_completions",
        ),
        api_key="sk-ant-test",
    )

    assert result.ok is True
    assert seen["url"] == "https://api.anthropic.com/v1/chat/completions"
    assert seen["headers"]["x-api-key"] == "sk-ant-test"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
