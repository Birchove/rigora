import { MarkdownView } from "../ui/markdown";

export function IdeaReviewCard({ heading, body }: { heading: string; body: string }) {
  return (
    <article className="phase-card phase-card-review">
      <p className="card-kicker">Idea Review</p>
      <h1>{heading}</h1>
      <MarkdownView text={body} />
    </article>
  );
}
