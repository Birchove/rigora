"""Translate panel submissions into `.env` assignments."""

from __future__ import annotations

from pathlib import Path

from research_mentor.config import (
    PANEL_SLOTS,
    SLOTS,
    format_plan_check_spec,
    parse_plan_check_spec,
)
from research_mentor.setup_wizard.env_file import (
    resolve_secret,
    secret_view,
    usable,
)
from research_mentor.setup_wizard.models import (
    CurrentConfig,
    OptionalState,
    PlanCheckPair,
    SaveRequest,
    SlotState,
)


def _optional_text(value: str) -> str | None:
    trimmed = value.strip()
    return trimmed or None


def build_updates(
    request: SaveRequest,
    existing: dict[str, str],
) -> dict[str, str | None]:
    """Managed `.env` assignments for this submission.

    `None` clears an assignment so the runtime default applies again.
    """
    slot_agents = request.slot_agents()
    submitted = {item.slot: item for item in request.slots}
    updates: dict[str, str | None] = {}

    for slot in SLOTS:
        upper = slot.upper()
        config = submitted.get(slot)
        if config is None:
            # 未选中的槽保留已填的 key，但停止承担 Agent。
            updates[f"{upper}_AGENTS"] = None
            continue

        key = resolve_secret(
            config.api_key,
            existing=existing,
            key=f"{upper}_API_KEY",
        )
        if key is None:
            raise ValueError(f"{slot} 缺少 API key")

        updates[f"{upper}_API_KEY"] = key
        updates[f"{upper}_BASE_URL"] = _optional_text(config.base_url)
        updates[f"{upper}_MODEL"] = config.model.strip()
        updates[f"{upper}_API_STYLE"] = config.api_style
        agents = slot_agents.get(slot, [])
        updates[f"{upper}_AGENTS"] = ",".join(agents) if agents else None

    updates["PLAN_CHECK_PAIRS"] = format_plan_check_spec(
        [(pair.plan, pair.check) for pair in request.pairs]
    )
    # 只有恰好 2 对时第三条路才需要交错组合，其余情况写默认值即可。
    updates["PLAN_CHECK_HIGH_CROSS"] = request.high_cross

    options = request.optional
    updates["MODEL_PROVIDER"] = "unset"
    updates["OPENALEX_API_KEY"] = resolve_secret(
        options.openalex_api_key, existing=existing, key="OPENALEX_API_KEY"
    )
    updates["HF_TOKEN"] = resolve_secret(
        options.hf_token, existing=existing, key="HF_TOKEN"
    )
    updates["DATABASE_URL"] = resolve_secret(
        options.database_url, existing=existing, key="DATABASE_URL"
    )
    updates["HF_ENDPOINT"] = _optional_text(options.hf_endpoint)
    updates["RERANKER_BACKEND"] = options.reranker_backend.strip() or "auto"
    return updates


def current_config(existing: dict[str, str], path: Path) -> CurrentConfig:
    """Panel-safe snapshot of the current `.env`; secrets stay masked."""
    slots: list[SlotState] = []
    for slot in SLOTS:
        upper = slot.upper()
        view = secret_view(existing, f"{upper}_API_KEY")
        raw_agents = existing.get(f"{upper}_AGENTS", "")
        slots.append(
            SlotState(
                slot=slot,
                has_key=view.has_value,
                masked_key=view.masked,
                base_url=existing.get(f"{upper}_BASE_URL", ""),
                model=existing.get(f"{upper}_MODEL", ""),
                api_style=existing.get(f"{upper}_API_STYLE", ""),
                agents=[
                    part.strip()
                    for part in raw_agents.replace(";", ",").split(",")
                    if part.strip()
                ],
            )
        )

    openalex = secret_view(existing, "OPENALEX_API_KEY")
    hf = secret_view(existing, "HF_TOKEN")
    database = secret_view(existing, "DATABASE_URL")
    return CurrentConfig(
        env_exists=path.is_file(),
        env_path=str(path),
        slots=slots,
        pairs=_stored_pairs(existing),
        high_cross=(existing.get("PLAN_CHECK_HIGH_CROSS") or "ad").strip().lower(),
        optional=OptionalState(
            openalex_has_key=openalex.has_value,
            openalex_masked=openalex.masked,
            hf_has_token=hf.has_value,
            hf_masked=hf.masked,
            hf_endpoint=existing.get("HF_ENDPOINT", ""),
            database_has_url=database.has_value,
            database_masked=database.masked,
            reranker_backend=existing.get("RERANKER_BACKEND", "auto") or "auto",
        ),
    )


def _stored_pairs(existing: dict[str, str]) -> list[PlanCheckPair]:
    """Read back the saved pairing, ignoring anything the panel cannot render."""
    raw = (existing.get("PLAN_CHECK_PAIRS") or "").strip()
    if not raw:
        return []
    try:
        parsed = parse_plan_check_spec(raw)
    except ValueError:
        return []
    return [
        PlanCheckPair(plan=plan, check=check)
        for plan, check in parsed
        if plan in PANEL_SLOTS and check in PANEL_SLOTS
    ]


def has_any_key(existing: dict[str, str]) -> bool:
    return any(usable(existing.get(f"{slot.upper()}_API_KEY")) for slot in SLOTS)
