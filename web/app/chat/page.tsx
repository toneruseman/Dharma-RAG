"use client";

import { useState } from "react";

import { AnswerView } from "@/components/chat/AnswerView";
import { ChatInput } from "@/components/chat/ChatInput";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { ask, isApiError, type AnswerResponse } from "@/lib/api-client";

export default function ChatPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  async function handleSubmit(query: string) {
    setIsLoading(true);
    setError(null);
    setLastQuery(query);
    try {
      const r = await ask({ query, top_k: 5 });
      setResponse(r);
    } catch (e) {
      const detail =
        isApiError(e) &&
        typeof e.body === "object" &&
        e.body !== null &&
        "detail" in e.body
          ? String((e.body as { detail: unknown }).detail)
          : e instanceof Error
            ? e.message
            : "Unknown error";
      setError(detail);
      setResponse(null);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Q&amp;A
        </p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Ask the corpus.
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Answers are grounded in retrieved Buddhist source texts and cite them
          inline with <span className="font-mono">[work_id]</span>. Click any
          citation to open the passage in the Reading Room.
        </p>
      </header>

      <ChatInput isLoading={isLoading} onSubmit={handleSubmit} />

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <p className="font-semibold">Request failed</p>
          <p className="mt-1 leading-relaxed">{error}</p>
        </div>
      ) : null}

      {isLoading && lastQuery ? (
        <div className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          Retrieving sources and synthesising an answer for{" "}
          <span className="dharma-text italic text-foreground">“{lastQuery}”</span>…
        </div>
      ) : null}

      {response && !isLoading ? (
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
            </div>
            <AnswerView response={response} />
          </div>
          <SourcesPanel sources={response.sources} />
        </section>
      ) : null}
    </main>
  );
}
