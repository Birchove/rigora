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
  finish_working: "实验已全部完成，进入下一步",
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
  "restart_research",
]);

const panelOwnedCommands = new Set<CommandType>([
  "decide_plan",
  "finish_working",
  "record_main_result",
  "record_validation_result",
  "select_validations",
  "decide_plan_revision",
]);

const activeRunStatuses = new Set(["queued", "running"]);

function isRunActive(project: ProjectView): boolean {
  return Boolean(
    project.active_run
    && (project.active_run.status === "queued" || project.active_run.status === "running"),
  );
}

function allowedSubmit(
  project: ProjectView,
  submit: ((draft: CommandDraft) => Promise<unknown>) | undefined,
  types: CommandType[],
) {
  if (submit === undefined) {
    return undefined;
  }
  if (!types.some((type) => project.allowed_commands.includes(type))) {
    return undefined;
  }
  return submit;
}

function phaseContent(
  project: ProjectView,
  submit?: (draft: CommandDraft) => Promise<unknown>,
  busy = false,
) {
  const phase = project.phase;
  switch (phase) {
    case "awaiting_idea":
    case "awaiting_idea_refinement":
    case "rejected":
      return (
        <IdeaView
          phase={phase}
          ideaReason={project.stage_progress?.idea_reason}
          normalizedIdea={project.stage_progress?.normalized_idea}
        />
      );
    case "planning":
    case "checking_key_insight":
    case "awaiting_plan_decision":
    case "check_loop_exhausted":
      return (
        <PlanView
          phase={phase}
          progress={project.stage_progress}
          running={isRunActive(project)}
          candidates={project.plan_candidates ?? []}
          submit={allowedSubmit(project, submit, ["run_plan", "run_check", "decide_plan"])}
          busy={busy}
        />
      );
    case "awaiting_working_context":
    case "working":
    case "awaiting_result_record":
      return (
        <WorkingView
          phase={phase}
          task={project.current_task}
          planQuestion={project.stage_progress?.plan_question}
          submit={allowedSubmit(project, submit, ["finish_working", "record_main_result", "record_validation_result"])}
          busy={busy || isRunActive(project)}
        />
      );
    case "completing":
    case "awaiting_validation_selection":
    case "awaiting_plan_revision_decision":
    case "completed":
      return (
        <CompletionView
          phase={phase}
          candidates={project.validation_candidates ?? []}
          guidance={project.writing_guidance}
          revisionReason={project.revision_reason}
          submit={allowedSubmit(project, submit, ["select_validations", "decide_plan_revision", "run_complete"])}
          busy={busy}
        />
      );
  }
}

function firstCandidateId(project: ProjectView, dispositions: string[]): string | null {
  const match = (project.plan_candidates ?? []).find((item) => dispositions.includes(item.disposition));
  return match?.candidate_id ?? project.plan_candidates?.[0]?.candidate_id ?? null;
}

function ideaFromDraft(draft: string, project: ProjectView) {
  return {
    original_idea: draft,
    domain: project.domain,
    available_resources: [] as string[],
    unavailable_resources: [] as string[],
    other_constraints: [] as string[],
  };
}

