import { useState } from "react";

import type { CommandType, Phase, ProjectView } from "../../api/types";
import { AppShell } from "../../components/AppShell";
import { CollapsibleRunTrace } from "../../components/CollapsibleRunTrace";
import { EvidencePanel } from "../../components/EvidencePanel";
import { ExportPanel } from "../../components/ExportPanel";
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

function phaseContent(phase: Phase) {
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
      return <CompletionView phase={phase} />;
  }
}

function ActionDock({ allowedCommands }: { allowedCommands: CommandType[] }) {
  const [draft, setDraft] = useState("");
  const composerEnabled = allowedCommands.some((command) => composerCommands.has(command));
  return (
    <footer className="action-dock">
      <div className="composer-wrap">
        <label htmlFor="research-message">研究消息</label>
        <textarea
          id="research-message"
          value={draft}
          maxLength={19999}
          disabled={!composerEnabled}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={composerEnabled ? "写下当前阶段需要提交的内容" : "当前阶段请使用右侧操作"}
        />
        <span className="character-count">{draft.length}/19999</span>
      </div>
      <div className="allowed-actions" aria-label="当前可执行操作">
        {allowedCommands.map((command) => (
          <button key={command} type="button" className={command === "cancel_run" ? "secondary-action" : undefined}>
            {actionLabels[command]}
          </button>
        ))}
      </div>
    </footer>
  );
}

export function ProjectWorkspace({ project }: { project: ProjectView }) {
  return (
    <AppShell
      project={project}
      evidence={<EvidencePanel />}
      actionDock={<ActionDock allowedCommands={project.allowed_commands} />}
    >
      <div className="research-stream" id={`project-${project.project_id}`}>
        <div className="research-context-line">
          <span>{project.domain}</span>
          <span>version {project.version}</span>
        </div>
        {phaseContent(project.phase)}
        <CollapsibleRunTrace />
        {project.phase === "completed" ? <ExportPanel /> : null}
      </div>
    </AppShell>
  );
}
