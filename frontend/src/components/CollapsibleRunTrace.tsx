import type { PublicActivityItem } from "../api/types";
import { stripHtml } from "../ui/safeDisplay";

export function CollapsibleRunTrace({ activity = [] }: { activity?: PublicActivityItem[] }) {
  return (
    <details className="run-trace" open={activity.length > 0}>
      <summary>查看公开运行步骤</summary>
      {activity.length === 0 ? (
        <p>只展示检索、评分和整理等公开步骤，不展示模型内部思维链。</p>
      ) : (
        <ol className="run-trace-list">
          {activity.map((item) => (
            <li key={item.sequence}>
              <span>{item.type}</span>
              <p>{stripHtml(item.summary)}</p>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}
