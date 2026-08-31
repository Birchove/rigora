"""Key insight assessment and harness decision models."""

from pydantic import BaseModel, Field

from research_mentor.domain.evidence import EvidenceRef


class DimensionScore(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    reason: str


class KeyInsightDiagnostics(BaseModel):
    core_claim: str
    expected_contribution: str
    validation_path: str
    plan_dependency: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_conflicts: list[str] = Field(default_factory=list)
    plan_mismatches: list[str] = Field(default_factory=list)
    feasibility_risks: list[str] = Field(default_factory=list)
    evaluation_limits: list[str] = Field(default_factory=list)


class KeyInsightScores(BaseModel):
    research_fit: DimensionScore
    novelty: DimensionScore
    research_value: DimensionScore
    testability_feasibility: DimensionScore
    evidence_support: DimensionScore


class KeyInsightAssessment(BaseModel):
    diagnostics: KeyInsightDiagnostics
    scores: KeyInsightScores
    reason: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    summary_advice: str
    revision_suggestions: list[str] = Field(default_factory=list)


class KeyInsightCheckOutput(BaseModel):
    assessment: KeyInsightAssessment
    final_score: float
    check_decision: bool
    decision_reason: str
    revision_request: list[str] = Field(default_factory=list)
    scoring_rule_version: str


class CheckDecision(BaseModel):
    final_score: float = Field(ge=0.0, le=10.0)
    passed: bool


class CheckRound(BaseModel):
    check_round: int = Field(ge=1)
    output: KeyInsightCheckOutput
    final_score: float = Field(ge=0.0, le=10.0)
    passed: bool
