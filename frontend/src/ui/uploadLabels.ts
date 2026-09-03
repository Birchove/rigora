/** 上传/解析状态的人类可读标签，composer 瞬时反馈与研究材料列表共用。 */
export const UPLOAD_TRANSFER_LABELS: Record<string, string> = {
  uploading: "正在上传…",
  complete: "完成",
  failed: "失败",
};

export const UPLOAD_PARSE_LABELS: Record<string, string> = {
  uploaded: "已上传，等待解析",
  parsing: "解析中…",
  ready: "完成",
  failed: "解析失败",
};
