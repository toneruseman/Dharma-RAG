"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AnswerView } from "@/components/chat/AnswerView";
import { ChatInput, type CorpusChoice } from "@/components/chat/ChatInput";
import { ConfidenceBadge } from "@/components/chat/ConfidenceBadge";
import { FeedbackWidget } from "@/components/chat/FeedbackWidget";
import { PullQuotePanel } from "@/components/chat/PullQuotePanel";
import { Button } from "@/components/ui/button";
import type { AnswerResponse, AnswerSnapshot, AnswerStyle, Source } from "@/lib/api-client";
import { computeConfidence } from "@/lib/confidence";
import { streamAsk, type DoneEvent } from "@/lib/sse";

const HIGHLIGHT_DURATION_MS = 1500;

/**
 * Build a synthetic `AnswerResponse` shape from the streaming events
 * so we can reuse `<AnswerView>` and `<PullQuotePanel>` unchanged.
 */
function buildLiveResponse({
  query,
  answer,
  sources,
  citations,
  retrievalLatencyMs,
  pipelineVersion,
  wallStartMs,
}: {
  query: string;
  answer: string;
  sources: Source[];
  citations: string[];
  retrievalLatencyMs: number;
  pipelineVersion: string;
  wallStartMs: number;
}): AnswerResponse {
  const elapsed = performance.now() - wallStartMs;
  return {
    query,
    answer,
    sources,
    citations,
    latency_ms: elapsed,
    retrieval_latency_ms: retrievalLatencyMs,
    llm_latency_ms: Math.max(0, elapsed - retrievalLatencyMs),
    metadata: {
      trace_id: "",
      pipeline_version: pipelineVersion,
      llm_model: "streaming…",
      llm_tokens_in: 0,
      llm_tokens_out: 0,
      style: "auto",
      retrieval_metadata: {
        version: pipelineVersion,
        collection: "",
        rerank: false,
        expand_parents: false,
        expand_pali: false,
        expand_definitional: false,
        foundational_boost: false,
        n_candidates: sources.length,
      },
    },
  };
}

function buildSnapshot(response: AnswerResponse): AnswerSnapshot {
  return {
    query_text: response.query,
    answer_text: response.answer,
    pipeline_version: response.metadata.pipeline_version,
    llm_model: response.metadata.llm_model,
    style: response.metadata.style,
    latency_ms: Math.max(0, Math.round(response.latency_ms)),
    llm_tokens_in: response.metadata.llm_tokens_in,
    llm_tokens_out: response.metadata.llm_tokens_out,
  };
}

