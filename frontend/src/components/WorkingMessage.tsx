import type { WorkingTurnView } from "../api/types";
import { stripHtml } from "../ui/safeDisplay";

const ACTION_LABELS: Record<string, string> = {
  answer: "回答",
  clarify: "需要澄清",
  decline: "拒绝",
  report_plan_issue: "报告方案问题",
};

export function WorkingMessage({ turn }: { turn: WorkingTurnView }) {
  const actionLabel = ACTION_LABELS[turn.action] ?? turn.action;
  return (
    <article className="working-message">
      <p className="card-kicker">{actionLabel}</p>
      <p>{stripHtml(turn.reply)}</p>
      {turn.reason ? <p className="working-message-reason">{stripHtml(turn.reason)}</p> : null}
    </article>
  );
}
