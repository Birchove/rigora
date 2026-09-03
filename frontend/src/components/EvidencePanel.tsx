import { useState } from "react";

import type { UploadedDocumentView, VisibleEvidenceItem } from "../api/types";
import { safeHttpUrl, stripHtml } from "../ui/safeDisplay";
import { DocumentPanel } from "./DocumentPanel";

type EvidenceFilter = "all" | "adopted" | "discarded";

const EVIDENCE_PANEL_VISIBLE_LIMIT = 12;

export function EvidencePanel({
  evidence = [],
  documents = [],
  documentNotice = null,
  onDeleteDocument,
  onClose,
}: {
  evidence?: VisibleEvidenceItem[];
  documents?: UploadedDocumentView[];
  documentNotice?: string | null;
  onDeleteDocument?: (documentId: string) => void;
  onClose?: () => void;
}) {
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const visible = evidence.filter((item) => {
    if (filter === "adopted") return item.selected;
    if (filter === "discarded") return !item.selected;
    return true;
  }).slice(0, EVIDENCE_PANEL_VISIBLE_LIMIT);
  return (
    <aside className="evidence-panel" aria-label="证据">
      <div className="panel-heading">
        <div className="panel-title">
          <span>Evidence</span>
          <strong>本轮证据</strong>
        </div>
        {onClose ? (
          <button type="button" className="panel-close" aria-label="收起证据栏" onClick={onClose}>
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M6 6l12 12" />
              <path d="M18 6L6 18" />
            </svg>
          </button>
        ) : null}
      </div>
      <div className="evidence-filters" aria-label="证据筛选">
        <button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>全部</button>
        <button type="button" aria-pressed={filter === "adopted"} onClick={() => setFilter("adopted")}>本轮采用</button>
        <button type="button" aria-pressed={filter === "discarded"} onClick={() => setFilter("discarded")}>未采用</button>
      </div>
      {visible.length === 0 ? (
        <div className="evidence-empty">
          <span aria-hidden="true">∅</span>
          <p>当前阶段尚无可展示证据。检索结果到达后会在这里区分“搜到”与“实际采用”。</p>
        </div>
      ) : (
        <ul className="evidence-list">
          {visible.map((item) => {
            const title = stripHtml(item.title);
            const href = safeHttpUrl(item.url);
            const detail = stripHtml(item.summary ?? item.support ?? "");
            return (
              <li
                key={`${item.title}:${item.url ?? ""}`}
                className={item.selected ? "evidence-adopted" : "evidence-retrieved"}
              >
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer">{title}</a>
                ) : (
                  <strong>{title}</strong>
                )}
                <small>{item.source_type}{item.selected ? " · 采用" : " · 未采用"}</small>
                {detail ? <p>{detail}</p> : null}
              </li>
            );
          })}
        </ul>
      )}
      <DocumentPanel
        documents={documents}
        notice={documentNotice}
        onDeleteDocument={onDeleteDocument}
      />
    </aside>
  );
}
