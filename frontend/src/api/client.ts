import type {
  ApiErrorEnvelope,
  Command,
  CommandResponse,
  JsonValue,
  ProjectView,
} from "./types";

export type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly details: Record<string, JsonValue>;

  constructor(
    status: number,
    detail: ApiErrorEnvelope["error"],
  ) {
    super(detail.message);
    this.name = "ApiError";
    this.status = status;
    this.code = detail.code;
    this.retryable = detail.retryable;
    this.details = detail.details;
  }
}

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
  fetcher: Fetcher = globalThis.fetch.bind(globalThis),
) {
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
      return json<JsonValue[]>(`/projects/${encodeURIComponent(projectId)}/documents`);
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
