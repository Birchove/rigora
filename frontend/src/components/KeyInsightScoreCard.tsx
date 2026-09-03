export function KeyInsightScoreCard({
  heading,
  body = "模型五维评分与 Harness final score 将分开呈现，不在浏览器重新计算。",
  checkRound,
  maxCheckRounds,
  score,
  passed,
}: {
  heading: string;
  body?: string;
  checkRound?: number;
  maxCheckRounds?: number;
  score?: number | null;
  passed?: boolean | null;
}) {
  return (
    <article className="phase-card">
      <p className="card-kicker">Key Insight Check</p>
      <h1>{heading}</h1>
      {checkRound !== undefined && maxCheckRounds !== undefined ? (
        <p>已完成 {checkRound}/{maxCheckRounds} 轮校验</p>
      ) : null}
      {score != null ? (
        <p>Harness 总分 {score.toFixed(1)}{passed == null ? "" : passed ? " · 通过" : " · 未通过"}</p>
      ) : null}
      <p>{body}</p>
    </article>
  );
}
