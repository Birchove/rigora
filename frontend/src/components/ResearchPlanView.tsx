export function ResearchPlanView({
  heading,
  body = "研究问题、里程碑与知识准备会在后端确认后作为结构化内容整块呈现。",
  planQuestion,
  keyInsightTitle,
  ideaReason,
}: {
  heading: string;
  body?: string;
  planQuestion?: string | null;
  keyInsightTitle?: string | null;
  ideaReason?: string | null;
}) {
  return (
    <article className="phase-card">
      <p className="card-kicker">Research Plan</p>
      <h1>{heading}</h1>
      {ideaReason ? <p>{ideaReason}</p> : null}
      {planQuestion ? <p><strong>研究问题</strong> {planQuestion}</p> : null}
      {keyInsightTitle ? <p><strong>点睛之笔</strong> {keyInsightTitle}</p> : null}
      <p>{body}</p>
    </article>
  );
}
