# Rigora

[![zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=for-the-badge&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/Birchove/rigora)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Birchove/rigora)

耐心严谨的个性化科研探索导师：用更具体的输入，换可核对的输出。不限学科，帮你审查想法、生成并修订方案、辅导实验、记录结果，再决定要不要补充验证或开始写。**不代写论文正文，不替你做实验，不编造结果。**

先看界面：[在线演示](https://birchove.github.io/rigora/)（只读，不跑真实模型）。要自己配置模型和走完整流程，按下面在本机启动。

## 它怎么带你做研究

1. **审查想法**：对照真实文献，判断你的输入够不够进入方案设计。
2. **生成方案**：写出研究问题、缺口、里程碑，以及最关键的「点睛之笔」。
3. **给点睛之笔打分**：另一家模型按固定规则评分；通不通过由系统判定，不是模型自己说了算。
4. **实验过程问答**：围绕当前任务答疑，不会替你宣布实验完成。
5. **补充验证或写作方向**：看完已有结果，给出下一步候选；选哪个由你决定。

方案可以同时生成 1 / 2 / 3 条（单方案 / 双方案 / 三方案）。配几对「方案生成 × 评分」模型，就决定了你能开到哪一档。

## 第一次启动

需要 Python 3.12、[uv](https://docs.astral.sh/uv/)、Node.js 20+。

```bash
uv sync --all-groups
uv run rigora-setup
```

浏览器里会打开本机配置面板。按顺序做完即可，不必先复制任何环境文件：

1. 看五个环节各自要什么样的模型。
2. 勾选你有 key 的供应商。目前包括千问、DeepSeek、ChatGPT、**Claude**、**Gemini**、GLM、Kimi、MiniMax、豆包、混元、阶跃星辰、LongCat、小米 MiMo、Grok、百灵、千帆。官方地址已经预填；中转服务只改地址即可。
3. 粘贴 API key，**自己填写模型名**（预填的是该厂商一个便宜、常用的默认名，可改成控制台里任意可用名称），并可当场点「测试连接」。
4. 给「想法审查 / 实验问答 / 补充验证」各指定一个模型。
5. 把「方案生成」和「点睛之笔评分」成对配置：一对只能开单方案；两对默认是双方案；三对才能开三方案。两对时不会自动变成三条路。
6. 可选：填 OpenAlex（文献检索更快更稳）、是否下载本地排序模型。

确认后写入仓库根目录 `.env`（权限 `600`，不会进 git）。想改配置就再跑一次 `uv run rigora-setup`，上次填的内容会读回来。

然后启动服务：

```bash
uv run alembic upgrade head
uv run uvicorn research_mentor.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

另一个终端：

```bash
cd frontend
npm install
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。也可一次拉起两端：`pwsh -File scripts/dev.ps1`。

五个环节都必须分到已配置的模型，否则启动会直接提示你去跑 `rigora-setup`，不会静默改用演示模型。

## 怎么选模型

面板里的参考型号来自仓库中的智能指数名单（`src/research_mentor/setup_wizard/model_ranking.json`），按环节需要的思考强度（低 / 中 / 高）挑选。方案生成和评分尽量换两家，避免自己写自己审。名单会不时更新，改这个文件即可。

ChatGPT 官方走 Responses 接口；Claude、Gemini 走各自的官方 OpenAI 兼容地址。模型名以你控制台里能用的为准。旧名如 `deepseek-chat`、`gpt-4o` 已经下线，不要再填。

## 可选增强

**文献检索。** 审查想法时会去 OpenAlex 查真实论文。建议在 [openalex.org/settings/api](https://openalex.org/settings/api) 申请免费 key，填进引导面板。不填也能用，只是大家共用额度，容易被限流。

**上传资料按意思排序。** 默认就能上传 `.txt` / `.md` / `.pdf`。只有希望按语义而不是按字面找词时，才需要额外下载约 1–2GB 的排序模型：

```bash
uv sync --extra local-ranking
uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror
```

国内走 ModelScope。不要用 `hf-mirror.com` 配当前 `huggingface_hub`，会下载失败。

数据默认存在本机 SQLite。个人使用不用改；多人共用或长期部署再换成 PostgreSQL，改完重新执行 `uv run alembic upgrade head`。

## 使用边界

只辅导真正在做的研究，不限定学科。不替写代码或论文正文，不解决无关细碎问题，也不替你执行实验。实验结果必须由你亲自记录；负面和不显著的结果会如实保留。

在线演示站点是纯前端快照，和本机配置、真实模型无关。
