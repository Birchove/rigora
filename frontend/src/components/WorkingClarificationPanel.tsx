import { useEffect, useState } from "react";

import type { PendingWorkingClarification } from "../api/types";
import type { CommandDraft } from "../hooks/useCommand";

export function WorkingClarificationPanel({
  pending,
  projectId,
  submit,
  busy = false,
}: {
  pending: PendingWorkingClarification;
  projectId: string;
  submit: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const storageKey = `research-mentor:draft:${projectId}:working:clarification`;
  const [clarification, setClarification] = useState(
    () => sessionStorage.getItem(storageKey) ?? "",
  );

  useEffect(() => {
    setClarification(sessionStorage.getItem(storageKey) ?? "");
  }, [storageKey]);

  return (
    <section className="inline-panel structured-panel" aria-label="澄清补充">
      <strong>补充当前澄清</strong>
      <p>这是对上一轮澄清问题的事实补充，不会当成新的实验问题去检索。</p>
      {pending.original_question ? (
        <p className="working-message-reason">原问题：{pending.original_question}</p>
      ) : null}
      <label className="structured-field">
        补充说明
        <textarea
          value={clarification}
          disabled={busy}
          onChange={(event) => {
            const value = event.target.value;
            setClarification(value);
            sessionStorage.setItem(storageKey, value);
          }}
          placeholder="只补充 Agent 问到的关键信息"
        />
      </label>
      <div className="structured-actions">
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            sessionStorage.removeItem(storageKey);
            void submit({
              type: "submit_working_clarification",
              clarification,
            });
          }}
        >
          提交补充说明
        </button>
      </div>
    </section>
  );
}
