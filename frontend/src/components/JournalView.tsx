import { useEffect, useState, type ReactNode } from "react";

import type { ResearchJournal } from "../api/types";
import { MarkdownView } from "../ui/markdown";
import { ExportPanel } from "./ExportPanel";

function textList(items?: string[] | null): string[] {
  return (items ?? []).map((item) => item.trim()).filter((item) => item !== "");
}

function formatWhen(iso?: string): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

function Field({ label, children }: { label: string; children?: ReactNode }) {
  if (children === null || children === undefined || children === "") {
    return null;
  }
  return (
    <p className="journal-field">
      <span className="journal-label">{label}</span>
      <span>{children}</span>
    </p>
  );
}

export function JournalView({
  onExportMarkdown,
  onExportJson,
  onLoadJournal,
}: {
  onExportMarkdown?: () => Promise<void> | void;
  onExportJson?: () => Promise<void> | void;
  onLoadJournal?: () => Promise<ResearchJournal>;
}) {
  const [journal, setJournal] = useState<ResearchJournal | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (onLoadJournal === undefined) {
      return;
    }
    let cancelled = false;
    void onLoadJournal()
      .then((next) => {
        if (!cancelled) {
          setJournal(next);
          setError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("研究日志暂时无法加载。仍可导出 Markdown / JSON。");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [onLoadJournal]);

  const idea = journal?.initial_input?.original_idea?.trim() ?? "";
  const normalized = journal?.idea_review?.normalized_idea?.trim() ?? "";
  const reviewReason = journal?.idea_review?.reason?.trim() ?? "";
  const resources = textList(journal?.initial_input?.available_resources);
  const constraints = textList(journal?.initial_input?.other_constraints);
  const literature = journal?.literature ?? [];
  const plans = journal?.plans ?? [];
  const tasks = journal?.experiment_tasks ?? [];
  const main = journal?.main_result ?? null;
  const validations = journal?.validation_results ?? [];
  const guidance = journal?.writing_guidance ?? null;
  const generated = formatWhen(journal?.generated_at);

  return (
    <section className="phase-card journal-view" aria-label="研究日志">
      <p className="card-kicker">Research Journal</p>
      <h1>研究日志</h1>
      <p>按研究阶段整理的可读摘要，可随时导出完整 Markdown / JSON。</p>
      {journal?.project?.title ? (
        <p className="journal-meta">
          <strong>{journal.project.title}</strong>
          {generated !== "" ? <span>生成于 {generated}</span> : null}
        </p>
      ) : null}
      <ExportPanel onExportMarkdown={onExportMarkdown} onExportJson={onExportJson} />
      {error ? <p className="command-error" role="alert">{error}</p> : null}
      {journal === null && error === null && onLoadJournal !== undefined ? (
        <p className="journal-placeholder">正在整理研究日志…</p>
      ) : null}
      {journal !== null ? (
        <div className="journal-sections">
          <article>
            <h2>研究想法</h2>
            {idea !== "" ? <MarkdownView text={idea} /> : <p>尚未提交研究想法。</p>}
            <Field label="领域">{journal.initial_input?.domain}</Field>
            <Field label="规范化表述">{normalized}</Field>
            {reviewReason !== "" ? <MarkdownView text={reviewReason} /> : null}
            {resources.length > 0 ? (
              <Field label="可用资源">{resources.join("、")}</Field>
            ) : null}
            {constraints.length > 0 ? (
              <Field label="约束">{constraints.join("、")}</Field>
            ) : null}
          </article>
          <article>
            <h2>证据</h2>
            {literature.length === 0 ? (
              <p>暂无结构化文献记录。</p>
            ) : (
              <ul className="journal-literature">
                {literature.map((item, index) => (
                  <li key={`${item.title ?? "lit"}-${index}`}>
                    <strong>{item.title ?? "未命名文献"}</strong>
                    {item.year ? <small> {item.year}</small> : null}
                    {item.provider ? <small> · {item.provider}</small> : null}
                    {item.summary ? <p>{item.summary}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </article>
          <article>
            <h2>研究方案</h2>
            {plans.length === 0 ? (
              <p>尚未生成研究方案。</p>
            ) : (
              plans.map((item, index) => (
                <div key={`plan-${index}`} className="journal-plan">
                  <Field label="研究问题">{item.plan?.research_question}</Field>
                  <Field label="点睛之笔">{item.plan?.key_insight?.title}</Field>
                  {item.plan?.key_insight?.content ? (
                    <MarkdownView text={item.plan.key_insight.content} />
                  ) : null}
                  {item.response_to_user ? <MarkdownView text={item.response_to_user} /> : null}
                </div>
              ))
            )}
          </article>
          <article>
            <h2>实验任务</h2>
            {tasks.length === 0 ? (
              <p>尚无实验任务记录。</p>
            ) : (
              <ul>
                {tasks.map((item, index) => (
                  <li key={`task-${index}`}>
                    {item.experiment_info?.current_experiment
                      ?? (item.task_kind === "validation" ? "验证任务" : "主实验")}
                    {item.task_kind ? <small> · {item.task_kind}</small> : null}
                  </li>
                ))}
              </ul>
            )}
          </article>
          <article>
            <h2>实验结果</h2>
            {main == null ? (
              <p>尚无主实验结果。</p>
            ) : (
              <div className="journal-plan">
                <Field label="目标">{main.objective}</Field>
                <Field label="方法">{main.method}</Field>
                <Field label="预期">{main.expected_result}</Field>
                <Field label="实际">{main.actual_result}</Field>
                <Field label="结论">{main.conclusion}</Field>
              </div>
            )}
            {validations.map((item, index) => (
              <div key={`validation-${index}`} className="journal-plan">
                <p>
                  <strong>{item.task?.name ?? `验证 ${index + 1}`}</strong>
                  {item.is_success === true ? " · 成功" : item.is_success === false ? " · 未达预期" : ""}
                </p>
                <Field label="实际">{item.actual_result}</Field>
                <Field label="结论">{item.conclusion}</Field>
              </div>
            ))}
          </article>
          <article>
            <h2>写作规划</h2>
            {guidance == null ? (
              <p>尚未生成写作指导。</p>
            ) : (
              <>
                {textList(guidance.suggested_structure).length > 0 ? (
                  <>
                    <h3>建议结构</h3>
                    <ul>
                      {textList(guidance.suggested_structure).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {textList(guidance.key_results_to_report).length > 0 ? (
                  <>
                    <h3>应报告的关键结果</h3>
                    <ul>
                      {textList(guidance.key_results_to_report).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {textList(guidance.key_discussion_points).length > 0 ? (
                  <>
                    <h3>讨论重点</h3>
                    <ul>
                      {textList(guidance.key_discussion_points).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {textList(guidance.limitations).length > 0 ? (
                  <>
                    <h3>限制</h3>
                    <ul>
                      {textList(guidance.limitations).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                ) : null}
              </>
            )}
          </article>
        </div>
      ) : null}
    </section>
  );
}
