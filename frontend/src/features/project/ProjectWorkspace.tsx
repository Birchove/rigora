import { useEffect, useState } from "react";

import type { CommandType, Phase, ProjectView } from "../../api/types";
import { AppShell } from "../../components/AppShell";
import { CollapsibleRunTrace } from "../../components/CollapsibleRunTrace";
import { EvidencePanel } from "../../components/EvidencePanel";
import { ExportPanel } from "../../components/ExportPanel";
import { useCommand, type CommandApi, type CommandDraft } from "../../hooks/useCommand";
import { CompletionView } from "../completion/CompletionView";
import { IdeaView } from "../idea/IdeaView";
import { PlanView } from "../plan/PlanView";
import { WorkingView } from "../working/WorkingView";
import "./workspace.css";

const actionLabels: Record<CommandType, string> = {
  submit_idea: "提交研究想法",
  submit_refinement: "提交补充说明",
  run_plan: "生成研究方案",
  run_check: "校验点睛之笔",
  decide_plan: "确认方案",
  send_working_message: "发送实验问题",
  resume_working: "继续实验问答",
  record_main_result: "记录主实验结果",
  record_validation_result: "记录验证结果",
  run_complete: "整理完成建议",
  select_validations: "选择验证任务",
  decide_plan_revision: "确认修订方向",
  cancel_run: "取消运行",
  restart_research: "重新审查新想法",
  archive_project: "归档项目",
};

const composerCommands = new Set<CommandType>([
  "submit_idea",
  "submit_refinement",
  "send_working_message",
]);

const activeRunStatuses = new Set(["queued", "running"]);

function phaseContent(project: ProjectView, api?: CommandApi) {
  const phase = project.phase;
  switch (phase) {
    case "awaiting_idea":
    case "awaiting_idea_refinement":
    case "rejected":
      return <IdeaView phase={phase} />;
    case "planning":
    case "checking_key_insight":
    case "awaiting_plan_decision":
    case "check_loop_exhausted":
      return <PlanView phase={phase} />;
    case "awaiting_working_context":
    case "working":
    case "awaiting_result_record":
      return <WorkingView phase={phase} />;
    case "completing":
    case "awaiting_validation_selection":
    case "awaiting_plan_revision_decision":
    case "completed":
      return (
        <CompletionView
          phase={phase}
          candidates={project.validation_candidates ?? []}
          api={api}
          expectedVersion={project.version}
        />
      );
  }
}

function draftFor(
  command: CommandType,
  draft: string,
  project: ProjectView,
): CommandDraft | null {
  switch (command) {
    case "submit_idea":
      return {
        type: "submit_idea",
        idea: {
          original_idea: draft,
          domain: project.domain,
          available_resources: [],
          unavailable_resources: [],
          other_constraints: [],
        },
      };
    case "submit_refinement":
      return { type: "submit_refinement", refinement: draft };
    case "send_working_message":
      return { type: "send_working_message", question: draft };
    case "run_plan":
      return { type: "run_plan" };
    case "run_check":
      return { type: "run_check" };
    case "run_complete":
      return { type: "run_complete" };
    case "resume_working":
      return { type: "resume_working" };
    case "decide_plan":
      return { type: "decide_plan", decision: { decision: "accept" } };
    case "decide_plan_revision":
      return { type: "decide_plan_revision", decision: "continue_with_warning" };
    case "cancel_run":
      return { type: "cancel_run", run_id: project.active_run?.run_id ?? null };
    case "archive_project":
      return { type: "archive_project" };
    default:
      return null;
  }
}

function draftKey(projectId: string, phase: Phase): string {
  return `research-mentor:draft:${projectId}:${phase}`;
}

function isRunLocked(project: ProjectView): boolean {
  return project.active_run !== undefined
    && project.active_run !== null
    && activeRunStatuses.has(project.active_run.status);
}

function visibleCommands(project: ProjectView): CommandType[] {
  if (!isRunLocked(project)) {
    return project.allowed_commands;
  }
  return project.allowed_commands.filter((command) => command === "cancel_run");
}

function ActionDock({
  project,
  api,
}: {
  project: ProjectView;
  api?: CommandApi;
}) {
  const allowedCommands = visibleCommands(project);
  const locked = isRunLocked(project);
  const composerAllowed = allowedCommands.some((command) => composerCommands.has(command));
  const composerEnabled = composerAllowed && !locked;
  const storageKey = draftKey(project.project_id, project.phase);
  const [draft, setDraft] = useState(() => sessionStorage.getItem(storageKey) ?? "");
  const commandApi = api ?? { dispatchCommand: async () => project };
  const { submit, retry, error, busy } = useCommand(project, commandApi);

  useEffect(() => {
    setDraft(sessionStorage.getItem(storageKey) ?? "");
  }, [storageKey]);

  return (
    <footer className="action-dock">
      <div className="composer-wrap">
        <label htmlFor="research-message">研究消息</label>
        <textarea
          id="research-message"
          value={draft}
          maxLength={19999}
          disabled={!composerEnabled}
          onChange={(event) => {
            const value = event.target.value;
            setDraft(value);
            sessionStorage.setItem(storageKey, value);
          }}
          placeholder={composerEnabled ? "写下当前阶段需要提交的内容" : "当前阶段请使用右侧操作"}
        />
        <span className="character-count">{draft.length}/19999</span>
        {error ? (
          <p className="command-error" role="alert">
            <strong>{error.code}</strong>
            <span>{error.message}</span>
            {error.retryable ? (
              <button type="button" onClick={() => void retry()} disabled={busy}>
                重试
              </button>
            ) : null}
          </p>
        ) : null}
      </div>
      <div className="allowed-actions" aria-label="当前可执行操作">
        {allowedCommands.map((command) => (
          <button
            key={command}
            type="button"
            className={command === "cancel_run" ? "secondary-action" : undefined}
            disabled={busy || (locked && command !== "cancel_run")}
            onClick={() => {
              if (api === undefined) {
                return;
              }
              const payload = draftFor(command, draft, project);
              if (payload !== null) {
                void submit(payload);
              }
            }}
          >
            {actionLabels[command]}
          </button>
        ))}
      </div>
    </footer>
  );
}

export function ProjectWorkspace({
  project,
  api,
  onUpload,
  transferStatus = null,
  parseStatus = null,
}: {
  project: ProjectView;
  api?: CommandApi;
  onUpload?: (file: File) => Promise<void>;
  transferStatus?: string | null;
  parseStatus?: string | null;
}) {
  return (
    <AppShell
      project={project}
      evidence={
        <EvidencePanel
          transferStatus={transferStatus}
          parseStatus={parseStatus}
          onUpload={onUpload}
        />
      }
      actionDock={<ActionDock project={project} api={api} />}
    >
      <div className="research-stream" id={`project-${project.project_id}`}>
        <div className="research-context-line">
          <span>{project.domain}</span>
          <span>version {project.version}</span>
        </div>
        {phaseContent(project, api)}
        <CollapsibleRunTrace />
        {project.phase === "completed" ? <ExportPanel /> : null}
      </div>
    </AppShell>
  );
}
