// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvidencePanel } from "./EvidencePanel";

afterEach(cleanup);

const ITEMS = [
  {
    title: "Adopted paper",
    source_type: "paper" as const,
    url: "javascript:alert(1)",
    summary: "<b>used</b>",
    selected: true,
  },
  {
    title: "Retrieved paper",
    source_type: "paper" as const,
    url: "https://example.com/paper",
    summary: "only retrieved",
    selected: false,
  },
  ...Array.from({ length: 14 }, (_, index) => ({
    title: `Extra ${index}`,
    source_type: "paper" as const,
    url: null,
    summary: "overflow",
    selected: false,
  })),
];

describe("EvidencePanel", () => {
  it("caps the visible list and distinguishes adopted evidence", () => {
    render(<EvidencePanel evidence={ITEMS} />);

    expect(screen.getByText("Adopted paper")).toBeVisible();
    expect(screen.getByText("used")).toBeVisible();
    expect(screen.queryByText("<b>used</b>")).toBeNull();
    expect(screen.queryByRole("link", { name: "Adopted paper" })).toBeNull();
    expect(screen.getByRole("link", { name: "Retrieved paper" })).toHaveAttribute(
      "href",
      "https://example.com/paper",
    );
    expect(screen.getByText("paper · 采用")).toBeVisible();
    expect(document.querySelectorAll(".evidence-list li")).toHaveLength(12);
    expect(screen.queryByText("Extra 11")).toBeNull();
  });

  it("shows only the first sentence of a long evidence summary", () => {
    render(
      <EvidencePanel
        evidence={[
          {
            title: "Long paper",
            source_type: "paper",
            url: null,
            summary: "第一句到此为止。后面还有很多不应出现的摘要内容。",
            selected: true,
          },
        ]}
      />,
    );

    expect(screen.getByText("第一句到此为止。")).toBeVisible();
    expect(screen.queryByText("后面还有很多不应出现的摘要内容。")).toBeNull();
  });

  it("filters to adopted evidence", () => {
    render(<EvidencePanel evidence={ITEMS} />);

    fireEvent.click(screen.getByRole("button", { name: "本轮采用" }));
    expect(screen.getByText("Adopted paper")).toBeVisible();
    expect(screen.queryByText("Retrieved paper")).toBeNull();
  });

  it("renders the uploaded document list with status labels", () => {
    render(
      <EvidencePanel
        documents={[
          { document_id: "d1", original_name: "survey.md", size_bytes: 2048, status: "ready" },
          {
            document_id: "d2",
            original_name: "broken.pdf",
            size_bytes: 1024 * 1024 + 5,
            status: "failed",
          },
        ]}
      />,
    );

    expect(screen.getByText("survey.md")).toBeVisible();
    expect(screen.getByText("2 KB")).toBeVisible();
    expect(screen.getByText("完成")).toBeVisible();
    expect(screen.getByText("broken.pdf")).toBeVisible();
    expect(screen.getByText("1.0 MB")).toBeVisible();
    expect(screen.getByText("解析失败")).toBeVisible();
  });

  it("deletes a document through the row remove button", () => {
    const onDeleteDocument = vi.fn();
    render(
      <EvidencePanel
        documents={[
          { document_id: "d1", original_name: "survey.md", size_bytes: 2048, status: "ready" },
        ]}
        onDeleteDocument={onDeleteDocument}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "删除 survey.md" }));
    expect(onDeleteDocument).toHaveBeenCalledWith("d1");
  });

  it("shows a delete failure notice", () => {
    render(
      <EvidencePanel
        documents={[
          { document_id: "d1", original_name: "survey.md", size_bytes: 2048, status: "ready" },
        ]}
        documentNotice="文档已被实验结果引用，不能删除。"
      />,
    );

    expect(
      screen.getByText("文档已被实验结果引用，不能删除。"),
    ).toBeVisible();
  });
});
