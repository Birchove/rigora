import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, createClient } from "./api/client";
import type { ProjectView, UploadedDocumentView } from "./api/types";
import { ProjectWorkspace } from "./features/project/ProjectWorkspace";
import { useProject } from "./hooks/useProject";
import type { ProjectEventNotice } from "./hooks/useProjectEvents";
import { ThemeProvider } from "./theme/ThemeProvider";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function BootNotice({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="connection-notice" role="alert">
      <h2>{title}</h2>
      <p>{message}</p>
      <button type="button" onClick={onRetry}>
        重试
      </button>
    </div>
  );
}

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
  const [transferStatus, setTransferStatus] = useState<string | null>(null);
  const [parseStatus, setParseStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<UploadedDocumentView[]>([]);
  const [documentNotice, setDocumentNotice] = useState<string | null>(null);

  const refreshDocuments = useCallback(
    (targetId: string) => {
      void client
        .listDocuments(targetId)
        .then(setDocuments)
        .catch((error: unknown) => {
          setDocumentNotice(
            errorMessage(error, "无法刷新文档列表，请稍后重试。"),
          );
          window.setTimeout(() => setDocumentNotice(null), 5000);
        });
    },
    [client],
  );

  const applyEvent = useCallback(
    (event: ProjectEventNotice) => {
      if (event.type !== "document.parsing_progress") {
        return;
      }
      const status = event.data.status;
      if (typeof status === "string") {
        setParseStatus(status);
        if (status === "ready") {
          window.setTimeout(() => {
            setTransferStatus(null);
            setParseStatus(null);
          }, 4000);
        }
      }
      refreshDocuments(projectId);
    },
    [projectId, refreshDocuments],
  );

  const projectApi = useMemo(
    () => ({
      getProject: (id: string) => client.getProject(id),
      applyEvent,
    }),
    [applyEvent, client],
  );
  const { project, refresh, error } = useProject(projectId, projectApi);

  const deleteDocument = (documentId: string) => {
    if (project === null) {
      return;
    }
    void client
      .deleteDocument(project.project_id, documentId)
      .then(() => {
        setDocuments((prev) =>
          prev.filter((item) => item.document_id !== documentId),
        );
        setDocumentNotice(null);
      })
      .catch((error: unknown) => {
        setDocumentNotice(errorMessage(error, "删除失败，请稍后重试。"));
        window.setTimeout(() => setDocumentNotice(null), 5000);
      });
  };

  useEffect(() => {
    if (project === null) {
      return;
    }
    refreshDocuments(project.project_id);
  }, [project?.project_id, refreshDocuments]);

  const loadJournal = useCallback(
    () => client.getJournal(projectId),
    [client, projectId],
  );

  if (error !== null && project === null) {
    return (
      <BootNotice
        title="项目加载失败"
        message={error}
        onRetry={() => {
          void refresh().catch(() => undefined);
        }}
      />
    );
  }

  if (project === null) {
    return (
      <p className="boot-loading" role="status">
        正在加载研究工作区…
      </p>
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
      documents={documents}
      documentNotice={documentNotice}
      onDeleteDocument={deleteDocument}
      onExportMarkdown={() => client.downloadJournal(project.project_id, "md")}
      onExportJson={() => client.downloadJournal(project.project_id, "json")}
      onLoadJournal={loadJournal}
      onUpload={async (file) => {
        setTransferStatus("uploading");
        try {
          const uploaded = (await client.uploadDocument(project.project_id, file)) as {
            document_id?: string;
            status?: string;
          };
          setTransferStatus("complete");
          setParseStatus(uploaded.status ?? "uploaded");
          refreshDocuments(project.project_id);
          if (typeof uploaded.document_id !== "string") {
            return;
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
  const [bootError, setBootError] = useState<string | null>(null);
  const [bootNonce, setBootNonce] = useState(0);

  const refreshProjects = useCallback(() => {
    void client.listProjects().then(setProjects).catch(() => undefined);
  }, [client]);

  const selectProject = (projectId: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("project", projectId);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setBootError(null);
    setLiveId(projectId);
    refreshProjects();
  };

  const createProject = () => {
    void client
      .createProject({
        title: "新研究",
        domain: "computer_science",
      })
      .then((created) => selectProject(created.project_id))
      .catch((error: unknown) => {
        setBootError(errorMessage(error, "无法创建项目。"));
      });
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
    void boot.then(selectProject).catch((error: unknown) => {
      setLiveId(null);
      setBootError(errorMessage(error, "无法连接研究服务。请确认后端已启动后重试。"));
    });
  }, [client, bootNonce]);

  return (
    <ThemeProvider>
      <h1 className="visually-hidden">Rigora</h1>
      {bootError && liveId === null ? (
        <BootNotice
          title="无法连接研究服务"
          message={bootError}
          onRetry={() => {
            setBootError(null);
            setBootNonce((value) => value + 1);
          }}
        />
      ) : liveId ? (
        <LiveWorkspace
          projectId={liveId}
          projects={projects}
          onCreateProject={createProject}
          onSelectProject={selectProject}
          onProjectsChanged={refreshProjects}
        />
      ) : (
        <p className="boot-loading" role="status">
          正在连接研究服务…
        </p>
      )}
    </ThemeProvider>
  );
}
