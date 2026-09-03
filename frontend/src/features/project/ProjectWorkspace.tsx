import { useEffect, useRef, useState } from "react";

import type { CommandType, Phase, ProjectView, UploadedDocumentView } from "../../api/types";
import { UPLOAD_PARSE_LABELS, UPLOAD_TRANSFER_LABELS } from "../../ui/uploadLabels";
import { AgentRunLive } from "../../components/AgentRunLive";
import { AppShell } from "../../components/AppShell";
import { CollapsibleRunTrace } from "../../components/CollapsibleRunTrace";
import { EvidencePanel } from "../../components/EvidencePanel";
import { ExportPanel } from "../../components/ExportPanel";
import {
  useCommand,
  type CommandApi,
  type CommandDraft,
  type CommandError,
} from "../../hooks/useCommand";
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
  submit_working_clarification: "提交补充说明",
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
  "submit_working_clarification",
  "record_main_result",
  "record_validation_result",
  "select_validations",
  // run_plan 与 run_check 由候选卡片内的按钮承载，dock 不再重复
  "run_plan",
  "run_check",
  "decide_plan_revision",
]);

const activeRunStatuses = new Set(["queued", "running"]);

const TSUNDERE_LENGTH_LIMIT = 16000;

// 输入框宽度随内容平滑增长（GPT 风格）：CJK/全角按 2 倍视觉宽度估算，触顶后不再增加
const COMPOSER_WIDTH_MIN_REM = 34;
const COMPOSER_WIDTH_MAX_REM = 56;
const COMPOSER_GROW_VISUAL_LENGTH = 120;

function composerWidthRem(draft: string): number {
  let visualLength = 0;
  for (const ch of draft) {
    visualLength += (ch.codePointAt(0) ?? 0) > 0x2e7f ? 2 : 1;
  }
  const ratio = Math.min(1, visualLength / COMPOSER_GROW_VISUAL_LENGTH);
  return COMPOSER_WIDTH_MIN_REM
    + (COMPOSER_WIDTH_MAX_REM - COMPOSER_WIDTH_MIN_REM) * ratio;
}

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
          allowedCommands={project.allowed_commands}
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
          turns={project.working_turns ?? []}
          pendingClarification={project.pending_clarification ?? null}
          projectId={project.project_id}
          submit={allowedSubmit(project, submit, ["finish_working", "record_main_result", "record_validation_result", "submit_working_clarification"])}
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
    case "submit_working_clarification":
      return { type: "submit_working_clarification", clarification: draft };
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
  if (isRunLocked(project)) {
    return project.allowed_commands.filter((command) => command === "cancel_run");
  }
  return project.allowed_commands.filter(
    (command) =>
      !panelOwnedCommands.has(command)
      // 后端恒允许 cancel_run，但没有活动 run 时点击必然报错，空闲时不渲染
      && command !== "cancel_run"
      // archive_project 后端目前是 no-op 占位（不落库），前端不渲染；
      // 后端真实现后由 allowed_commands 恢复。
      && command !== "archive_project",
  );
}

type SubmitFn = (draft: CommandDraft) => Promise<unknown>;

