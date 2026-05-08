import { Fragment, useMemo } from "react";

import { CitationBadge } from "@/components/chat/CitationBadge";
import type { AnswerResponse, Source } from "@/lib/api-client";
import { parseAnswerCitations } from "@/lib/citations";

// Defense-in-depth: the system prompt forbids markdown in answers, but
// some models still emit `**bold**` / `*italic*` / leading `#` headings.
// The renderer is plain-text only, so strip the most common offenders
// rather than ship literal asterisks to the user.
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/(^|[^*])\*(?!\s)([^*\n]+?)\*(?!\*)/g, "$1$2")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "");
}

type AnswerViewProps = {
  response: AnswerResponse;
  /** True while tokens are still being streamed in — suppresses the
   * "no sources matched" placeholder which would otherwise flash
   * between `retrieval_done` and the first token. */
  isStreaming?: boolean;
  /** Highlighted by transient pulse — `null` when nothing is highlighted. */
  highlightedCitationId?: string | null;
  /** Fires when the user hovers / focuses a citation badge for `workId`. */
  onCitationActivate?: (workId: string) => void;
};

export function AnswerView({
  response,
  isStreaming,
  highlightedCitationId,
  onCitationActivate,
}: AnswerViewProps) {
  // Multiple sources can share a work_canonical_id (different segments
  // matched). For hover-preview we pick the highest-scoring one — same
  // source the user would land on if they clicked through.
  const sourceByWorkId = useMemo(() => {
    const map = new Map<string, Source>();
    for (const source of response.sources) {
      const existing = map.get(source.work_canonical_id);
      if (!existing || source.score > existing.score) {
        map.set(source.work_canonical_id, source);
      }
    }
    return map;
  }, [response.sources]);

  if (response.answer.trim().length === 0) {
    if (isStreaming) {
      return (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          Generating answer…
        </div>
      );
    }
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
        No sources matched this query — the model declined to answer rather
        than hallucinate. Try rephrasing or removing filters.
      </div>
    );
  }

  const knownIds = new Set(sourceByWorkId.keys());
  const segments = parseAnswerCitations(response.answer, knownIds);

  // Track how many times each work_id has been rendered so far so we
  // can mint unique anchor ids (`cite-mn10-0`, `cite-mn10-1`). The
  // pull-quote panel always scrolls to occurrence index 0 — the first
  // appearance — but every badge needs a unique DOM id.
  const occurrenceCount = new Map<string, number>();

  return (
    <article className="dharma-text text-base leading-[1.85]">
      {segments.map((segment, i) => {
        if (segment.type === "text") {
          // Preserve paragraph breaks the LLM emitted.
          const paragraphs = stripMarkdown(segment.text).split(/\n{2,}/);
          return (
            <Fragment key={i}>
              {paragraphs.map((paragraph, pi) => (
                <span key={pi} className="whitespace-pre-wrap">
                  {paragraph}
                  {pi < paragraphs.length - 1 ? "\n\n" : ""}
                </span>
              ))}
            </Fragment>
          );
        }
        return (
          <span key={i} className="inline-flex flex-wrap items-baseline gap-1">
            {segment.ids.map((id, idx) => {
              const occ = occurrenceCount.get(id) ?? 0;
              occurrenceCount.set(id, occ + 1);
              return (
                <Fragment key={id}>
                  {idx > 0 ? <span className="text-muted-foreground">,</span> : null}
                  <CitationBadge
                    workId={id}
                    source={sourceByWorkId.get(id)}
                    anchorId={`cite-${id}-${occ}`}
                    highlighted={highlightedCitationId === id}
                    onActivate={
                      onCitationActivate ? () => onCitationActivate(id) : undefined
                    }
                  />
                </Fragment>
              );
            })}
          </span>
        );
      })}
    </article>
  );
}
