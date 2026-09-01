import type { Phase } from "../../api/types";
import { ValidationSelectionPanel } from "../../components/ValidationSelectionPanel";
import { WritingGuidanceView } from "../../components/WritingGuidanceView";

type CompletionPhase = Extract<Phase, "completing" | "awaiting_validation_selection" | "awaiting_plan_revision_decision" | "completed">;

export function CompletionView({ phase }: { phase: CompletionPhase }) {
  if (phase === "awaiting_validation_selection") return <ValidationSelectionPanel />;
  if (phase === "completed") return <WritingGuidanceView />;
  const heading = phase === "completing" ? "正在整理完成建议" : "方案修订";
  return (
    <section className="phase-card">
      <p className="card-kicker">Complete</p>
      <h1>{heading}</h1>
      <p>系统将根据用户亲录结果，决定补充验证、方案修订或写作规划。</p>
    </section>
  );
}
