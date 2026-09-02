"""Atomic orchestration for idea review, planning, checking, and plan decisions.

Phase logic lives in `research_mentor.harness.orchestration`. This module keeps the
public `ResearchMentorOrchestrator` facade so existing imports stay stable.
"""

from research_mentor.harness.orchestration.completion import CompletionOrchestrator
from research_mentor.harness.orchestration.idea_review import IdeaReviewOrchestrator
from research_mentor.harness.orchestration.plan_check import PlanCheckOrchestrator
from research_mentor.harness.orchestration.working import WorkingOrchestrator


class ResearchMentorOrchestrator(
    IdeaReviewOrchestrator,
    PlanCheckOrchestrator,
    WorkingOrchestrator,
    CompletionOrchestrator,
):
    """Facade over phase-specific orchestrators; public API is unchanged."""
