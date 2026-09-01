export function KeyInsightScoreCard({ heading }: { heading: string }) {
  return (
    <article className="phase-card">
      <p className="card-kicker">Key Insight Check</p>
      <h1>{heading}</h1>
      <p>模型五维评分与 Harness final score 将分开呈现，不在浏览器重新计算。</p>
    </article>
  );
}