function draftFor(
  command: CommandType,
  draft: string,
  project: ProjectView,
): CommandDraft | null {
  switch (command) {
    case "submit_idea":
      return { type: "submit_idea", idea: ideaFromDraft(draft, project) };
    case "submit_refinement":
      return { type: "submit_refinement", refinement: draft };
    case "send_working_message":
      return { type: "send_working_message", question: draft };
    case "run_plan":
      return { type: "run_plan", mode: "low" };
    case "run_check":
      return {
        type: "run_check",
        candidate_id: firstCandidateId(project, ["active"]),
      };
    case "run_complete":
      return { type: "run_complete", completion_status: true };
    case "resume_working":
      return { type: "resume_working" };
    case "finish_working":
      return { type: "finish_working" };
    case "decide_plan":
      if (project.phase === "check_loop_exhausted") {
        return {
          type: "decide_plan",
          candidate_id: firstCandidateId(project, ["exhausted"]),
          decision: { decision: "continue_imperfect", user_reason: draft },
        };
      }
      return {
        type: "decide_plan",
        candidate_id: firstCandidateId(project, ["ready", "override"]),
        decision: { decision: "accept" },
      };
    case "decide_plan_revision":
      return {
        type: "decide_plan_revision",
        decision: draft.trim() ? "continue_with_warning" : "revise",
        user_reason: draft.trim() ? draft : null,
      };
    case "restart_research":
      return {
        type: "restart_research",
        confirm_restart: true,
        idea: ideaFromDraft(draft, project),
      };
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
  const allowed = isRunLocked(project)
    ? project.allowed_commands.filter((command) => command === "cancel_run")
    : project.allowed_commands;
  return allowed.filter((command) => !panelOwnedCommands.has(command));
}

function ActionDock({
  project,
  api,
  submit,
  retry,
  error,
  busy,
}: {
  project: ProjectView;
  api?: CommandApi;
  submit: (draft: CommandDraft) => Promise<unknown>;
  retry: () => Promise<unknown>;
  error: { code: string; message: string; retryable: boolean } | null;
  busy: boolean;
}) {
  const allowedCommands = visibleCommands(project);
  const locked = isRunLocked(project);
  const composerAllowed = allowedCommands.some((command) => composerCommands.has(command));
  const composerEnabled = composerAllowed && !locked && api !== undefined;
  const storageKey = draftKey(project.project_id, project.phase);
  const [draft, setDraft] = useState(() => sessionStorage.getItem(storageKey) ?? "");

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
          placeholder={composerEnabled ? "写下当前阶段需要提交的内容" : "当前阶段请使用页面中的表单或右侧操作"}
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
            className={command === "cancel_run" || command === "archive_project" ? "secondary-action" : undefined}
            disabled={
              api === undefined
              || (command !== "cancel_run" && (busy || locked))
            }
            onClick={() => {
              if (api === undefined) {
                return;
              }
              const payload = draftFor(command, draft, project);
              if (payload === null) {
                return;
              }
              if (command === "restart_research") {
                if (!draft.trim()) {
                  void submit(payload);
                  return;
                }
                if (!window.confirm("确认封存当前研究轮次，并用这条新想法重新开始？")) {
                  return;
                }
              }
              void submit(payload);
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
  onCreateProject,
  onSelectProject,
  projects,
  onExportMarkdown,
  onExportJson,
  transferStatus = null,
  parseStatus = null,
}: {
  project: ProjectView;
  api?: CommandApi;
  onUpload?: (file: File) => Promise<void>;
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
  projects?: ProjectView[];
  onExportMarkdown?: () => Promise<void> | void;
  onExportJson?: () => Promise<void> | void;
  transferStatus?: string | null;
  parseStatus?: string | null;
}) {
  const commandApi = api ?? { dispatchCommand: async () => project };
  const { submit, retry, error, busy } = useCommand(project, commandApi);
  const liveSubmit = api === undefined ? undefined : submit;

  return (
    <AppShell
      project={project}
      projects={projects}
      onCreateProject={onCreateProject}
      onSelectProject={onSelectProject}
      evidence={
        <EvidencePanel
          evidence={project.visible_evidence ?? []}
          transferStatus={transferStatus}
          parseStatus={parseStatus}
          onUpload={onUpload}
        />
      }
      actionDock={
        <ActionDock
          project={project}
          api={api}
          submit={submit}
          retry={retry}
          error={error}
          busy={busy}
        />
      }
    >
      <div className="research-stream" id={`project-${project.project_id}`}>
        <div className="research-context-line">
          <span>{project.domain}</span>
          <span>version {project.version}</span>
        </div>
        {phaseContent(project, liveSubmit, busy)}
        <CollapsibleRunTrace activity={project.recent_activity ?? []} />
        {project.phase === "completed" ? (
          <ExportPanel onExportMarkdown={onExportMarkdown} onExportJson={onExportJson} />
        ) : null}
      </div>
    </AppShell>
  );
}
