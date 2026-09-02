"""Dispatch structured-model calls to the adapter bound to each agent."""

from collections.abc import Mapping

from research_mentor.ports.model import ModelRequest, OutputT, StructuredModelPort


class RoutingModelAdapter:
    def __init__(
        self,
        routes: Mapping[str, StructuredModelPort],
        *,
        fallback: StructuredModelPort,
    ) -> None:
        self._routes = dict(routes)
        self._fallback = fallback

    async def generate(self, request: ModelRequest[OutputT]) -> OutputT:
        adapter = (
            self._routes.get(request.model_profile)
            or self._routes.get(request.agent_name)
            or self._fallback
        )
        return await adapter.generate(request)
