import { useEffect, useState } from "react";

import type { ProjectView } from "../api/types";

const AGENT_LABELS: Record<string, string> = {
  idea_review: "文献审查 Agent",
  plan_loop: "方案生成 Agent",
  key_insight_check: "点睛之笔校验 Agent",
  working_qa: "实验问答 Agent",
  complete: "完成建议 Agent",
};

const STEP_LABELS: Record<string, string> = {
  "command.accepted": "指令已受理",
  "run.started": "启动运行",
  "run.completed": "运行完成",
  "run.failed": "运行失败",
  "retrieval.started": "开始检索文献",
  "retrieval.results": "检索返回结果",
  "retrieval.unavailable": "检索暂不可用",
  "agent.stage": "阶段更新",
  "session.phase_changed": "研究阶段推进",
  "document.parsing_progress": "文档解析",
  "evidence.added": "证据入库",
  "user_input.required": "等待输入",
  "export.ready": "导出就绪",
};

/** 按最新事件类型轮换的灰色状态短语，模拟“正在做什么”的实况感。 */
const STATUS_PHRASES: Record<string, string[]> = {
  idle: ["正在排队等待执行…", "正在分配运行资源…"],
  "command.accepted": ["指令已受理，正在排队…", "正在等待 Agent 领取任务…"],
  "run.started": ["正在初始化研究上下文…", "正在装载本次运行快照…"],
  "retrieval.started": [
    "正在查询文献库…",
    "正在拉取论文元数据…",
    "正在筛选高相关文献…",
  ],
  "retrieval.results": ["正在阅读文献摘要…", "正在筛选可支撑判断的证据…"],
  "retrieval.unavailable": ["检索服务暂不可用，正在走降级路径…"],
  "agent.stage": ["正在整理阶段结论…", "正在准备下一步…"],
  "session.phase_changed": ["正在推进研究流程…"],
};

const PHRASE_ROTATE_MS = 3500;
const VISIBLE_STEPS = 6;

function useElapsedSeconds(resetKey: string): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    setSeconds(0);
    const timer = window.setInterval(() => {
      setSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resetKey]);
  return seconds;
}

function useRotatingIndex(length: number, resetKey: string): number {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    setIndex(0);
    if (length <= 1) {
      return;
    }
    const timer = window.setInterval(() => {
      setIndex((value) => (value + 1) % length);
    }, PHRASE_ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [length, resetKey]);
  return index;
}

/** 主界面 Agent 运行实况：真实后端步骤流 + 已耗时 + 灰色状态短语，运行期间替代底部折叠轨迹。 */
export function AgentRunLive({ project }: { project: ProjectView }) {
  const run = project.active_run;
  const active = run !== undefined && run !== null
    && (run.status === "queued" || run.status === "running");
  const seconds = useElapsedSeconds(run?.run_id ?? "idle");
  if (!active || run === undefined || run === null) {
    return null;
  }
  const agentLabel = AGENT_LABELS[run.agent_name] ?? "Agent";
  const steps = (project.recent_activity ?? []).slice(-VISIBLE_STEPS);
  const latestType = steps.length > 0 ? steps[steps.length - 1].type : "idle";
  const phrases = STATUS_PHRASES[latestType] ?? ["正在后台处理…"];
  const phraseIndex = useRotatingIndex(
    phrases.length,
    `${run.run_id}:${latestType}`,
  );
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(
    seconds % 60,
  ).padStart(2, "0")}`;
  return (
    <section className="agent-live" role="status" aria-live="polite" aria-label="Agent 运行实况">
      <div className="agent-live-bar" aria-hidden="true" />
      <header className="agent-live-head">
        <span className="agent-live-dot" aria-hidden="true" />
        <strong>{agentLabel}运行中</strong>
        <span className="agent-live-clock">{clock}</span>
      </header>
      {steps.length === 0 ? (
        <p className="agent-live-waiting">
          已受理，等待 Agent 领取任务<span className="agent-live-ellipsis" aria-hidden="true" />
        </p>
      ) : (
        <ol className="agent-live-steps">
          {steps.map((item, index) => (
            <li
              key={item.sequence}
              className={index === steps.length - 1 ? "is-latest" : undefined}
            >
              <span className="agent-live-step-type">
                {STEP_LABELS[item.type] ?? item.type}
              </span>
              <p>{item.summary}</p>
            </li>
          ))}
        </ol>
      )}
      <p className="agent-live-status" aria-hidden="true" key={`${latestType}:${phraseIndex}`}>
        {phrases[phraseIndex]}
      </p>
    </section>
  );
}
