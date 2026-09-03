import { useCallback, useEffect, useMemo, useState } from "react";

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

function LiveWorkspace({
  projectId,
  projects,
  onCreateProject,
  onSelectProject,
  onProjectsChanged,
}: {
  projectId: string;
  projects: ProjectView[];
  onCreateProject: () => void;
  onSelectProject: (projectId: string) => void;
  onProjectsChanged: () => void;
}) {
  const client = useMemo(() => createClient(), []);
  const projectApi = useMemo(
    () => ({ getProject: (id: string) => client.getProject(id) }),
    [client],
  );
  const { project, refresh } = useProject(projectId, projectApi);
  const [transferStatus, setTransferStatus] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<string | null>(null);

  if (project === null) {
    return (
      <ProjectWorkspace
        project={previewProject}
        projects={projects}
        onCreateProject={onCreateProject}
        onSelectProject={onSelectProject}
      />
    );
  }

  return (
    <ProjectWorkspace
      project={project}
      projects={projects}
      onCreateProject={onCreateProject}
      onSelectProject={onSelectProject}
      api={{
        async dispatchCommand(command) {
          const result = await client.dispatchCommand(project.project_id, command);
          await refresh();
          onProjectsChanged();
          return result;
        },
      }}
      transferStatus={transferStatus}
      parseStatus={parseStatus}
      onExportMarkdown={() => client.downloadJournal(project.project_id, "md")}
      onExportJson={() => client.downloadJournal(project.project_id, "json")}
      onUpload={async (file) => {
        setTransferStatus("uploading");
        try {
          const uploaded = (await client.uploadDocument(project.project_id, file)) as {
            document_id?: string;
            status?: string;
          };
          setTransferStatus("complete");
          setParseStatus(uploaded.status ?? "uploaded");
          const documentId = uploaded.document_id;
          if (typeof documentId !== "string") {
            return;
          }
          const deadline = Date.now() + 120_000;
          while (Date.now() < deadline) {
            const documents = (await client.listDocuments(project.project_id)) as Array<{
              document_id?: string;
              status?: string;
            }>;
            const current = documents.find((item) => item.document_id === documentId);
            if (current?.status !== undefined) {
              setParseStatus(current.status);
              if (current.status === "ready" || current.status === "failed") {
                break;
              }
            }
            await new Promise((resolve) => {
              window.setTimeout(resolve, 400);
            });
          }
        } catch {
          setTransferStatus("failed");
        }
      }}
    />
  );
}

export default function App() {
  const client = useMemo(() => createClient(), []);
  const [liveId, setLiveId] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectView[]>([]);

  const refreshProjects = useCallback(() => {
    void client.listProjects().then(setProjects).catch(() => undefined);
  }, [client]);

  const selectProject = (projectId: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("project", projectId);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setLiveId(projectId);
    refreshProjects();
  };

  const createProject = () => {
    void client
      .createProject({
        title: "新研究",
        domain: "computer_science",
      })
      .then((created) => selectProject(created.project_id));
  };

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("project");
    const boot = requested
      ? client.getProject(requested).then((item) => item.project_id)
      : client.listProjects().then(async (listed) => {
          if (listed[0] !== undefined) {
            setProjects(listed);
            return listed[0].project_id;
          }
          const created = await client.createProject({
            title: "新研究",
            domain: "computer_science",
          });
          return created.project_id;
        });
    void boot.then(selectProject).catch(() => undefined);
  }, [client]);

  return (
    <>
      <h1 className="visually-hidden">Rigora</h1>
      {liveId ? (
        <LiveWorkspace
          projectId={liveId}
          projects={projects}
          onCreateProject={createProject}
          onSelectProject={selectProject}
          onProjectsChanged={refreshProjects}
        />
      ) : (
        <ProjectWorkspace
          project={previewProject}
          projects={projects}
          onCreateProject={createProject}
          onSelectProject={selectProject}
        />
      )}
    </>
  );
}
