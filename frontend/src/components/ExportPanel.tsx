export function ExportPanel({
  onExportMarkdown,
  onExportJson,
}: {
  onExportMarkdown?: () => Promise<void> | void;
  onExportJson?: () => Promise<void> | void;
}) {
  return (
    <section className="inline-panel export-panel" aria-label="研究日志导出">
      <strong>研究日志</strong>
      <div className="structured-actions">
        <button
          type="button"
          disabled={onExportMarkdown === undefined}
          onClick={() => {
            if (onExportMarkdown !== undefined) {
              void onExportMarkdown();
            }
          }}
        >
          导出 Markdown
        </button>
        <button
          type="button"
          disabled={onExportJson === undefined}
          onClick={() => {
            if (onExportJson !== undefined) {
              void onExportJson();
            }
          }}
        >
          导出 JSON
        </button>
      </div>
    </section>
  );
}
