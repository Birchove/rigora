// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CommandType, Phase, ProjectView } from "../../api/types";
import { ProjectWorkspace } from "./ProjectWorkspace";

afterEach(cleanup);

function project(
  phase: Phase,
  allowedCommands: CommandType[],
  overrides: Partial<ProjectView> = {},
): ProjectView {
  return {
    project_id: "project-1",
    title: "稳健代码检索",
    domain: "computer_science",
    version: 3,
    phase,
    is_demo: false,
    allowed_commands: allowedCommands,
    ...overrides,
  };
}

describe("ProjectWorkspace", () => {
  it.each([
    ["awaiting_idea", "研究起点"],
    ["awaiting_idea_refinement", "补充研究边界"],
    ["planning", "等待生成研究方案"],
    ["checking_key_insight", "等待校验点睛之笔"],
    ["awaiting_plan_decision", "研究方案"],
    ["awaiting_working_context", "准备实验上下文"],
    ["working", "实验问答"],
    ["awaiting_result_record", "实验结果"],
    ["completing", "正在整理完成建议"],
    ["awaiting_validation_selection", "补充实验"],
    ["awaiting_plan_revision_decision", "方案修订"],
    ["completed", "写作规划"],
    ["rejected", "Idea 审查结果"],
    ["check_loop_exhausted", "点睛之笔评分"],
  ] as const)("renders the exact %s phase card", (phase, heading) => {
    render(<ProjectWorkspace project={project(phase, [])} />);

    expect(screen.getByRole("heading", { name: heading })).toBeVisible();
  });

  it.each([
    ["awaiting_idea", "submit_idea", "提交研究想法"],
    ["awaiting_plan_decision", "decide_plan", "确认方案"],
    ["working", "finish_working", "实验已全部完成，进入下一步"],
    ["awaiting_result_record", "record_main_result", "记录主实验结果"],
    ["awaiting_validation_selection", "select_validations", "确认选择"],
  ] as const)("renders the server-allowed %s primary action", (phase, command, label) => {
    render(
      <ProjectWorkspace
        project={project(phase, [command])}
        api={{ dispatchCommand: async () => project(phase, [command]) }}
      />,
    );

    expect(screen.getByRole("button", { name: label })).toBeEnabled();
  });

  it("does not infer an action from phase when the server disallows it", () => {
    render(<ProjectWorkspace project={project("awaiting_plan_decision", [])} />);

    expect(screen.queryByRole("button", { name: "确认方案" })).toBeNull();
  });

  it("does not infer finish_working from the working phase", () => {
    render(
      <ProjectWorkspace
        project={project("working", ["send_working_message"])}
        api={{ dispatchCommand: async () => project("working", ["send_working_message"]) }}
      />,
    );

    expect(screen.queryByRole("button", { name: "实验已全部完成，进入下一步" })).toBeNull();
  });

  it("keeps plan revision decisions on the panel, not the dock", () => {
    render(
      <ProjectWorkspace
        project={project("awaiting_plan_revision_decision", ["decide_plan_revision"])}
        api={{
          dispatchCommand: async () =>
            project("awaiting_plan_revision_decision", ["decide_plan_revision"]),
        }}
      />,
    );

    expect(screen.getByRole("button", { name: "按建议修订" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "确认修订方向" })).toBeNull();
  });

  it("keeps demo data visibly marked in the workspace header", () => {
    render(
      <ProjectWorkspace
        project={project("working", ["send_working_message"], { is_demo: true })}
      />,
    );

    expect(screen.getByText("DEMO DATA")).toBeVisible();
  });

  it("keeps evidence in a dedicated filterable region", () => {
    render(<ProjectWorkspace project={project("working", [])} />);

    expect(screen.getByRole("complementary", { name: "证据" })).toBeVisible();
    expect(screen.getByRole("button", { name: "本轮采用" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "未采用" })).toBeEnabled();
  });

  it("locks background scroll while a narrow-screen panel is open and closes on Escape", () => {
    render(<ProjectWorkspace project={project("working", [])} />);
    const toggle = screen.getByRole("button", { name: "证据" });

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.body).toHaveStyle({ overflow: "hidden" });

    fireEvent.keyDown(window, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });
  });
});
