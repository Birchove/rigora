// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Phase, ProjectView } from "../api/types";
import { useProjectEvents } from "./useProjectEvents";

type FakeEvent = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

const fakeEvents = {
  lastUrl: "",
  listeners: new Set<(event: FakeEvent) => void>(),
  emit(event: FakeEvent) {
    for (const listener of this.listeners) {
      listener(event);
    }
  },
};

function project(overrides: Partial<ProjectView> & { last_event_sequence?: number } = {}) {
  return {
    project_id: "p1",
    title: "稳健代码检索",
    domain: "computer_science",
    version: 1,
    phase: "planning" as Phase,
    is_demo: true,
    allowed_commands: [],
    last_event_sequence: 0,
    ...overrides,
  };
}

function fakeApi() {
  return {
    getProject: vi.fn().mockResolvedValue(project()),
    applyEvent: vi.fn(),
    watchEvents(
      projectId: string,
      after: number,
      onEvent: (event: FakeEvent) => void,
    ) {
      fakeEvents.lastUrl = `/api/v1/projects/${projectId}/events?after=${after}`;
      fakeEvents.listeners.add(onEvent);
      return {
        close() {
          fakeEvents.listeners.delete(onEvent);
        },
      };
    },
  };
}

describe("useProjectEvents", () => {
  it("refreshes view after session.phase_changed", async () => {
    const api = fakeApi();
    renderHook(() => useProjectEvents("p1", api));
    fakeEvents.emit({ id: "4", type: "session.phase_changed", data: { phase: "working" } });
    await waitFor(() => expect(api.getProject).toHaveBeenCalledWith("p1"));
  });

  it("does not treat the obsolete phase.changed alias as a real event type", async () => {
    const api = fakeApi();
    renderHook(() => useProjectEvents("p1", api));
    fakeEvents.emit({ id: "4", type: "phase.changed", data: { phase: "working" } });
    await waitFor(() => expect(api.applyEvent).toHaveBeenCalledTimes(1));
    expect(api.getProject).not.toHaveBeenCalled();
  });

  it("drops replayed sequences and reconnects with after", async () => {
    const api = fakeApi();
    renderHook(() => useProjectEvents(project({ last_event_sequence: 4 }), api));
    fakeEvents.emit({ id: "4", type: "session.phase_changed", data: {} });
    fakeEvents.emit({ id: "5", type: "session.phase_changed", data: { phase: "working" } });
    await waitFor(() => expect(api.applyEvent).toHaveBeenCalledTimes(1));
    expect(fakeEvents.lastUrl).toContain("/api/v1/projects/p1/events?after=5");
  });
});
