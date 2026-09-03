// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("presents the product as a research workspace with five main stages", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Rigora" }),
    ).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.queryByText("AI 聊天助手")).toBeNull();
  });
});
