import type { Phase } from "../../api/types";
import { IdeaReviewCard } from "../../components/IdeaReviewCard";

export function IdeaView({ phase }: { phase: Extract<Phase, "awaiting_idea" | "awaiting_idea_refinement" | "rejected"> }) {
  if (phase === "awaiting_idea") {
    return <IdeaReviewCard heading="研究起点" body="描述你要判断的研究想法、可用资源和现实约束。" />;
  }
  if (phase === "awaiting_idea_refinement") {
    return <IdeaReviewCard heading="补充研究边界" body="当前方向仍过宽，请补充问题范围或确认具体研究目标。" />;
  }
  return <IdeaReviewCard heading="Idea 审查结果" body="该方向暂未通过准入；理由与证据将保持中性、可核查。" />;
}
