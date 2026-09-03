import { ApiError } from "./errors";
import type { Command, ProjectView } from "./types";

const readonlyError = {
  code: "static_demo_readonly",
  message: "GitHub Pages 演示为只读。本地启动完整服务后才能提交命令或上传文件。",
  retryable: false,
  details: {},
} as const;

const evidence = [
  {
    title: "State Compression for Reliable Long-Context Recovery",
    source_type: "paper",
    url: "demo://literature/state-compression",
    summary: "用于演示状态压缩研究的证据引用 contract。",
    support: "支撑分层状态压缩降低长对话恢复漂移的假设。",
    selected: true,
  },
];

function planningProject(): ProjectView {
  return {
    project_id: "demo-project-planning",
    title: "Demo：刚提交研究想法",
    domain: "computer_science",
    version: 1,
    phase: "planning",
    is_demo: true,
    allowed_commands: ["run_plan", "cancel_run", "restart_research", "archive_project"],
    last_event_sequence: 1,
    visible_evidence: evidence,
    stage_progress: {
      headline: "想法已审查，可以生成研究方案",
      detail: "研究问题明确、可验证且资源范围合理。",
      check_round: 0,
      max_check_rounds: 5,
      candidate_count: 0,
      idea_type: "opinion",
      idea_action: "proceed_to_plan",
      idea_reason: "研究问题明确、可验证且资源范围合理。",
      normalized_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
    },
    recent_activity: [
      { sequence: 1, type: "session.phase_changed", summary: "进入方案生成" },
    ],
  };
}

function workingProject(): ProjectView {
  return {
    project_id: "demo-project-working",
    title: "Demo：正在进行主实验",
    domain: "computer_science",
    version: 1,
    phase: "working",
    is_demo: true,
    allowed_commands: [
      "send_working_message",
      "finish_working",
      "cancel_run",
      "restart_research",
      "archive_project",
    ],
    last_event_sequence: 2,
    visible_evidence: evidence,
    stage_progress: {
      headline: "正在进行主实验",
      detail: "比较分层状态压缩与完整历史基线。",
      check_round: 1,
      max_check_rounds: 5,
      candidate_count: 1,
      idea_type: "opinion",
      idea_action: "proceed_to_plan",
      idea_reason: "研究问题明确、可验证且资源范围合理。",
      normalized_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
      plan_question: "分层状态压缩能否降低长对话恢复中的状态漂移？",
      key_insight_title: "分层状态压缩",
    },
    current_task: {
      task_id: "demo-main-task",
      task_kind: "main",
      origin: "plan",
      status: "in_progress",
      current_experiment: "比较分层状态压缩与完整历史基线",
      expected_result: "分层状态压缩具有更高恢复正确率",
    },
    working_turns: [
      {
        question: "主实验第一步怎么卡死变量？",
        action: "answer",
        reply: "先固定任务、模型和随机种子，再比较恢复正确率与漂移失败案例。",
        reason: "把主实验收成可核对的对照。",
      },
    ],
    recent_activity: [
      { sequence: 2, type: "session.phase_changed", summary: "进入实验问答" },
    ],
  };
}

