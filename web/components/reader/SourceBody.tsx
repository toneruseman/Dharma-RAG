import type { SourceParagraph } from "@/lib/api-client";

export function SourceBody({ paragraphs }: { paragraphs: SourceParagraph[] }) {
  if (paragraphs.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
        No paragraphs ingested for this work yet.
      </div>
    );
  }

  return (
    <article className="dharma-text flex flex-col gap-6 text-base leading-[1.85]">
      {paragraphs.map((paragraph) => (
        <section
          key={paragraph.sequence}
          id={paragraph.segment_id ?? `seq-${paragraph.sequence}`}
          className="group flex gap-4"
        >
          {paragraph.segment_id ? (
            <a
              href={`#${paragraph.segment_id}`}
              className="hidden shrink-0 select-none pt-1 font-mono text-xs text-muted-foreground/60 transition-colors hover:text-foreground sm:block sm:w-20"
              aria-label={`Anchor for ${paragraph.segment_id}`}
            >
              {paragraph.segment_id}
            </a>
          ) : (
            <span className="hidden shrink-0 sm:block sm:w-20" aria-hidden />
          )}
          <p className="flex-1">{paragraph.text}</p>
        </section>
      ))}
    </article>
  );
}
