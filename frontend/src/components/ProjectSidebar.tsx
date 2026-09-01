import type { ProjectView } from "../api/types";

interface ProjectSidebarProps {
  project: ProjectView;
}

export function ProjectSidebar({ project }: ProjectSidebarProps) {
  return (
    <nav className="project-sidebar" aria-label="研究项目">
      <div className="sidebar-heading">
        <span>Projects</span>
        <button type="button" aria-label="新建项目">＋</button>
      </div>
      <a className="project-link is-active" href={`#project-${project.project_id}`}>
        <span className="project-index">01</span>
        <span>
          <strong>{project.title}</strong>
          <small>{project.phase.replaceAll("_", " ")}</small>
        </span>
      </a>
      <div className="product-boundary">
        <strong>使用边界</strong>
        <p>管理科研判断、实验推进与证据记录；不替你执行实验，也不代写论文正文。</p>
      </div>
    </nav>
  );
}
