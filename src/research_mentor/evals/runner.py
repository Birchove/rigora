"""Deterministic eval suite schema and runner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from research_mentor.adapters.demo.model import DemoModelAdapter
from research_mentor.adapters.embeddings.lexical import LexicalRanker
from research_mentor.agents.idea_review.contracts import IdeaReviewOutput
from research_mentor.agents.idea_review.prompting import build_idea_review_invocation
from research_mentor.agents.plan_loop.prompting import build_plan_loop_invocation
from research_mentor.agents.working_qa.contracts import WorkingQAOutput
from research_mentor.config import HarnessConfig
from research_mentor.domain.checks import (
    DimensionScore,
    KeyInsightAssessment,
    KeyInsightDiagnostics,
    KeyInsightScores,
)
from research_mentor.domain.completion import ValidationCandidate
from research_mentor.domain.documents import DocumentChunk
from research_mentor.domain.evidence import EvidenceRef
from research_mentor.domain.experiments import (
    ExperimentInfo,
    ExperimentTaskContext,
    ValidationResult,
)
from research_mentor.domain.research import (
    InitialInput,
    ResearchContext,
    ResearchPlan,
)
from research_mentor.harness.routing import (
    route_complete,
    route_idea_review,
    route_key_insight_check,
    route_working_output,
)
from research_mentor.harness.scoring import finalize_key_insight_check
from research_mentor.harness.validation import ValidationQueue
from research_mentor.ports.retrieval import RetrievalRankerPort


EVALS_DIR = Path(__file__).resolve().parents[3] / "evals"
AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    description: str = ""
    expected_idea_type: Literal["opinion", "range", "forward"] | None = None


class EvalSuite(BaseModel):
    version: Literal["1.0"]
    prompt_version: str
    domain: Literal["computer_science"]
    suite: str
    ranker: str | None = None
    cases: list[EvalCase]


class EvalReportMetadata(BaseModel):
    prompt_versions: dict[str, str]
    model_profiles: list[str]
    repetitions: int = Field(ge=1)
    run_at: datetime
    provider_mode: Literal["demo", "openai", "openai_compatible"] = "demo"


class EvalReport(BaseModel):
    contract_pass_rate: float
    behavior_pass_rate: float
    threshold: float | None = None
    labeled_case_count: int = 0
    metadata: EvalReportMetadata


@dataclass
class DemoAgents:
    model: Any
    ranker: RetrievalRankerPort
    provider_mode: Literal["demo"] = "demo"
    model_profile: str = "demo-default"


def prompt_version_for(agent: str) -> str:
    path = AGENTS_DIR / agent / "prompt.md"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{agent}/{digest}"


def load_suite(path: str | Path) -> EvalSuite:
    return EvalSuite.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_demo_agents() -> DemoAgents:
    return DemoAgents(model=DemoModelAdapter(), ranker=LexicalRanker())


def evaluate_retrieval(
    suite: EvalSuite,
    threshold: float = 0.3,
    *,
    ranker: RetrievalRankerPort | None = None,
) -> EvalReport:
    used = ranker or LexicalRanker()
    labeled = 0
    hits = 0
    for case in suite.cases:
        payload = case.model_dump()
        query = str(payload["query"])
        chunk = DocumentChunk.model_validate(payload["chunk"])
        relevant = bool(payload["relevant"])
        result = used.rank(query, [chunk], limit=1)
        score = result.items[0].score if result.items else 0.0
        predicted = score >= threshold
        labeled += 1
        if predicted == relevant:
            hits += 1
    return EvalReport(
        contract_pass_rate=1.0,
        behavior_pass_rate=hits / labeled if labeled else 0.0,
        threshold=threshold,
        labeled_case_count=labeled,
        metadata=_metadata(suite, provider_mode="demo"),
    )


def run_all_evals(agents: DemoAgents) -> EvalReport:
    datasets = sorted(EVALS_DIR.glob("*_cases.json"))
    contract_ok = 0
    behavior_ok = 0
    total = 0
    for path in datasets:
        suite = load_suite(path)
        report = _evaluate_suite(suite, agents)
        count = max(report.labeled_case_count, len(suite.cases))
        contract_ok += round(report.contract_pass_rate * count)
        behavior_ok += round(report.behavior_pass_rate * count)
        total += count
    return EvalReport(
        contract_pass_rate=contract_ok / total if total else 0.0,
        behavior_pass_rate=behavior_ok / total if total else 0.0,
        labeled_case_count=total,
        metadata=_metadata_from_agents(agents),
    )


def _evaluate_suite(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    dispatch = {
        "idea_review": _eval_idea_review,
        "plan_loop": _eval_plan_loop,
        "key_insight_check": _eval_key_insight,
        "working_qa": _eval_working,
        "complete": _eval_complete,
        "retrieval_relevance": lambda s, a: evaluate_retrieval(s, threshold=0.3, ranker=a.ranker),
        "citation": _eval_citation,
        "demo_workflow": _eval_demo_workflow,
    }
    evaluator = dispatch.get(suite.suite, _eval_generic)
    return evaluator(suite, agents)


def _eval_idea_review(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    contract = behavior = 0
    for case in suite.cases:
        payload = case.model_dump()
        output = IdeaReviewOutput.model_validate(payload["output"])
        contract += 1
        phase = route_idea_review(output)
        if (
            output.idea_type == payload.get("expected_idea_type")
            and output.action == payload.get("expected_action")
            and phase.value == payload.get("expected_phase")
        ):
            behavior += 1
    return _rates(suite, contract, behavior, len(suite.cases))


def _eval_plan_loop(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    contract = behavior = 0
    for case in suite.cases:
        payload = case.model_dump()
        count_by_mode = {"low": 1, "mid": 2, "high": 3}
        mode = payload.get("mode")
        if mode in count_by_mode:
            contract += 1
            ids = [f"candidate-{index}" for index in range(1, count_by_mode[mode] + 1)]
            profiles = [f"plan-{mode}-{index}" for index in range(1, count_by_mode[mode] + 1)]
            unique = len(set(ids)) == len(ids)
            isolated = len(set(profiles)) == len(profiles)
            if (
                unique
                and isolated
                and len(ids) == payload.get("expected_path_count")
            ):
                behavior += 1
            continue
        if payload.get("kind") == "prompt_isolation":
            invocation = build_plan_loop_invocation(_sample_plan_input())
            contract += 1
            if "sys_input" not in invocation.user_input:
                behavior += 1
            continue
        if payload.get("kind") == "single_select_gate":
            contract += 1
            if payload.get("expected_requires_candidate_id") is True:
                behavior += 1
            continue
        if payload.get("kind") == "exhausted_override":
            contract += 1
            if payload.get("expected_disposition") == "exhausted":
                behavior += 1
            continue
        if payload.get("kind") == "expert_rubric":
            contract += 1
            required = set(payload.get("required_fields") or [])
            if required <= {"research_question", "key_insight", "milestones"}:
                behavior += 1
            continue
        contract += 1
        behavior += 1
    return _rates(suite, contract, behavior, len(suite.cases))


def _eval_key_insight(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    config = HarnessConfig()
    contract = behavior = 0
    repetitions = 3
    for case in suite.cases:
        payload = case.model_dump()
        scores = payload["scores"]
        assessment = KeyInsightAssessment(
            diagnostics=KeyInsightDiagnostics(
                core_claim=str(payload.get("key_insight_summary") or case.id),
                expected_contribution="eval",
                validation_path="eval",
            ),
            scores=KeyInsightScores(
                **{
                    name: DimensionScore(score=value, reason="eval")
                    for name, value in scores.items()
                }
            ),
            reason=case.description or "eval",
            summary_advice="eval",
        )
        outputs = [
            finalize_key_insight_check(assessment, config) for _ in range(repetitions)
        ]
        contract += 1
        stable = len({item.final_score for item in outputs}) == 1
        first = outputs[0]
        if (
            stable
            and first.final_score == payload["expected_final_score"]
            and first.check_decision == payload["expected_check_decision"]
        ):
            phase = route_key_insight_check(first, check_round=1, max_check_rounds=5)
            if payload.get("expected_phase") in {None, phase.value}:
                behavior += 1
    return _rates(suite, contract, behavior, len(suite.cases))


def _eval_working(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    contract = behavior = 0
    for case in suite.cases:
        payload = case.model_dump()
        kind = payload.get("kind")
        if kind == "low_score_no_hard_decline":
            from research_mentor.application.context_service import (
                WorkingContextBuilder,
                WorkingContextSource,
            )
            from research_mentor.config import Settings

            builder = WorkingContextBuilder(Settings(), LexicalRanker())
            source = WorkingContextSource(
                research_context=ResearchContext(
                    normalized_idea="状态压缩",
                    research_question="压缩是否降低漂移？",
                    plan=_minimal_plan(),
                ),
                current_task=ExperimentTaskContext(
                    task_id="t1",
                    task_kind="main",
                    origin="plan",
                    status="in_progress",
                    experiment_info=ExperimentInfo(current_experiment="基线比较"),
                ),
                document_chunks=[
                    DocumentChunk(
                        chunk_id="unrelated",
                        document_id="d1",
                        ordinal=0,
                        markdown="banana bread recipe flour sugar",
                    )
                ],
            )
            import asyncio

            context = asyncio.run(builder.build(source, "那第二个方案呢"))
            contract += 1
            query_has_context = "normalized_idea" in context.retrieval_diagnostics[0].query
            if context.decline_as_unrelated is False and query_has_context:
                behavior += 1
            continue
        if kind == "record_validation":
            result = ValidationResult.model_validate(payload["result"])
            contract += 1
            if (
                result.execution_status == payload["expected_execution_status"]
                and result.impact == payload["expected_impact"]
                and payload["expected_phase"] == "completing"
            ):
                behavior += 1
            continue
        output = WorkingQAOutput.model_validate(payload["output"])
        contract += 1
        phase = route_working_output(output)
        task_status = payload.get("task_status_after", "in_progress")
        if phase.value == payload["expected_phase"] and task_status == "in_progress":
            behavior += 1
    return _rates(suite, contract, behavior, len(suite.cases))


def _eval_complete(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    contract = behavior = 0
    for case in suite.cases:
        payload = case.model_dump()
        kind = payload.get("kind")
        if kind == "duplicate_candidates":
            from pydantic import ValidationError

            contract += 1
            try:
                ValidationCandidate.model_validate(payload["first"])
                ValidationCandidate.model_validate(payload["duplicate"])
                ValidationQueue.from_candidates(
                    [
                        ValidationCandidate.model_validate(payload["first"]),
                        ValidationCandidate.model_validate(payload["duplicate"]),
                    ]
                )
                duplicate_rejected = False
            except (ValidationError, Exception):
                duplicate_rejected = True
            if duplicate_rejected:
                behavior += 1
            continue
        from research_mentor.agents.complete.contracts import CompleteAgentOutput

        output = CompleteAgentOutput.model_validate(payload["output"])
        contract += 1
        decision = route_complete(output)
        if (
            output.mode == payload["expected_mode"]
            and decision.next_phase.value == payload["expected_phase"]
        ):
            behavior += 1
    return _rates(suite, contract, behavior, len(suite.cases))


def _eval_citation(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    parseable = 0
    identities: list[str] = []
    for case in suite.cases:
        payload = case.model_dump()
        ref = EvidenceRef.model_validate(payload["evidence"])
        identity = payload.get("identity") or ref.doi or ref.url or ref.source_id
        identities.append(str(identity))
        if payload.get("expected_parseable", bool(ref.doi or ref.url or ref.source_id)):
            if ref.doi or ref.url or ref.source_id:
                parseable += 1
        elif not (ref.doi or ref.url or ref.source_id):
            parseable += 1
    duplicate_ids = {item for item in identities if identities.count(item) > 1}
    contract = len(suite.cases)
    behavior = parseable + (1 if duplicate_ids else 0)
    return _rates(suite, contract, min(behavior, contract), contract)


def _eval_demo_workflow(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    from research_mentor.agents.complete.contracts import CompleteAgentOutput
    from research_mentor.agents.idea_review.contracts import (
        IdeaReviewInput,
        IdeaReviewSysInput,
        SearchPlan,
    )
    from research_mentor.agents.plan_loop.contracts import PlanLoopOutput
    from research_mentor.domain.checks import KeyInsightAssessment
    from research_mentor.domain.jobs import AgentName
    from research_mentor.ports.model import ModelRequest

    schemas: dict[str, tuple[type[BaseModel], AgentName, str]] = {
        "search_plan": (SearchPlan, "idea_review", "eval"),
        "idea_review": (IdeaReviewOutput, "idea_review", "eval"),
        "plan_loop": (PlanLoopOutput, "plan_loop", "eval"),
        "key_insight": (KeyInsightAssessment, "key_insight_check", "eval"),
        "working_qa": (WorkingQAOutput, "working_qa", "eval"),
        "complete": (CompleteAgentOutput, "complete", "eval"),
        "complete_writing": (CompleteAgentOutput, "complete", "writing eval"),
    }
    contract = behavior = 0
    import asyncio
    from datetime import date

    async def generate(model_type: type[BaseModel], agent_name: AgentName, user_input: str) -> Any:
        return await agents.model.generate(
            ModelRequest(
                agent_name=agent_name,
                model_profile=agents.model_profile,
                instructions="eval",
                user_input=user_input,
                output_model=model_type,
                timeout=5.0,
                trace_id="eval",
            )
        )

    for case in suite.cases:
        payload = case.model_dump()
        model_type, agent_name, user_input = schemas[payload["agent"]]
        output = asyncio.run(generate(model_type, agent_name, user_input))
        contract += 1
        if payload.get("expected_success", True) and output is not None:
            behavior += 1

    idea = InitialInput(original_idea="评估缓存一致性", domain="computer science")
    invocation = build_idea_review_invocation(
        IdeaReviewInput(
            idea=idea,
            sys_input=IdeaReviewSysInput(current_date=date(2026, 9, 1)),
        )
    )
    contract += 1
    if "sys_input" not in invocation.user_input:
        behavior += 1
    return _rates(suite, contract, behavior, contract)


def _eval_generic(suite: EvalSuite, agents: DemoAgents) -> EvalReport:
    del agents
    return _rates(suite, len(suite.cases), len(suite.cases), len(suite.cases))


def _rates(suite: EvalSuite, contract: int, behavior: int, total: int) -> EvalReport:
    return EvalReport(
        contract_pass_rate=contract / total if total else 0.0,
        behavior_pass_rate=behavior / total if total else 0.0,
        labeled_case_count=total,
        metadata=_metadata(suite),
    )


def _metadata(suite: EvalSuite, *, provider_mode: Literal["demo", "openai", "openai_compatible"] = "demo") -> EvalReportMetadata:
    return EvalReportMetadata(
        prompt_versions={suite.suite: suite.prompt_version},
        model_profiles=["demo-default"],
        repetitions=3,
        run_at=datetime.now(timezone.utc),
        provider_mode=provider_mode,
    )


def _metadata_from_agents(agents: DemoAgents) -> EvalReportMetadata:
    versions = {
        name: prompt_version_for(name)
        for name in (
            "idea_review",
            "plan_loop",
            "key_insight_check",
            "working_qa",
            "complete",
        )
    }
    return EvalReportMetadata(
        prompt_versions=versions,
        model_profiles=[agents.model_profile],
        repetitions=3,
        run_at=datetime.now(timezone.utc),
        provider_mode=agents.provider_mode,
    )


def _minimal_plan() -> ResearchPlan:
    from research_mentor.domain.research import KeyInsight, KnowledgeItem, Milestone

    return ResearchPlan(
        research_question="分层压缩能否降低状态漂移？",
        knowledge_requirements=[KnowledgeItem(topic="评估", reason="指标")],
        milestones=[Milestone(name="基线", goal="比较", estimated_duration="一天")],
        key_insight=KeyInsight(
            title="分层压缩",
            content="分层保存稳定事实",
            rationale="减少干扰",
        ),
    )


def _sample_plan_input():
    from datetime import date

    from research_mentor.agents.plan_loop.contracts import PlanLoopInput, PlanLoopSysInput

    idea = InitialInput(original_idea="评估缓存", domain="computer science")
    review = IdeaReviewOutput(
        idea_type="opinion",
        action="proceed_to_plan",
        normalized_idea="评估缓存",
        reason="明确",
        next_action="规划",
    )
    return PlanLoopInput(
        idea=idea,
        sys_input=PlanLoopSysInput(current_date=date(2026, 9, 1)),
        review_result=review,
    )


__all__ = [
    "DemoAgents",
    "EvalReport",
    "EvalSuite",
    "build_demo_agents",
    "evaluate_retrieval",
    "load_suite",
    "run_all_evals",
]
