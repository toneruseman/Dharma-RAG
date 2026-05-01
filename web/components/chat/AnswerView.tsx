import { Fragment, useMemo } from "react";

import { CitationBadge } from "@/components/chat/CitationBadge";
import type { AnswerResponse, Source } from "@/lib/api-client";
import { parseAnswerCitations } from "@/lib/citations";

type AnswerViewProps = {
  response: AnswerResponse;
};

export function AnswerView({ response }: AnswerViewProps) {
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
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
        No sources matched this query — the model declined to answer rather
        than hallucinate. Try rephrasing or removing filters.
      </div>
    );
  }

  const knownIds = new Set(sourceByWorkId.keys());
  const segments = parseAnswerCitations(response.answer, knownIds);

  return (
    <article className="dharma-text text-base leading-[1.85]">
      {segments.map((segment, i) => {
        if (segment.type === "text") {
          // Preserve paragraph breaks the LLM emitted.
          const paragraphs = segment.text.split(/\n{2,}/);
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
            {segment.ids.map((id, idx) => (
              <Fragment key={id}>
                {idx > 0 ? <span className="text-muted-foreground">,</span> : null}
                <CitationBadge workId={id} source={sourceByWorkId.get(id)} />
              </Fragment>
            ))}
          </span>
        );
      })}
    </article>
  );
}
