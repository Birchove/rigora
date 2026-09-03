import type { CurrentTaskView, PendingWorkingClarification, Phase, WorkingTurnView } from "../../api/types";
import { ExperimentRecordForm } from "../../components/ExperimentRecordForm";
import { WorkingClarificationPanel } from "../../components/WorkingClarificationPanel";
import { WorkingMessage } from "../../components/WorkingMessage";
import type { CommandDraft } from "../../hooks/useCommand";

type WorkingPhase = Extract<Phase, "awaiting_working_context" | "working" | "awaiting_result_record">;

export function WorkingView({
  phase,
  task,
  planQuestion,
  turns = [],
  pendingClarification = null,
  projectId,
  submit,
  busy = false,
}: {
  phase: WorkingPhase;
  task?: CurrentTaskView | null;
  planQuestion?: string | null;
  turns?: WorkingTurnView[];
  pendingClarification?: PendingWorkingClarification | null;
  projectId?: string;
  submit?: (draft: CommandDraft) => Promise<unknown>;
  busy?: boolean;
}) {
  if (phase === "awaiting_result_record") {
    return (
      <ExperimentRecordForm
        task={task}
        planQuestion={planQuestion}
        submit={submit}
        busy={busy}
      />
    );
  }
  const heading = phase === "working" ? "实验问答" : "准备实验上下文";
  const canFinish = phase === "working" && submit !== undefined;
  const showClarification =
    phase === "working"
    && pendingClarification !== null
    && pendingClarification !== undefined
    && submit !== undefined
    && projectId !== undefined;
  return (
    <section className="phase-card">
      <p className="card-kicker">Working</p>
      <h1>{heading}</h1>
      {task?.current_experiment ? <p><strong>当前实验</strong> {task.current_experiment}</p> : null}
      <p>围绕当前实验任务与已确认研究上下文推进，不把低检索分数当作硬拒绝。</p>
      {turns.length > 0 ? (
        <div className="working-turns">
          {turns.map((turn, index) => (
            <WorkingMessage key={`${turn.action}-${index}`} turn={turn} />
          ))}
        </div>
      ) : null}
      {showClarification ? (
        <WorkingClarificationPanel
          pending={pendingClarification}
          projectId={projectId}
          submit={submit}
          busy={busy}
        />
      ) : null}
      {canFinish ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            void submit({ type: "finish_working" });
          }}
        >
          实验已全部完成，进入下一步
        </button>
      ) : null}
    </section>
  );
}
