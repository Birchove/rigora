"""Configure Hugging Face Hub endpoint, token, and China-friendly download flags."""

from __future__ import annotations

import os
import sys

from research_mentor.hyperparameters import (
    HF_MIRROR_ENDPOINT,
    HF_OFFICIAL_ENDPOINT,
    MODELSCOPE_ENDPOINT,
)

_MODELSCOPE_ALIASES = frozenset(
    {
        "mirror",
        "modelscope",
        "modelscope.cn",
        "www.modelscope.cn",
        MODELSCOPE_ENDPOINT,
    }
)
_HF_MIRROR_ALIASES = frozenset({"hf-mirror", "hf-mirror.com", HF_MIRROR_ENDPOINT})
_OFFICIAL_ALIASES = frozenset(
    {"official", "huggingface", "huggingface.co", HF_OFFICIAL_ENDPOINT}
)


def resolve_hf_endpoint(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().rstrip("/")
    if not text:
        return None
    lowered = text.lower()
    aliases = {alias.lower() for alias in _MODELSCOPE_ALIASES}
    if lowered in aliases or lowered.endswith("modelscope.cn"):
        return MODELSCOPE_ENDPOINT
    if lowered in {alias.lower() for alias in _HF_MIRROR_ALIASES} or lowered.endswith(
        "hf-mirror.com"
    ):
        return HF_MIRROR_ENDPOINT
    if lowered in {alias.lower() for alias in _OFFICIAL_ALIASES}:
        return HF_OFFICIAL_ENDPOINT
    if not text.startswith(("http://", "https://")):
        text = f"https://{text}"
    return text


def is_modelscope_endpoint(endpoint: str | None) -> bool:
    return resolve_hf_endpoint(endpoint) == MODELSCOPE_ENDPOINT


def _patch_imported_hub_constants(endpoint: str) -> None:
    module = sys.modules.get("huggingface_hub.constants")
    if module is None:
        return
    hub = endpoint.rstrip("/")
    module.ENDPOINT = hub
    module.HUGGINGFACE_CO_URL_TEMPLATE = f"{hub}/{{repo_id}}/resolve/{{revision}}/{{filename}}"


def configure_huggingface_hub(
    *,
    endpoint: str | None = None,
    token: str | None = None,
) -> str | None:
    """Set Hub env vars used by huggingface_hub / FlagEmbedding.

    ModelScope is a different protocol: do not set HF_ENDPOINT to it.
    Hugging Face mirrors disable Xet so bytes do not bypass the mirror CDN.
    """
    resolved = resolve_hf_endpoint(endpoint)
    if resolved and resolved != MODELSCOPE_ENDPOINT:
        os.environ["HF_ENDPOINT"] = resolved
        _patch_imported_hub_constants(resolved)
        if resolved != HF_OFFICIAL_ENDPOINT:
            os.environ["HF_HUB_DISABLE_XET"] = "1"
    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = token
    return resolved
