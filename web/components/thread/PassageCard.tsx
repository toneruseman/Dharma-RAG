"use client";

import Link from "next/link";

import type { ThreadCard } from "@/lib/api-client";

type PassageCardProps = {
  card: ThreadCard;
  /** 1-based round number for this card. Renders as a small ordinal. */
  roundNumber: number;
};

/**
 * Single passage in the LLM-free «infinite thread» (rag-day-36).
 *
 * Layout (top-to-bottom):
 *   1. Round badge + work / segment metadata + relevance score.
 *   2. Optional contextual prefix (Haiku-generated at ingest), italic,
 *      to orient the reader before the canonical text.
 *   3. The canonical chunk text — verbatim, no synthesis.
 *   4. Footer: translator, language, "Open in Reading Room" link.
 */
export function PassageCard({ card, roundNumber }: PassageCardProps) {
  const target = card.segment_id
    ? `/read/${card.work_canonical_id}#${encodeURIComponent(card.segment_id)}`
    : `/read/${card.work_canonical_id}`;

  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-sm">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <div className="flex items-baseline gap-2">
          <span className="rounded-md bg-accent/60 px-1.5 py-0.5 font-mono font-semibold text-accent-foreground">
            #{roundNumber}
          </span>
          <span className="font-mono font-semibold text-foreground">
            {card.work_canonical_id}
            {card.segment_id ? (
              <span className="text-muted-foreground"> · {card.segment_id}</span>
            ) : null}
          </span>
        </div>
        <span className="font-mono">{card.score.toFixed(2)}</span>
      </header>

      {card.context_text ? (
        <p className="text-sm italic leading-relaxed text-muted-foreground">
          {card.context_text}
        </p>
      ) : null}

      <p className="dharma-text whitespace-pre-wrap text-base leading-[1.85] text-foreground">
        {card.text}
      </p>

      <footer className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          {card.translator ? (
            <>
              <span className="font-mono">{card.translator}</span> ·{" "}
            </>
          ) : null}
          {card.language_code}
        </span>
        <Link
          href={target}
          className="font-medium text-foreground/80 underline-offset-4 hover:underline"
        >
          Open in Reading Room →
        </Link>
      </footer>
    </article>
  );
}
