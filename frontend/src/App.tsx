import type { ProjectView } from "./api/types";
import { ProjectWorkspace } from "./features/project/ProjectWorkspace";

const previewProject: ProjectView = {
  project_id: "preview-project",
  title: "稳健代码检索研究",
  domain: "computer_science",
  version: 1,
  phase: "awaiting_idea",
  is_demo: true,
  allowed_commands: ["submit_idea"],
};

export default function App() {
  return (
    <>
      <h1 className="visually-hidden">科研判断与推进工作台</h1>
      <ProjectWorkspace project={previewProject} />
    </>
  );
}
