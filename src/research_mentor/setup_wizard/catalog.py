"""Onboarding copy and provider catalog served to the setup panel.

Vendor presets, model options and agent names all come from `config.py`, so the
panel never carries a second copy that can drift from the runtime behaviour.
"""

from __future__ import annotations

from typing import Any

from research_mentor.config import (
    ALL_AGENTS,
    PLAN_CHECK_PAIR_MAX,
    PANEL_SLOTS,
    SHARED_AGENTS,
    SLOT_VENDOR,
    VENDOR_DEFAULT_MODELS,
    VENDOR_LABELS,
    VENDOR_MODEL_OPTIONS,
    VENDOR_PRESETS,
)
from research_mentor.hyperparameters import (
    CHECK_PASS_SCORE,
    MAX_CHECK_ROUNDS,
    PLAN_CANDIDATE_COUNTS,
    SCORE_WEIGHTS,
)


PRODUCT_INTRO: dict[str, Any] = {
    "name": "Rigora",
    "tagline": "耐心严谨的个性化科研探索导师",
    "idea": "用更严格、更具体的用户输入，换更优质、可核对的系统输出。",
    "scope": "只辅导 computer science。不代写论文正文，不替你做实验，不编造结果。",
    "flow": [
        "审查想法",
        "生成并修订方案",
        "辅导实验问答",
        "记录实验结果",
        "选补充验证或整理写作方向",
    ],
    "boundaries": [
        "五个 Agent 各自只做一次结构化推理，彼此不互相调用。",
        "状态流转、评分和确认闸门由 Harness 独占，模型说的话不会被当成指令执行。",
        "实验结果必须由你显式记录；负面和不显著的结果会如实保留。",
    ],
}


# 每个 Agent 一屏。text 保持两三句，避免新手引导变成文档。
AGENT_GUIDE: tuple[dict[str, Any], ...] = (
    {
        "name": "idea_review",
        "step": 1,
        "title": "想法审查",
        "role": "判断你的输入够不够格进入方案设计",
        "text": (
            "它先检索文献，再判断你给的是一个可验证的主张、一个还没收敛的方向，"
            "还是一段已经在做的实验。够明确就进入方案设计，太宽泛就回来问你要补充什么。"
        ),
        "highlights": [
            "只有明确主张能直接进方案阶段",
            "宽泛方向会被要求补充，不会替你决定研究问题",
            "会区分「搜到了什么」和「实际用了什么来支撑判断」",
        ],
        "needs": "要读多篇文献摘要，吃长上下文，且必须稳定输出 JSON。",
        "recommended": ("deepseek-v4-flash", "qwen3.7-plus", "gpt-5.6-terra"),
    },
    {
        "name": "plan_loop",
        "step": 2,
        "title": "方案生成与修订",
        "role": "产出研究方案，并按反馈做最小必要修改",
        "text": (
            "它写出研究问题、需要补的知识、里程碑，以及最关键的「点睛之笔」。"
            "后续每一轮只改该改的地方，并告诉你相对上一版变了什么。"
        ),
        "highlights": [
            "点睛之笔必须说明增量、成立理由和验证路径",
            "时间或资源不够时写进待定事项，不用假设填空",
            "它不能宣布方案已通过，确认权在你手上",
        ],
        "needs": "要一次生成较长的结构化方案，选生成能力强的模型。",
        "recommended": ("gpt-5.6-sol", "deepseek-v4-pro", "glm-5.3"),
    },
    {
        "name": "key_insight_check",
        "step": 3,
        "title": "点睛之笔评分",
        "role": "从五个维度给方案的核心创新打分",
        "text": (
            "它只给原始分数和修订建议，不决定通过与否。"
            f"总分由系统按固定权重重算，达到 {CHECK_PASS_SCORE} 且每一维不低于下界才算过，"
            f"最多循环 {MAX_CHECK_ROUNDS} 轮。"
        ),
        "highlights": [
            "五维："
            + "、".join(
                f"{name}({weight:.0%})" for name, weight in SCORE_WEIGHTS.items()
            ),
            "分数由系统重算，模型改不了判定",
            "建议和方案生成换一家模型，避免自己写自己审",
        ],
        "needs": "要严格推理和稳定打分，选推理型模型。",
        "recommended": ("deepseek-v4-pro", "gpt-5.6-sol", "glm-5.3"),
    },
    {
        "name": "working_qa",
        "step": 4,
        "title": "实验过程问答",
        "role": "在你做实验的过程中随时答疑",
        "text": (
            "它围绕当前这个实验任务回答问题，信息不足就只问最少的关键信息。"
            "只有当事实表明主方案需要重估时，它才会提出方案有问题。"
        ),
        "highlights": [
            "不能替你宣布实验完成，进入下一阶段由你点确认",
            "会检索你上传的项目文档来辅助回答",
            "结果不符合预期不等于执行失败，它会如实保留",
        ],
        "needs": "交互最频繁的一环，优先选便宜且快的模型。",
        "recommended": ("gpt-5.6-luna", "qwen3.8-flash", "glm-5.3-flash"),
    },
    {
        "name": "complete",
        "step": 5,
        "title": "补充验证与写作方向",
        "role": "看完已有结果，决定下一步做什么",
        "text": (
            "它综合主实验和已完成的验证，给出三种走向之一："
            "还需要哪些补充验证、结果动摇主张所以要修订方案、或者证据够了可以开始写。"
        ),
        "highlights": [
            "只提验证候选，选哪个由你决定",
            "写作方向只给结构和讨论重点，不生成论文正文",
            "不会把没跑的实验当成已完成",
        ],
        "needs": "要综合多份实验结果，选推理和归纳强的模型。",
        "recommended": ("gpt-5.6-sol", "deepseek-v4-pro", "qwen3.8-max"),
    },
)


