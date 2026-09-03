import type { WorkingTurnView } from "../api/types";
import { MarkdownView } from "../ui/markdown";

const ACTION_LABELS: Record<string, string> = {
  answer: "回答",
  clarify: "需要澄清",
  decline: "拒绝",
  report_plan_issue: "报告方案问题",
};

/** 单组问答：摘要显示问题，展开后同时看到问题与回答。 */
export function WorkingMessage({
  turn,
  defaultOpen = false,
}: {
  turn: WorkingTurnView;
  defaultOpen?: boolean;
}) {
  const actionLabel = ACTION_LABELS[turn.action] ?? turn.action;
  const question = turn.question?.trim() ?? "";
  return (
    <details className="qa-item" open={defaultOpen}>
      <summary>
        <span className="qa-question">
          {question !== "" ? question : "（未记下问题）"}
        </span>
        <span className={`qa-action is-${turn.action}`}>{actionLabel}</span>
      </summary>
      <div className="qa-body">
        {question !== "" ? (
          <p className="qa-ask">
            <strong>问</strong>
            <span>{question}</span>
          </p>
        ) : null}
        <div className="qa-reply">
          <strong>答</strong>
          <MarkdownView text={turn.reply} />
        </div>
        {turn.reason ? (
          <MarkdownView text={turn.reason} className="working-message-reason" />
        ) : null}
      </div>
    </details>
  );
}
