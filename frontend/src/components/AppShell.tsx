import { useEffect, useState, type ReactNode } from "react";

import type { ProjectView } from "../api/types";
import { PhaseTimeline } from "./PhaseTimeline";
import { ProjectSidebar } from "./ProjectSidebar";
import { RunStatus } from "./RunStatus";

interface AppShellProps {
  project: ProjectView;
  children: ReactNode;
  evidence: ReactNode;
  actionDock: ReactNode;
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
  projects?: ProjectView[];
}

export function AppShell({
  project,
  children,
  evidence,
  actionDock,
  onCreateProject,
  onSelectProject,
  projects,
}: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const panelOpen = sidebarOpen || evidenceOpen;

  useEffect(() => {
    if (!panelOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    const closePanels = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSidebarOpen(false);
        setEvidenceOpen(false);
      }
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closePanels);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closePanels);
    };
  }, [panelOpen]);
  return (
    <div className="workspace-shell">
      {import.meta.env.VITE_STATIC_DEMO === "true" ? (
        <p className="static-demo-banner" role="status">
          GitHub Pages 只读演示：可切换三个 Demo 项目查看各阶段界面。提交命令与模型推理请本地运行完整服务。
        </p>
      ) : null}
      <header className="workspace-header">
        <button className="mobile-panel-toggle sidebar-toggle" type="button" aria-controls="project-drawer" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen((open) => !open)}>项目</button>
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="Rigora 首页">
          <span className="brand-mark" aria-hidden="true">R</span>
          <span>
            <strong>Rigora</strong>
            <small>个性化科研探索导师</small>
          </span>
        </a>
        <PhaseTimeline phase={project.phase} />
        <div className="workspace-status-cluster">
        <RunStatus project={project} />
          {project.is_demo ? <strong className="demo-badge">DEMO DATA</strong> : null}
          <button className="mobile-panel-toggle evidence-toggle" type="button" aria-controls="evidence-sheet" aria-expanded={evidenceOpen} onClick={() => setEvidenceOpen((open) => !open)}>证据</button>
        </div>
      </header>

      <div className="workspace-grid">
        <div id="project-drawer" className="project-drawer" data-open={sidebarOpen}>
          <ProjectSidebar
            project={project}
            projects={projects}
            onCreateProject={onCreateProject}
            onSelectProject={onSelectProject}
          />
        </div>
        <main className="research-main" id="research-main">{children}</main>
        <div id="evidence-sheet" className="evidence-sheet" data-open={evidenceOpen}>{evidence}</div>
      </div>
      {panelOpen ? <button className="panel-scrim" type="button" aria-label="关闭侧栏" onClick={() => { setSidebarOpen(false); setEvidenceOpen(false); }} /> : null}
      {actionDock}
    </div>
  );
}