export default function ChatPage() {
  // Thread mode (rag-day-37 enhancement): each round is one LLM call
  // for the same query, with prior rounds' work_canonical_ids stuffed
  // into ``forbidden_works`` so each press of «Далее» surfaces
  // different sources.
  const [rounds, setRounds] = useState<AnswerResponse[]>([]);
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [style, setStyle] = useState<AnswerStyle>("auto");
  const [corpus, setCorpus] = useState<CorpusChoice>("all");

  const controllerRef = useRef<AbortController | null>(null);

  const [highlightedQuoteId, setHighlightedQuoteId] = useState<string | null>(null);
  const [highlightedCitationId, setHighlightedCitationId] = useState<string | null>(null);
  const quoteHighlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const citationHighlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      if (quoteHighlightTimer.current) clearTimeout(quoteHighlightTimer.current);
      if (citationHighlightTimer.current) clearTimeout(citationHighlightTimer.current);
    };
  }, []);

  function handleCitationActivate(workId: string) {
    setHighlightedQuoteId(workId);
    if (quoteHighlightTimer.current) clearTimeout(quoteHighlightTimer.current);
    quoteHighlightTimer.current = setTimeout(
      () => setHighlightedQuoteId(null),
      HIGHLIGHT_DURATION_MS,
    );
  }

  function handleQuoteClick(workId: string) {
    const target = document.getElementById(`cite-${workId}-0`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setHighlightedCitationId(workId);
    if (citationHighlightTimer.current) clearTimeout(citationHighlightTimer.current);
    citationHighlightTimer.current = setTimeout(
      () => setHighlightedCitationId(null),
      HIGHLIGHT_DURATION_MS,
    );
  }

  // Last round is the one currently rendering / streaming. Confidence
  // is computed only for the latest round to keep the indicator
  // aligned with what the user is reading right now.
  const lastRound = rounds[rounds.length - 1] ?? null;
  const confidence = useMemo(
    () => (lastRound ? computeConfidence(lastRound.answer, lastRound.sources) : null),
    [lastRound],
  );

  function startRound(query: string, forbiddenWorks: string[], replaceLast: boolean) {
    setIsStreaming(true);
    setError(null);

    let answerText = "";
    let sources: Source[] = [];
    let citations: string[] = [];
    let retrievalLatencyMs = 0;
    let pipelineVersion = "";
    const wallStartMs = performance.now();

    const replaceTail = (next: AnswerResponse) => {
      setRounds((prev) => {
        if (replaceLast || prev.length === 0) return [...prev.slice(0, -1), next];
        return [...prev, next];
      });
    };

    const refreshLive = () => {
      replaceTail(
        buildLiveResponse({
          query,
          answer: answerText,
          sources,
          citations,
          retrievalLatencyMs,
          pipelineVersion,
          wallStartMs,
        }),
      );
    };

    // Seed the round so the UI renders «Connecting…» / «Generating answer…»
    // placeholders even before the first SSE frame arrives.
    setRounds((prev) =>
      replaceLast
        ? [
            ...prev.slice(0, -1),
            buildLiveResponse({
              query,
              answer: "",
              sources: [],
              citations: [],
              retrievalLatencyMs: 0,
              pipelineVersion: "",
              wallStartMs,
            }),
          ]
        : [
            ...prev,
            buildLiveResponse({
              query,
              answer: "",
              sources: [],
              citations: [],
              retrievalLatencyMs: 0,
              pipelineVersion: "",
              wallStartMs,
            }),
          ],
    );

    controllerRef.current = streamAsk(
      {
        query,
        top_k: 5,
        style,
        corpora: corpus === "all" ? null : [corpus],
        forbidden_works: forbiddenWorks.length > 0 ? forbiddenWorks : null,
      },
      {
        onRetrievalDone: (event) => {
          sources = event.sources;
          retrievalLatencyMs = event.retrieval_latency_ms;
          pipelineVersion = event.pipeline_version;
          refreshLive();
        },
        onToken: (event) => {
          answerText += event.delta;
          refreshLive();
        },
        onCitation: (event) => {
          if (!citations.includes(event.id)) {
            citations = [...citations, event.id];
          }
        },
        onDone: (event: DoneEvent) => {
          replaceTail({
            query,
            answer: event.answer,
            sources,
            citations: event.citations,
            latency_ms: event.latency_ms,
            retrieval_latency_ms: retrievalLatencyMs,
            llm_latency_ms: event.llm_latency_ms,
            metadata: event.metadata,
          });
          setIsStreaming(false);
        },
        onError: (event) => {
          setError(event.message);
          setIsStreaming(false);
        },
        onTransportError: (err) => {
          setError(err instanceof Error ? err.message : String(err));
          setIsStreaming(false);
        },
      },
    );
  }

  function handleSubmit(query: string) {
    controllerRef.current?.abort();
    setRounds([]);
    setActiveQuery(query);
    startRound(query, [], false);
  }

  function handleNext() {
    if (!activeQuery || isStreaming) return;
    // Accumulate every work_canonical_id we've already shown across
    // all completed rounds. ``forbidden_works`` is post-RRF, so a long
    // list naturally exhausts the pool — that is the «End of thread»
    // signal.
    const seen = new Set<string>();
    for (const r of rounds) {
      for (const s of r.sources) seen.add(s.work_canonical_id);
    }
    startRound(activeQuery, [...seen], false);
  }

  function handleNewQuestion() {
    controllerRef.current?.abort();
    setRounds([]);
    setActiveQuery(null);
    setIsStreaming(false);
    setError(null);
  }

  function handleStop() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }

  // «End of thread» when the latest non-streaming round returned no
  // sources — pool is exhausted given the accumulated forbidden_works.
  const exhausted =
    !isStreaming && lastRound !== null && lastRound.sources.length === 0 && rounds.length > 1;

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Q&amp;A</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Ask the corpus.
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Answers are grounded in retrieved Buddhist source texts and cite them inline
          with <span className="font-mono">[work_id]</span>. Press{" "}
          <span className="font-mono">Далее</span> for another angle on the same
          question, drawing from new sources each round.
        </p>
      </header>

      <ChatInput
        isLoading={isStreaming}
        style={style}
        onStyleChange={setStyle}
        corpus={corpus}
        onCorpusChange={setCorpus}
        onSubmit={handleSubmit}
      />

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <p className="font-semibold">Stream failed</p>
          <p className="mt-1 leading-relaxed">{error}</p>
        </div>
      ) : null}

      {activeQuery && rounds.length > 0 ? (
        <section className="grid gap-8 lg:grid-cols-[1fr_280px]">
          <div className="flex flex-col gap-8">
            {rounds.map((round, idx) => {
              const isLast = idx === rounds.length - 1;
              const roundIsStreaming = isLast && isStreaming;
              return (
                <article
                  key={`${activeQuery}-${idx}`}
                  className="flex flex-col gap-3 border-l-2 border-border pl-4"
                >
                  <header className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span className="rounded-md bg-accent/60 px-1.5 py-0.5 font-mono font-semibold text-accent-foreground">
                      Round {idx + 1}
                    </span>
                    <span>
                      Latency: {Math.round(round.latency_ms)} ms · retrieval{" "}
                      {Math.round(round.retrieval_latency_ms)} ms · LLM{" "}
                      {Math.round(round.llm_latency_ms)} ms
                    </span>
                    {round.metadata?.llm_model ? (
                      <span className="font-mono">{round.metadata.llm_model}</span>
                    ) : null}
                    {roundIsStreaming ? (
                      <button
                        type="button"
                        onClick={handleStop}
                        className="rounded border border-border px-2 py-0.5 text-xs hover:bg-accent"
                      >
                        Stop
                      </button>
                    ) : null}
                  </header>
                  {isLast && confidence && !roundIsStreaming ? (
                    <ConfidenceBadge verdict={confidence} />
                  ) : null}
                  <AnswerView
                    response={round}
                    isStreaming={roundIsStreaming}
                    highlightedCitationId={isLast ? highlightedCitationId : null}
                    onCitationActivate={isLast ? handleCitationActivate : undefined}
                  />
                  {isLast &&
                  !roundIsStreaming &&
                  round.metadata?.trace_id &&
                  round.answer.trim().length > 0 ? (
                    <FeedbackWidget
                      key={round.metadata.trace_id}
                      traceId={round.metadata.trace_id}
                      snapshot={buildSnapshot(round)}
                    />
                  ) : null}
                </article>
              );
            })}

            <div className="flex flex-wrap items-center gap-3 pl-4 pt-2">
              {exhausted ? (
                <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                  End of thread · {rounds.length - 1} round{rounds.length === 2 ? "" : "s"}
                </span>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={handleNext}
                  disabled={isStreaming}
                >
                  {isStreaming ? "Generating…" : "Далее"}
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={handleNewQuestion}
                disabled={isStreaming}
              >
                Новый вопрос
              </Button>
            </div>
          </div>
          {lastRound ? (
            <PullQuotePanel
              answer={lastRound.answer}
              sources={lastRound.sources}
              citations={lastRound.citations}
              highlightedQuoteId={highlightedQuoteId}
              onQuoteClick={handleQuoteClick}
            />
          ) : null}
        </section>
      ) : null}
    </main>
  );
}
