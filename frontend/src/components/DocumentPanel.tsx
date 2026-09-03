import type { UploadedDocumentView } from "../api/types";
import { UPLOAD_PARSE_LABELS } from "../ui/uploadLabels";

/** 研究材料列表；上传入口统一收口到底部输入框左侧的“+”按钮。 */
export function DocumentPanel({
  documents = [],
  notice = null,
  onDeleteDocument,
}: {
  documents?: UploadedDocumentView[];
  notice?: string | null;
  onDeleteDocument?: (documentId: string) => void;
}) {
  return (
    <section className="document-panel" aria-labelledby="document-panel-title">
      <div>
        <span>Files</span>
        <h2 id="document-panel-title">研究材料</h2>
      </div>
      {notice !== null ? (
        <p className="document-notice" role="alert">{notice}</p>
      ) : null}
      {documents.length === 0 ? (
        <p>通过输入框左侧的“+”上传 .txt / .md / .pdf。</p>
      ) : (
        <ul className="document-list">
          {documents.map((item) => (
            <li key={item.document_id}>
              <div className="document-meta">
                <strong>{item.original_name}</strong>
                <small>{formatSize(item.size_bytes)}</small>
              </div>
              <div className="document-actions">
                <span
                  className={
                    item.status === "failed"
                      ? "document-status is-error"
                      : "document-status"
                  }
                >
                  {UPLOAD_PARSE_LABELS[item.status] ?? item.status}
                </span>
                {onDeleteDocument ? (
                  <button
                    type="button"
                    className="document-remove"
                    aria-label={`删除 ${item.original_name}`}
                    onClick={() => onDeleteDocument(item.document_id)}
                  >
                    ×
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "";
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}
