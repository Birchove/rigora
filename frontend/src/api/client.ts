import { ApiError } from "./errors";
import { createStaticDemoClient, isStaticDemo } from "./staticDemo";
import type {
  ApiErrorEnvelope,
  Command,
  CommandResponse,
  JsonValue,
  ProjectView,
  ResearchJournal,
  UploadedDocumentView,
} from "./types";

export { ApiError };

export type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

const defaultFetcher: Fetcher = globalThis.fetch.bind(globalThis);

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }

  const fallback: ApiErrorEnvelope = {
    error: {
      code: "unexpected_response",
      message: "服务器返回了无法识别的错误。",
      retryable: response.status >= 500,
      details: {},
    },
  };
  const envelope = (await response.json().catch(() => fallback)) as ApiErrorEnvelope;
  throw new ApiError(response.status, envelope.error ?? fallback.error);
}

export function createClient(
  fetcher: Fetcher = defaultFetcher,
) {
  if (isStaticDemo() && fetcher === defaultFetcher) {
    return createStaticDemoClient();
  }
  const json = <T>(path: string, init?: RequestInit) =>
    fetcher(`/api/v1${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    }).then(parseResponse<T>);

  return {
    createProject(input: { title: string; domain: string }) {
      return json<ProjectView>("/projects", {
        method: "POST",
        body: JSON.stringify(input),
      });
    },

    listProjects() {
      return json<ProjectView[]>("/projects");
    },

    getProject(projectId: string) {
      return json<ProjectView>(`/projects/${encodeURIComponent(projectId)}`);
    },

    dispatchCommand(projectId: string, command: Command) {
      return json<CommandResponse>(
        `/projects/${encodeURIComponent(projectId)}/commands`,
        {
          method: "POST",
          body: JSON.stringify({ ...command, project_id: projectId }),
        },
      );
    },

    listDocuments(projectId: string) {
      return json<UploadedDocumentView[]>(`/projects/${encodeURIComponent(projectId)}/documents`);
    },

    getJournal(projectId: string) {
      return json<ResearchJournal>(`/projects/${encodeURIComponent(projectId)}/journal.json`);
    },

    async deleteDocument(projectId: string, documentId: string) {
      const response = await fetcher(
        `/api/v1/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}`,
        { method: "DELETE" },
      );
      if (response.ok || response.status === 204) {
        return;
      }
      const fallback: ApiErrorEnvelope = {
        error: {
          code: "unexpected_response",
          message: "服务器返回了无法识别的错误。",
          retryable: response.status >= 500,
          details: {},
        },
      };
      const envelope = (await response.json().catch(() => fallback)) as ApiErrorEnvelope;
      throw new ApiError(response.status, envelope.error ?? fallback.error);
    },

    async downloadJournal(projectId: string, format: "md" | "json") {
      const suffix = format === "json" ? "json" : "md";
      const response = await fetcher(
        `/api/v1/projects/${encodeURIComponent(projectId)}/journal.${suffix}`,
      );
      if (!response.ok) {
        const fallback: ApiErrorEnvelope = {
          error: {
            code: "unexpected_response",
            message: "服务器返回了无法识别的错误。",
            retryable: response.status >= 500,
            details: {},
          },
        };
        const envelope = (await response.json().catch(() => fallback)) as ApiErrorEnvelope;
        throw new ApiError(response.status, envelope.error ?? fallback.error);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `research-journal.${suffix}`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },

    async uploadDocument(projectId: string, file: File) {
      const response = await fetcher(
        `/api/v1/projects/${encodeURIComponent(projectId)}/documents`,
        { method: "POST", body: (() => {
          const body = new FormData();
          body.append("file", file);
          return body;
        })() },
      );
      if (response.ok) {
        return (await response.json()) as JsonValue;
      }
      const fallback: ApiErrorEnvelope = {
        error: {
          code: "unexpected_response",
          message: "服务器返回了无法识别的错误。",
          retryable: response.status >= 500,
          details: {},
        },
      };
      const envelope = (await response.json().catch(() => fallback)) as ApiErrorEnvelope;
      throw new ApiError(response.status, envelope.error ?? fallback.error);
    },
  };
}

export type ResearchMentorClient = ReturnType<typeof createClient>;
