"""OpenAI-compatible chat completions structured-output adapter."""

import json
import logging
import re
from time import perf_counter
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from research_mentor.adapters.model.errors import (
    ModelProviderRejected,
    ModelTemporarilyUnavailable,
)
from research_mentor.errors import ModelOutputInvalid
from research_mentor.ports.model import ModelRequest, OutputT


logger = logging.getLogger("research_mentor.runs")

ResponseFormatMode = Literal["json_schema", "json_object"]

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _invalid_output(message: str) -> ModelOutputInvalid:
    return ModelOutputInvalid(
        errors=[
            {
                "type": "model_output_invalid",
                "loc": (),
                "msg": message,
                "input": None,
            }
        ]
    )


def _provider_error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:500] if text else f"HTTP {response.status_code}"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    if isinstance(error, str):
        return error
    return str(body)[:500]


def _coerce_json_text(content: str) -> str:
    text = _FENCE_RE.sub("", content.strip()).strip()
    if text.startswith("{") or text.startswith("["):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _json_schema_format(request: ModelRequest[OutputT]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": request.output_model.__name__,
            "strict": True,
            "schema": request.output_model.model_json_schema(),
        },
    }


class OpenAICompatibleModelAdapter:
    def __init__(
        self,
        client: Any,
        *,
        base_url: str,
        response_format_mode: ResponseFormatMode = "json_schema",
    ) -> None:
        self._client = client
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self._response_format_mode = response_format_mode

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        started_at = perf_counter()
        logger.info(
            "model generate start model=%s endpoint=%s format=%s agent=%s",
            request.model_profile,
            self._endpoint,
            self._response_format_mode,
            request.agent_name,
        )
        try:
            if self._response_format_mode == "json_object":
                response = await self._post(request, json_object=True)
            else:
                response = await self._post(request, json_object=False)
                if response.status_code == 400:
                    logger.warning(
                        "json_schema rejected by %s, retrying json_object: %s",
                        self._endpoint,
                        _provider_error_text(response),
                    )
                    response = await self._post(request, json_object=True)
            self._raise_status(response)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            detail = str(exc).strip() or type(exc).__name__
            logger.warning(
                "model transport failed endpoint=%s model=%s agent=%s: %s",
                self._endpoint,
                request.model_profile,
                request.agent_name,
                detail,
            )
            raise ModelTemporarilyUnavailable(detail) from exc

        try:
            body = response.json()
            message = body["choices"][0]["message"]
            content = message.get("content") or message.get("reasoning_content")
            if not isinstance(content, str) or not content.strip():
                raise _invalid_output("Provider message content is not text")
            result = request.output_model.model_validate_json(_coerce_json_text(content))
        except ModelOutputInvalid:
            raise
        except ValidationError as exc:
            raise ModelOutputInvalid(errors=exc.errors()) from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise _invalid_output("Provider response envelope is invalid") from exc

        logger.info(
            "structured model request completed",
            extra={
                "trace_id": request.trace_id,
                "provider_request_id": body.get("id"),
                "model_profile": request.model_profile,
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
                "usage": body.get("usage"),
            },
        )
        return result

    async def _post(
        self,
        request: ModelRequest[OutputT],
        *,
        json_object: bool,
    ) -> httpx.Response:
        schema = request.output_model.model_json_schema()
        instructions = request.instructions
        response_format: dict[str, Any]
        if json_object:
            instructions = (
                f"{request.instructions}\n\n"
                "Return a JSON object that matches this schema. "
                "Do not wrap the JSON in markdown.\n"
                f"<json_schema>{json.dumps(schema, ensure_ascii=False)}</json_schema>"
            )
            response_format = {"type": "json_object"}
        else:
            response_format = _json_schema_format(request)
        return await self._client.post(
            self._endpoint,
            json={
                "model": request.model_profile,
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": request.user_input},
                ],
                "response_format": response_format,
            },
            timeout=request.timeout,
        )

    @staticmethod
    def _raise_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = _provider_error_text(exc.response)
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                raise ModelTemporarilyUnavailable(
                    f"HTTP {exc.response.status_code}: {detail}"
                ) from exc
            raise ModelProviderRejected(
                f"HTTP {exc.response.status_code}: {detail}"
            ) from exc