AGENT_LABELS: dict[str, str] = {
    item["name"]: item["title"] for item in AGENT_GUIDE
}


# 多方案模式：路径数直接取自 hyperparameters，避免面板说一套、运行时做另一套。
PLAN_MODES: tuple[dict[str, Any], ...] = tuple(
    {
        "mode": mode,
        "paths": PLAN_CANDIDATE_COUNTS[mode],
        "title": title,
        "text": text,
    }
    for mode, title, text in (
        ("low", "单方案", "只生成一条方案，最快也最省。"),
        ("mid", "双方案", "同时生成两条思路不同的方案，你挑一条继续。"),
        ("high", "三方案", "同时生成三条方案，覆盖面最广，花费也最高。"),
    )
)

PAIRING_RULES: dict[str, Any] = {
    "max_pairs": PLAN_CHECK_PAIR_MAX,
    "advice": "同一对里尽量用不同厂商、能力相近的两个模型：不同厂商避免自己写自己审，"
    "能力相近才不会出现强模型压着弱模型改。",
    "by_count": [
        {
            "pairs": 1,
            "modes": ["low"],
            "text": "配 1 对只能用单方案模式。想用双方案或三方案，至少配 2 对。",
        },
        {
            "pairs": 2,
            "modes": ["low", "mid", "high"],
            "text": "配 2 对时，前两条路按你填的顺序配对；三方案模式的第三条路"
            "用一个交错组合补齐，下面可以选是哪一个。",
        },
        {
            "pairs": 3,
            "modes": ["low", "mid", "high"],
            "text": "配 3 对时三种模式都可用，每条路就是你填的一对。",
        },
    ],
}


OPTIONAL_DEPENDENCIES: tuple[dict[str, Any], ...] = (
    {
        "key": "openalex",
        "title": "文献检索加速",
        "advanced": False,
        "recommended": True,
        "why": "审查想法时要去真实论文里核对。填上之后检索更快、更稳。",
        "without": "不填也能用，只是和所有人共用一个通道，检索会变慢，偶尔失败。",
        "how": "在 openalex.org 免费注册，把页面上给你的那串字符粘进来。不花钱。",
        "url": "https://openalex.org/settings/api",
        "command": None,
    },
    {
        "key": "reranker",
        "title": "让你上传的资料更好用",
        "advanced": False,
        "recommended": False,
        "why": "开启后，你上传的论文和笔记会按意思相关度排序，做实验时提问更容易命中要点。",
        "without": "不开也能上传和阅读，只是按字面找词，命中率低一些。系统会明确告诉你没开。",
        "how": "需要一次性下载约 1–2GB 的模型文件，之后一直可用。现在可以先跳过，想用了再回来开。",
        "url": None,
        "command": "uv sync --extra local-ranking\n"
        "uv run --extra local-ranking python -m research_mentor.cli.download_reranker --mirror",
    },
    {
        "key": "hf_token",
        "title": "模型文件从哪里下",
        "advanced": True,
        "recommended": False,
        "why": "上一项的模型文件默认走国内镜像，通常不用管这里。",
        "without": "留空就是走镜像，一般更快。",
        "how": "只有你想改从 Hugging Face 官方下载时，才需要填一个访问令牌。",
        "url": "https://huggingface.co/settings/tokens",
        "command": None,
    },
    {
        "key": "database",
        "title": "数据存在哪里",
        "advanced": True,
        "recommended": False,
        "why": "默认存成你电脑上的一个文件，个人使用完全够用，也不用额外装东西。",
        "without": "留空就用默认的本地文件。",
        "how": "只有多人共用同一份数据，或者要长期部署在服务器上时，才需要换成数据库地址。"
        "换完要重新执行一次数据库升级命令。",
        "url": None,
        "command": "uv run alembic upgrade head",
    },
)


def vendor_catalog() -> list[dict[str, Any]]:
    """Provider metadata for the panel: label, official base URL, model options."""
    entries: list[dict[str, Any]] = []
    for slot in PANEL_SLOTS:
        vendor = SLOT_VENDOR[slot]
        api_style, base_url = VENDOR_PRESETS[vendor]
        entries.append(
            {
                "slot": slot,
                "vendor": vendor,
                "label": VENDOR_LABELS[vendor],
                "default_base_url": base_url,
                "default_api_style": api_style,
                "default_model": VENDOR_DEFAULT_MODELS[vendor],
                "model_options": list(VENDOR_MODEL_OPTIONS[vendor]),
            }
        )
    return entries


def catalog() -> dict[str, Any]:
    return {
        "product": PRODUCT_INTRO,
        "agents": list(AGENT_GUIDE),
        "agent_order": list(ALL_AGENTS),
        "shared_agents": sorted(SHARED_AGENTS),
        "vendors": vendor_catalog(),
        "plan_modes": list(PLAN_MODES),
        "pairing": PAIRING_RULES,
        "max_pairs": PLAN_CHECK_PAIR_MAX,
        "optional": list(OPTIONAL_DEPENDENCIES),
    }
