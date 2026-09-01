import type { JsonValue } from "./types";

export const PUBLIC_EVENT_TYPES = [
  "command.accepted",
  "run.started",
  "run.completed",
  "run.failed",
  "retrieval.started",
  "retrieval.results",
  "retrieval.unavailable",
  "document.parsing_progress",
  "agent.stage",
  "session.phase_changed",
  "evidence.added",
  "user_input.required",
  "export.ready",
] as const;

export type PublicEventType = (typeof PUBLIC_EVENT_TYPES)[number];

export interface ProjectEvent {
  sequence: number;
  type: PublicEventType;
  data: Record<string, JsonValue>;
}

interface EventSourceLike {
  addEventListener(type: string, listener: (event: MessageEvent) => void): void;
  close(): void;
}

interface ConnectProjectEventsOptions {
  after?: number;
  eventSourceFactory?: (url: string) => EventSourceLike;
  onEvent: (event: ProjectEvent) => void;
}

export function connectProjectEvents(
  projectId: string,
  options: ConnectProjectEventsOptions,
) {
  let cursor = Math.max(0, options.after ?? 0);
  const url = `/api/v1/projects/${encodeURIComponent(projectId)}/events?after=${cursor}`;
  const factory =
    options.eventSourceFactory ?? ((path: string) => new EventSource(path));
  const source = factory(url);

  for (const type of PUBLIC_EVENT_TYPES) {
    source.addEventListener(type, (message) => {
      const sequence = Number.parseInt(message.lastEventId, 10);
      if (!Number.isSafeInteger(sequence) || sequence <= cursor) {
        return;
      }
      cursor = sequence;
      options.onEvent({
        sequence,
        type,
        data: JSON.parse(message.data) as Record<string, JsonValue>,
      });
    });
  }

  return {
    close: () => source.close(),
    lastSequence: () => cursor,
  };
}
