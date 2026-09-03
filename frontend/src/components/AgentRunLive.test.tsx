// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ProjectView } from "../api/types";
import { AgentRunLive } from "./AgentRunLive";

afterEach(cleanup);

function projectWithRun(
  overrides: Partial<ProjectView> = {},
  run?: ProjectView["active_run"],
): ProjectView {
  return {
    project_id: "p1",
    title: "研究",
    domain: "computer_science",
    version: 3,
    phase: "planning",
    is_demo: false,
    allowed_commands: [],
    active_run: run ?? {
      run_id: "run-1",
      agent_name: "idea_review",
      status: "running",
      public_message: null,
    },
    recent_activity: [
      { sequence: 1, type: "command.accepted", summary: "已受理指令：submit_idea" },
      { sequence: 2, type: "run.started", summary: "启动文献审查 Agent 运行" },
      { sequence: 3, type: "retrieval.started", summary: "开始检索文献" },
      { sequence: 4, type: "retrieval.results", summary: "文献检索完成，找到 39 条记录" },
    ],
    ...overrides,
  } as ProjectView;
}

describe("AgentRunLive", () => {
  it("shows the running agent with real backend steps", () => {
    render(<AgentRunLive project={projectWithRun()} />);

    expect(screen.getByText("文献审查 Agent运行中")).toBeVisible();
    expect(screen.getByText("指令已受理")).toBeVisible();
    expect(screen.getByText("启动运行")).toBeVisible();
    // 类型标签与后端摘要可能同文，断言至少出现一次
    expect(screen.getAllByText("开始检索文献").length).toBeGreaterThan(0);
    expect(screen.getByText("文献检索完成，找到 39 条记录")).toBeVisible();
    expect(screen.getByText(/00:00/)).toBeVisible();
  });

  it("renders a waiting hint before the first event arrives", () => {
    render(<AgentRunLive project={projectWithRun({ recent_activity: [] })} />);

    expect(screen.getByText(/已受理，等待 Agent 领取任务/)).toBeVisible();
  });

  it("shows a rotating gray status phrase based on the latest event", () => {
    render(<AgentRunLive project={projectWithRun()} />);

    // 最新事件是 retrieval.results → 显示该状态组的第一句短语
    expect(screen.getByText("正在阅读文献摘要…")).toBeVisible();
  });

  it("renders nothing when no run is active", () => {
    const { container } = render(
      <AgentRunLive
        project={projectWithRun({}, {
          run_id: "run-1",
          agent_name: "idea_review",
          status: "succeeded",
          public_message: "运行已完成。",
        })}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
