import type { ProjectView } from "../api/types";

export function RunStatus({ project }: { project: ProjectView }) {
  const running = project.active_run != null
    && (project.active_run.status === "queued" || project.active_run.status === "running");
  const label = running
    ? (project.active_run?.public_message ?? project.stage_progress?.headline ?? "正在运行")
    : (project.stage_progress?.headline ?? "等待你的操作");
  return (
    <span className="run-status" aria-live="polite">
      <i aria-hidden="true" data-running={running ? "true" : "false"} />
      {label}
    </span>
  );
}
