import { useState } from "react";

import type { ValidationCandidate } from "../api/types";
import type { CommandDraft } from "../hooks/useCommand";

export function ValidationSelectionPanel({
  candidates = [],
  submit,
  busy = false,
}: {
  candidates?: ValidationCandidate[];
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [finishWithoutMore, setFinishWithoutMore] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const disabled = submit === undefined || busy;

  function toggle(candidateId: string) {
    setFinishWithoutMore(false);
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(candidateId)) {
        next.delete(candidateId);
      } else {
        next.add(candidateId);
      }
      return next;
    });
  }

  function confirm() {
    if (submit === undefined) {
      return;
    }
    const selectedIds = candidates
      .filter((candidate) => selected.has(candidate.candidate_id))
      .map((candidate) => candidate.candidate_id);
    if (!finishWithoutMore && selectedIds.length === 0) {
      setError("请先勾选至少一项补充实验，或选择本轮不再补充验证。");
      return;
    }
    if (finishWithoutMore && !reason.trim()) {
      setError("结束本轮补充验证需要写下理由。");
      return;
    }
    setError(null);
    void submit({
      type: "select_validations",
      selection: {
        selected_candidate_ids: finishWithoutMore ? [] : selectedIds,
        skipped_candidate_ids: finishWithoutMore
          ? candidates.map((candidate) => candidate.candidate_id)
          : candidates
            .filter((candidate) => !selected.has(candidate.candidate_id))
            .map((candidate) => candidate.candidate_id),
        finish_without_more_validation: finishWithoutMore,
        user_reason: finishWithoutMore ? reason : null,
      },
    });
  }

  return (
    <section className="phase-card">
      <p className="card-kicker">Validation Queue</p>
      <h1>补充实验</h1>
      <p>候选项按服务器提供的 ID 提交；未选择的验证不会进入执行队列。</p>
      {candidates.length > 0 ? (
        <ul className="validation-candidates">
          {candidates.map((candidate) => (
            <li key={candidate.candidate_id}>
              <label>
                <input
                  type="checkbox"
                  aria-label={candidate.task.name}
                  checked={!finishWithoutMore && selected.has(candidate.candidate_id)}
                  disabled={disabled || finishWithoutMore}
                  onChange={() => toggle(candidate.candidate_id)}
                />
                <span>{candidate.task.name}</span>
              </label>
            </li>
          ))}
        </ul>
      ) : null}
      <label className="structured-check">
        <input
          type="checkbox"
          checked={finishWithoutMore}
          disabled={disabled}
          onChange={(event) => {
            setFinishWithoutMore(event.target.checked);
            if (event.target.checked) {
              setSelected(new Set());
            }
          }}
        />
        本轮不再补充验证
      </label>
      {finishWithoutMore ? (
        <label className="structured-field">
          结束理由
          <textarea
            value={reason}
            disabled={disabled}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
      ) : null}
      {error ? <p className="command-error" role="alert">{error}</p> : null}
      {submit !== undefined ? (
        <button type="button" onClick={confirm} disabled={disabled}>
          确认选择
        </button>
      ) : null}
    </section>
  );
}