/** 底部输入区：单输入框，左侧“+”上传文档，右侧圆形发送按钮。 */
function Composer({
  project,
  apiAttached,
  onUpload,
  busy,
  error,
  retry,
  submit,
  transferStatus = null,
  parseStatus = null,
}: {
  project: ProjectView;
  apiAttached: boolean;
  onUpload?: (file: File) => Promise<void>;
  busy: boolean;
  error: CommandError | null;
  retry: () => Promise<unknown>;
  submit: SubmitFn;
  transferStatus?: string | null;
  parseStatus?: string | null;
}) {
  const locked = isRunLocked(project);
  const composerCommand = visibleCommands(project).find((command) =>
    composerCommands.has(command),
  );
  const composerEnabled = composerCommand !== undefined && !locked && apiAttached;
  const storageKey = draftKey(project.project_id, project.phase);
  const [draft, setDraft] = useState(() => sessionStorage.getItem(storageKey) ?? "");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [multiline, setMultiline] = useState(false);
  const overTsundere = draft.length > TSUNDERE_LENGTH_LIMIT;

  useEffect(() => {
    setDraft(sessionStorage.getItem(storageKey) ?? "");
  }, [storageKey]);

  // 自动增高并探测是否超过一行：超过后“+”/发送按钮平滑移到左下/右下角。
  // 阈值带迟滞（>48 开启、<40 关闭）：两种布局的换行宽度不同，
  // 单一阈值会在 1↔2 行边界来回振荡。
  useEffect(() => {
    const el = textareaRef.current;
    if (el === null) {
      return;
    }
    el.style.height = "0px";
    const content = el.scrollHeight;
    el.style.height = `${Math.min(content, 160)}px`;
    setMultiline((prev) => (content > 48 ? true : content < 40 ? false : prev));
  }, [draft, storageKey]);

  const sendComposer = () => {
    if (composerCommand === undefined || busy || !apiAttached) {
      return;
    }
    const payload = draftFor(composerCommand, draft, project);
    if (payload === null) {
      return;
    }
    if (composerCommand === "restart_research" && draft.trim()) {
      if (!window.confirm("确认封存当前研究轮次，并用这条新想法重新开始？")) {
        return;
      }
    }
    void submit(payload);
  };

  const transferText: string | null = transferStatus === null
    ? null
    : (UPLOAD_TRANSFER_LABELS[transferStatus] ?? transferStatus);
  const parseText: string | null = parseStatus === null
    ? null
    : (UPLOAD_PARSE_LABELS[parseStatus] ?? parseStatus);
  const uploadFailed = transferStatus === "failed" || parseStatus === "failed";

  return (
    <footer className="action-dock">
      {transferText !== null || parseText !== null ? (
        <p
          className={uploadFailed ? "composer-note is-error" : "composer-note"}
          role="status"
        >
          {[
            transferText !== null ? `传输：${transferText}` : null,
            parseText !== null ? `解析：${parseText}` : null,
          ]
            .filter((part) => part !== null)
            .join("　")}
        </p>
      ) : null}
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
      {overTsundere ? (
        <p className="composer-note" role="status">
          内容较长，建议精简后分多次发送　{draft.length}/19999
        </p>
      ) : null}
      <div
        className={multiline ? "composer-wrap is-multiline" : "composer-wrap"}
        style={{ width: `min(${composerWidthRem(draft).toFixed(2)}rem, 100%)` }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.markdown,.pdf"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file !== undefined && onUpload !== undefined) {
              void onUpload(file);
            }
          }}
        />
        <button
          type="button"
          className="composer-attach"
          aria-label="上传文档"
          disabled={onUpload === undefined || busy}
          onClick={() => fileInputRef.current?.click()}
        >
          +
        </button>
        <label className="visually-hidden" htmlFor="research-message">研究消息</label>
        <textarea
          ref={textareaRef}
          id="research-message"
          value={draft}
          maxLength={19999}
          disabled={!composerEnabled}
          onChange={(event) => {
            const value = event.target.value;
            setDraft(value);
            sessionStorage.setItem(storageKey, value);
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
              return;
            }
            event.preventDefault();
            sendComposer();
          }}
          placeholder={composerEnabled
            ? "输入研究消息（Enter 发送，Shift+Enter 换行）"
            : "当前阶段请在内容区选择操作"}
        />
        <button
          type="button"
          className="composer-send"
          aria-label={composerCommand === undefined ? "发送" : actionLabels[composerCommand]}
          disabled={!composerEnabled || busy}
          onClick={sendComposer}
        >
          <svg
            viewBox="0 0 24 24"
            width="16"
            height="16"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 19V5" />
            <path d="M5 12l7-7 7 7" />
          </svg>
        </button>
      </div>
    </footer>
  );
}

