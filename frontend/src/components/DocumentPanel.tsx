import { useRef, useState } from "react";

interface DocumentPanelProps {
  transferStatus?: string | null;
  parseStatus?: string | null;
  onUpload?: (file: File) => Promise<void>;
}

export function DocumentPanel({
  transferStatus = null,
  parseStatus = null,
  onUpload,
}: DocumentPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  return (
    <section className="document-panel" aria-labelledby="document-panel-title">
      <div>
        <span>Files</span>
        <h2 id="document-panel-title">研究材料</h2>
      </div>
      <input
        ref={inputRef}
        type="file"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file === undefined || onUpload === undefined) {
            return;
          }
          setBusy(true);
          void onUpload(file).finally(() => setBusy(false));
        }}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          if (onUpload === undefined) {
            return;
          }
          inputRef.current?.click();
        }}
      >
        上传文档
      </button>
      {transferStatus !== null ? <p>传输：{transferStatus}</p> : null}
      {parseStatus !== null ? <p>解析：{parseStatus}</p> : null}
    </section>
  );
}
