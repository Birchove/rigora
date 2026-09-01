import { describe, expect, it, vi } from "vitest";

import { connectProjectEvents } from "./events";

class FakeEventSource {
  readonly listeners = new Map<string, EventListener>();
  close = vi.fn();

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, listener);
  }

  emit(type: string, sequence: number, data: object) {
    this.listeners.get(type)?.({
      type,
      lastEventId: String(sequence),
      data: JSON.stringify(data),
    } as MessageEvent);
  }
}

describe("connectProjectEvents", () => {
  it("connects after the cursor and drops replayed sequences", () => {
    const source = new FakeEventSource();
    const factory = vi.fn().mockReturnValue(source);
    const onEvent = vi.fn();

    const connection = connectProjectEvents("project/1", {
      after: 4,
      eventSourceFactory: factory,
      onEvent,
    });

    expect(factory).toHaveBeenCalledWith(
      "/api/v1/projects/project%2F1/events?after=4",
    );
    source.emit("session.phase_changed", 4, { phase_after: "planning" });
    source.emit("session.phase_changed", 5, { phase_after: "working" });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        sequence: 5,
        type: "session.phase_changed",
        data: { phase_after: "working" },
      }),
    );
    expect(connection.lastSequence()).toBe(5);

    connection.close();
    expect(source.close).toHaveBeenCalledOnce();
  });
});
