"""Single-use localhost panel that writes `.env`.

Deliberately isolated from the FastAPI app: it never touches the database, never
starts a worker, and exits as soon as the configuration is written. Security
posture:

- bound to 127.0.0.1 on an ephemeral port;
- every request must carry a one-time token;
- `Host` and `Origin` are validated to block DNS-rebinding and cross-site POSTs;
- stored secrets are only ever returned masked;
- request lines and bodies are not logged.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from research_mentor.setup_wizard.apply import build_updates, current_config
from research_mentor.setup_wizard.catalog import catalog
from research_mentor.setup_wizard.env_file import (
    env_path,
    read_env,
    repo_root,
    resolve_secret,
    write_env,
)
from research_mentor.setup_wizard.models import ProbeRequest, SaveRequest
from research_mentor.setup_wizard.probe import probe_slot


PANEL_DIR = Path(__file__).parent / "panel"
MAX_BODY_BYTES = 256 * 1024
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})

_FRONTEND_STYLES = ("tokens.css", "global.css")
_STYLE_FALLBACK = """:root {
  color-scheme: light;
  --bg: #f8efe6; --surface: #fffaf4; --surface-2: #f3e6d8;
  --fill-quiet: rgb(226 90 50 / 10%); --fill-hover: rgb(226 90 50 / 16%);
  --text-1: #2a1d18; --text-2: #6f564c; --text-3: #b39486;
  --separator: rgb(198 90 46 / 10%); --separator-strong: rgb(198 90 46 / 18%);
  --accent: #e25a32; --accent-strong: #c94a28;
  --accent-tint: rgb(226 90 50 / 12%); --on-accent: #fffaf4;
  --adopted: #2bbbad; --danger: #f25070;
  --font-ui: "Figtree", "Avenir Next", "PingFang SC", "Microsoft YaHei UI", sans-serif;
  --font-data: ui-monospace, "SF Mono", Consolas, monospace;
  --radius-card: 1.25rem; --radius-input: 0.9rem; --radius-small: 0.7rem;
  --radius-pill: 999px;
  --shadow-1: 0 10px 24px rgb(198 90 46 / 7%);
  --shadow-2: 0 16px 36px rgb(122 99 232 / 12%);
  --ease-mac: cubic-bezier(0.32, 0.72, 0, 1);
  --focus-ring: 0 0 0 4px rgb(226 90 50 / 28%);
}
html[data-theme="dark"] {
  color-scheme: dark;
  --bg: #14111c; --surface: #211b2c; --surface-2: #2c243a;
  --fill-quiet: rgb(255 147 108 / 10%); --fill-hover: rgb(255 147 108 / 16%);
  --text-1: #f6efe7; --text-2: #cbb8ab; --text-3: #8e7b72;
  --separator: rgb(246 239 231 / 10%); --separator-strong: rgb(246 239 231 / 16%);
  --accent: #ff936c; --accent-strong: #ffb08a;
  --accent-tint: rgb(255 147 108 / 16%); --on-accent: #2a1d18;
  --adopted: #5ee0c5; --danger: #ff7b93;
  --shadow-1: 0 12px 28px rgb(0 0 0 / 28%);
  --shadow-2: 0 18px 40px rgb(122 99 232 / 22%);
  --focus-ring: 0 0 0 4px rgb(255 147 108 / 30%);
}
* { box-sizing: border-box; }
button, input, textarea, select { font: inherit; }
button { border: 0; background: none; color: inherit; cursor: pointer; }
button:disabled { cursor: default; opacity: 0.45; }
a:focus-visible, button:focus-visible, input:focus-visible,
select:focus-visible { outline: none; box-shadow: var(--focus-ring); }
"""

_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
}


def app_styles() -> str:
    """Reuse the React app's design tokens so the panel matches the product."""
    styles_dir = repo_root() / "frontend" / "src" / "styles"
    collected: list[str] = []
    for name in _FRONTEND_STYLES:
        candidate = styles_dir / name
        if candidate.is_file():
            collected.append(candidate.read_text(encoding="utf-8"))
    if collected:
        return "\n".join(collected)
    return _STYLE_FALLBACK


@dataclass(slots=True)
class WizardState:
    token: str
    # 目标文件显式注入：handler 绝不自行推断路径，避免测试写到真实 .env。
    env_file: Path
    finished: threading.Event = field(default_factory=threading.Event)
    written_to: str | None = None