function validationProject(): ProjectView {
  return {
    project_id: "demo-project-validation",
    title: "Demo：选择补充验证",
    domain: "computer_science",
    version: 1,
    phase: "awaiting_validation_selection",
    is_demo: true,
    allowed_commands: [
      "select_validations",
      "cancel_run",
      "restart_research",
      "archive_project",
    ],
    last_event_sequence: 3,
    visible_evidence: evidence,
    stage_progress: {
      headline: "请选择补充验证",
      detail: "主实验支持分层状态压缩，但仍需消融验证。",
      check_round: 1,
      max_check_rounds: 5,
      candidate_count: 1,
      idea_type: "opinion",
      idea_action: "proceed_to_plan",
      normalized_idea: "评估分层状态压缩对长对话恢复稳定性的作用",
      plan_question: "分层状态压缩能否降低长对话恢复中的状态漂移？",
      key_insight_title: "分层状态压缩",
    },
    current_task: {
      task_id: "demo-main-task",
      task_kind: "main",
      origin: "plan",
      status: "completed",
      current_experiment: "比较分层状态压缩与完整历史基线",
      expected_result: "分层状态压缩具有更高恢复正确率",
    },
    validation_candidates: [
      {
        candidate_id: "demo-validation-ablation",
        rank: 1,
        priority: "critical",
        rationale: "直接检验核心机制。",
        addresses_claims: ["分层状态压缩降低状态漂移"],
        task: {
          paradigm: "effectiveness",
          validation_type: "ablation",
          name: "移除分层摘要的消融实验",
          purpose: "确认性能增益来自分层状态压缩",
          method: "在相同任务和随机种子上移除分层摘要后比较恢复正确率",
          expected_result: "完整方法的恢复正确率更高",
        },
      },
    ],
    writing_guidance: {
      suggested_structure: ["问题与方法", "主实验结果", "验证与局限"],
      key_results_to_report: ["恢复正确率", "状态漂移失败案例"],
      key_discussion_points: ["分层摘要贡献与替代解释"],
      limitations: ["当前为 deterministic demo fixture，不代表真实实验结果"],
    },
    recent_activity: [
      { sequence: 3, type: "session.phase_changed", summary: "进入验证选择" },
    ],
  };
}

export function staticDemoProjects(): ProjectView[] {
  return [planningProject(), workingProject(), validationProject()];
}

export function isStaticDemo(): boolean {
  return import.meta.env.VITE_STATIC_DEMO === "true";
}

export function createStaticDemoClient() {
  const projects = new Map(
    staticDemoProjects().map((project) => [project.project_id, structuredClone(project)]),
  );

  const readonly = () => {
    throw new ApiError(403, { ...readonlyError });
  };

  return {
    async createProject(input: { title: string; domain: string }) {
      const created: ProjectView = {
        project_id: `static-${crypto.randomUUID()}`,
        title: input.title,
        domain: input.domain,
        version: 1,
        phase: "awaiting_idea",
        is_demo: true,
        allowed_commands: ["submit_idea"],
      };
      projects.set(created.project_id, created);
      return structuredClone(created);
    },

    async listProjects() {
      return [...projects.values()].map((item) => structuredClone(item));
    },

    async getProject(projectId: string) {
      const project = projects.get(projectId);
      if (project === undefined) {
        throw new ApiError(404, {
          code: "project_not_found",
          message: "未找到该演示项目。",
          retryable: false,
          details: {},
        });
      }
      return structuredClone(project);
    },

    async dispatchCommand(_projectId: string, _command: Command): Promise<never> {
      return readonly();
    },

    async listDocuments() {
      return [];
    },

    async downloadJournal(projectId: string, format: "md" | "json") {
      const project = await this.getProject(projectId);
      const body =
        format === "json"
          ? JSON.stringify(project, null, 2)
          : `# ${project.title}\n\nphase: ${project.phase}\n`;
      const blob = new Blob([body], {
        type: format === "json" ? "application/json" : "text/markdown",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `research-journal.${format}`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    },

    async getJournal(projectId: string) {
      const project = await this.getProject(projectId);
      return {
        project: {
          project_id: project.project_id,
          title: project.title,
          domain: project.domain,
        },
        initial_input: {
          original_idea: project.stage_progress?.normalized_idea ?? project.title,
        },
        idea_review: {
          normalized_idea: project.stage_progress?.normalized_idea ?? undefined,
          reason: project.stage_progress?.idea_reason ?? undefined,
        },
        literature: (project.visible_evidence ?? []).map((item) => ({
          title: item.title,
          summary: item.summary ?? undefined,
          url: item.url,
        })),
        writing_guidance: project.writing_guidance ?? null,
      };
    },

    async uploadDocument(_projectId: string, _file: File): Promise<never> {
      return readonly();
    },

    async deleteDocument(_projectId: string, _documentId: string): Promise<never> {
      return readonly();
    },
  };
}
