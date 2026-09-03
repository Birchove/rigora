import { useState } from "react";

import type { CurrentTaskView } from "../api/types";
import type { CommandDraft } from "../hooks/useCommand";

type ExecutionChoice = "completed" | "failed" | "cancelled";
type ImpactChoice = "supports" | "neutral" | "contradicts" | "invalidates";

export function ExperimentRecordForm({
  task,
  planQuestion,
  submit,
  busy = false,
}: {
  task?: CurrentTaskView | null;
  planQuestion?: string | null;
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  const isValidation = task?.task_kind === "validation";
  const [objective, setObjective] = useState(planQuestion ?? task?.current_experiment ?? "");
  const [method, setMethod] = useState(task?.validation_task?.method ?? "");
  const [expectedResult, setExpectedResult] = useState("");
  const [executionStatus, setExecutionStatus] = useState<ExecutionChoice>("completed");
  const [impact, setImpact] = useState<ImpactChoice>("supports");
  const [actualResult, setActualResult] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [failureReason, setFailureReason] = useState("");
  const [isSuccess, setIsSuccess] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const disabled = submit === undefined || busy;

  function record(): CommandDraft | null {
    if (!actualResult.trim() || !conclusion.trim()) {
      setError("请填写实际结果与结论。实验结果必须由你亲自录入。");
      return null;
    }
    if (executionStatus !== "completed" && !failureReason.trim()) {
      setError("失败或取消时需要填写原因。");
      return null;
    }
    if (isValidation && task?.validation_task == null) {
      setError("当前没有可记录的验证任务。");
      return null;
    }
    const shared = {
      execution_status: executionStatus,
      impact,
      actual_result: actualResult,
      conclusion,
      failure_reason: executionStatus === "completed" ? null : failureReason,
      evidence_files: [],
    };
    if (isValidation && task?.validation_task != null) {
      return {
        type: "record_validation_result",
        result: {
          ...shared,
          task: task.validation_task,
          is_success: isSuccess,
        },
      };
    }
    return {
      type: "record_main_result",
      result: {
        ...shared,
        objective: objective.trim() || task?.current_experiment || "主实验",
        method: method.trim() || "按当前实验任务执行",
        expected_result: expectedResult.trim() || null,
      },
    };
  }

  return (
    <section className="phase-card">
      <p className="card-kicker">Result Record</p>
      <h1>实验结果</h1>
      <p>实验结果必须由用户亲自录入；系统不会从对话中猜测结果。</p>
      {task?.current_experiment ? <p><strong>当前任务</strong> {task.current_experiment}</p> : null}
      <form
        className="structured-form"
        onSubmit={(event) => {
          event.preventDefault();
          const draft = record();
          if (draft === null || submit === undefined) {
            return;
          }
          setError(null);
          void submit(draft);
        }}
      >
        {isValidation ? null : (
          <>
            <label className="structured-field">
              实验目标
              <input value={objective} onChange={(event) => setObjective(event.target.value)} disabled={disabled} />
            </label>
            <label className="structured-field">
              方法
              <input value={method} onChange={(event) => setMethod(event.target.value)} disabled={disabled} />
            </label>
          </>
        )}
        <label className="structured-field">
          预期结果
          <input value={expectedResult} onChange={(event) => setExpectedResult(event.target.value)} disabled={disabled} />
        </label>
        <label className="structured-field">
          执行状态
          <select
            value={executionStatus}
            disabled={disabled}
            onChange={(event) => setExecutionStatus(event.target.value as ExecutionChoice)}
          >
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">取消</option>
          </select>
        </label>
        <label className="structured-field">
          对主张的影响
          <select
            value={impact}
            disabled={disabled}
            onChange={(event) => setImpact(event.target.value as ImpactChoice)}
          >
            <option value="supports">支持</option>
            <option value="neutral">中性</option>
            <option value="contradicts">矛盾</option>
            <option value="invalidates">证伪</option>
          </select>
        </label>
        {executionStatus === "completed" ? null : (
          <label className="structured-field">
            失败或取消原因
            <textarea value={failureReason} onChange={(event) => setFailureReason(event.target.value)} disabled={disabled} />
          </label>
        )}
        <label className="structured-field">
          实际结果
          <textarea value={actualResult} onChange={(event) => setActualResult(event.target.value)} disabled={disabled} required />
        </label>
        <label className="structured-field">
          结论
          <textarea value={conclusion} onChange={(event) => setConclusion(event.target.value)} disabled={disabled} required />
        </label>
        {isValidation ? (
          <label className="structured-check">
            <input
              type="checkbox"
              checked={isSuccess}
              disabled={disabled}
              onChange={(event) => setIsSuccess(event.target.checked)}
            />
            验证成功
          </label>
        ) : null}
        {error ? <p className="command-error" role="alert">{error}</p> : null}
        {submit !== undefined ? (
          <button type="submit" disabled={disabled}>
            {isValidation ? "记录验证结果" : "记录主实验结果"}
          </button>
        ) : null}
      </form>
    </section>
  );
}
