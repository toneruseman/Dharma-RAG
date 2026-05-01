import Link from "next/link";
import { Fragment } from "react";

import type { AnswerResponse } from "@/lib/api-client";
import { parseAnswerCitations } from "@/lib/citations";

type AnswerViewProps = {
  response: AnswerResponse;
};

export function AnswerView({ response }: AnswerViewProps) {
  if (response.answer.trim().length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
        No sources matched this query — the model declined to answer rather
        than hallucinate. Try rephrasing or removing filters.
      </div>
    );
  }

  const knownIds = new Set(response.sources.map((s) => s.work_canonical_id));
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
                <Link
                  href={`/read/${id}`}
                  className="rounded bg-accent/60 px-1.5 py-0.5 font-mono text-xs font-medium text-accent-foreground transition-colors hover:bg-accent"
                  title={`Open ${id} in the Reading Room`}
                >
                  {id}
                </Link>
              </Fragment>
            ))}
          </span>
        );
      })}
    </article>
  );
}
