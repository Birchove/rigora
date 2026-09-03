import { useEffect, type ReactNode } from "react";

import type { ProjectView } from "../api/types";
import { BrandMark } from "./BrandMark";
import { PhaseTimeline } from "./PhaseTimeline";
import { ProjectSidebar } from "./ProjectSidebar";
import { RunStatus } from "./RunStatus";
import { ThemeToggle } from "./ThemeToggle";

interface AppShellProps {
  project: ProjectView;
  children: ReactNode;
  evidence: ReactNode;
  actionDock: ReactNode;
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
  onDeleteProject?: (projectId: string) => void;
  projects?: ProjectView[];
  sidebarOpen: boolean;
  onSidebarOpenChange: (open: boolean) => void;
  evidenceOpen: boolean;
  onEvidenceOpenChange: (open: boolean) => void;
}

export function AppShell({
  project,
  children,
  evidence,
  actionDock,
  onCreateProject,
  onSelectProject,
  onDeleteProject,
  projects,
  sidebarOpen,
  onSidebarOpenChange,
  evidenceOpen,
  onEvidenceOpenChange,
}: AppShellProps) {
  const panelOpen = sidebarOpen || evidenceOpen;

  useEffect(() => {
    if (!panelOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closePanels = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onSidebarOpenChange(false);
        onEvidenceOpenChange(false);
      }
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closePanels);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closePanels);
    };
  }, [panelOpen, onSidebarOpenChange, onEvidenceOpenChange]);
  return (
    <div className="workspace-shell" data-evidence-open={evidenceOpen}>
      {import.meta.env.VITE_STATIC_DEMO === "true" ? (
        <p className="static-demo-banner" role="status">
          GitHub Pages 只读演示：可切换三个 Demo 项目查看各阶段界面。提交命令与模型推理请本地运行完整服务。
        </p>
      ) : null}
      <header className="workspace-header">
        <button className="mobile-panel-toggle sidebar-toggle" type="button" aria-controls="project-drawer" aria-expanded={sidebarOpen} onClick={() => onSidebarOpenChange(!sidebarOpen)}>项目</button>
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="Rigora 首页">
          <BrandMark />
        </a>
        <PhaseTimeline phase={project.phase} />
        <div className="workspace-status-cluster">
          <RunStatus project={project} />
          {project.is_demo ? <strong className="demo-badge">DEMO DATA</strong> : null}
          <ThemeToggle />
          <button className="evidence-toggle" type="button" aria-controls="evidence-sheet" aria-expanded={evidenceOpen} onClick={() => onEvidenceOpenChange(!evidenceOpen)}>Evidence</button>
        </div>
      </header>

      <div className="workspace-grid">
        <div id="project-drawer" className="project-drawer" data-open={sidebarOpen}>
          <ProjectSidebar
            project={project}
            projects={projects}
            onCreateProject={onCreateProject}
            onSelectProject={onSelectProject}
            onDeleteProject={onDeleteProject}
          />
        </div>
        <main className="research-main" id="research-main">{children}</main>
        <div id="evidence-sheet" className="evidence-sheet" data-open={evidenceOpen}>{evidence}</div>
      </div>
      {panelOpen ? <button className="panel-scrim" type="button" aria-label="关闭侧栏" onClick={() => { onSidebarOpenChange(false); onEvidenceOpenChange(false); }} /> : null}
      {actionDock}
    </div>
  );
}
