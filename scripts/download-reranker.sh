#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "Installing FlagEmbedding extra and downloading BGE reranker weights into ./data/models"
echo "ModelScope: https://www.modelscope.cn/models/BAAI/bge-reranker-v2-m3"
echo "Hub: https://huggingface.co/BAAI/bge-reranker-v2-m3"
echo "Toolkit: https://github.com/FlagOpen/FlagEmbedding"
uv sync --extra local-ranking
uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror "$@"
