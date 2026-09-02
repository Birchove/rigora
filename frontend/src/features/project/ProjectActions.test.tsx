// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ValidationSelectionPanel } from "../../components/ValidationSelectionPanel";
import type { CommandType, Phase, ProjectView } from "../../api/types";
import { ProjectWorkspace } from "./ProjectWorkspace";

afterEach(cleanup);

function runningRun() {
  return {
    run_id: "run-1",
    agent_name: "idea_review" as const,
    status: "running" as const,
    public_message: "正在审查研究想法",
  };
}

function project(
  overrides: Partial<ProjectView> & { active_run?: ReturnType<typeof runningRun> } = {},
): ProjectView & { active_run?: ReturnType<typeof runningRun> } {
  return {
    project_id: "project-1",
    title: "稳健代码检索",
    domain: "computer_science",
    version: 3,
    phase: "awaiting_idea" as Phase,
    is_demo: false,
    allowed_commands: ["cancel_run"] as CommandType[],
    ...overrides,
  };
}

const CANDIDATES_REORDERED_FOR_DISPLAY = [
  {
    candidate_id: "candidate-v2",
    rank: 2,
    priority: "high" as const,
    rationale: "检验分布外稳定性",
    addresses_claims: ["robustness"],
    task: {
      paradigm: "robustness_reliability",
      validation_type: "ood_detection",
      name: "鲁棒性验证",
      purpose: "检验分布外稳定性",
      method: "替换测试分布",
      expected_result: null,
    },
  },
  {
    candidate_id: "candidate-v1",
    rank: 1,
    priority: "critical" as const,
    rationale: "排除模块贡献混淆",
    addresses_claims: ["ablation"],
    task: {
      paradigm: "effectiveness",
      validation_type: "ablation",
      name: "消融实验",
      purpose: "排除模块贡献混淆",
      method: "去掉关键模块后重测",
      expected_result: null,
    },
  },
];

function fakeApi() {
  return {
    dispatchCommand: vi.fn().mockResolvedValue({
      project_id: "project-1",
      command_id: "command-1",
      version: 4,
      phase: "working" as Phase,
      is_demo: false,
      allowed_commands: [],
    }),
    getProject: vi.fn(),
  };
}

describe("ProjectActions", () => {
  it("locks ordinary mutations for the full active run", async () => {
    render(
      <ProjectWorkspace
        project={project({ active_run: runningRun(), allowed_commands: ["cancel_run"] })}
      />,
    );
    expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消运行" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "提交研究想法" })).not.toBeInTheDocument();
  });

  it("submits validation candidate IDs in rank-independent UI order", async () => {
    const api = fakeApi();
    render(
      <ValidationSelectionPanel candidates={CANDIDATES_REORDERED_FOR_DISPLAY} api={api} />,
    );
    fireEvent.click(screen.getByLabelText("鲁棒性验证"));
    fireEvent.click(screen.getByRole("button", { name: "确认选择" }));
    expect(api.dispatchCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "select_validations",
        selection: {
          selected_candidate_ids: ["candidate-v2"],
          skipped_candidate_ids: [],
          finish_without_more_validation: false,
          user_reason: null,
        },
      }),
    );
  });
});
