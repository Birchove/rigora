import { useMemo, useState } from "react";

import type { Phase, PlanCandidateView } from "../api/types";
import { MarkdownView } from "../ui/markdown";
import type { CommandDraft } from "../hooks/useCommand";

type PanelPhase = Extract<
  Phase,
  "checking_key_insight" | "awaiting_plan_decision" | "check_loop_exhausted"
>;

const DISPOSITION_LABELS: Record<string, string> = {
  active: "待校验",
  ready: "校验通过",
  exhausted: "轮次用尽",
  override: "已覆盖",
};

export function PlanDecisionPanel({
  phase,
  candidates = [],
  allowedCommands = [],
  submit,
  busy = false,
}: {
  phase: PanelPhase;
  candidates?: PlanCandidateView[];
  allowedCommands?: string[];
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const checking = phase === "checking_key_insight";
  const selectable = useMemo(() => {
    if (checking) {
      return candidates;
    }
    const wanted = phase === "check_loop_exhausted"
      ? ["exhausted"]
      : ["ready", "override"];
    const matched = candidates.filter((item) => wanted.includes(item.disposition));
    return matched.length > 0 ? matched : candidates;
  }, [candidates, checking, phase]);
  const [reason, setReason] = useState("");
  const [overrideTitle, setOverrideTitle] = useState("");
  const [overrideContent, setOverrideContent] = useState("");
  const [overrideRationale, setOverrideRationale] = useState("");
  const disabled = submit === undefined || busy;
  // 单栏/双栏/三栏随候选数量变化，超过三个折叠为三栏
  const columns = Math.min(3, Math.max(1, selectable.length));
  const canDecide = allowedCommands.includes("decide_plan");
  const canCheck = allowedCommands.includes("run_check");
  const recommendedId = selectable[0]?.candidate_id ?? null;

  function send(draft: CommandDraft) {
    if (submit === undefined) {
      return;
    }
    void submit(draft);
  }

  function cardActions(item: PlanCandidateView) {
    if (submit === undefined) {
      return null;
    }
    if (checking) {
      if (item.disposition !== "active") {
        return null;
      }
      if (!canCheck) {
        return null;
      }
      return (
        <button
          type="button"
          className="candidate-action"
          disabled={disabled}
          onClick={() => send({ type: "run_check", candidate_id: item.candidate_id })}
        >
          校验此方案
        </button>
      );
    }
    if (!canDecide) {
      return null;
    }
    if (phase === "check_loop_exhausted") {
      return (
        <button
          type="button"
          className="candidate-action"
          disabled={disabled || !reason.trim()}
          title="带警告继续需要先在下方填写理由"
          onClick={() => send({
            type: "decide_plan",
            candidate_id: item.candidate_id,
            decision: { decision: "continue_imperfect", user_reason: reason },
          })}
        >
          带警告继续此方案
        </button>
      );
    }
    return (
      <>
        <button
          type="button"
          className="candidate-action"
          disabled={disabled}
          onClick={() => send({
            type: "decide_plan",
            candidate_id: item.candidate_id,
            decision: { decision: "accept" },
          })}
        >
          确认此方案
        </button>
        <button
          type="button"
          className="candidate-action secondary-action"
          disabled={disabled}
          onClick={() => send({
            type: "decide_plan",
            candidate_id: item.candidate_id,
            decision: { decision: "request_revision", user_reason: reason || null },
          })}
        >
          请求修改
        </button>
      </>
    );
  }

  if (selectable.length === 0) {
    return null;
  }
  return (
    <section
      className="inline-panel structured-panel plan-decision"
      aria-label={checking ? "候选方案校验" : "方案确认"}
    >
      <strong>
        {checking ? "候选方案校验" : phase === "check_loop_exhausted" ? "校验轮次已用尽" : "等待确认"}
      </strong>
      <p>
        {checking
          ? "每个候选独立校验点睛之笔，全部通过后进入方案确认。"
          : phase === "check_loop_exhausted"
            ? "可以带警告继续某个候选，或在底部用新想法重新审查。"
            : "直接采用推荐方案，或在下方逐个比较确认。"}
      </p>
      <div className={`candidate-grid cols-${columns}`}>
        {selectable.map((item, index) => (
          <article
            key={item.candidate_id}
            className="candidate-card"
            data-disposition={item.disposition}
          >
            <header className="candidate-card-head">
              <strong>
                {item.focus_hint || (selectable.length > 1 ? `候选 ${index + 1}` : "当前方案")}
              </strong>
              <span
                className={
                  item.disposition === "ready" || item.disposition === "override"
                    ? "candidate-badge is-ready"
                    : "candidate-badge"
                }
              >
                {DISPOSITION_LABELS[item.disposition] ?? item.disposition}
                {item.check_round ? ` · ${item.check_round} 轮` : ""}
              </span>
            </header>
            {item.research_question ? (
              <div className="candidate-section">
                <span className="candidate-label">研究问题</span>
                <MarkdownView text={item.research_question} />
              </div>
            ) : null}
            {item.key_insight_title ? (
              <div className="candidate-section">
                <span className="candidate-label">点睛之笔</span>
                <p className="candidate-ki-title">{item.key_insight_title}</p>
                {item.key_insight_content ? (
                  <MarkdownView text={item.key_insight_content} className="candidate-ki-content" />
                ) : null}
              </div>
            ) : null}
            {!item.research_question && !item.key_insight_title ? (
              <p className="candidate-empty">该候选暂无方案内容。</p>
            ) : null}
            <footer className="candidate-card-actions">{cardActions(item)}</footer>
          </article>
        ))}
      </div>
      {submit === undefined ? null : (
        <>
          {!checking && selectable.length > 1 && recommendedId !== null ? (
            <div className="structured-actions">
              <button
                type="button"
                disabled={disabled}
                onClick={() => send({
                  type: "decide_plan",
                  candidate_id: recommendedId,
                  decision: { decision: "accept" },
                })}
              >
                直接采用当前推荐方案
              </button>
            </div>
          ) : null}
          <label className="structured-field">
            理由
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={disabled}
              placeholder={
                phase === "check_loop_exhausted"
                  ? "带警告继续需要填写理由"
                  : "请求修改时建议填写；覆盖点睛之笔时需要填写"
              }
            />
          </label>
          {phase === "awaiting_plan_decision" && recommendedId !== null ? (
            <details className="override-details">
              <summary>覆盖推荐方案的点睛之笔</summary>
              <label className="structured-field">
                标题
                <input
                  value={overrideTitle}
                  onChange={(event) => setOverrideTitle(event.target.value)}
                  disabled={disabled}
                />
              </label>
              <label className="structured-field">
                内容
                <textarea
                  value={overrideContent}
                  onChange={(event) => setOverrideContent(event.target.value)}
                  disabled={disabled}
                />
              </label>
              <label className="structured-field">
                覆盖理由
                <textarea
                  value={overrideRationale}
                  onChange={(event) => setOverrideRationale(event.target.value)}
                  disabled={disabled}
                />
              </label>
              <button
                type="button"
                disabled={disabled}
                onClick={() => send({
                  type: "decide_plan",
                  candidate_id: recommendedId,
                  decision: {
                    decision: "override",
                    user_reason: reason || null,
                    overridden_key_insight: {
                      title: overrideTitle,
                      content: overrideContent,
                      rationale: overrideRationale,
                    },
                  },
                })}
              >
                覆盖后接受
              </button>
            </details>
          ) : null}
        </>
      )}
    </section>
  );
}
