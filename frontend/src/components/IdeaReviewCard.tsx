import { stripHtml } from "../ui/safeDisplay";

export function IdeaReviewCard({ heading, body }: { heading: string; body: string }) {
  return (
    <article className="phase-card phase-card-review">
      <p className="card-kicker">Idea Review</p>
      <h1>{stripHtml(heading)}</h1>
      <p>{stripHtml(body)}</p>
    </article>
  );
}
