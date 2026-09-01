import type { Phase } from "../api/types";

const stages = ["Idea Review", "Plan", "Check", "Working", "Complete"] as const;

function stageIndex(phase: Phase): number {
  if (phase === "awaiting_idea" || phase === "awaiting_idea_refinement" || phase === "rejected") return 0;
  if (phase === "planning" || phase === "awaiting_plan_decision") return 1;
  if (phase === "checking_key_insight" || phase === "check_loop_exhausted") return 2;
  if (phase === "awaiting_working_context" || phase === "working" || phase === "awaiting_result_record") return 3;
  return 4;
}

export function PhaseTimeline({ phase }: { phase: Phase }) {
  const active = stageIndex(phase);
  return (
    <ol className="phase-timeline" aria-label="研究阶段">
      {stages.map((stage, index) => (
        <li key={stage} className={index <= active ? "is-reached" : undefined} aria-current={index === active ? "step" : undefined}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <strong>{stage}</strong>
        </li>
      ))}
    </ol>
  );
}
