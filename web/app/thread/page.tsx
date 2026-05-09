"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

import { PassageCard } from "@/components/thread/PassageCard";
import { Button } from "@/components/ui/button";
import { ApiError, threadNext, type ThreadCard } from "@/lib/api-client";

const CARDS_PER_ROUND = 3;

type CorpusChoice = "all" | "canonical" | "dharmaseed_talk";

const CORPUS_OPTIONS: ReadonlyArray<{
  value: CorpusChoice;
  label: string;
  hint: string;
}> = [
  { value: "all", label: "Все", hint: "канон + dharmaseed transcripts" },
  { value: "canonical", label: "Канон", hint: "Pāli Canon (SuttaCentral)" },
  {
    value: "dharmaseed_talk",
    label: "Dharmaseed",
    hint: "Modern oral teachings (pilot: Rob Burbea)",
  },
];

function corporaFor(choice: CorpusChoice): string[] | null {
  return choice === "all" ? null : [choice];
}

export default function ThreadPage() {
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState<string | null>(null);
  const [corpus, setCorpus] = useState<CorpusChoice>("all");
  const [cards, setCards] = useState<ThreadCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exhausted, setExhausted] = useState(false);

  async function fetchRound(q: string, excluded: string[]): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const response = await threadNext({
        query: q,
        excluded_chunk_ids: excluded,
        top_k: CARDS_PER_ROUND,
        corpora: corporaFor(corpus),
      });
      setCards((prev) => [...prev, ...response.cards]);
      setExhausted(response.exhausted);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Server returned ${err.status}: ${err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setLoading(false);
    }
  }

  async function startThread() {
    const trimmed = query.trim();
    if (!trimmed) return;
    setActiveQuery(trimmed);
    setCards([]);
    setExhausted(false);
    await fetchRound(trimmed, []);
  }

  async function loadMore() {
    if (!activeQuery || loading || exhausted) return;
    const excluded = cards.map((c) => c.chunk_id);
    await fetchRound(activeQuery, excluded);
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void startThread();
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void startThread();
    }
  }

  const canSubmit = !loading && query.trim().length > 0;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-2">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Yoniso · Read source
        </p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Read the suttas, one passage at a time.
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Ask a question once, then press <span className="font-mono">Далее</span> to walk
          through canonical passages in order of relevance. No paraphrase, no
          summary — just the words of the sources, with a one-line context note
          for each. Free, instant, hallucination-proof.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <label htmlFor="thread-input" className="sr-only">
          Question
        </label>
        <textarea
          id="thread-input"
          rows={2}
          placeholder="Ask about a sutta, a Pāli term, or a concept…"
          className="dharma-text w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-base leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
          aria-label="Question"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <div
            role="radiogroup"
            aria-label="Источник"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 p-0.5"
          >
            {CORPUS_OPTIONS.map((opt) => {
              const selected = corpus === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  title={opt.hint}
                  disabled={loading}
                  onClick={() => setCorpus(opt.value)}
                  className={`rounded px-2 py-0.5 text-xs transition-colors ${
                    selected
                      ? "bg-background font-medium text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  } disabled:opacity-50`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline">
              Enter to start · Shift+Enter for newline
            </span>
            <Button type="submit" disabled={!canSubmit} size="sm">
              {loading && cards.length === 0 ? "Searching…" : "Start thread"}
            </Button>
          </div>
        </div>
      </form>

      {error ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
        >
          <p className="font-semibold">Request failed</p>
          <p className="mt-1 leading-relaxed">{error}</p>
        </div>
      ) : null}

      {activeQuery && cards.length === 0 && !loading && !error ? (
        <p className="rounded-md border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
          No passages matched. Try a different question or remove specific
          terms.
        </p>
      ) : null}

      {cards.length > 0 ? (
        <ol className="flex flex-col gap-5">
          {cards.map((card, i) => (
            <li key={card.chunk_id}>
              <PassageCard card={card} roundNumber={i + 1} />
            </li>
          ))}
        </ol>
      ) : null}

      {activeQuery && cards.length > 0 ? (
        <div className="flex flex-col items-center gap-2 pt-2">
          {exhausted ? (
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              End of thread · {cards.length} passages
            </p>
          ) : (
            <Button onClick={loadMore} disabled={loading} size="sm">
              {loading ? "Loading…" : "Далее"}
            </Button>
          )}
        </div>
      ) : null}
    </main>
  );
}
