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
        api={fakeApi()}
      />,
    );
    expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消运行" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "提交研究想法" })).not.toBeInTheDocument();
  });

  it("does not send submit_idea until a live command api is attached", () => {
    render(
      <ProjectWorkspace
        project={project({ phase: "awaiting_idea", allowed_commands: ["submit_idea"] })}
      />,
    );
    expect(screen.getByRole("button", { name: "提交研究想法" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
  });

  it("rejects a blank research idea before calling the api", () => {
    const api = fakeApi();
    render(
      <ProjectWorkspace
        project={project({ phase: "awaiting_idea", allowed_commands: ["submit_idea"] })}
        api={api}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "提交研究想法" }));
    expect(api.dispatchCommand).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("请先在输入框写下研究想法");
  });

  it("submits the composer draft with submit_idea", () => {
    const api = fakeApi();
    render(
      <ProjectWorkspace
        project={project({ phase: "awaiting_idea", allowed_commands: ["submit_idea"] })}
        api={api}
      />,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "研究消息" }), {
      target: { value: "评估分层状态压缩对长对话恢复稳定性的作用" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交研究想法" }));
    expect(api.dispatchCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "submit_idea",
        idea: expect.objectContaining({
          original_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
          domain: "computer_science",
        }),
      }),
    );
  });

  it("invokes create-project from the sidebar", () => {
    const onCreateProject = vi.fn();
    render(
      <ProjectWorkspace
        project={project({ phase: "awaiting_idea", allowed_commands: ["submit_idea"] })}
        onCreateProject={onCreateProject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "新建项目" }));
    expect(onCreateProject).toHaveBeenCalledTimes(1);
  });

  it("submits validation candidate IDs in rank-independent UI order", async () => {
    const submit = vi.fn().mockResolvedValue({});
    render(
      <ValidationSelectionPanel candidates={CANDIDATES_REORDERED_FOR_DISPLAY} submit={submit} />,
    );
    fireEvent.click(screen.getByLabelText("鲁棒性验证"));
    fireEvent.click(screen.getByRole("button", { name: "确认选择" }));
    expect(submit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "select_validations",
        selection: {
          selected_candidate_ids: ["candidate-v2"],
          skipped_candidate_ids: ["candidate-v1"],
          finish_without_more_validation: false,
          user_reason: null,
        },
      }),
    );
  });

  it("records a main experiment result from the structured form", () => {
    const api = fakeApi();
    render(
      <ProjectWorkspace
        project={project({
          phase: "awaiting_result_record",
          allowed_commands: ["record_main_result"],
          current_task: {
            task_id: "task-1",
            task_kind: "main",
            origin: "plan",
            status: "in_progress",
            current_experiment: "运行缓存基准",
            expected_result: "延迟下降",
          },
        })}
        api={api}
      />,
    );
    fireEvent.change(screen.getByLabelText("实际结果"), { target: { value: "P95 下降 18%" } });
    fireEvent.change(screen.getByLabelText("结论"), { target: { value: "主实验支持主张" } });
    fireEvent.click(screen.getByRole("button", { name: "记录主实验结果" }));
    expect(api.dispatchCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "record_main_result",
        result: expect.objectContaining({
          actual_result: "P95 下降 18%",
          conclusion: "主实验支持主张",
          expected_result: null,
          execution_status: "completed",
        }),
      }),
    );
  });

  it("leaves expected result blank instead of copying the experiment design", () => {
    render(
      <ProjectWorkspace
        project={project({
          phase: "awaiting_result_record",
          allowed_commands: ["record_main_result"],
          current_task: {
            task_id: "task-1",
            task_kind: "main",
            origin: "plan",
            status: "in_progress",
            current_experiment: "运行缓存基准",
            expected_result: "延迟下降",
          },
        })}
      />,
    );
    expect(screen.getByLabelText("预期结果")).toHaveValue("");
  });

  it("finishes working from the working panel without a composer draft", () => {
    const api = fakeApi();
    render(
      <ProjectWorkspace
        project={project({
          phase: "working",
          allowed_commands: ["send_working_message", "finish_working"],
          current_task: {
            task_id: "task-1",
            task_kind: "main",
            origin: "plan",
            status: "in_progress",
            current_experiment: "运行缓存基准",
          },
        })}
        api={api}
      />,
    );
    expect(screen.getByRole("button", { name: "发送实验问题" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "实验已全部完成，进入下一步" }));
    expect(api.dispatchCommand).toHaveBeenCalledWith(
      expect.objectContaining({ type: "finish_working" }),
    );
    expect(screen.getAllByRole("button", { name: "实验已全部完成，进入下一步" })).toHaveLength(1);
  });

  it("hides the working composer while a clarification panel is pending", () => {
    render(
      <ProjectWorkspace
        project={project({
          phase: "working",
          allowed_commands: ["submit_working_clarification", "finish_working"],
          pending_clarification: {
            original_question: "掉点原因是什么？",
            clarify_reply: "请补充 actual_result。",
          },
          working_turns: [
            { action: "clarify", reason: "缺结果", reply: "请补充 actual_result。" },
          ],
          current_task: {
            task_id: "task-1",
            task_kind: "main",
            origin: "plan",
            status: "in_progress",
            current_experiment: "运行缓存基准",
          },
        })}
        api={fakeApi()}
      />,
    );

    expect(screen.queryByRole("button", { name: "发送实验问题" })).toBeNull();
    expect(screen.getByRole("textbox", { name: "研究消息" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "补充说明" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "提交补充说明" })).toBeEnabled();
  });

  it("disables finish_working while a working run is active", () => {
    render(
      <ProjectWorkspace
        project={project({
          phase: "working",
          allowed_commands: ["send_working_message", "finish_working", "cancel_run"],
          active_run: runningRun(),
          current_task: {
            task_id: "task-1",
            task_kind: "main",
            origin: "plan",
            status: "in_progress",
            current_experiment: "运行缓存基准",
          },
        })}
        api={fakeApi()}
      />,
    );
    expect(screen.getByRole("button", { name: "实验已全部完成，进入下一步" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "取消运行" })).toBeEnabled();
  });

  it("accepts a plan from the decision panel", () => {
    const api = fakeApi();
    render(
      <ProjectWorkspace
        project={project({
          phase: "awaiting_plan_decision",
          allowed_commands: ["decide_plan"],
          plan_candidates: [
            { candidate_id: "candidate-1", disposition: "ready", focus_hint: "稳健性" },
          ],
        })}
        api={api}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "确认此方案" }));
    expect(api.dispatchCommand).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "decide_plan",
        candidate_id: "candidate-1",
        decision: { decision: "accept" },
      }),
    );
  });
});
