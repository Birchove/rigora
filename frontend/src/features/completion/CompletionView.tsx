import type { Phase, ValidationCandidate, WritingGuidance } from "../../api/types";
import { PlanRevisionPanel } from "../../components/PlanRevisionPanel";
import { ValidationSelectionPanel } from "../../components/ValidationSelectionPanel";
import { WritingGuidanceView } from "../../components/WritingGuidanceView";
import type { CommandDraft } from "../../hooks/useCommand";

type CompletionPhase = Extract<Phase, "completing" | "awaiting_validation_selection" | "awaiting_plan_revision_decision" | "completed">;

export function CompletionView({
  phase,
  candidates = [],
  guidance,
  revisionReason,
  submit,
  busy = false,
}: {
  phase: CompletionPhase;
  candidates?: ValidationCandidate[];
  guidance?: WritingGuidance | null;
  revisionReason?: string | null;
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  if (phase === "awaiting_validation_selection") {
    return (
      <ValidationSelectionPanel
        candidates={candidates}
        submit={submit}
        busy={busy}
      />
    );
  }
  if (phase === "completed") return <WritingGuidanceView guidance={guidance} />;
  if (phase === "awaiting_plan_revision_decision") {
    return (
      <PlanRevisionPanel
        revisionReason={revisionReason}
        submit={submit}
        busy={busy}
      />
    );
  }
  return (
    <section className="phase-card">
      <p className="card-kicker">Complete</p>
      <h1>正在整理完成建议</h1>
      <p>系统将根据用户亲录结果，决定补充验证、方案修订或写作规划。</p>
    </section>
  );
}
