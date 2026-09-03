// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("does not fall back to a fake preview project when the API is down", async () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Rigora" })).toBeTruthy();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "无法连接研究服务" })).toBeTruthy();
    expect(screen.queryByText("稳健代码检索研究")).toBeNull();
    expect(screen.queryByText("AI 聊天助手")).toBeNull();
  });
});
