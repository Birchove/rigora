"""Quiet polling access logs and keep Agent event lines visible."""

from __future__ import annotations

import logging
import re


_POLL_GET_PROJECT = re.compile(r'"GET /api/v1/projects/[^/]+ HTTP/')
_RUNTIME_HANDLER_ATTR = "research_mentor_runtime"


class DropPollingAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        if "/events" in message:
            return False
        if "/api/v1/health" in message:
            return False
        if _POLL_GET_PROJECT.search(message) is not None:
            return False
        return True


def install_runtime_logging() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, DropPollingAccessFilter) for item in access.filters):
        access.addFilter(DropPollingAccessFilter())
    package = logging.getLogger("research_mentor")
    package.setLevel(logging.INFO)
    if not any(getattr(item, _RUNTIME_HANDLER_ATTR, False) for item in package.handlers):
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter("%(levelname)s:     %(name)s %(message)s")
        )
        setattr(handler, _RUNTIME_HANDLER_ATTR, True)
        package.addHandler(handler)
    for name in ("research_mentor.events", "research_mentor.runs"):
        logging.getLogger(name).setLevel(logging.INFO)
