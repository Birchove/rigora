"""Operator docs, env template, and check scripts must stay executable."""

from pathlib import Path

from research_mentor.config import Settings


def test_readme_documents_required_start_commands():
    readme = Path("README.md").read_text(encoding="utf-8")
    for command in (
        "uv sync --all-groups",
        "alembic upgrade head",
        "uvicorn research_mentor.api.app:create_app",
        "npm run dev",
    ):
        assert command in readme


def test_env_example_has_no_secret_values():
    text = Path(".env.example").read_text(encoding="utf-8")
    for name in (
        "RESEARCH_MENTOR_QWEN_API_KEY=",
        "RESEARCH_MENTOR_QWEN_BASE_URL=",
        "RESEARCH_MENTOR_DEEPSEEK_API_KEY=",
        "RESEARCH_MENTOR_CHATGPT_API_KEY=",
        "RESEARCH_MENTOR_GLM_API_KEY=",
        "RESEARCH_MENTOR_OPENALEX_API_KEY=",
        "RESEARCH_MENTOR_HF_ENDPOINT=",
        "RESEARCH_MENTOR_HF_TOKEN=",
    ):
        assert name in text
    assert "sk-" not in text


def test_readme_covers_v1_operator_topics():
    readme = Path("README.md").read_text(encoding="utf-8")
    for needle in (
        "frontend/tests/e2e/visual.spec.ts-snapshots",
        "idea_review",
        "plan_loop",
        "key_insight_check",
        "working_qa",
        "complete",
        "low/mid/high",
        "默认 low",
        "OpenAI",
        "openai_compatible",
        "OpenAlex",
        "mailto",
        "Anydoc",
        "FlagEmbedding",
        "download_reranker",
        "--mirror",
        "hf-mirror.com",
        "modelscope.cn",
        "SQLite",
        "PostgreSQL",
        "/api/v1",
        "Last-Event-ID",
        "不替写代码/论文正文、不解决无关细碎问题",
        "https://birchove.github.io/rigora/",
    ):
        assert needle in readme


def test_env_example_keys_are_known_settings():
    names = []
    for line in Path(".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        names.append(stripped.split("=", 1)[0])
    known = {
        f"RESEARCH_MENTOR_{field_name.upper()}" for field_name in Settings.model_fields
    }
    assert names
    assert all(name in known for name in names)


def test_dev_and_check_scripts_cover_runtime_gates():
    dev = Path("scripts/dev.ps1").read_text(encoding="utf-8")
    check = Path("scripts/check.ps1").read_text(encoding="utf-8")
    assert "uvicorn research_mentor.api.app:create_app" in dev
    assert "npm run dev" in dev
    assert "alembic upgrade head" in check
    assert "pytest" in check
    assert "npm test" in check
    assert "npm run build" in check
    assert "npm run e2e" in check


def test_gitignore_excludes_runtime_artifacts_not_source():
    text = Path(".gitignore").read_text(encoding="utf-8")
    for needle in (".env", "data/", "data/models/", "*.db", "test-results/", "playwright-report/"):
        assert needle in text
    ignored = {
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert "migrations/" not in ignored
    assert "evals/" not in ignored
    assert "uv.lock" not in ignored
    assert "frontend/package-lock.json" not in ignored
