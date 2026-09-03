// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { JournalView } from "./JournalView";

afterEach(cleanup);

describe("JournalView", () => {
  it("renders journal sections as readable copy instead of raw JSON", async () => {
    render(
      <JournalView
        onLoadJournal={async () => ({
          project: {
            project_id: "p1",
            title: "分层状态压缩",
            domain: "computer_science",
          },
          generated_at: "2026-09-01T08:00:00.000Z",
          initial_input: {
            original_idea: "比较分层压缩对长对话恢复的影响",
            domain: "computer science",
          },
          idea_review: {
            normalized_idea: "评估分层状态压缩能否降低恢复漂移",
          },
          literature: [
            {
              title: "State Compression",
              year: 2024,
              summary: "用于长上下文恢复的压缩方法。",
            },
          ],
          plans: [
            {
              response_to_user: "建议先固定随机种子再比较显存。",
              plan: {
                research_question: "分层压缩能否降低漂移？",
                key_insight: { title: "按层冻结状态", content: "只压缩低层激活。" },
              },
            },
          ],
          main_result: {
            objective: "比较恢复正确率",
            actual_result: "正确率提升 4 个点",
            conclusion: "主张成立",
          },
          writing_guidance: {
            suggested_structure: ["引言", "方法"],
            key_results_to_report: ["主实验正确率"],
            key_discussion_points: ["压缩损失"],
            limitations: ["单数据集"],
          },
        })}
      />,
    );

    expect(await screen.findByText("分层状态压缩")).toBeVisible();
    expect(screen.getByText("比较分层压缩对长对话恢复的影响")).toBeVisible();
    expect(screen.getByText("评估分层状态压缩能否降低恢复漂移")).toBeVisible();
    expect(screen.getByText("State Compression")).toBeVisible();
    expect(screen.getByText("分层压缩能否降低漂移？")).toBeVisible();
    expect(screen.getByText("正确率提升 4 个点")).toBeVisible();
    expect(screen.getByText("引言")).toBeVisible();
    expect(screen.queryByText(/"original_idea"/)).toBeNull();
  });

  it("shows a load failure without hiding export actions", async () => {
    render(
      <JournalView
        onExportMarkdown={() => undefined}
        onLoadJournal={async () => {
          throw new Error("offline");
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("研究日志暂时无法加载");
    });
    expect(screen.getByRole("button", { name: "导出 Markdown" })).toBeEnabled();
  });
});
