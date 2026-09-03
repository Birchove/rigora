import { useState } from "react";

import { MarkdownView } from "../ui/markdown";
import type { CommandDraft } from "../hooks/useCommand";

export function PlanRevisionPanel({
  revisionReason,
  submit,
  busy = false,
}: {
  revisionReason?: string | null;
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const [reason, setReason] = useState("");
  const disabled = submit === undefined || busy;

  function send(decision: "revise" | "continue_with_warning" | "end_project") {
    if (submit === undefined) {
      return;
    }
    void submit({
      type: "decide_plan_revision",
      decision,
      user_reason: reason.trim() ? reason : null,
    });
  }

  return (
    <section className="phase-card">
      <p className="card-kicker">Complete</p>
      <h1>方案修订</h1>
      <MarkdownView
        text={revisionReason ?? "系统将根据用户亲录结果，决定补充验证、方案修订或写作规划。"}
      />
      <label className="structured-field">
        你的理由
        <textarea
          value={reason}
          disabled={disabled}
          onChange={(event) => setReason(event.target.value)}
          placeholder="带风险继续或结束项目时必填"
        />
      </label>
      {submit !== undefined ? (
        <div className="structured-actions">
          <button type="button" disabled={disabled} onClick={() => send("revise")}>
            按建议修订
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={disabled}
            onClick={() => send("continue_with_warning")}
          >
            带风险继续
          </button>
          <button
            type="button"
            className="secondary-action"
            disabled={disabled}
            onClick={() => send("end_project")}
          >
            结束项目
          </button>
        </div>
      ) : null}
    </section>
  );
}
