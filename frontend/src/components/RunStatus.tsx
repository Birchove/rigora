import type { Phase } from "../api/types";

const runningCopy: Partial<Record<Phase, string>> = {
  planning: "正在生成方案",
  checking_key_insight: "正在核对证据",
  working: "实验问答中",
  completing: "正在整理结果",
};

export function RunStatus({ phase }: { phase: Phase }) {
  const label = runningCopy[phase] ?? "等待你的操作";
  return <span className="run-status" aria-live="polite"><i aria-hidden="true" />{label}</span>;
}
