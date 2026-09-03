import type { WorkingTurnView } from "../api/types";
import { MarkdownView } from "../ui/markdown";

const ACTION_LABELS: Record<string, string> = {
  answer: "回答",
  clarify: "需要澄清",
  decline: "拒绝",
  report_plan_issue: "报告方案问题",
};

/** 单组问答：默认收起（最新一组由调用方展开），点开显示完整回答。 */
export function WorkingMessage({
  turn,
  defaultOpen = false,
}: {
  turn: WorkingTurnView;
  defaultOpen?: boolean;
}) {
  const actionLabel = ACTION_LABELS[turn.action] ?? turn.action;
  return (
    <details className="qa-item" open={defaultOpen}>
      <summary>
        <span className="qa-question">
          {turn.question ? turn.question : "（历史问答）"}
        </span>
        <span className={`qa-action is-${turn.action}`}>{actionLabel}</span>
      </summary>
      <div className="qa-body">
        <MarkdownView text={turn.reply} />
        {turn.reason ? (
          <MarkdownView text={turn.reason} className="working-message-reason" />
        ) : null}
      </div>
    </details>
  );
}
