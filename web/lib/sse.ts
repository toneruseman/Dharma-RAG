/**
 * Tiny manual SSE (Server-Sent Events) parser over `fetch` +
 * `ReadableStream`.
 *
 * Why not use the browser's native `EventSource`? It's GET-only and
 * doesn't allow custom headers — that kills any future BYOK
 * (Bring Your Own Key) flow where the user's LLM API key has to
 * travel in an `Authorization` header. Manual parsing is ~50 lines
 * and supports POST + JSON body + arbitrary headers natively.
 *
 * Wire format (one event):
 *   event: <event-name>\n
 *   data: <single-line JSON>\n
 *   \n
 *
 * Frames are separated by a blank line (`\n\n`). Multi-line `data:`
 * is allowed by the SSE spec; we collapse them with `\n` per spec.
 *
 * Usage:
 *
 *   const ctrl = streamAsk(
 *     { query: "...", top_k: 5 },
 *     {
 *       onRetrievalDone: (e) => setSources(e.sources),
 *       onToken: (e) => appendDelta(e.delta),
 *       onCitation: (e) => trackCitation(e.id),
 *       onDone: (e) => finalize(e),
 *       onError: (e) => showError(e.message),
 *     },
 *   );
 *   // Later, on cleanup:
 *   ctrl.abort();
 */

import { API_BASE_URL, type AnswerMetadata, type AnswerRequest, type Source } from "./api-client";

// Event payload shapes mirror src/answer/stream_schemas.py. They aren't
// auto-generated into api-types.ts because the streaming endpoint
// returns text/event-stream rather than a JSON response_model — so
// FastAPI doesn't see them as referenced in any operation. Mirroring
// here is acceptable: the surface is 5 small models and the wire
// format is locked in by the SSE spec.

export type RetrievalDoneEvent = {
  sources: Source[];
  retrieval_latency_ms: number;
  pipeline_version: string;
};

export type TokenEvent = {
  delta: string;
};

export type CitationEvent = {
  id: string;
  position: number;
};

export type DoneEvent = {
  answer: string;
  citations: string[];
  latency_ms: number;
  llm_latency_ms: number;
  metadata: AnswerMetadata;
};

export type ErrorEvent_ = {
  code: "llm_failed" | "retrieval_failed" | "internal";
  message: string;
};

export type StreamHandlers = {
  onRetrievalDone?: (event: RetrievalDoneEvent) => void;
  onToken?: (event: TokenEvent) => void;
  onCitation?: (event: CitationEvent) => void;
  onDone?: (event: DoneEvent) => void;
  onError?: (event: ErrorEvent_) => void;
  /** Network/transport failure — separate from a structured error event. */
  onTransportError?: (error: unknown) => void;
};

/**
 * Start a streaming `/api/answer/stream` request. Returns an
 * `AbortController` so the caller can cancel — typically on component
 * unmount or when the user clicks "Stop".
 */
export function streamAsk(body: AnswerRequest, handlers: StreamHandlers): AbortController {
  const controller = new AbortController();
  void runStream(body, handlers, controller.signal);
  return controller;
}

async function runStream(
  body: AnswerRequest,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/answer/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal.aborted) return;
    handlers.onTransportError?.(err);
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onTransportError?.(
      new Error(`Stream request failed: ${response.status} ${response.statusText}`),
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      // Normalise CRLF → LF — SSE spec allows both; sse-starlette
      // sends `\r\n`. Without normalising, `indexOf("\n\n")` never
      // matches and the parser starves the entire stream.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

      // Each SSE frame ends with a blank line.
      let frameEnd = buffer.indexOf("\n\n");
      while (frameEnd !== -1) {
        const frame = buffer.slice(0, frameEnd);
        buffer = buffer.slice(frameEnd + 2);
        dispatchFrame(frame, handlers);
        frameEnd = buffer.indexOf("\n\n");
      }
    }
    // Trailing buffer at EOF should be empty for a well-formed
    // server (every event closes with `\n\n`). Anything left is
    // a truncated frame — silently drop instead of surfacing it as
    // a malformed-data error.
  } catch (err) {
    if (signal.aborted) return;
    handlers.onTransportError?.(err);
  } finally {
    reader.releaseLock();
  }
}

function dispatchFrame(frame: string, handlers: StreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const rawLine of frame.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (line.startsWith(":")) continue; // SSE comment / keep-alive ping
    if (line === "") continue;
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;
    const field = line.slice(0, colonIdx);
    // Per spec, single space after the colon is stripped; otherwise raw.
    const value =
      colonIdx + 1 < line.length && line[colonIdx + 1] === " "
        ? line.slice(colonIdx + 2)
        : line.slice(colonIdx + 1);
    if (field === "event") eventName = value;
    else if (field === "data") dataLines.push(value);
    // Other fields (id, retry) are ignored — we don't reconnect.
  }

  if (dataLines.length === 0) return;
  const dataJson = dataLines.join("\n");

  let payload: unknown;
  try {
    payload = JSON.parse(dataJson);
  } catch {
    handlers.onTransportError?.(new Error(`Malformed SSE data: ${dataJson.slice(0, 80)}`));
    return;
  }

  switch (eventName) {
    case "retrieval_done":
      handlers.onRetrievalDone?.(payload as RetrievalDoneEvent);
      break;
    case "token":
      handlers.onToken?.(payload as TokenEvent);
      break;
    case "citation":
      handlers.onCitation?.(payload as CitationEvent);
      break;
    case "done":
      handlers.onDone?.(payload as DoneEvent);
      break;
    case "error":
      handlers.onError?.(payload as ErrorEvent_);
      break;
    default:
      // Unknown event type — ignore. Forward-compat: future event
      // types can be added on the backend without breaking older
      // clients.
      break;
  }
}
