// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

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

  it("filters to adopted evidence", () => {
    render(<EvidencePanel evidence={ITEMS} />);

    fireEvent.click(screen.getByRole("button", { name: "本轮采用" }));
    expect(screen.getByText("Adopted paper")).toBeVisible();
    expect(screen.queryByText("Retrieved paper")).toBeNull();
  });
});
