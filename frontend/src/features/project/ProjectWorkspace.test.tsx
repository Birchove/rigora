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
    ["awaiting_plan_decision", "decide_plan", "确认此方案"],
    ["working", "finish_working", "实验已全部完成，进入下一步"],
    ["awaiting_result_record", "record_main_result", "记录主实验结果"],
    ["awaiting_validation_selection", "select_validations", "确认选择"],
  ] as const)("renders the server-allowed %s primary action", (phase, command, label) => {
    render(
      <ProjectWorkspace
        project={project(phase, [command], {
          // 决策面板以候选卡片为操作单元，需提供候选才能渲染确认按钮
          plan_candidates: [
            {
              candidate_id: "candidate-1",
              disposition: "ready",
              focus_hint: "稳健性",
              check_round: 1,
            },
          ],
        })}
        api={{ dispatchCommand: async () => project(phase, [command]) }}
      />,
    );

    expect(screen.getByRole("button", { name: label })).toBeEnabled();
  });

  it("does not infer an action from phase when the server disallows it", () => {
    render(<ProjectWorkspace project={project("awaiting_plan_decision", [])} />);

    expect(screen.queryByRole("button", { name: "确认此方案" })).toBeNull();
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

  it("renders validated working replies on the working card", () => {
    render(
      <ProjectWorkspace
        project={project("working", ["send_working_message", "finish_working"], {
          working_turns: [
            {
              action: "answer",
              reason: "信息足够",
              reply: "先固定随机种子再比较显存。",
            },
          ],
        })}
      />,
    );

    expect(screen.getByText("先固定随机种子再比较显存。")).toBeVisible();
    expect(screen.getByText("回答")).toBeVisible();
  });

  it("collects working clarification on the card instead of the composer", () => {
    const dispatched: Array<{ type: string; clarification?: string }> = [];
    render(
      <ProjectWorkspace
        project={project("working", ["submit_working_clarification", "finish_working"], {
          pending_clarification: {
            original_question: "如果恢复 exact-match 掉了 3 个点，是压缩还是实现 bug？",
            clarify_reply: "请补充是否已有 actual_result。",
            clarify_reason: "缺少会改变判断的结果",
          },
          working_turns: [
            {
              action: "clarify",
              reason: "缺少会改变判断的结果",
              reply: "请补充是否已有 actual_result。",
            },
          ],
        })}
        api={{
          dispatchCommand: async (command) => {
            dispatched.push(command);
            return project("working", ["send_working_message", "finish_working"]);
          },
        }}
      />,
    );

    expect(screen.queryByRole("button", { name: "发送实验问题" })).toBeNull();
    expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "补充说明" }), {
      target: { value: "目前还没跑完，没有 actual_result。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交补充说明" }));

    expect(dispatched).toEqual([
      expect.objectContaining({
        type: "submit_working_clarification",
        clarification: "目前还没跑完，没有 actual_result。",
      }),
    ]);
  });

  it("asks for in-ui confirmation before restart_research", () => {
    const dispatched: Array<{ type: string }> = [];
    render(
      <ProjectWorkspace
        project={project("rejected", ["restart_research"])}
        api={{
          dispatchCommand: async (command) => {
            dispatched.push(command);
            return project("rejected", ["restart_research"]);
          },
        }}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "研究消息" }), {
      target: { value: "换一个更窄的研究问题" },
    });
    fireEvent.click(screen.getByRole("button", { name: "重新审查新想法" }));

    expect(screen.getByRole("alertdialog")).toHaveTextContent("确认封存当前研究轮次");
    expect(dispatched).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "确认重开" }));
    expect(dispatched).toEqual([
      expect.objectContaining({ type: "restart_research" }),
    ]);
  });

  it("warns at the 16k tsundere line, not the 19999 hard cap", () => {
    render(
      <ProjectWorkspace
        project={project("awaiting_idea", ["submit_idea"])}
        api={{ dispatchCommand: async () => project("awaiting_idea", ["submit_idea"]) }}
      />,
    );

    fireEvent.change(screen.getByRole("textbox", { name: "研究消息" }), {
      target: { value: "研".repeat(16001) },
    });

    expect(screen.getByRole("status")).toHaveTextContent("16001/16000");
    expect(screen.queryByText(/19999/)).toBeNull();
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
    const toggle = screen.getByRole("button", { name: "Evidence" });

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(document.body).toHaveStyle({ overflow: "hidden" });

    fireEvent.keyDown(window, { key: "Escape" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });
  });
});
