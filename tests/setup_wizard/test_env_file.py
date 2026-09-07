import stat

import pytest

from research_mentor.setup_wizard.env_file import (
    KEEP_SENTINEL,
    MANAGED_KEYS,
    SECRET_KEYS,
    mask,
    merge_lines,
    parse_env,
    read_env,
    resolve_secret,
    secret_view,
    usable,
    write_env,
)


def test_parse_env_keeps_only_prefixed_keys_and_strips_quotes():
    values = parse_env(
        "\n".join(
            [
                "# comment",
                "",
                "RESEARCH_MENTOR_QWEN_MODEL=qwen-plus",
                'RESEARCH_MENTOR_QWEN_API_KEY="sk-quoted"',
                "export RESEARCH_MENTOR_GLM_MODEL=glm-4.6",
                "UNRELATED=1",
                "no_equals_sign",
            ]
        )
    )

    assert values == {
        "QWEN_MODEL": "qwen-plus",
        "QWEN_API_KEY": "sk-quoted",
        "GLM_MODEL": "glm-4.6",
    }


def test_mask_never_reveals_full_secret():
    assert mask("sk-abcdefghijklmnop") == "sk-••••••mnop"
    assert mask("short") == "•••••"
    assert mask("   ") == ""


def test_usable_rejects_placeholder_and_blank():
    assert usable("sk-real") is True
    assert usable("xxxx") is False
    assert usable("  ") is False
    assert usable(None) is False


def test_secret_view_hides_value_but_reports_presence():
    view = secret_view({"QWEN_API_KEY": "sk-abcdefghijklmnop"}, "QWEN_API_KEY")

    assert view.has_value is True
    assert "abcdefghijklmnop" not in view.masked

    absent = secret_view({"QWEN_API_KEY": "xxxx"}, "QWEN_API_KEY")
    assert absent.has_value is False
    assert absent.masked == ""


def test_resolve_secret_keeps_existing_on_sentinel_and_blank():
    existing = {"QWEN_API_KEY": "sk-existing"}

    assert resolve_secret(KEEP_SENTINEL, existing=existing, key="QWEN_API_KEY") == (
        "sk-existing"
    )
    assert resolve_secret("", existing=existing, key="QWEN_API_KEY") is None
    assert resolve_secret("sk-new", existing=existing, key="QWEN_API_KEY") == "sk-new"
    assert resolve_secret("xxxx", existing=existing, key="QWEN_API_KEY") is None
    assert (
        resolve_secret(KEEP_SENTINEL, existing={}, key="QWEN_API_KEY") is None
    )


def test_merge_lines_updates_in_place_and_preserves_everything_else():
    original = "\n".join(
        [
            "# --- 千问 Qwen ---",
            "RESEARCH_MENTOR_QWEN_API_KEY=sk-old",
            "RESEARCH_MENTOR_QWEN_MODEL=qwen-plus",
            "",
            "# unrelated block kept verbatim",
            "RESEARCH_MENTOR_UPLOAD_ROOT=./data/uploads",
        ]
    )

    merged = merge_lines(
        original,
        {
            "QWEN_API_KEY": "sk-new",
            "QWEN_MODEL": None,
            "GLM_MODEL": "glm-4.6",
        },
    )

    assert "# --- 千问 Qwen ---" in merged
    assert "RESEARCH_MENTOR_QWEN_API_KEY=sk-new" in merged
    assert "RESEARCH_MENTOR_QWEN_MODEL" not in merged
    assert "# unrelated block kept verbatim" in merged
    assert "RESEARCH_MENTOR_UPLOAD_ROOT=./data/uploads" in merged
    assert "RESEARCH_MENTOR_GLM_MODEL=glm-4.6" in merged


def test_merge_lines_rejects_unmanaged_keys():
    with pytest.raises(ValueError, match="不是 wizard 管理"):
        merge_lines("", {"SOME_OTHER_SETTING": "1"})


def test_write_env_is_atomic_owner_only_and_readable_back(tmp_path):
    target = tmp_path / ".env"
    target.write_text("RESEARCH_MENTOR_RERANKER_BACKEND=lexical\n", encoding="utf-8")

    write_env({"RERANKER_BACKEND": "auto", "QWEN_MODEL": "qwen3-coder-plus"}, path=target)

    assert read_env(target) == {
        "RERANKER_BACKEND": "auto",
        "QWEN_MODEL": "qwen3-coder-plus",
    }
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600
    assert not list(tmp_path.glob(".env.*.tmp"))


def test_write_env_creates_file_when_absent(tmp_path):
    target = tmp_path / ".env"

    write_env({"QWEN_API_KEY": "sk-first"}, path=target)

    assert target.is_file()
    assert read_env(target)["QWEN_API_KEY"] == "sk-first"


def test_every_slot_secret_is_declared_as_secret():
    for key in MANAGED_KEYS:
        if key.endswith("API_KEY") or key in {"HF_TOKEN", "DATABASE_URL"}:
            assert key in SECRET_KEYS
