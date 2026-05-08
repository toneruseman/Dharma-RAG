"use client";

import Link from "next/link";
import { useMemo } from "react";

import { CitedQuote } from "@/components/chat/CitedQuote";
import type { Source } from "@/lib/api-client";
import { citedSourcesInOrder } from "@/lib/citedSourcesInOrder";

type PullQuotePanelProps = {
  answer: string;
  sources: Source[];
  citations: string[];
  highlightedQuoteId: string | null;
  onQuoteClick: (workId: string) => void;
};

/**
 * Side panel of "pull-quotes" — the subset of `sources` the LLM
 * actually cited in `answer`, ordered by first appearance of the
 * `[work_id]` marker in the text. Replaces the older `<SourcesPanel>`
 * for the chat view; transparency for non-cited sources is preserved
 * via a collapsed `<details>` disclosure at the bottom.
 *
 * Two-way anchoring with the answer body:
 *   - hover a `[mn10]` badge in the answer → matching pull-quote scrolls
 *     into view + briefly highlights (parent owns that state via
 *     `highlightedQuoteId`).
 *   - click a pull-quote card → first `[mn10]` in the answer scrolls
 *     into view + briefly highlights (parent reacts via `onQuoteClick`).
 */
export function PullQuotePanel({
  answer,
  sources,
  citations,
  highlightedQuoteId,
  onQuoteClick,
}: PullQuotePanelProps) {
  const cited = useMemo(
    () => citedSourcesInOrder(answer, sources, citations),
    [answer, sources, citations],
  );

  if (answer.trim() === "") return null;

  const citedIds = new Set(cited.map((s) => s.work_canonical_id));
  const otherRetrieved = sources.filter((s) => !citedIds.has(s.work_canonical_id));

  if (cited.length === 0) {
    // LLM produced an answer but didn't cite anything. Show the
    // disclosure open so transparency is preserved by default.
    return (
      <aside
        className="flex flex-col gap-3 lg:sticky lg:top-8 lg:self-start lg:max-h-[calc(100vh-4rem)] lg:overflow-y-auto lg:pr-1"
        aria-label="Pull-quotes for this answer"
      >
        <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Quotes
        </h2>
        <p className="text-xs text-muted-foreground">
          No quotes used in the answer.
        </p>
        {otherRetrieved.length > 0 ? (
          <details open className="flex flex-col gap-2">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Other retrieved ({otherRetrieved.length})
            </summary>
            <ul className="mt-2 flex flex-col gap-2">
              {otherRetrieved.map((source, i) => (
                <SlimRetrievedCard key={`${source.work_canonical_id}-${i}`} source={source} />
              ))}
            </ul>
          </details>
        ) : null}
      </aside>
    );
  }

  return (
    <aside
      className="flex flex-col gap-3 lg:sticky lg:top-8 lg:self-start lg:max-h-[calc(100vh-4rem)] lg:overflow-y-auto lg:pr-1"
      aria-label="Pull-quotes for this answer"
    >
      <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Quotes ({cited.length})
      </h2>
      <ol className="flex flex-col gap-3">
        {cited.map((source) => (
          <li key={source.work_canonical_id}>
            <CitedQuote
              source={source}
              highlighted={highlightedQuoteId === source.work_canonical_id}
              onClick={() => onQuoteClick(source.work_canonical_id)}
            />
          </li>
        ))}
      </ol>

      {otherRetrieved.length > 0 ? (
        <details className="mt-2 flex flex-col gap-2">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Other retrieved ({otherRetrieved.length})
          </summary>
          <ul className="mt-2 flex flex-col gap-2">
            {otherRetrieved.map((source, i) => (
              <SlimRetrievedCard key={`${source.work_canonical_id}-${i}`} source={source} />
            ))}
          </ul>
        </details>
      ) : null}
    </aside>
  );
}

function SlimRetrievedCard({ source }: { source: Source }) {
  const target = source.segment_id
    ? `/read/${source.work_canonical_id}#${encodeURIComponent(source.segment_id)}`
    : `/read/${source.work_canonical_id}`;

  return (
    <li>
      <Link
        href={target}
        className="group block rounded-md border border-border bg-card p-2 transition-colors hover:border-foreground/30"
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
        <p className="dharma-text mt-1 line-clamp-2 text-xs leading-snug text-foreground/85">
          {source.snippet}
        </p>
      </Link>
    </li>
  );
}
