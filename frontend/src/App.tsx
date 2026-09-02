import { useEffect, useMemo, useState } from "react";

import { createClient } from "./api/client";
import type { ProjectView } from "./api/types";
import { ProjectWorkspace } from "./features/project/ProjectWorkspace";
import { useProject } from "./hooks/useProject";

const previewProject: ProjectView = {
  project_id: "preview-project",
  title: "稳健代码检索研究",
  domain: "computer_science",
  version: 1,
  phase: "awaiting_idea",
  is_demo: true,
  allowed_commands: ["submit_idea"],
};

function LiveWorkspace({ projectId }: { projectId: string }) {
  const client = useMemo(() => createClient(), []);
  const projectApi = useMemo(
    () => ({ getProject: (id: string) => client.getProject(id) }),
    [client],
  );
  const { project, refresh } = useProject(projectId, projectApi);
  const [transferStatus, setTransferStatus] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<string | null>(null);

  if (project === null) {
    return <ProjectWorkspace project={previewProject} />;
  }

  return (
    <ProjectWorkspace
      project={project}
      api={{
        async dispatchCommand(command) {
          const result = await client.dispatchCommand(project.project_id, command);
          await refresh();
          return result;
        },
      }}
      transferStatus={transferStatus}
      parseStatus={parseStatus}
      onUpload={async (file) => {
        setTransferStatus("uploading");
        try {
          const uploaded = (await client.uploadDocument(project.project_id, file)) as {
            status?: string;
          };
          setTransferStatus("complete");
          setParseStatus(uploaded.status ?? "uploaded");
        } catch {
          setTransferStatus("failed");
        }
      }}
    />
  );
}

export default function App() {
  const [liveId, setLiveId] = useState<string | null>(null);

  useEffect(() => {
    const client = createClient();
    const requested = new URLSearchParams(window.location.search).get("project");
    const boot = requested
      ? client.getProject(requested).then((item) => item.project_id)
      : client.listProjects().then(async (projects) => {
          if (projects[0] !== undefined) {
            return projects[0].project_id;
          }
          const created = await client.createProject({
            title: "新研究",
            domain: "computer_science",
          });
          return created.project_id;
        });
    void boot.then(setLiveId).catch(() => undefined);
  }, []);

  return (
    <>
      <h1 className="visually-hidden">科研判断与推进工作台</h1>
      {liveId ? <LiveWorkspace projectId={liveId} /> : <ProjectWorkspace project={previewProject} />}
    </>
  );
}
