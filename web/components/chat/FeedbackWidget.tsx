"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  sendFeedback,
  type AnswerSnapshot,
  type FeedbackRequest,
} from "@/lib/api-client";

type FeedbackWidgetProps = {
  traceId: string;
  snapshot: AnswerSnapshot;
};

type Thumb = 1 | -1;

export function FeedbackWidget({ traceId, snapshot }: FeedbackWidgetProps) {
  const [thumb, setThumb] = useState<Thumb | null>(null);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (thumb === null || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const body: FeedbackRequest = {
        trace_id: traceId,
        thumb,
        comment: comment.trim() ? comment.trim() : null,
        answer_snapshot: snapshot,
      };
      await sendFeedback(body);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div
        role="status"
        className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground"
      >
        <span aria-hidden>✓</span>
        <span>Спасибо за feedback.</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/20 px-3 py-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Был ли ответ полезен?</span>
        <Button
          type="button"
          variant={thumb === 1 ? "default" : "outline"}
          size="sm"
          onClick={() => setThumb(1)}
          aria-pressed={thumb === 1}
          aria-label="Полезно"
          disabled={isSubmitting}
        >
          <span aria-hidden>👍</span>
          <span className="ml-1">Полезно</span>
        </Button>
        <Button
          type="button"
          variant={thumb === -1 ? "default" : "outline"}
          size="sm"
          onClick={() => setThumb(-1)}
          aria-pressed={thumb === -1}
          aria-label="Не помогло"
          disabled={isSubmitting}
        >
          <span aria-hidden>👎</span>
          <span className="ml-1">Не помогло</span>
        </Button>
      </div>

      {thumb !== null ? (
        <>
          <label htmlFor={`fb-comment-${traceId}`} className="sr-only">
            Комментарий
          </label>
          <textarea
            id={`fb-comment-${traceId}`}
            rows={2}
            placeholder="Что не так? (необязательно)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
            disabled={isSubmitting}
            className="w-full resize-y rounded-md border border-input bg-background px-2 py-1.5 text-sm leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">
              {comment.length}/2000
            </span>
            <Button
              type="button"
              size="sm"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Отправка…" : "Отправить"}
            </Button>
          </div>
        </>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="text-xs text-destructive"
        >
          Не удалось отправить: {error}. Попробуйте ещё раз.
        </p>
      ) : null}
    </div>
  );
}
