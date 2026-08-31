"""OpenAI Responses API structured-output adapter."""

import logging
from time import perf_counter
from typing import Any

from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel, ValidationError

from research_mentor.adapters.model.errors import ModelTemporarilyUnavailable
from research_mentor.errors import ModelOutputInvalid
from research_mentor.ports.model import ModelRequest, OutputT


logger = logging.getLogger(__name__)


class OpenAIResponsesModelAdapter:
    def __init__(self, client: Any) -> None:
        self._client = client

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        started_at = perf_counter()
        try:
            response = await self._client.responses.parse(
                model=request.model_profile,
                instructions=request.instructions,
                input=request.user_input,
                text_format=request.output_model,
                timeout=request.timeout,
            )
            parsed = response.output_parsed
            payload = (
                parsed.model_dump(mode="python", warnings=False)
                if isinstance(parsed, BaseModel)
                else parsed
            )
            result = request.output_model.model_validate(payload)
        except (APITimeoutError, RateLimitError, APIConnectionError) as exc:
            raise ModelTemporarilyUnavailable(str(exc)) from exc
        except ValidationError as exc:
            raise ModelOutputInvalid(errors=exc.errors()) from exc

        usage = getattr(response, "usage", None)
        logger.info(
            "structured model request completed",
            extra={
                "trace_id": request.trace_id,
                "provider_request_id": getattr(response, "_request_id", None)
                or getattr(response, "id", None),
                "model_profile": request.model_profile,
                "latency_ms": round((perf_counter() - started_at) * 1000, 3),
                "usage": (
                    usage.model_dump(mode="json")
                    if hasattr(usage, "model_dump")
                    else usage
                ),
            },
        )
        return result
