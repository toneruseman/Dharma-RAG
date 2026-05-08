"use client";

import Link from "next/link";
import { useState } from "react";

import type { Source } from "@/lib/api-client";

type CitedQuoteProps = {
  source: Source;
  highlighted: boolean;
  onClick: () => void;
};

const COLLAPSE_THRESHOLD = 400;
const COLLAPSED_PREVIEW_CHARS = 200;

/**
 * One pull-quote card. Shows the **full** parent passage (`Source.text`)
 * the LLM saw, not the short retrieval snippet — this is the text
 * pinned next to the answer for verification.
 *
 * Long passages are adaptive-collapsed: ≤400 chars rendered fully,
 * longer ones show a 200-char preview with a "Развернуть" toggle.
 *
 * `highlighted` is a transient flag set by the parent when the user
 * hovers the matching citation badge — drives a brief background
 * pulse so the eye finds the just-scrolled card.
 */
export function CitedQuote({ source, highlighted, onClick }: CitedQuoteProps) {
  const [expanded, setExpanded] = useState(false);

  const fullText = source.text;
  const isLong = fullText.length > COLLAPSE_THRESHOLD;
  const displayText =
    !isLong || expanded ? fullText : `${fullText.slice(0, COLLAPSED_PREVIEW_CHARS).trimEnd()}…`;

  const target = source.segment_id
    ? `/read/${source.work_canonical_id}#${encodeURIComponent(source.segment_id)}`
    : `/read/${source.work_canonical_id}`;

  return (
    <article
      id={`quote-${source.work_canonical_id}`}
      onClick={onClick}
      className={`flex cursor-pointer flex-col gap-2 rounded-md border bg-card p-3 transition-colors duration-300 ${
        highlighted ? "border-foreground/60 bg-accent/40" : "border-border hover:border-foreground/30"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-mono font-semibold text-foreground">
          {source.work_canonical_id}
          {source.segment_id ? (
            <span className="text-muted-foreground"> · {source.segment_id}</span>
          ) : null}
        </span>
        <span className="text-muted-foreground">{source.score.toFixed(2)}</span>
      </div>

      <p className="dharma-text whitespace-pre-wrap text-sm leading-relaxed text-foreground/85">
        {displayText}
      </p>

      <div className="flex items-center justify-between gap-2 text-xs">
        {isLong ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
            className="text-muted-foreground underline-offset-2 hover:underline"
            aria-expanded={expanded}
          >
            {expanded ? "Свернуть" : "Развернуть"}
          </button>
        ) : (
          <span />
        )}
        <Link
          href={target}
          onClick={(e) => e.stopPropagation()}
          className="text-muted-foreground underline-offset-2 hover:underline"
        >
          Open in Reading Room →
        </Link>
      </div>
    </article>
  );
}
