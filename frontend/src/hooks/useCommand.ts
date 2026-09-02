import { useRef, useState } from "react";

import { ApiError } from "../api/client";
import type { Command, CommandResponse, ProjectView } from "../api/types";

export type CommandApi = {
  dispatchCommand: (command: Command) => Promise<CommandResponse>;
};

export type CommandError = {
  code: string;
  message: string;
  retryable: boolean;
};

type DistributiveOmit<T, K extends PropertyKey> = T extends unknown ? Omit<T, K> : never;

export type CommandDraft = DistributiveOmit<Command, "command_id" | "expected_version">;

function newCommandId(): string {
  return crypto.randomUUID();
}

function asCommandError(caught: unknown): CommandError {
  if (caught instanceof ApiError) {
    return {
      code: caught.code,
      message: caught.message,
      retryable: caught.retryable,
    };
  }
  if (typeof caught === "object" && caught !== null) {
    const detail = caught as { code?: string; message?: string; retryable?: boolean };
    return {
      code: detail.code ?? "unexpected_response",
      message: detail.message ?? "命令提交失败。",
      retryable: detail.retryable === true,
    };
  }
  return {
    code: "unexpected_response",
    message: "命令提交失败。",
    retryable: false,
  };
}

export function useCommand(project: ProjectView, api: CommandApi) {
  const pendingType = useRef<Command["type"] | null>(null);
  const pendingId = useRef<string | null>(null);
  const lastDraft = useRef<CommandDraft | null>(null);
  const [error, setError] = useState<CommandError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(draft: CommandDraft): Promise<CommandResponse | undefined> {
    lastDraft.current = draft;
    const commandId =
      pendingType.current === draft.type && pendingId.current
        ? pendingId.current
        : newCommandId();
    pendingType.current = draft.type;
    pendingId.current = commandId;
    const command = {
      ...draft,
      command_id: commandId,
      expected_version: project.version,
    } as Command;
    setBusy(true);
    try {
      const result = await api.dispatchCommand(command);
      setError(null);
      pendingType.current = null;
      pendingId.current = null;
      return result;
    } catch (caught) {
      setError(asCommandError(caught));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  async function retry(): Promise<CommandResponse | undefined> {
    if (lastDraft.current === null) {
      return undefined;
    }
    return submit(lastDraft.current);
  }

  function beginNewIntent() {
    pendingType.current = null;
    pendingId.current = null;
  }

  return { submit, retry, beginNewIntent, error, busy };
}
