"""Read, merge and atomically write the repository `.env`.

Rules enforced here:
- only wizard-managed keys are touched; comments and unrelated settings survive;
- secrets are never returned in clear text, only masked for display;
- the file is written atomically with owner-only permissions.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from research_mentor.config import SLOTS


ENV_PREFIX = "RESEARCH_MENTOR_"
# 面板回传这个哨兵值表示「保留 .env 里已有的密钥」，明文不出后端。
KEEP_SENTINEL = "__RIGORA_KEEP__"
PLACEHOLDERS = frozenset({"xxxx", "XXXX"})

_SLOT_SUFFIXES = ("API_KEY", "BASE_URL", "MODEL", "API_STYLE", "AGENTS")

SECRET_KEYS: frozenset[str] = frozenset(
    {f"{slot.upper()}_API_KEY" for slot in SLOTS}
    | {"OPENALEX_API_KEY", "HF_TOKEN", "MODEL_API_KEY", "DATABASE_URL"}
)

MANAGED_KEYS: tuple[str, ...] = (
    *(
        f"{slot.upper()}_{suffix}"
        for slot in SLOTS
        for suffix in _SLOT_SUFFIXES
    ),
    "MODEL_PROVIDER",
    "PLAN_CHECK_PAIRS",
    "PLAN_CHECK_HIGH_CROSS",
    "OPENALEX_API_KEY",
    "DATABASE_URL",
    "RERANKER_BACKEND",
    "HF_ENDPOINT",
    "HF_TOKEN",
)


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


def env_path() -> Path:
    return repo_root() / ".env"


def mask(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= 8:
        return "•" * len(trimmed)
    return f"{trimmed[:3]}{'•' * 6}{trimmed[-4:]}"


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _quote(value: str) -> str:
    if value and (value != value.strip() or "#" in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def parse_env(text: str) -> dict[str, str]:
    """Map unprefixed managed names to their raw values."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        raw_key, _, raw_value = stripped.partition("=")
        key = raw_key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key.startswith(ENV_PREFIX):
            continue
        values[key[len(ENV_PREFIX) :].upper()] = _unquote(raw_value)
    return values


def read_env(path: Path | None = None) -> dict[str, str]:
    target = path if path is not None else env_path()
    if not target.is_file():
        return {}
    return parse_env(target.read_text(encoding="utf-8"))


def usable(value: str | None) -> bool:
    if value is None:
        return False
    trimmed = value.strip()
    return bool(trimmed) and trimmed not in PLACEHOLDERS


@dataclass(frozen=True, slots=True)
class SecretView:
    """What the panel is allowed to know about an existing secret."""

    has_value: bool
    masked: str


def secret_view(values: dict[str, str], key: str) -> SecretView:
    raw = values.get(key)
    if not usable(raw):
        return SecretView(has_value=False, masked="")
    assert raw is not None
    return SecretView(has_value=True, masked=mask(raw))


def resolve_secret(
    submitted: str | None,
    *,
    existing: dict[str, str],
    key: str,
) -> str | None:
    """Turn a submitted secret into the value to persist.

    `KEEP_SENTINEL` and empty input both mean "do not change", which lets the
    panel prefill masked values without ever receiving the clear text.
    """
    if submitted is None:
        return None
    text = submitted.strip()
    if text == KEEP_SENTINEL:
        current = existing.get(key)
        return current if usable(current) else None
    if not text or text in PLACEHOLDERS:
        return None
    return text


def merge_lines(existing_text: str, updates: dict[str, str | None]) -> str:
    """Rewrite managed assignments in place, append the rest, keep everything else.

    A `None` value removes the assignment so the runtime default applies again.
    """
    managed = {key.upper() for key in MANAGED_KEYS}
    for key in updates:
        if key.upper() not in managed:
            raise ValueError(f"{key} 不是 wizard 管理的配置项")

    normalized = {key.upper(): value for key, value in updates.items()}
    seen: set[str] = set()
    lines = existing_text.splitlines()
    output: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        raw_key = stripped.partition("=")[0].strip()
        if raw_key.startswith("export "):
            raw_key = raw_key[len("export ") :].strip()
        if not raw_key.startswith(ENV_PREFIX):
            output.append(line)
            continue
        name = raw_key[len(ENV_PREFIX) :].upper()
        if name not in normalized:
            output.append(line)
            continue
        seen.add(name)
        value = normalized[name]
        if value is None:
            continue
        output.append(f"{ENV_PREFIX}{name}={_quote(value)}")

    appended = [
        f"{ENV_PREFIX}{name}={_quote(value)}"
        for name, value in normalized.items()
        if name not in seen and value is not None
    ]
    if appended:
        if output and output[-1].strip():
            output.append("")
        output.append("# 由 rigora-setup 写入")
        output.extend(appended)

    text = "\n".join(output).rstrip("\n")
    return f"{text}\n" if text else ""


def write_env(updates: dict[str, str | None], *, path: Path | None = None) -> Path:
    target = path if path is not None else env_path()
    existing_text = target.read_text(encoding="utf-8") if target.is_file() else ""
    merged = merge_lines(existing_text, updates)

    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=str(target.parent), prefix=".env.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(merged)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return target
