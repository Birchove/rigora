"""Minimal live credential check for one provider slot.

Sends the cheapest possible request so the panel can tell "key works" from
"address wrong" before anything is written. The key is never logged and any
provider text is redacted before it reaches the panel.
"""

from __future__ import annotations

import httpx

from research_mentor.config import vendor_http_headers
from research_mentor.runtime_logging import redact_secrets
from research_mentor.setup_wizard.models import ProbeRequest, ProbeResult


PROBE_TIMEOUT_SECONDS = 25.0
_MAX_MESSAGE_CHARS = 240


def _payload(request: ProbeRequest) -> tuple[str, dict[str, object]]:
    model = request.model.strip()
    if request.api_style == "responses":
        return "responses", {
            "model": model,
            "input": "ping",
            "max_output_tokens": 16,
        }
    return "chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }


def _provider_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return redact_secrets(text)[:_MAX_MESSAGE_CHARS]
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        detail = str(error.get("message") or error)
    elif isinstance(error, str):
        detail = error
    else:
        detail = str(body)
    return redact_secrets(detail)[:_MAX_MESSAGE_CHARS]


def _interpret(response: httpx.Response) -> ProbeResult:
    if response.is_success:
        return ProbeResult(ok=True, message="连接成功，key 与模型名都可用。")
    detail = _provider_message(response)
    status = response.status_code
    if status in {401, 403}:
        return ProbeResult(ok=False, message=f"凭据被拒绝（{status}）：{detail}")
    if status == 404:
        return ProbeResult(
            ok=False,
            message=(
                f"接口不存在（404）：请检查 base_url 是否填到 /v1 一级，"
                f"以及模型名是否正确。{detail}"
            ),
        )
    if status == 429:
        return ProbeResult(
            ok=False,
            message=f"被限流（429），稍后重试即可确认。{detail}",
        )
    return ProbeResult(ok=False, message=f"provider 返回 {status}：{detail}")


def _is_windows_access_denied(error: BaseException) -> bool:
    text = str(error)
    return "10013" in text or "WinError 10013" in text or "WSAEACCES" in text


def _connect_error_message(error: BaseException) -> str:
    if _is_windows_access_denied(error):
        return (
            "Windows 拒绝了这次出站连接（WinError 10013）。"
            "常见原因是系统代理/VPN 指向了一个被 Hyper-V 保留的本地端口，"
            "或防火墙拦了 Python。请关掉无效的 HTTP_PROXY / HTTPS_PROXY，"
            "或在防火墙里允许当前 Python。"
        )
    return "无法连接：" + redact_secrets(str(error))[:_MAX_MESSAGE_CHARS]


def _http_client(*, trust_env: bool) -> httpx.Client:
    # 不要绑 local_address=0.0.0.0：Windows 上 Hyper-V 保留端口时 bind 会直接
    # 变成 WinError 10013，所有厂商的测试连接都会失败。
    return httpx.Client(
        timeout=PROBE_TIMEOUT_SECONDS,
        trust_env=trust_env,
    )


def probe_slot(request: ProbeRequest, *, api_key: str | None) -> ProbeResult:
    if not api_key:
        return ProbeResult(ok=False, message="还没有可用的 API key。")
    base_url = request.base_url.strip().rstrip("/")
    if not base_url:
        return ProbeResult(ok=False, message="缺少 base_url，无法发起测试。")
    if not request.model.strip():
        return ProbeResult(ok=False, message="缺少模型名，无法发起测试。")

    suffix, body = _payload(request)
    last_error: BaseException | None = None
    timed_out = False
    # 先直连，再走系统代理。坏掉的 HTTP_PROXY 在 Windows 上常表现为 10013。
    for use_env_proxy in (False, True):
        try:
            with _http_client(trust_env=use_env_proxy) as client:
                response = client.post(
                    f"{base_url}/{suffix}",
                    headers=vendor_http_headers(base_url, api_key),
                    json=body,
                )
            return _interpret(response)
        except httpx.TimeoutException:
            timed_out = True
            continue
        except (httpx.HTTPError, OSError) as error:
            last_error = error
            continue
    if last_error is not None:
        return ProbeResult(ok=False, message=_connect_error_message(last_error))
    if timed_out:
        return ProbeResult(
            ok=False,
            message="请求超时。检查网络，或确认这个地址是否需要代理。",
        )
    return ProbeResult(ok=False, message="无法连接。")
