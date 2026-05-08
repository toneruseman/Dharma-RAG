/**
 * Typed thin wrappers around the FastAPI endpoints.
 *
 * The schema source-of-truth is the committed `openapi.json` at repo
 * root; types are generated into `./api-types.ts` (gitignored) by
 * `pnpm typegen`. This file exposes ergonomic, typed functions so
 * components don't poke at raw fetch boilerplate.
 *
 * Why a hand-rolled wrapper instead of a full client codegen
 * (orval / openapi-fetch):
 *   - We currently have 3 endpoints. Codegen at this scale is
 *     overkill — a 60-line wrapper is easier to read and easier to
 *     extend with project-specific concerns (auth headers, retry
 *     policy, telemetry).
 *   - When the surface grows past ~10 endpoints we can swap to
 *     `openapi-fetch` (which uses the same `paths` type we already
 *     generate) without touching call sites.
 */

import type { components, paths } from "./api-types";

// ---------------------------------------------------------------------------
// Re-exported types (so consumers don't import from api-types directly)
// ---------------------------------------------------------------------------

/** Body of `POST /api/query`. */
export type QueryRequest = components["schemas"]["QueryRequest"];

/** Body of the response from `POST /api/query`. */
export type QueryResponse = components["schemas"]["QueryResponse"];

/** Body of `POST /api/answer`. */
export type AnswerRequest = components["schemas"]["AnswerRequest"];

/** Body of the response from `POST /api/answer`. */
export type AnswerResponse = components["schemas"]["AnswerResponse"];

/** One source passage in either response. */
export type Source = components["schemas"]["Source"];

/** Full document body for the Reading Room (`GET /api/sources/{uid}`). */
export type SourceDocument = components["schemas"]["SourceDocument"];

/** One ordered paragraph (parent-chunk) inside a `SourceDocument`. */
export type SourceParagraph = components["schemas"]["SourceParagraph"];

/** Provenance metadata for the rendered translation. */
export type SourceTranslation = components["schemas"]["SourceTranslation"];

/** Pipeline metadata (retrieval config that produced the response). */
export type PipelineMetadata = components["schemas"]["PipelineMetadata"];

/** Answer-layer metadata (LLM model, tokens, effective style). */
export type AnswerMetadata = components["schemas"]["AnswerMetadata"];

/** Answer length / depth preference. */
export type AnswerStyle = NonNullable<AnswerRequest["style"]>;

/** Body of `POST /api/feedback`. */
export type FeedbackRequest = components["schemas"]["FeedbackRequest"];

/** Body of the response from `POST /api/feedback`. */
export type FeedbackResponse = components["schemas"]["FeedbackResponse"];

/** Snapshot of the answer fields persisted alongside a feedback row. */
export type AnswerSnapshot = components["schemas"]["AnswerSnapshot"];

/** Body of `POST /api/thread/next` — LLM-free passage rotation. */
export type ThreadRequest = components["schemas"]["ThreadRequest"];

/** Body of the response from `POST /api/thread/next`. */
export type ThreadResponse = components["schemas"]["ThreadResponse"];

/** One canonical passage card in the LLM-free thread. */
export type ThreadCard = components["schemas"]["ThreadCard"];

/** Health-check response. */
export type HealthResponse = paths["/health"]["get"]["responses"]["200"]["content"]["application/json"];

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Base URL of the FastAPI backend. In Next.js dev `web` runs on `:3001`
 * and uvicorn on `:8000`, so we hit a different origin (CORS already
 * permitted in the API for dev). Override via `NEXT_PUBLIC_API_BASE_URL`
 * for staging/prod where the frontend is served from the same origin.
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

