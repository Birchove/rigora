import { useEffect } from "react";

import type { ProjectView } from "../api/types";

const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 15000];

export type ProjectEventNotice = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

export type ProjectEventsApi = {
  getProject: (projectId: string) => Promise<unknown>;
  applyEvent: (event: ProjectEventNotice) => void;
  watchEvents: (
    projectId: string,
    after: number,
    onEvent: (event: ProjectEventNotice) => void,
    onDisconnect?: () => void,
  ) => { close: () => void };
};

function projectIdOf(source: string | ProjectView): string {
  return typeof source === "string" ? source : source.project_id;
}

function initialSequence(source: string | ProjectView): number {
  return typeof source === "string" ? 0 : (source.last_event_sequence ?? 0);
}

function shouldRefresh(type: string): boolean {
  return (
    type === "session.phase_changed"
    || type === "agent.stage"
    || type === "run.started"
    || type === "run.completed"
    || type === "run.failed"
    || type === "retrieval.started"
    || type === "retrieval.results"
    || type === "evidence.added"
  );
}

export function useProjectEvents(
  source: string | ProjectView,
  api: ProjectEventsApi,
): void {
  const projectId = projectIdOf(source);
  const after = initialSequence(source);

  useEffect(() => {
    let cancelled = false;
    let lastApplied = after;
    let connection: { close: () => void } | undefined;
    let retryIndex = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const handleEvent = (event: ProjectEventNotice) => {
      const sequence = Number.parseInt(event.id, 10);
      if (!Number.isSafeInteger(sequence) || sequence <= lastApplied) {
        return;
      }
      lastApplied = sequence;
      retryIndex = 0;
      api.applyEvent(event);
      if (shouldRefresh(event.type)) {
        void api.getProject(projectId);
      }
      connect();
    };

    const connect = (refresh = false) => {
      if (cancelled) {
        return;
      }
      if (retryTimer !== undefined) {
        clearTimeout(retryTimer);
        retryTimer = undefined;
      }
      connection?.close();
      connection = api.watchEvents(projectId, lastApplied, handleEvent, scheduleReconnect);
      if (refresh) {
        void api.getProject(projectId);
      }
    };

    const scheduleReconnect = () => {
      if (cancelled) {
        return;
      }
      const delay =
        RECONNECT_DELAYS_MS[Math.min(retryIndex, RECONNECT_DELAYS_MS.length - 1)];
      retryIndex += 1;
      retryTimer = setTimeout(() => connect(true), delay);
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer !== undefined) {
        clearTimeout(retryTimer);
      }
      connection?.close();
    };
  }, [after, api, projectId]);
}
