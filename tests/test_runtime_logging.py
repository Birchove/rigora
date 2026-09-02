import logging

from research_mentor.runtime_logging import DropPollingAccessFilter, install_runtime_logging


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
    assert sum(isinstance(item, DropPollingAccessFilter) for item in access.filters) == 1
