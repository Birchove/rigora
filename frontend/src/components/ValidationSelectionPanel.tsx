import { useState } from "react";

import type { ValidationCandidate } from "../api/types";
import type { CommandApi } from "../hooks/useCommand";

export type ValidationCommandApi = CommandApi;

interface ValidationSelectionPanelProps {
  candidates?: ValidationCandidate[];
  api?: ValidationCommandApi;
  expectedVersion?: number;
}

export function ValidationSelectionPanel({
  candidates = [],
  api,
  expectedVersion = 1,
}: ValidationSelectionPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  function toggle(candidateId: string) {
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
    if (api === undefined) {
      return;
    }
    void api.dispatchCommand({
      type: "select_validations",
      command_id: crypto.randomUUID(),
      expected_version: expectedVersion,
      selection: {
        selected_candidate_ids: candidates
          .filter((candidate) => selected.has(candidate.candidate_id))
          .map((candidate) => candidate.candidate_id),
        skipped_candidate_ids: [],
        finish_without_more_validation: false,
        user_reason: null,
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
                  checked={selected.has(candidate.candidate_id)}
                  onChange={() => toggle(candidate.candidate_id)}
                />
                <span>{candidate.task.name}</span>
              </label>
            </li>
          ))}
        </ul>
      ) : null}
      {api !== undefined ? (
        <button type="button" onClick={confirm}>
          确认选择
        </button>
      ) : null}
    </section>
  );
}
