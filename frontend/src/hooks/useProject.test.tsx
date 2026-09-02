// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Phase, ProjectView } from "../api/types";
import { useProject } from "./useProject";

function project(overrides: Partial<ProjectView> = {}): ProjectView {
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

describe("useProject", () => {
  it("does not reopen the event stream when the parent api object identity changes", async () => {
    const view = project();
    const getProject = vi.fn().mockResolvedValue(view);
    const close = vi.fn();
    const watchEvents = vi.fn(() => ({ close }));

    const { rerender } = renderHook(
      ({ api }) => useProject("p1", api),
      {
        initialProps: {
          api: { getProject, watchEvents },
        },
      },
    );

    await waitFor(() => expect(watchEvents).toHaveBeenCalledTimes(1));

    rerender({ api: { getProject, watchEvents } });
    rerender({ api: { getProject, watchEvents } });

    expect(watchEvents).toHaveBeenCalledTimes(1);
    expect(close).not.toHaveBeenCalled();
  });
});
