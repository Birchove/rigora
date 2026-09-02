import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { connectProjectEvents } from "../api/events";
import type { ProjectView } from "../api/types";
import { useProjectEvents, type ProjectEventNotice, type ProjectEventsApi } from "./useProjectEvents";

export type ProjectApi = {
  getProject: (projectId: string) => Promise<ProjectView>;
  watchEvents?: ProjectEventsApi["watchEvents"];
  applyEvent?: ProjectEventsApi["applyEvent"];
};

export function useProject(projectId: string, api: ProjectApi) {
  const [project, setProject] = useState<ProjectView | null>(null);
  const apiRef = useRef(api);
  apiRef.current = api;

  const refresh = useCallback(async () => {
    const next = await apiRef.current.getProject(projectId);
    setProject(next);
    return next;
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const eventsApi = useMemo<ProjectEventsApi>(
    () => ({
      getProject: refresh,
      applyEvent: (event) => apiRef.current.applyEvent?.(event),
      watchEvents: (id, after, onEvent, onDisconnect) => {
        const custom = apiRef.current.watchEvents;
        if (custom !== undefined) {
          return custom(id, after, onEvent, onDisconnect);
        }
        let closed = false;
        const connection = connectProjectEvents(id, {
          after,
          onEvent: (event) => {
            onEvent({
              id: String(event.sequence),
              type: event.type,
              data: event.data,
            } satisfies ProjectEventNotice);
          },
          eventSourceFactory: (path) => {
            const source = new EventSource(path);
            source.onerror = () => {
              if (closed) {
                return;
              }
              if (source.readyState === EventSource.CLOSED) {
                onDisconnect?.();
              }
            };
            return source;
          },
        });
        return {
          close: () => {
            closed = true;
            connection.close();
          },
        };
      },
    }),
    [refresh],
  );

  useProjectEvents(project ?? projectId, eventsApi);
  return { project, refresh };
}
