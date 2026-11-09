export default function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted">—</span>;

  let tone = "border-danger/40 bg-danger/15 text-danger";
  if (score >= 80) tone = "border-ok/40 bg-ok/15 text-ok";
  else if (score >= 60) tone = "border-warn/40 bg-warn/15 text-warn";

  return (
    <span
      className={`inline-flex min-w-10 justify-center rounded border px-2 py-0.5 font-mono text-xs font-medium ${tone}`}
    >
      {score}
    </span>
  );
}