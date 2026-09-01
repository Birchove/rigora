export function ResearchPlanView({ heading }: { heading: string }) {
  return (
    <article className="phase-card">
      <p className="card-kicker">Research Plan</p>
      <h1>{heading}</h1>
      <p>研究问题、里程碑与知识准备会在后端确认后作为结构化内容整块呈现。</p>
    </article>
  );
}
