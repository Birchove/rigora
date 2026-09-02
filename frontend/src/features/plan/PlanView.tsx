import type { Phase, PlanCandidateView, StageProgress } from "../../api/types";
import { KeyInsightScoreCard } from "../../components/KeyInsightScoreCard";
import { PlanDecisionPanel } from "../../components/PlanDecisionPanel";
import { ResearchPlanView } from "../../components/ResearchPlanView";
import type { CommandDraft } from "../../hooks/useCommand";

type PlanPhase = Extract<Phase, "planning" | "checking_key_insight" | "awaiting_plan_decision" | "check_loop_exhausted">;

export function PlanView({
  phase,
  progress,
  running = false,
  candidates = [],
  submit,
  busy = false,
}: {
  phase: PlanPhase;
  progress?: StageProgress | null;
  running?: boolean;
  candidates?: PlanCandidateView[];
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const heading = progress?.headline
    ?? (phase === "planning"
      ? "等待生成研究方案"
      : phase === "checking_key_insight"
        ? "等待校验点睛之笔"
        : phase === "check_loop_exhausted"
          ? "点睛之笔评分"
          : "研究方案");
  const body = progress?.detail
    ?? (running
      ? "当前 Agent 正在运行，步骤会显示在下方公开运行轨迹中。"
      : "研究问题、里程碑与知识准备会在后端确认后作为结构化内容整块呈现。");
  const modeButtons = phase === "planning" && submit !== undefined && !running ? (
    <div className="structured-actions plan-mode-row">
      <button type="button" disabled={busy} onClick={() => void submit({ type: "run_plan", mode: "low" })}>
        低配生成
      </button>
      <button type="button" disabled={busy} onClick={() => void submit({ type: "run_plan", mode: "mid" })}>
        中配生成
      </button>
      <button type="button" disabled={busy} onClick={() => void submit({ type: "run_plan", mode: "high" })}>
        高配生成
      </button>
    </div>
  ) : null;

  if (phase === "planning") {
    return (
      <>
        <ResearchPlanView
          heading={heading}
          body={body}
          planQuestion={progress?.plan_question}
          keyInsightTitle={progress?.key_insight_title}
          ideaReason={progress?.idea_reason}
        />
        {modeButtons}
      </>
    );
  }
  if (phase === "checking_key_insight") {
    return (
      <KeyInsightScoreCard
        heading={heading}
        body={body}
        checkRound={progress?.check_round}
        maxCheckRounds={progress?.max_check_rounds}
        score={progress?.last_check_score}
        passed={progress?.last_check_passed}
      />
    );
  }
  if (phase === "check_loop_exhausted") {
    return (
      <>
        <KeyInsightScoreCard
          heading={heading}
          body={body}
          checkRound={progress?.check_round}
          maxCheckRounds={progress?.max_check_rounds}
          score={progress?.last_check_score}
          passed={progress?.last_check_passed}
        />
        <PlanDecisionPanel phase={phase} candidates={candidates} submit={submit} busy={busy} />
      </>
    );
  }
  return (
    <>
      <ResearchPlanView
        heading={heading}
        body={body}
        planQuestion={progress?.plan_question}
        keyInsightTitle={progress?.key_insight_title}
        ideaReason={progress?.idea_reason}
      />
      <PlanDecisionPanel phase={phase} candidates={candidates} submit={submit} busy={busy} />
    </>
  );
}
