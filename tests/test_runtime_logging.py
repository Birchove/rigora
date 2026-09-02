import logging

from research_mentor.runtime_logging import (
    DropPollingAccessFilter,
    RedactSecretsFilter,
    install_runtime_logging,
    redact_secrets,
)


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="%s",
        args=(message,),
        exc_info=None,
    )


def test_access_filter_drops_sse_and_project_polls() -> None:
    filter_ = DropPollingAccessFilter()
    assert filter_.filter(
        _record('127.0.0.1:1 - "GET /api/v1/projects/demo-project-planning/events?after=1 HTTP/1.1" 200 OK')
    ) is False
    assert filter_.filter(
        _record('127.0.0.1:1 - "GET /api/v1/projects/demo-project-planning HTTP/1.1" 200 OK')
    ) is False
    assert filter_.filter(
        _record('127.0.0.1:1 - "GET /api/v1/health HTTP/1.1" 200 OK')
    ) is False
    assert filter_.filter(
        _record('127.0.0.1:1 - "POST /api/v1/projects/demo-project-planning/commands HTTP/1.1" 202 Accepted')
    ) is True


def test_install_runtime_logging_is_idempotent() -> None:
    install_runtime_logging()
    install_runtime_logging()
    access = logging.getLogger("uvicorn.access")
    package = logging.getLogger("research_mentor")
    assert sum(isinstance(item, DropPollingAccessFilter) for item in access.filters) == 1
    assert (
        sum(getattr(item, "research_mentor_runtime", False) for item in package.handlers)
        == 1
    )
    assert sum(isinstance(item, RedactSecretsFilter) for item in package.filters) == 1


def test_log_redaction_masks_keys_and_connection_strings() -> None:
    assert redact_secrets("using sk-live-secret-key-value") == "using sk-***"
    assert redact_secrets("Authorization: Bearer tok_abc.def") == "Authorization: Bearer ***"
    assert redact_secrets("api_key=super-secret") == "api_key=***"
    assert (
        redact_secrets("db=postgresql://user:pass@localhost:5432/mentor")
        == "db=postgresql://***/mentor"
    )
    filter_ = RedactSecretsFilter()
    record = _record("Bearer tok_abc api_key=xyz sk-abcdefghijklmnop")
    assert filter_.filter(record) is True
    assert "sk-" not in record.getMessage() or "sk-***" in record.getMessage()
    assert "tok_abc" not in record.getMessage()
    assert "xyz" not in record.getMessage()
