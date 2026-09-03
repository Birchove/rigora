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
  allowedCommands = [],
  submit,
  busy = false,
}: {
  phase: PlanPhase;
  progress?: StageProgress | null;
  running?: boolean;
  candidates?: PlanCandidateView[];
  allowedCommands?: string[];
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
  // Harness 语义：session 已有候选时 run_plan 一律走修订（mode 被忽略），
  // 因此仅在没有候选的初次生成时展示低/中/高，修订场景只给一个入口。
  const modeButtons = phase === "planning" && submit !== undefined && !running ? (
    candidates.length > 0 ? (
      <div className="structured-actions plan-mode-row">
        <button type="button" disabled={busy} onClick={() => void submit({ type: "run_plan", mode: "low" })}>
          按你的反馈修订方案
        </button>
      </div>
    ) : (
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
    )
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
      <>
        <KeyInsightScoreCard
          heading={heading}
          body={body}
          checkRound={progress?.check_round}
          maxCheckRounds={progress?.max_check_rounds}
          score={progress?.last_check_score}
          passed={progress?.last_check_passed}
        />
        {candidates.length > 0 ? (
          <PlanDecisionPanel
            phase={phase}
            candidates={candidates}
            allowedCommands={allowedCommands}
            submit={submit}
            busy={busy || running}
          />
        ) : null}
      </>
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
        <PlanDecisionPanel
          phase={phase}
          candidates={candidates}
          allowedCommands={allowedCommands}
          submit={submit}
          busy={busy}
        />
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
      <PlanDecisionPanel
        phase={phase}
        candidates={candidates}
        allowedCommands={allowedCommands}
        submit={submit}
        busy={busy}
      />
    </>
  );
}
