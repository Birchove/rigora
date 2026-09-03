import { useState } from "react";

import type { Phase, ProjectView } from "../api/types";

const phaseLabels: Record<Phase, string> = {
  awaiting_idea: "等待提交想法",
  awaiting_idea_refinement: "等待补充说明",
  rejected: "Idea 未通过",
  planning: "生成方案中",
  checking_key_insight: "校验点睛之笔",
  awaiting_plan_decision: "等待方案确认",
  check_loop_exhausted: "候选评分完成",
  awaiting_working_context: "准备实验上下文",
  working: "实验问答中",
  awaiting_result_record: "等待结果录入",
  completing: "整理完成建议",
  awaiting_validation_selection: "选择补充验证",
  awaiting_plan_revision_decision: "等待修订决策",
  completed: "已完成",
};

interface ProjectSidebarProps {
  project: ProjectView;
  projects?: ProjectView[];
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
  onDeleteProject?: (projectId: string) => void;
}

/** 侧栏以项目标题命名；标题为空才显示 Untitled。 */
function displayName(item: ProjectView): string {
  const title = item.title.trim();
  return title !== "" ? title : "Untitled";
}

/** 已确认的研究 idea 作为副标题展示，帮助区分同名项目。 */
function ideaSubtitle(item: ProjectView): string {
  return item.stage_progress?.normalized_idea?.trim() ?? "";
}

export function ProjectSidebar({
  project,
  projects,
  onCreateProject,
  onSelectProject,
  onDeleteProject,
}: ProjectSidebarProps) {
  const items = projects && projects.length > 0 ? projects : [project];
  const [menuFor, setMenuFor] = useState<string | null>(null);
  return (
    <nav className="project-sidebar" aria-label="研究项目">
      <div className="sidebar-heading">
        <span>Projects</span>
        <button type="button" aria-label="新建项目" onClick={() => onCreateProject?.()}>
          ＋
        </button>
      </div>
      {items.map((item, index) => {
        const active = item.project_id === project.project_id;
        const menuOpen = menuFor === item.project_id;
        return (
          <a
            key={item.project_id}
            className={active ? "project-link is-active" : "project-link"}
            href={`#project-${item.project_id}`}
            aria-current={active ? "page" : undefined}
            onClick={(event) => {
              if (onSelectProject === undefined || active) {
                return;
              }
              event.preventDefault();
              onSelectProject(item.project_id);
            }}
          >
            <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
            <span>
              <strong>{displayName(item)}</strong>
              {ideaSubtitle(item) !== "" ? (
                <small className="project-idea">{ideaSubtitle(item)}</small>
              ) : null}
              <small>{phaseLabels[item.phase]}</small>
            </span>
            {onDeleteProject !== undefined ? (
              <button
                type="button"
                className={menuOpen ? "project-menu danger" : "project-menu"}
                aria-label={menuOpen ? `删除项目 ${displayName(item)}` : "更多操作"}
                aria-expanded={menuOpen}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  if (menuOpen) {
                    setMenuFor(null);
                    onDeleteProject(item.project_id);
                  } else {
                    setMenuFor(item.project_id);
                  }
                }}
              >
                {menuOpen ? "×" : "…"}
              </button>
            ) : null}
          </a>
        );
      })}
      <div className="product-boundary">
        <strong>使用边界</strong>
        <p>管理科研判断、实验推进与证据记录；不替你执行实验，也不代写论文正文。</p>
      </div>
    </nav>
  );
}
