import { useState } from "react";

import { DocumentPanel } from "./DocumentPanel";

type EvidenceFilter = "all" | "adopted" | "discarded";

export function EvidencePanel() {
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  return (
    <aside className="evidence-panel" aria-label="证据">
      <div className="panel-heading">
        <span>Evidence</span>
        <strong>本轮证据</strong>
      </div>
      <div className="evidence-filters" aria-label="证据筛选">
        <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>全部</button>
        <button type="button" aria-pressed={filter === "adopted"} onClick={() => setFilter("adopted")}>本轮采用</button>
        <button type="button" aria-pressed={filter === "discarded"} onClick={() => setFilter("discarded")}>未采用</button>
      </div>
      <div className="evidence-empty">
        <span aria-hidden="true">∅</span>
        <p>当前阶段尚无可展示证据。检索结果到达后会在这里区分“搜到”与“实际采用”。</p>
      </div>
      <DocumentPanel />
    </aside>
  );
}
