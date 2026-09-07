// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("App", () => {
  it("does not fall back to a fake preview project when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const { default: App } = await import("./App");
    render(<App />);

    expect(screen.getByRole("heading", { name: "Rigora" })).toBeTruthy();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "无法连接研究服务" })).toBeTruthy();
    expect(screen.queryByText("稳健代码检索研究")).toBeNull();
    expect(screen.queryByText("AI 聊天助手")).toBeNull();
  });

  it("creates the first project with a user supplied title and domain", async () => {
    const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return new Promise<Response>(() => undefined);
      }
      return Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetcher);
    const { default: App } = await import("./App");
    render(<App />);

    fireEvent.change(await screen.findByRole("textbox", { name: "项目名称" }), {
      target: { value: "课堂反馈研究" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "研究领域" }), {
      target: { value: "教育研究" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    expect(fetcher).toHaveBeenLastCalledWith(
      "/api/v1/projects",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ title: "课堂反馈研究", domain: "教育研究" }),
      }),
    );
  });
});
