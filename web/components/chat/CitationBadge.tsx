"use client";

import Link from "next/link";

import type { Source } from "@/lib/api-client";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type CitationBadgeProps = {
  workId: string;
  source: Source | undefined;
  /**
   * Optional unique anchor for two-way scroll between the answer body
   * and the pull-quote panel. Shape: `cite-${workId}-${occurrenceIndex}`
   * — `occurrenceIndex` because the same work_id can appear several
   * times in the answer; only the first one is the scroll target from
   * the panel side, but unique ids are required regardless.
   */
  anchorId?: string;
  /**
   * Highlighted state set briefly by the parent when the user clicks
   * the matching pull-quote card. Drives a transient background pulse.
   */
  highlighted?: boolean;
  /**
   * Fires on `mouseenter` / `focus`. The chat page uses it to scroll
   * the matching pull-quote into view in real time. Click semantics
   * stay on the underlying `<Link>` (open Reading Room) — by design,
   * see concept 24.
   */
  onActivate?: () => void;
};

/**
 * Inline `[mn10]`-style citation. Hovering reveals a tooltip with the
 * matched snippet from the retrieval result; clicking opens the
 * Reading Room with the segment anchor (unchanged from app-day-23).
 *
 * `source` is `undefined` when the LLM cited a work_id we don't have
 * in `response.sources` (defensive — the upstream parser already
 * filters those out, but the type leaves room for it). In that case
 * we drop the tooltip and render a plain link.
 */
export function CitationBadge({
  workId,
  source,
  anchorId,
  highlighted,
  onActivate,
}: CitationBadgeProps) {
  const target = source?.segment_id
    ? `/read/${workId}#${encodeURIComponent(source.segment_id)}`
    : `/read/${workId}`;

  const link = (
    <Link
      href={target}
      id={anchorId}
      onMouseEnter={onActivate}
      onFocus={onActivate}
      className={`rounded px-1.5 py-0.5 font-mono text-xs font-medium transition-colors ${
        highlighted
          ? "bg-accent text-accent-foreground ring-2 ring-foreground/40"
          : "bg-accent/60 text-accent-foreground hover:bg-accent"
      }`}
    >
      {workId}
    </Link>
  );

  if (!source) {
    return link;
  }

  return (
    <Tooltip>
      <TooltipTrigger render={link} />
      <TooltipContent
        side="top"
        sideOffset={6}
        className="max-w-sm whitespace-normal bg-popover p-3 text-sm text-popover-foreground shadow-md"
      >
        <div className="flex items-baseline justify-between gap-3 text-xs">
          <span className="font-mono font-semibold">
            {source.work_canonical_id}
            {source.segment_id ? (
              <span className="text-muted-foreground"> · {source.segment_id}</span>
            ) : null}
          </span>
          <span className="text-muted-foreground">{source.score.toFixed(2)}</span>
        </div>
        <p className="dharma-text mt-1.5 leading-snug">{source.snippet}</p>
      </TooltipContent>
    </Tooltip>
  );
}
