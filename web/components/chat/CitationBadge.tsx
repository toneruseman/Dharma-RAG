import Link from "next/link";

import type { Source } from "@/lib/api-client";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type CitationBadgeProps = {
  workId: string;
  source: Source | undefined;
};

/**
 * Inline `[mn10]`-style citation. Hovering reveals a tooltip with the
 * matched snippet from the retrieval result; clicking jumps to the
 * Reading Room with the segment anchor.
 *
 * `source` is `undefined` when the LLM cited a work_id we don't have
 * in `response.sources` (defensive — the upstream parser already
 * filters those out, but the type leaves room for it). In that case
 * we drop the tooltip and render a plain link.
 */
export function CitationBadge({ workId, source }: CitationBadgeProps) {
  const target = source?.segment_id
    ? `/read/${workId}#${encodeURIComponent(source.segment_id)}`
    : `/read/${workId}`;

  const link = (
    <Link
      href={target}
      className="rounded bg-accent/60 px-1.5 py-0.5 font-mono text-xs font-medium text-accent-foreground transition-colors hover:bg-accent"
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
