"""Operator docs and check scripts must stay executable."""

from pathlib import Path


def test_readme_documents_required_start_commands():
    readme = Path("README.md").read_text(encoding="utf-8")
    for command in (
        "uv sync --all-groups",
        "alembic upgrade head",
        "uvicorn research_mentor.api.app:create_app",
        "npm run dev",
        "uv run rigora-setup",
    ):
        assert command in readme


def test_readme_covers_user_setup_topics():
    readme = Path("README.md").read_text(encoding="utf-8")
    for needle in (
        "https://birchove.github.io/rigora/",
        "审查想法",
        "点睛之笔",
        "Claude",
        "Gemini",
        "自己填写模型名",
        "双方案",
        "三方案",
        "OpenAlex",
        "download_reranker",
        "--mirror",
        "hf-mirror.com",
        "SQLite",
        "PostgreSQL",
        "不代写论文正文",
        "不替写代码或论文正文，不解决无关细碎问题",
    ):
        assert needle in readme


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
