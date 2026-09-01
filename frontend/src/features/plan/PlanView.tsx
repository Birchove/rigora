import type { Phase } from "../../api/types";
import { KeyInsightScoreCard } from "../../components/KeyInsightScoreCard";
import { PlanDecisionPanel } from "../../components/PlanDecisionPanel";
import { ResearchPlanView } from "../../components/ResearchPlanView";

type PlanPhase = Extract<Phase, "planning" | "checking_key_insight" | "awaiting_plan_decision" | "check_loop_exhausted">;

export function PlanView({ phase }: { phase: PlanPhase }) {
  if (phase === "planning") return <ResearchPlanView heading="正在生成研究方案" />;
  if (phase === "checking_key_insight") return <KeyInsightScoreCard heading="正在校验点睛之笔" />;
  if (phase === "check_loop_exhausted") return <KeyInsightScoreCard heading="点睛之笔评分" />;
  return (
    <>
      <ResearchPlanView heading="研究方案" />
      <PlanDecisionPanel />
    </>
  );
}
