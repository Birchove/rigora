import type { Phase } from "../../api/types";
import { ExperimentRecordForm } from "../../components/ExperimentRecordForm";

type WorkingPhase = Extract<Phase, "awaiting_working_context" | "working" | "awaiting_result_record">;

export function WorkingView({ phase }: { phase: WorkingPhase }) {
  if (phase === "awaiting_result_record") return <ExperimentRecordForm />;
  const heading = phase === "working" ? "实验问答" : "准备实验上下文";
  return (
    <section className="phase-card">
      <p className="card-kicker">Working</p>
      <h1>{heading}</h1>
      <p>围绕当前实验任务与已确认研究上下文推进，不把低检索分数当作硬拒绝。</p>
    </section>
  );
}