class _Handler(BaseHTTPRequestHandler):
    server_version = "rigora-setup"
    state: WizardState
    protocol_version = "HTTP/1.1"

    # 请求行里带 token，绝不进日志。
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    # --- security helpers -------------------------------------------------

    def _host_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        name = host.rsplit(":", 1)[0].strip("[]") if host else ""
        return name in _ALLOWED_HOSTS

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urlparse(origin)
        return (
            parsed.scheme == "http"
            and parsed.hostname in _ALLOWED_HOSTS
            and parsed.port == self.server.server_address[1]
        )

    def _token_ok(self, query: dict[str, list[str]]) -> bool:
        supplied = self.headers.get("X-Rigora-Setup-Token")
        if supplied is None:
            values = query.get("t")
            supplied = values[0] if values else None
        if supplied is None:
            return False
        return secrets.compare_digest(supplied, self.state.token)

    # --- response helpers -------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("请求体大小不合法")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return payload

    # --- routing ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self._host_allowed():
            self._error(400, "非法 Host")
            return
        if not self._token_ok(query):
            self._error(403, "缺少或错误的一次性 token，请使用终端打印的完整地址。")
            return

        route = parsed.path
        if route in {"/", "/index.html"}:
            self._serve_panel()
            return
        if route == "/assets/app.css":
            self._send(200, app_styles().encode("utf-8"), _CONTENT_TYPES[".css"])
            return
        if route.startswith("/assets/"):
            self._serve_asset(route[len("/assets/") :])
            return
        if route == "/api/catalog":
            self._json(200, catalog())
            return
        if route == "/api/current":
            path = self.state.env_file
            self._json(200, current_config(read_env(path), path).model_dump())
            return
        self._error(404, "未知路径")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if not self._host_allowed():
            self._error(400, "非法 Host")
            return
        if not self._origin_allowed():
            self._error(403, "非法 Origin")
            return
        if not self._token_ok(query):
            self._error(403, "缺少或错误的一次性 token")
            return

        try:
            payload = self._read_json()
        except (ValueError, UnicodeDecodeError):
            self._error(400, "请求体不是合法 JSON")
            return

        if parsed.path == "/api/probe":
            self._handle_probe(payload)
            return
        if parsed.path == "/api/save":
            self._handle_save(payload)
            return
        self._error(404, "未知路径")

    # --- handlers ---------------------------------------------------------

    def _serve_panel(self) -> None:
        template = (PANEL_DIR / "index.html").read_text(encoding="utf-8")
        html = template.replace("__SETUP_TOKEN__", self.state.token)
        self._send(200, html.encode("utf-8"), _CONTENT_TYPES[".html"])

    def _serve_asset(self, name: str) -> None:
        if "/" in name or "\\" in name or name.startswith("."):
            self._error(400, "非法资源名")
            return
        candidate = PANEL_DIR / name
        if not candidate.is_file():
            self._error(404, "资源不存在")
            return
        content_type = _CONTENT_TYPES.get(
            candidate.suffix, "application/octet-stream"
        )
        self._send(200, candidate.read_bytes(), content_type)

    def _handle_probe(self, payload: dict[str, Any]) -> None:
        try:
            request = ProbeRequest.model_validate(payload)
        except ValidationError as error:
            self._error(400, _first_error(error))
            return
        existing = read_env(self.state.env_file)
        key = resolve_secret(
            request.api_key,
            existing=existing,
            key=f"{request.slot.upper()}_API_KEY",
        )
        self._json(200, probe_slot(request, api_key=key).model_dump())

    def _handle_save(self, payload: dict[str, Any]) -> None:
        try:
            request = SaveRequest.model_validate(payload)
        except ValidationError as error:
            self._error(400, _first_error(error))
            return
        path = self.state.env_file
        existing = read_env(path)
        try:
            updates = build_updates(request, existing)
        except ValueError as error:
            self._error(400, str(error))
            return
        written = write_env(updates, path=path)
        self.state.written_to = str(written)
        summary = current_config(read_env(written), written)
        self._json(
            200,
            {
                "env_path": str(written),
                "parallel_paths": request.parallel_path_count(),
                "current": summary.model_dump(),
            },
        )
        self.state.finished.set()


def _first_error(error: ValidationError) -> str:
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", "参数不合法"))
        return f"{location}: {message}" if location else message
    return "参数不合法"


def build_server(state: WizardState, *, port: int = 0) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (_Handler,), {"state": state})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    return server


def new_state(*, env_file: Path | None = None) -> WizardState:
    return WizardState(
        token=secrets.token_urlsafe(32),
        env_file=env_file if env_file is not None else env_path(),
    )