/**
 * Thrown when the backend returns a non-2xx response. Carries the HTTP
 * status, the parsed JSON body if any (FastAPI returns
 * ``{detail: ...}`` shapes for 4xx/5xx), and the original `Response`
 * for advanced consumers.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  readonly response: Response;

  constructor(message: string, response: Response, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = response.status;
    this.body = body;
    this.response = response;
  }
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

async function postJson<TReq, TRes>(
  path: string,
  body: TReq,
  init?: RequestInit,
): Promise<TRes> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: "POST",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    body: JSON.stringify(body),
  });
  return parseOrThrow<TRes>(response);
}

async function parseOrThrow<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  // Try to surface FastAPI's `{detail: ...}` body so the UI can show
  // a meaningful message; fall back to status-only on non-JSON bodies.
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = await response.text().catch(() => null);
  }
  throw new ApiError(
    `${response.status} ${response.statusText}`,
    response,
    body,
  );
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Liveness check. Use sparingly — the FastAPI `/health` endpoint
 * intentionally does no downstream verification.
 */
export async function getHealth(init?: RequestInit): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, init);
  return parseOrThrow<HealthResponse>(response);
}

/**
 * Run retrieval and return the top-k source passages.
 *
 * Use this when the consumer (eval scripts, debug UIs, future
 * admin views) needs the raw retrieval pool. End-user features
 * should prefer ``ask`` which adds a synthesised LLM answer on top.
 */
export async function query(
  body: QueryRequest,
  init?: RequestInit,
): Promise<QueryResponse> {
  return postJson<QueryRequest, QueryResponse>("/api/query", body, init);
}

/**
 * Fetch a full document for the Reading Room.
 *
 * Returns the work's title, the chosen translation's metadata, and
 * all parent paragraphs in document order. ``null`` when the
 * canonical_id is not in the corpus (404) — call sites can render a
 * "not found" UI without a try/catch.
 */
export async function getSource(
  canonicalId: string,
  init?: RequestInit,
): Promise<SourceDocument | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/${encodeURIComponent(canonicalId)}`,
    init,
  );
  if (response.status === 404) {
    return null;
  }
  return parseOrThrow<SourceDocument>(response);
}

/**
 * Run retrieval + LLM synthesis. Returns a grounded answer with
 * inline ``[work_id]`` citations alongside the source passages
 * actually fed to the model.
 *
 * Common parameters:
 *   - ``style: "auto" | "concise" | "detailed"`` — answer length.
 *     ``null``/omitted defers to the server-side default.
 *   - ``model`` — override OpenRouter model id per request.
 *   - ``expand_pali`` — toggle Pāli glossary expansion.
 *   - ``forbidden_works`` — filter out specific source ids.
 */
export async function ask(
  body: AnswerRequest,
  init?: RequestInit,
): Promise<AnswerResponse> {
  return postJson<AnswerRequest, AnswerResponse>("/api/answer", body, init);
}

/**
 * Fetch the next round of canonical passages for the LLM-free
 * "infinite thread" UX (rag-day-36). Pass back the accumulated
 * ``excluded_chunk_ids`` from prior rounds so the server skips them.
 *
 * No LLM in the loop — each round is one retrieval call (~200 ms,
 * $0). When ``response.exhausted`` is true the pool is empty and the
 * UI should label or hide the «Далее» button.
 */
export async function threadNext(
  body: ThreadRequest,
  init?: RequestInit,
): Promise<ThreadResponse> {
  return postJson<ThreadRequest, ThreadResponse>("/api/thread/next", body, init);
}

/**
 * Submit a 👍/👎 vote (and optional comment) for a previous answer.
 *
 * Idempotent — repeating the call with the same ``trace_id`` updates
 * the existing row server-side. The ``answer_snapshot`` is the subset
 * of ``AnswerResponse`` / ``DoneEvent`` fields that the row needs to
 * be self-contained for review through ``psql``.
 */
export async function sendFeedback(
  body: FeedbackRequest,
  init?: RequestInit,
): Promise<FeedbackResponse> {
  return postJson<FeedbackRequest, FeedbackResponse>("/api/feedback", body, init);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Type guard for the error shape `ApiError` exposes. Useful in
 * try/catch where ``error`` is typed as ``unknown``.
 */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
