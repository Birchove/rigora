import { useMemo } from "react";
import MarkdownIt from "markdown-it";

// html:false 原始 HTML 一律转义（防注入）；breaks 使单换行即换行，贴近对话阅读习惯
const markdown = MarkdownIt({ html: false, linkify: true, breaks: true });

markdown.renderer.rules.link_open = (tokens, idx, options, _env, self) => {
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noopener noreferrer nofollow");
  return self.renderToken(tokens, idx, options);
};

/** 受控 Markdown 渲染：模型输出中的 markdown 不再以源码形式展示。 */
export function MarkdownView({ text, className }: { text: string; className?: string }) {
  const html = useMemo(() => markdown.render(text ?? ""), [text]);
  return (
    <div
      className={className === undefined ? "md-view" : `md-view ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
