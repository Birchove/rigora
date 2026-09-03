// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarkdownView } from "./markdown";

afterEach(cleanup);

describe("MarkdownView", () => {
  it("renders markdown structure instead of source text", () => {
    render(<MarkdownView text={"# 标题\n\n**重点**与`代码`"} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("标题");
    expect(screen.getByText("重点").tagName).toBe("STRONG");
    expect(screen.getByText("代码").tagName).toBe("CODE");
    expect(screen.queryByText("\\*\\*重点\\*\\*")).toBeNull();
  });

  it("escapes raw html and hardens outbound links", () => {
    render(
      <MarkdownView
        text={"<img src=x onerror=alert(1)>\n\n[论文](https://example.com/a)"}
      />,
    );

    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText(/onerror/)).toBeVisible();
    const link = screen.getByRole("link", { name: "论文" });
    expect(link).toHaveAttribute("href", "https://example.com/a");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
  });

  it("keeps javascript links inert", () => {
    const { container } = render(
      <MarkdownView text="[点击](javascript:alert(1))" />,
    );

    // markdown-it 的 validateLink 直接中和 javascript: 协议，不产生可点击链接
    const links = container.querySelectorAll("a");
    expect(
      Array.from(links).some((item) =>
        (item.getAttribute("href") ?? "").startsWith("javascript:"),
      ),
    ).toBe(false);
  });
});
