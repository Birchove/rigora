from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from research_mentor.adapters.sql.base import Base
from research_mentor.application.commands import (
    DecidePlanCommand,
    RunCheckCommand,
    RunPlanCommand,
    SendWorkingMessageCommand,
    SubmitIdeaCommand,
)
from research_mentor.application.views import ProjectViewService
from research_mentor.bootstrap import build_container
from research_mentor.config import Settings
from research_mentor.domain.research import InitialInput, UserPlanDecision
from research_mentor.harness.phase import SessionPhase


IDEA = InitialInput(
    original_idea="评估分层状态压缩对长对话恢复稳定性的作用",
    domain="computer science",
)


async def _container(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'journey.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    settings = Settings(
        model_provider="demo",
        demo_mode=False,
        database_url=database_url,
        upload_root=tmp_path / "uploads",
    )
    return await build_container(settings)


async def _drain(worker, *, limit: int = 8) -> str | None:
    last = None
    for _ in range(limit):
        last = await worker.drain_once()
        if last is None:
            return last
    return last


@pytest.mark.anyio
async def test_project_view_exposes_active_run_and_event_cursor(tmp_path):
    container = await _container(tmp_path)
    try:
        views = ProjectViewService(
            container.uow_factory,
            supported_domains=container.settings.supported_domains,
            supported_domain_aliases=container.settings.supported_domain_aliases,
        )
        created = await views.create(title="缓存研究", domain="computer_science")
        assert created.active_run is None
        assert created.last_event_sequence == 1
        assert created.validation_candidates == []

        receipt = await container.command_bus.dispatch(
            SubmitIdeaCommand(
                project_id=created.project_id,
                command_id=str(uuid4()),
                expected_version=created.version,
                idea=IDEA,
            )
        )
        locked = await views.get(created.project_id)
        assert locked.active_run is not None
        assert locked.active_run.run_id == receipt.run_id
        assert locked.active_run.agent_name == "idea_review"
        assert locked.active_run.status in {"queued", "running"}
        assert locked.last_event_sequence >= 1
    finally:
        await container.close_provider()
        await container.engine.dispose()


@pytest.mark.anyio
async def test_production_handlers_cover_commands_and_agents(tmp_path):
    container = await _container(tmp_path)
    try:
        assert set(container.command_bus._handlers) >= {
            "submit_idea",
            "submit_refinement",
            "run_plan",
            "run_check",
            "decide_plan",
            "send_working_message",
            "submit_working_clarification",
            "resume_working",
            "finish_working",
            "record_main_result",
            "record_validation_result",
            "run_complete",
            "select_validations",
            "decide_plan_revision",
            "cancel_run",
            "restart_research",
            "archive_project",
        }
        assert set(container.worker._handlers) == {
            "idea_review",
            "plan_loop",
            "key_insight_check",
            "working_qa",
            "complete",
        }
    finally:
        await container.close_provider()
        await container.engine.dispose()


@pytest.mark.anyio
async def test_submit_idea_through_worker_reaches_working(tmp_path):
    container = await _container(tmp_path)
    try:
        views = ProjectViewService(
            container.uow_factory,
            supported_domains=container.settings.supported_domains,
            supported_domain_aliases=container.settings.supported_domain_aliases,
        )
        project = await views.create(title="演示研究", domain="computer_science")
        idea = await container.command_bus.dispatch(
            SubmitIdeaCommand(
                project_id=project.project_id,
                command_id=str(uuid4()),
                expected_version=project.version,
                idea=IDEA,
            )
        )
        assert idea.run_id
        await _drain(container.worker)
        after_idea = await views.get(project.project_id)
        assert after_idea.phase is SessionPhase.PLANNING
        assert after_idea.active_run is None
        assert after_idea.visible_evidence
        assert after_idea.stage_progress is not None
        assert "等待生成研究方案" in after_idea.stage_progress.headline

        plan = await container.command_bus.dispatch(
            RunPlanCommand(
                project_id=project.project_id,
                command_id=str(uuid4()),
                expected_version=after_idea.version,
            )
        )
        await _drain(container.worker)
        after_plan = await views.get(project.project_id)
        assert after_plan.phase is SessionPhase.CHECKING_KEY_INSIGHT
        assert plan.run_id

        check = await container.command_bus.dispatch(
            RunCheckCommand(
                project_id=project.project_id,
                command_id=str(uuid4()),
                expected_version=after_plan.version,
            )
        )
        await _drain(container.worker)
        after_check = await views.get(project.project_id)
        assert after_check.phase is SessionPhase.AWAITING_PLAN_DECISION
        assert check.run_id

        decided = await container.command_bus.dispatch(
            DecidePlanCommand(
                project_id=project.project_id,
                command_id=str(uuid4()),
                expected_version=after_check.version,
                decision=UserPlanDecision(decision="accept"),
            )
        )
        working = await views.get(project.project_id)
        assert decided.phase is SessionPhase.WORKING
        assert working.phase is SessionPhase.WORKING
        assert working.active_run is None
        assert working.last_event_sequence > after_check.last_event_sequence
        assert working.working_turns == []

        await container.command_bus.dispatch(
            SendWorkingMessageCommand(
                project_id=project.project_id,
                command_id=str(uuid4()),
                expected_version=working.version,
                question="主实验第一步怎么卡死变量？",
            )
        )
        await _drain(container.worker)
        after_qa = await views.get(project.project_id)
        assert after_qa.phase is SessionPhase.WORKING
        assert after_qa.active_run is None
        assert len(after_qa.working_turns) == 1
        assert after_qa.working_turns[0].action == "answer"
        assert after_qa.working_turns[0].reply == "先固定任务集与随机种子，再比较恢复正确率。"
    finally:
        await container.close_provider()
        await container.engine.dispose()
