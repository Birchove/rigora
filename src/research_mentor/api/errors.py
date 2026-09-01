"""Stable public API error envelopes."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from research_mentor.application.views import (
    ProjectNotFoundError,
    UnsupportedDomainError,
)
from research_mentor.errors import (
    ConcurrencyConflict,
    IllegalTransitionError,
    LiteratureSearchUnavailable,
    PortExecutionError,
    SessionNotFoundError,
)


class ApiContractError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details or {},
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _response(422, "validation_error", "请求内容不符合 API contract。")

    @app.exception_handler(ApiContractError)
    async def api_contract_error(
        request: Request, exc: ApiContractError
    ) -> JSONResponse:
        return _response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(UnsupportedDomainError)
    async def unsupported_domain(
        request: Request, exc: UnsupportedDomainError
    ) -> JSONResponse:
        return _response(422, "unsupported_domain", "v1 仅支持计算机科学领域。")

    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found(
        request: Request, exc: ProjectNotFoundError
    ) -> JSONResponse:
        return _response(404, "project_not_found", "项目不存在。")

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found(
        request: Request, exc: SessionNotFoundError
    ) -> JSONResponse:
        return _response(404, "project_not_found", "项目不存在。")

    @app.exception_handler(ConcurrencyConflict)
    async def concurrency_conflict(
        request: Request, exc: ConcurrencyConflict
    ) -> JSONResponse:
        return _response(
            409,
            "stale_project_version",
            "项目已在其他操作中更新，请刷新后重试。",
        )

    @app.exception_handler(IllegalTransitionError)
    async def illegal_transition(
        request: Request, exc: IllegalTransitionError
    ) -> JSONResponse:
        code = "run_in_progress" if "run in progress" in str(exc) else "illegal_phase"
        return _response(409, code, "当前项目状态不允许该操作。")

    async def provider_unavailable(request: Request, exc: Exception) -> JSONResponse:
        return _response(
            503,
            "provider_unavailable",
            "外部服务暂时不可用，请稍后重试。",
            retryable=True,
        )

    app.add_exception_handler(PortExecutionError, provider_unavailable)
    app.add_exception_handler(LiteratureSearchUnavailable, provider_unavailable)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        return _response(500, "internal_error", "服务器内部错误。")
