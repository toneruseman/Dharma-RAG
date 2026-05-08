"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { AnswerView } from "@/components/chat/AnswerView";
import { ChatInput } from "@/components/chat/ChatInput";
import { ConfidenceBadge } from "@/components/chat/ConfidenceBadge";
import { FeedbackWidget } from "@/components/chat/FeedbackWidget";
import { PullQuotePanel } from "@/components/chat/PullQuotePanel";
import type { AnswerResponse, AnswerSnapshot, Source } from "@/lib/api-client";
import { computeConfidence } from "@/lib/confidence";
import { streamAsk, type DoneEvent } from "@/lib/sse";

const HIGHLIGHT_DURATION_MS = 1500;

/**
 * Build a synthetic `AnswerResponse` shape from the streaming events
 * so we can reuse `<AnswerView>` and `<PullQuotePanel>` unchanged.
 *
 * During streaming `latency_ms` / `retrieval_latency_ms` /
 * `llm_latency_ms` come from `RetrievalDoneEvent` for retrieval and
 * `wallStartMs` for the rest. After `done` we replace this with the
 * authoritative version from the server.
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
      // Real ``trace_id`` arrives in ``DoneEvent.metadata`` and replaces
      // this placeholder via ``setResponse`` below. The empty string
      // prevents the FeedbackWidget from rendering during streaming
      // (it gates on a non-empty trace_id).
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
  const [isStreaming, setIsStreaming] = useState(false);
  const [response, setResponse] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  // Hold the active AbortController so we can cancel on unmount or
  // when the user starts a new query while one is still streaming.
  const controllerRef = useRef<AbortController | null>(null);

  // Two-way anchoring state for the citation ↔ pull-quote pairing.
  // `highlightedQuoteId` is set when the user hovers a citation in the
  // answer body; `highlightedCitationId` is set when the user clicks
  // a pull-quote card. Each clears itself after HIGHLIGHT_DURATION_MS.
  const [highlightedQuoteId, setHighlightedQuoteId] = useState<string | null>(null);
  const [highlightedCitationId, setHighlightedCitationId] = useState<string | null>(null);
  const quoteHighlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const citationHighlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup on unmount — drop the in-flight stream so it doesn't try
  // to setState after the component is gone.
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      if (quoteHighlightTimer.current) clearTimeout(quoteHighlightTimer.current);
      if (citationHighlightTimer.current) clearTimeout(citationHighlightTimer.current);
    };
  }, []);

  function handleCitationActivate(workId: string) {
    const target = document.getElementById(`quote-${workId}`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setHighlightedQuoteId(workId);
    if (quoteHighlightTimer.current) clearTimeout(quoteHighlightTimer.current);
    quoteHighlightTimer.current = setTimeout(
      () => setHighlightedQuoteId(null),
      HIGHLIGHT_DURATION_MS,
    );
  }

  function handleQuoteClick(workId: string) {
    // Always jump to occurrence 0 — the first appearance — even if
    // there are duplicates. The remaining ones are typically a few
    // sentences away and within the same scroll viewport.
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

  const confidence = useMemo(
    () => (response ? computeConfidence(response.answer, response.sources) : null),
    [response],
  );

  function handleSubmit(query: string) {
    // Abort any prior in-flight stream — submitting a new query
    // while the previous is still running shouldn't interleave.
    controllerRef.current?.abort();

    setIsStreaming(true);
    setError(null);
    setLastQuery(query);
    setResponse(null);

    let answerText = "";
    let sources: Source[] = [];
    let citations: string[] = [];
    let retrievalLatencyMs = 0;
    let pipelineVersion = "";
    const wallStartMs = performance.now();

    const refreshLive = () => {
      setResponse(
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

    controllerRef.current = streamAsk(
      { query, top_k: 5 },
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
          // No setState — citation events are advisory; AnswerView
          // re-parses the buffer on each render.
        },
        onDone: (event: DoneEvent) => {
          // Replace the synthesised live shape with the authoritative
          // server-side result (correct latency_ms, real metadata).
          setResponse({
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

  function handleStop() {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setIsStreaming(false);
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Q&amp;A</p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Ask the corpus.
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Answers are grounded in retrieved Buddhist source texts and cite them inline
          with <span className="font-mono">[work_id]</span>. Click any citation to open
          the passage in the Reading Room.
        </p>
      </header>

      <ChatInput isLoading={isStreaming} onSubmit={handleSubmit} />

      {isStreaming && lastQuery && !response ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          Connecting…{" "}
          <span className="dharma-text italic text-foreground">“{lastQuery}”</span>
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <p className="font-semibold">Stream failed</p>
          <p className="mt-1 leading-relaxed">{error}</p>
        </div>
      ) : null}

      {response ? (
        <section className="grid gap-8 lg:grid-cols-[1fr_280px]">
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>
                Latency: {Math.round(response.latency_ms)} ms · retrieval{" "}
                {Math.round(response.retrieval_latency_ms)} ms · LLM{" "}
                {Math.round(response.llm_latency_ms)} ms
              </span>
              {response.metadata?.llm_model ? (
                <span className="font-mono">{response.metadata.llm_model}</span>
              ) : null}
              {isStreaming ? (
                <button
                  type="button"
                  onClick={handleStop}
                  className="rounded border border-border px-2 py-0.5 text-xs hover:bg-accent"
                >
                  Stop
                </button>
              ) : null}
            </div>
            {confidence && !isStreaming ? <ConfidenceBadge verdict={confidence} /> : null}
            <AnswerView
              response={response}
              highlightedCitationId={highlightedCitationId}
              onCitationActivate={handleCitationActivate}
            />
            {!isStreaming && response.metadata?.trace_id && response.answer.trim().length > 0 ? (
              <FeedbackWidget
                key={response.metadata.trace_id}
                traceId={response.metadata.trace_id}
                snapshot={buildSnapshot(response)}
              />
            ) : null}
          </div>
          <PullQuotePanel
            answer={response.answer}
            sources={response.sources}
            citations={response.citations}
            highlightedQuoteId={highlightedQuoteId}
            onQuoteClick={handleQuoteClick}
          />
        </section>
      ) : null}
    </main>
  );
}
