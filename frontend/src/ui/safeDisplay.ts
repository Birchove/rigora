const HTML_TAG = /<\/?[^>]+>/g;

export function stripHtml(text: string): string {
  return text.replace(HTML_TAG, "");
}

export function safeHttpUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.href;
    }
  } catch {
    return null;
  }
  return null;
}
