import Link from "next/link";

import type { Source } from "@/lib/api-client";

type SourcesPanelProps = {
  sources: Source[];
};

export function SourcesPanel({ sources }: SourcesPanelProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <aside className="flex flex-col gap-3" aria-label="Sources used for this answer">
      <h2 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Sources ({sources.length})
      </h2>
      <ol className="flex flex-col gap-2">
        {sources.map((source, i) => {
          const target = source.segment_id
            ? `/read/${source.work_canonical_id}#${encodeURIComponent(source.segment_id)}`
            : `/read/${source.work_canonical_id}`;
          return (
            <li key={`${source.work_canonical_id}-${i}`}>
              <Link
                href={target}
                className="group block rounded-md border border-border bg-card p-3 transition-colors hover:border-foreground/30"
              >
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="font-mono font-semibold text-foreground">
                    {source.work_canonical_id}
                    {source.segment_id ? (
                      <span className="text-muted-foreground"> · {source.segment_id}</span>
                    ) : null}
                  </span>
                  <span className="text-muted-foreground">
                    {source.score.toFixed(2)}
                  </span>
                </div>
                <p className="dharma-text mt-1 line-clamp-3 text-sm leading-snug text-foreground/85">
                  {source.snippet}
                </p>
              </Link>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
