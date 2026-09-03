from pathlib import Path
import os

import httpx

from research_mentor.adapters.embeddings.huggingface_hub_env import (
    configure_huggingface_hub,
    resolve_hf_endpoint,
)
from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.adapters.embeddings.modelscope_download import (
    modelscope_snapshot_download,
)
from research_mentor.application.document_ranker import document_ranker_for
from research_mentor.adapters.embeddings.unavailable import UnavailableRanker
from research_mentor.cli.download_reranker import download_reranker
from research_mentor.config import Settings
from research_mentor.hyperparameters import (
    HF_MIRROR_ENDPOINT,
    HF_OFFICIAL_ENDPOINT,
    MODELSCOPE_ENDPOINT,
)


def test_auto_backend_skips_weights_under_pytest() -> None:
    ranker = document_ranker_for(Settings(reranker_backend="auto"))
    assert isinstance(ranker, UnavailableRanker)
    result = ranker.rank("q", [], limit=1)
    assert result.status == "unavailable"
    assert "pytest" in (result.limitation or "")


def test_lexical_backend_is_explicit() -> None:
    ranker = document_ranker_for(Settings(reranker_backend="lexical"))
    assert isinstance(ranker, LexicalRanker)


def test_resolve_hf_endpoint_aliases() -> None:
    assert resolve_hf_endpoint("mirror") == MODELSCOPE_ENDPOINT
    assert resolve_hf_endpoint("modelscope") == MODELSCOPE_ENDPOINT
    assert resolve_hf_endpoint("official") == HF_OFFICIAL_ENDPOINT
    assert resolve_hf_endpoint("hf-mirror") == HF_MIRROR_ENDPOINT
    assert resolve_hf_endpoint("https://hf-mirror.com/") == HF_MIRROR_ENDPOINT
    assert resolve_hf_endpoint("") is None


def test_configure_modelscope_does_not_set_hf_endpoint(monkeypatch) -> None:
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
    resolved = configure_huggingface_hub(endpoint="mirror")
    assert resolved == MODELSCOPE_ENDPOINT
    assert os.environ.get("HF_ENDPOINT") is None


def test_configure_huggingface_hub_disables_xet_for_hf_mirror(monkeypatch) -> None:
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    resolved = configure_huggingface_hub(endpoint="hf-mirror", token="hf_test_token")
    assert resolved == HF_MIRROR_ENDPOINT
    assert os.environ["HF_ENDPOINT"] == HF_MIRROR_ENDPOINT
    assert os.environ["HF_HUB_DISABLE_XET"] == "1"
    assert os.environ["HF_TOKEN"] == "hf_test_token"


def test_download_reranker_writes_gitignored_local_dir(tmp_path) -> None:
    captured: dict[str, str] = {}

    def fake_snapshot_download(*, repo_id: str, local_dir: str, **kwargs: str) -> str:
        captured["repo_id"] = repo_id
        captured["local_dir"] = local_dir
        captured.update(kwargs)
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        (Path(local_dir) / "config.json").write_text("{}", encoding="utf-8")
        return local_dir

    target = download_reranker(
        model_name="BAAI/bge-reranker-v2-m3",
        cache_dir=tmp_path,
        downloader=fake_snapshot_download,
        endpoint="official",
        token="hf_test_token",
    )
    assert target == tmp_path / "BAAI--bge-reranker-v2-m3"
    assert (target / "config.json").is_file()
    assert captured["repo_id"] == "BAAI/bge-reranker-v2-m3"
    assert captured["token"] == "hf_test_token"
    assert captured["endpoint"] == HF_OFFICIAL_ENDPOINT


def test_modelscope_snapshot_download_writes_blobs(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "repo/files" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "Code": 200,
                    "Data": {
                        "Files": [
                            {"Type": "tree", "Path": "assets", "Size": 0},
                            {
                                "Type": "blob",
                                "Name": "config.json",
                                "Path": "config.json",
                                "Size": 2,
                            },
                        ]
                    },
                },
            )
        return httpx.Response(200, content=b"{}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    target = modelscope_snapshot_download(
        "BAAI/bge-reranker-v2-m3",
        tmp_path / "BAAI--bge-reranker-v2-m3",
        client=client,
    )
    assert (target / "config.json").read_bytes() == b"{}"
    assert not (target / "assets").exists()
