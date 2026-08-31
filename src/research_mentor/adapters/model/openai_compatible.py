"""OpenAI-compatible chat completions structured-output adapter."""

import logging
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from research_mentor.adapters.model.errors import (
    ModelProviderRejected,
    ModelTemporarilyUnavailable,
)
from research_mentor.errors import ModelOutputInvalid
from research_mentor.ports.model import ModelRequest, OutputT


logger = logging.getLogger(__name__)


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


class OpenAICompatibleModelAdapter:
    def __init__(self, client: Any, *, base_url: str) -> None:
        self._client = client
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        started_at = perf_counter()
        try:
            response = await self._client.post(
                self._endpoint,
                json={
                    "model": request.model_profile,
                    "messages": [
                        {"role": "system", "content": request.instructions},
                        {"role": "user", "content": request.user_input},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": request.output_model.__name__,
                            "strict": True,
                            "schema": request.output_model.model_json_schema(),
                        },
                    },
                },
                timeout=request.timeout,
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ModelTemporarilyUnavailable(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                raise ModelTemporarilyUnavailable(str(exc)) from exc
            raise ModelProviderRejected(str(exc)) from exc

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise _invalid_output("Provider message content is not text")
            result = request.output_model.model_validate_json(content)
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
