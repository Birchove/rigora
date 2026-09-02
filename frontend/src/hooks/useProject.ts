import { useCallback, useEffect, useMemo, useState } from "react";

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

  const refresh = useCallback(async () => {
    const next = await api.getProject(projectId);
    setProject(next);
    return next;
  }, [api, projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const eventsApi = useMemo<ProjectEventsApi>(
    () => ({
      getProject: refresh,
      applyEvent: api.applyEvent ?? (() => undefined),
      watchEvents:
        api.watchEvents ??
        ((id, after, onEvent, onDisconnect) => {
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
                source.close();
                onDisconnect?.();
              };
              return source;
            },
          });
          return { close: connection.close };
        }),
    }),
    [api.applyEvent, api.watchEvents, refresh],
  );

  useProjectEvents(project ?? projectId, eventsApi);
  return { project, refresh };
}
