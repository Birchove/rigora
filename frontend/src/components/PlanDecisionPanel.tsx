import { useMemo, useState } from "react";

import type { Phase, PlanCandidateView } from "../api/types";
import type { CommandDraft } from "../hooks/useCommand";

type DecisionPhase = Extract<Phase, "awaiting_plan_decision" | "check_loop_exhausted">;

export function PlanDecisionPanel({
  phase,
  candidates = [],
  submit,
  busy = false,
}: {
  phase: DecisionPhase;
  candidates?: PlanCandidateView[];
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const selectable = useMemo(() => {
    const wanted = phase === "check_loop_exhausted" ? "exhausted" : "ready";
    const matched = candidates.filter(
      (item) => item.disposition === wanted || (wanted === "ready" && item.disposition === "override"),
    );
    return matched.length > 0 ? matched : candidates;
  }, [candidates, phase]);
  const [candidateId, setCandidateId] = useState(selectable[0]?.candidate_id ?? "");
  const [reason, setReason] = useState("");
  const [overrideTitle, setOverrideTitle] = useState("");
  const [overrideContent, setOverrideContent] = useState("");
  const [overrideRationale, setOverrideRationale] = useState("");
  const resolvedCandidateId = candidateId || selectable[0]?.candidate_id || null;
  const disabled = submit === undefined || busy;

  function send(draft: CommandDraft) {
    if (submit === undefined) {
      return;
    }
    void submit(draft);
  }

  return (
    <section className="inline-panel structured-panel" aria-label="方案确认">
      <strong>{phase === "check_loop_exhausted" ? "校验轮次已用尽" : "等待确认"}</strong>
      <p>
        {phase === "check_loop_exhausted"
          ? "可以带警告继续当前候选，或在底部用新想法重新审查。"
          : "接受当前方案、请求修改，或覆盖点睛之笔后再进入实验。"}
      </p>
      {selectable.length > 1 ? (
        <fieldset className="structured-fieldset">
          <legend>候选方案</legend>
          {selectable.map((item) => (
            <label key={item.candidate_id}>
              <input
                type="radio"
                name="plan-candidate"
                checked={resolvedCandidateId === item.candidate_id}
                onChange={() => setCandidateId(item.candidate_id)}
              />
              <span>{item.focus_hint || item.candidate_id}</span>
            </label>
          ))}
        </fieldset>
      ) : null}
      {submit === undefined ? null : (
        <>
          <label className="structured-field">
            理由
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              disabled={disabled}
              placeholder="请求修改、不完美继续或覆盖时需要填写"
            />
          </label>
          {phase === "check_loop_exhausted" ? (
            <div className="structured-actions">
              <button
                type="button"
                disabled={disabled}
                onClick={() => send({
                  type: "decide_plan",
                  candidate_id: resolvedCandidateId,
                  decision: { decision: "continue_imperfect", user_reason: reason },
                })}
              >
                不完美继续
              </button>
            </div>
          ) : (
            <>
              <details className="override-details">
                <summary>覆盖点睛之笔</summary>
                <label className="structured-field">
                  标题
                  <input value={overrideTitle} onChange={(event) => setOverrideTitle(event.target.value)} disabled={disabled} />
                </label>
                <label className="structured-field">
                  内容
                  <textarea value={overrideContent} onChange={(event) => setOverrideContent(event.target.value)} disabled={disabled} />
                </label>
                <label className="structured-field">
                  覆盖理由
                  <textarea value={overrideRationale} onChange={(event) => setOverrideRationale(event.target.value)} disabled={disabled} />
                </label>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => send({
                    type: "decide_plan",
                    candidate_id: resolvedCandidateId,
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
              <div className="structured-actions">
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => send({
                    type: "decide_plan",
                    candidate_id: resolvedCandidateId,
                    decision: { decision: "accept" },
                  })}
                >
                  确认方案
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  disabled={disabled}
                  onClick={() => send({
                    type: "decide_plan",
                    candidate_id: resolvedCandidateId,
                    decision: { decision: "request_revision", user_reason: reason },
                  })}
                >
                  请求修改方案
                </button>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
