"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";

type ChatInputProps = {
  isLoading: boolean;
  onSubmit: (query: string) => void;
};

export function ChatInput({ isLoading, onSubmit }: ChatInputProps) {
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
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Enter to send · Shift+Enter for newline</span>
        <Button type="submit" disabled={!canSubmit} size="sm">
          {isLoading ? "Thinking…" : "Ask"}
        </Button>
      </div>
    </form>
  );
}
