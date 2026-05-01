import type { ConfidenceTier, ConfidenceVerdict } from "@/lib/confidence";

const TIER_STYLES: Record<ConfidenceTier, string> = {
  "well-grounded":
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  synthesized:
    "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  limited:
    "border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  interpretive:
    "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  "no-sources":
    "border-destructive/40 bg-destructive/10 text-destructive",
};

const TIER_DOT: Record<ConfidenceTier, string> = {
  "well-grounded": "bg-emerald-500",
  synthesized: "bg-amber-500",
  limited: "bg-orange-500",
  interpretive: "bg-rose-500",
  "no-sources": "bg-destructive",
};

export function ConfidenceBadge({ verdict }: { verdict: ConfidenceVerdict }) {
  return (
    <div
      className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs ${TIER_STYLES[verdict.tier]}`}
      role="status"
      aria-label={`Confidence: ${verdict.label}`}
    >
      <span
        className={`inline-block h-2 w-2 shrink-0 rounded-full ${TIER_DOT[verdict.tier]}`}
        aria-hidden
      />
      <span className="font-semibold uppercase tracking-wider">
        {verdict.label}
      </span>
      <span className="opacity-80">·</span>
      <span className="leading-snug opacity-90">{verdict.reason}</span>
    </div>
  );
}
