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

function composerBlankMessage(draft: CommandDraft): string | null {
  if (draft.type === "submit_idea" && !draft.idea.original_idea.trim()) {
    return "请先在输入框写下研究想法，再提交。";
  }
  if (draft.type === "submit_refinement" && !draft.refinement.trim()) {
    return "请先填写补充说明，再提交。";
  }
  if (draft.type === "send_working_message" && !draft.question.trim()) {
    return "请先填写要发送的问题，再提交。";
  }
  if (draft.type === "restart_research" && !draft.idea.original_idea.trim()) {
    return "请先写下新的研究想法，再重新开始。";
  }
  if (draft.type === "decide_plan") {
    if (draft.decision.decision === "request_revision" && !draft.decision.user_reason?.trim()) {
      return "请求修改方案时需要写下理由。";
    }
    if (draft.decision.decision === "continue_imperfect" && !draft.decision.user_reason.trim()) {
      return "不完美继续需要写下理由。";
    }
    if (draft.decision.decision === "override") {
      const insight = draft.decision.overridden_key_insight;
      if (!insight.title.trim() || !insight.content.trim() || !insight.rationale.trim()) {
        return "覆盖点睛之笔需要填写标题、内容和理由。";
      }
    }
  }
  if (
    draft.type === "decide_plan_revision"
    && (draft.decision === "continue_with_warning" || draft.decision === "end_project")
    && !draft.user_reason?.trim()
  ) {
    return "该修订决定需要写下理由。";
  }
  return null;
}

export function useCommand(project: ProjectView, api: CommandApi) {
  const pendingType = useRef<Command["type"] | null>(null);
  const pendingId = useRef<string | null>(null);
  const lastDraft = useRef<CommandDraft | null>(null);
  const [error, setError] = useState<CommandError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(draft: CommandDraft): Promise<CommandResponse | undefined> {
    const blankMessage = composerBlankMessage(draft);
    if (blankMessage !== null) {
      setError({ code: "validation_error", message: blankMessage, retryable: false });
      return undefined;
    }
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
