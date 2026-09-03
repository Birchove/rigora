import type { WritingGuidance } from "../api/types";
import { MarkdownView } from "../ui/markdown";

function GuidanceList({ heading, items }: { heading: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <>
      <h2>{heading}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <MarkdownView text={item} />
          </li>
        ))}
      </ul>
    </>
  );
}

export function WritingGuidanceView({
  guidance,
}: {
  guidance?: WritingGuidance | null;
}) {
  return (
    <section className="phase-card">
      <p className="card-kicker">Complete</p>
      <h1>写作规划</h1>
      <p>这里组织结构、关键结果、讨论重点与限制，不生成完整论文正文。</p>
      {guidance ? (
        <div className="writing-guidance">
          <GuidanceList heading="建议结构" items={guidance.suggested_structure} />
          <GuidanceList heading="应报告的关键结果" items={guidance.key_results_to_report} />
          <GuidanceList heading="讨论重点" items={guidance.key_discussion_points} />
          <GuidanceList heading="限制" items={guidance.limitations} />
        </div>
      ) : (
        <p>写作指导将在完成阶段生成后显示。</p>
      )}
    </section>
  );
}
