# CLAUDE.md

## 项目概述

Rigora:个性化科研探索导师(FastAPI + SQLAlchemy/Alembic + React/Vite)。五 Agent(idea_review / plan_loop / key_insight_check / working_qa / complete)由 Harness 统一裁决,用户确认 gate 贯穿全程。接入与启动见 README.md。

## 硬性约定

- **任意研究领域**:domain 是自由文本,不存在领域 allowlist;补充实验(ValidationTask)是通用结构 `name/purpose/method/evaluation_criteria/expected_result`,没有 paradigm/validation_type 分类。不要重新引入固定分类或领域枚举。
- **旧 JSON 兼容是有意设计**:旧 persisted JSON 里的 paradigm/validation_type 被 Pydantic 静默忽略;ExcludedValidation 把旧 validation_type 迁移为 name(见 `domain/completion.py`)。`tests/domain/test_experiments.py` 与 `tests/domain/test_completion.py` 里的 legacy 用例是兼容测试,不要"清理";其余 fixture 一律用新结构。
- **Harness 是权威**:评分、phase 转移、能否进入下一阶段全部由 Harness 判定,模型输出只是提案。
- `for_zp/` 是本地交接目录:不提交、不 add。
- 历史设计文档(`docs/design/`、`docs/superpowers/`)是过程记录,不要批量改写。

## 本机环境陷阱(Windows)

- 全局 `npm` 与 `claude` shim 指向不存在的路径,**不能直接用**。用 Codex 自带运行时:
  - Python:`C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`(仓库 `.venv` 的 python.exe 已失效,但其 site-packages 加入 PYTHONPATH 可用)
  - Node:`C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe`
- 后端测试:`PYTHONPATH='D:\A_main\rigora\.venv\Lib\site-packages;D:\A_main\rigora\src'`,`TEMP/TMP=D:\A_main\rigora\.codex-tmp`,结束后删除 .codex-tmp;pytest 必须加 `-p no:cacheprovider`(.pytest_cache 写入被拒)。
- 前端在 `frontend/` 下用上述 node 直接调:`node_modules/vitest/vitest.mjs --run`、`node_modules/typescript/bin/tsc -b`、`node_modules/vite/bin/vite.js build`。不要用 pnpm(会移动 node_modules 依赖,出过事故)。
- **预存失败测试**(与任何改动无关,不要试图修复):
  - `tests/setup_wizard/test_env_file.py::test_write_env_is_atomic_owner_only_and_readable_back` 断言 0o600,Windows 实际 0o666,恒失败。
  - `tests/setup_wizard/test_server.py::test_cross_site_origin_is_refused_on_post` 偶发全量跑污染,单跑即过。
- `LF will be replaced by CRLF` warning 属正常;以 `git diff --check` 退出码为准,不要批量格式化。

## 常用命令

```bash
uv run alembic upgrade head            # 迁移,当前 head: 20260908_0007
uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

## 工作流偏好(用户明确要求)

- 分步实施:每完成一步停下,等人工审核后再进入下一步。
- 不主动 commit / push,除非明确要求。
- 改动走 TDD:先写失败测试确认 RED,最小实现确认 GREEN。
