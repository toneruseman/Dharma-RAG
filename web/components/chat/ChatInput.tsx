"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import type { AnswerStyle } from "@/lib/api-client";

export type CorpusChoice = "all" | "canonical" | "dharmaseed_talk";

type ChatInputProps = {
  isLoading: boolean;
  style: AnswerStyle;
  onStyleChange: (style: AnswerStyle) => void;
  corpus: CorpusChoice;
  onCorpusChange: (corpus: CorpusChoice) => void;
  onSubmit: (query: string) => void;
};

const STYLE_OPTIONS: ReadonlyArray<{ value: AnswerStyle; label: string; hint: string }> = [
  { value: "concise", label: "Concise", hint: "2-4 sentences (~512 tokens)" },
  { value: "auto", label: "Auto", hint: "model picks length (~1024 tokens)" },
  { value: "detailed", label: "Detailed", hint: "multi-paragraph (~3072 tokens)" },
];

const CORPUS_OPTIONS: ReadonlyArray<{ value: CorpusChoice; label: string; hint: string }> = [
  { value: "all", label: "Все", hint: "канон + dharmaseed transcripts" },
  { value: "canonical", label: "Канон", hint: "Pāli Canon (SuttaCentral EN/RU)" },
  {
    value: "dharmaseed_talk",
    label: "Dharmaseed",
    hint: "Modern oral teachings (pilot: Rob Burbea)",
  },
];

export function ChatInput({
  isLoading,
  style,
  onStyleChange,
  corpus,
  onCorpusChange,
  onSubmit,
}: ChatInputProps) {
  const [value, setValue] = useState("");

  const trimmed = value.trim();
  const canSubmit = !isLoading && trimmed.length > 0;

  function submit() {
    if (!canSubmit) return;
    onSubmit(trimmed);
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter submits, Shift+Enter inserts newline (standard chat UX).
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  function handleForm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    submit();
  }

  return (
    <form onSubmit={handleForm} className="flex flex-col gap-2">
      <label htmlFor="chat-input" className="sr-only">
        Question
      </label>
      <textarea
        id="chat-input"
        rows={3}
        placeholder="Ask about a sutta, a Pāli term, or a concept…"
        className="dharma-text w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-base leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKey}
        disabled={isLoading}
        aria-label="Question"
      />
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2">
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
                  disabled={isLoading}
                  onClick={() => onCorpusChange(opt.value)}
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
          <div
            role="radiogroup"
            aria-label="Answer length"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 p-0.5"
          >
            {STYLE_OPTIONS.map((opt) => {
              const selected = style === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  title={opt.hint}
                  disabled={isLoading}
                  onClick={() => onStyleChange(opt.value)}
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
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline">Enter to send · Shift+Enter for newline</span>
          <Button type="submit" disabled={!canSubmit} size="sm">
            {isLoading ? "Thinking…" : "Ask"}
          </Button>
        </div>
      </div>
    </form>
  );
}
