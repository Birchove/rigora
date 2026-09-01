export function CollapsibleRunTrace() {
  return (
    <details className="run-trace">
      <summary>查看公开运行步骤</summary>
      <p>只展示检索、评分和整理等公开步骤，不展示模型内部思维链。</p>
    </details>
  );
}