/** 内容区下方操作行：非输入类、非 panel 类的 allowed_commands 药丸按钮。 */
function StreamActions({
  project,
  api,
  busy,
  submit,
}: {
  project: ProjectView;
  api?: CommandApi;
  busy: boolean;
  submit: SubmitFn;
}) {
  const locked = isRunLocked(project);
  const composerCommand = visibleCommands(project).find((command) =>
    composerCommands.has(command),
  );
  const commands = visibleCommands(project).filter((command) => {
    if (command === "restart_research") {
      return composerCommand !== "restart_research";
    }
    return !composerCommands.has(command);
  });
  if (commands.length === 0) {
    return null;
  }
  return (
    <div className="stream-actions" role="group" aria-label="当前可执行操作">
      {commands.map((command) => (
        <button
          key={command}
          type="button"
          className={
            command === "cancel_run" || command === "archive_project"
              ? "action-pill secondary-action"
              : "action-pill"
          }
          disabled={busy || (locked && command !== "cancel_run")}
          onClick={() => {
            if (api === undefined) {
              return;
            }
            const payload = draftFor(command, "", project);
            if (payload !== null) {
              void submit(payload);
            }
          }}
        >
          {actionLabels[command]}
        </button>
      ))}
    </div>
  );
}

export function ProjectWorkspace({
  project,
  api,
  onUpload,
  onCreateProject,
  onSelectProject,
  onDeleteProject,
  projects,
  onExportMarkdown,
  onExportJson,
  transferStatus = null,
  parseStatus = null,
  documents = [],
  documentNotice = null,
  onDeleteDocument,
}: {
  project: ProjectView;
  api?: CommandApi;
  onUpload?: (file: File) => Promise<void>;
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
  onDeleteProject?: (projectId: string) => void;
  projects?: ProjectView[];
  onExportMarkdown?: () => Promise<void> | void;
  onExportJson?: () => Promise<void> | void;
  transferStatus?: string | null;
  parseStatus?: string | null;
  documents?: UploadedDocumentView[];
  documentNotice?: string | null;
  onDeleteDocument?: (documentId: string) => void;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const commandApi = api ?? { dispatchCommand: async () => project };
  const { submit, retry, error, busy } = useCommand(project, commandApi);
  const liveSubmit = api === undefined ? undefined : submit;
  const evidenceCount = project.visible_evidence?.length ?? 0;
  const prevEvidenceCount = useRef(0);

  // 检索证据从无到有时从右侧弹出；用户手动收起后不再自动弹出。
  useEffect(() => {
    if (evidenceCount > 0 && prevEvidenceCount.current === 0) {
      setEvidenceOpen(true);
    }
    prevEvidenceCount.current = evidenceCount;
  }, [evidenceCount]);

  return (
    <AppShell
      project={project}
      projects={projects}
      onCreateProject={onCreateProject}
      onSelectProject={onSelectProject}
      onDeleteProject={onDeleteProject}
      sidebarOpen={sidebarOpen}
      onSidebarOpenChange={setSidebarOpen}
      evidenceOpen={evidenceOpen}
      onEvidenceOpenChange={setEvidenceOpen}
      evidence={
        <EvidencePanel
          evidence={project.visible_evidence ?? []}
          documents={documents}
          documentNotice={documentNotice}
          onDeleteDocument={onDeleteDocument}
          onClose={() => setEvidenceOpen(false)}
        />
      }
      actionDock={
        <Composer
          project={project}
          apiAttached={api !== undefined}
          onUpload={onUpload}
          busy={busy}
          error={error}
          retry={retry}
          submit={submit}
          transferStatus={transferStatus}
          parseStatus={parseStatus}
        />
      }
    >
      <div className="research-stream" id={`project-${project.project_id}`}>
        <div className="research-context-line">
          <span>{project.domain}</span>
          <span>version {project.version}</span>
        </div>
        {isRunActive(project) ? <AgentRunLive project={project} /> : null}
        {phaseContent(project, liveSubmit, busy)}
        <StreamActions
          project={project}
          api={api}
          busy={busy}
          submit={submit}
        />
        {isRunActive(project) ? null : (
          <CollapsibleRunTrace activity={project.recent_activity ?? []} />
        )}
        {project.phase === "completed" ? (
          <ExportPanel onExportMarkdown={onExportMarkdown} onExportJson={onExportJson} />
        ) : null}
      </div>
    </AppShell>
  );
}
