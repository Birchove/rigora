import type { ProjectView } from "../api/types";

interface ProjectSidebarProps {
  project: ProjectView;
  projects?: ProjectView[];
  onCreateProject?: () => void;
  onSelectProject?: (projectId: string) => void;
}

export function ProjectSidebar({
  project,
  projects,
  onCreateProject,
  onSelectProject,
}: ProjectSidebarProps) {
  const items = projects && projects.length > 0 ? projects : [project];
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
        return (
          <a
            key={item.project_id}
            className={active ? "project-link is-active" : "project-link"}
            href={`#project-${item.project_id}`}
            onClick={(event) => {
              if (onSelectProject === undefined) {
                return;
              }
              event.preventDefault();
              onSelectProject(item.project_id);
            }}
          >
            <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
            <span>
              <strong>{item.title}</strong>
              <small>{item.phase.replaceAll("_", " ")}</small>
            </span>
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
