"""Download FlagEmbedding reranker weights into the gitignored cache directory."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from research_mentor.adapters.embeddings.flag_embedding import local_reranker_dir
from research_mentor.adapters.embeddings.huggingface_hub_env import (
    configure_huggingface_hub,
    is_modelscope_endpoint,
    resolve_hf_endpoint,
)
from research_mentor.adapters.embeddings.modelscope_download import (
    modelscope_snapshot_download,
)
from research_mentor.config import Settings
from research_mentor.hyperparameters import (
    FLAGEMBEDDING_REPO_URL,
    HF_MIRROR_ENDPOINT,
    HF_OFFICIAL_ENDPOINT,
    MODELSCOPE_ENDPOINT,
    MODELSCOPE_RERANKER_URL,
    RERANKER_MODEL_HUB_URL,
)


def download_reranker(
    *,
    model_name: str,
    cache_dir: Path,
    downloader: Callable[..., str] | None = None,
    endpoint: str | None = None,
    token: str | None = None,
) -> Path:
    resolved = resolve_hf_endpoint(endpoint)
    configure_huggingface_hub(endpoint=resolved, token=token)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = local_reranker_dir(model_name, cache_dir)
    if downloader is None and is_modelscope_endpoint(resolved):
        modelscope_snapshot_download(
            model_name,
            target,
            on_progress=_print_progress,
        )
        return target
    if downloader is None:
        try:
            from huggingface_hub import snapshot_download as downloader
        except ImportError as exc:
            raise SystemExit(
                "缺少 huggingface_hub。先执行: uv sync --extra local-ranking"
            ) from exc
    kwargs: dict[str, str] = {"repo_id": model_name, "local_dir": str(target)}
    if token:
        kwargs["token"] = token
    if resolved and resolved != MODELSCOPE_ENDPOINT:
        kwargs["endpoint"] = resolved
    downloader(**kwargs)
    return target


def _print_progress(name: str, downloaded: int, total: int | None) -> None:
    if total:
        pct = min(100, downloaded * 100 // total)
        print(f"\r{name}: {downloaded}/{total} ({pct}%)", end="", file=sys.stderr, flush=True)
        if downloaded >= total:
            print(file=sys.stderr)
    elif downloaded == 0:
        print(f"{name} ...", file=sys.stderr, flush=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载 BGE reranker 权重到 ./data/models（已 gitignore）"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--mirror",
        action="store_true",
        help=f"走 ModelScope 国内源 {MODELSCOPE_ENDPOINT}（推荐）",
    )
    source.add_argument(
        "--hf-mirror",
        action="store_true",
        help=f"走 hf-mirror.com（huggingface_hub 1.29 常因跨域 308 失败）",
    )
    source.add_argument(
        "--official",
        action="store_true",
        help=f"走官网 {HF_OFFICIAL_ENDPOINT}（可配合 --login / HF_TOKEN）",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="交互登录 Hugging Face，仅对官网有效",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = Settings()
    token = settings.huggingface_hub_token()
    if args.login:
        try:
            from huggingface_hub import login
        except ImportError as exc:
            raise SystemExit(
                "缺少 huggingface_hub。先执行: uv sync --extra local-ranking"
            ) from exc
        print("打开 Hugging Face 登录。Token 见 https://huggingface.co/settings/tokens")
        login()
        try:
            from huggingface_hub import get_token

            token = get_token() or token
        except Exception:
            token = settings.huggingface_hub_token() or token
    if args.mirror:
        endpoint = MODELSCOPE_ENDPOINT
    elif args.hf_mirror:
        endpoint = HF_MIRROR_ENDPOINT
    elif args.official:
        endpoint = HF_OFFICIAL_ENDPOINT
    elif settings.hf_endpoint:
        endpoint = settings.hf_endpoint
    else:
        endpoint = MODELSCOPE_ENDPOINT
        print(
            "默认走 ModelScope 国内源。"
            " 官网请加 --official；hf-mirror.com 请加 --hf-mirror。"
        )
    resolved = configure_huggingface_hub(endpoint=endpoint, token=token)
    print(f"工具包: {FLAGEMBEDDING_REPO_URL}")
    print(f"模型页: {RERANKER_MODEL_HUB_URL}")
    if is_modelscope_endpoint(resolved):
        print(f"下载源: ModelScope {MODELSCOPE_RERANKER_URL}")
    else:
        print(f"Hub: {resolved or HF_OFFICIAL_ENDPOINT}")
        if token:
            print("已使用 Hugging Face token")
        else:
            print("未登录（官网会限速）。可用 --login，或设置 HF_TOKEN")
    print(f"下载 {settings.reranker_model} → {settings.reranker_cache_dir}")
    target = download_reranker(
        model_name=settings.reranker_model,
        cache_dir=settings.reranker_cache_dir,
        endpoint=endpoint,
        token=token,
    )
    print(f"已写入 {target}（该目录已在 .gitignore，不会进入 git）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
