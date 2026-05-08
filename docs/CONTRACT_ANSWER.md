# `POST /api/answer` — Public Contract

LLM-grounded answer endpoint. Layer above `/api/query` — same
retrieval pool, plus a single synthesised answer with inline
citations.

> **Status:** stable contract from rag-day-24. Adding optional
> request fields is backwards-compatible. Removing or renaming
> fields, or changing semantics of existing ones, is a breaking
> change and warrants a major version bump.

---

## Request

```http
POST /api/answer
Content-Type: application/json
```

```json
{
  "query": "что такое джхана?",
  "top_k": 5,
  "expand_pali": null,
  "forbidden_works": null,
  "model": null
}
```

| Field | Type | Required | Default | Description |
|---|---|:---:|---|---|
| `query` | string (1-2000) | ✓ | — | The user's question. Russian, English, mixed all supported. |
| `top_k` | int (1-10) | | 5 | How many source passages to retrieve and feed to the LLM. Tighter cap than `/api/query` (which allows up to 20) because each extra passage costs ~500-1500 input tokens. |
| `expand_pali` | bool \| null | | null | Forwarded to retrieval. `null` defers to server-side default; `true`/`false` overrides per request. |
| `forbidden_works` | string[] \| null | | null | Forwarded to retrieval. Drops sources whose `work_canonical_id` appears in this list **before** the LLM call. |
| `model` | string \| null | | null | Optional override of the OpenRouter model id (e.g. `"anthropic/claude-3.5-haiku"`). `null` uses the server-side `answer_llm_model`. |
| `style` | `"auto"` \| `"concise"` \| `"detailed"` \| null | | null | Length/depth preference. `null` defers to server-side `answer_default_style` (currently `"auto"`). `"concise"` = 2-4 sentences. `"detailed"` = multi-paragraph, every claim cited. `"auto"` = model picks length to match question complexity. |

---

## Response (200 OK)

```json
{
  "query": "что такое джхана?",
  "answer": "Джхана (jhāna) — это состояние глубокого медитативного покоя, описанное в [mn36] как основа пробуждения Будды. Существует четыре последовательных уровня джхан, каждый с возрастающей чистотой [an9.36].",
  "sources": [
    {
      "work_canonical_id": "mn36",
      "segment_id": "mn36:30.1",
      "text": "...full parent passage...",
      "snippet": "...matched child fragment...",
      "score": 0.91
    }
  ],
  "citations": ["mn36", "an9.36"],
  "latency_ms": 2154.3,
  "retrieval_latency_ms": 84.1,
  "llm_latency_ms": 2068.0,
  "metadata": {
    "pipeline_version": "dharma_v2-rerank0-parents1-pali1",
    "llm_model": "openrouter/anthropic/claude-haiku-4.5",
    "llm_tokens_in": 1820,
    "llm_tokens_out": 124,
    "style": "auto",
    "retrieval_metadata": {
      "version": "dharma_v2-rerank0-parents1-pali1",
      "collection": "dharma_v2",
      "rerank": false,
      "expand_parents": true,
      "expand_pali": true,
      "n_candidates": 5
    }
  }
}
```

### Field semantics

| Field | Description |
|---|---|
| `query` | Echo of the user's input. Use for caching keys / UI rehydration. |
| `answer` | Free-form text in the language of the question. **May be empty string** when retrieval returned no sources — UI should render a "no relevant passages" fallback in that case. Inline citations: `[work_id]` format, e.g. `[mn10]`. |
| `sources` | Same shape as `/api/query`. `text` is the parent chunk (LLM context); `snippet` is the matched child fragment (UI highlight). |
| `citations` | **Distinct work_ids the LLM actually cited**, intersected with the retrieved sources. Hallucinated citations (model invents a work_id not in the source set) are filtered out. Order = first appearance in `answer`. |
| `latency_ms` | End-to-end wall-clock time. |
| `retrieval_latency_ms` | Time spent in retrieval (encode + Qdrant + DB enrich + RRF + optional reranker). |
| `llm_latency_ms` | Time spent in the LLM call. **`0.0` when `sources` is empty** (we skip the LLM entirely to avoid burning tokens on no context). |
| `metadata.pipeline_version` | Compact retrieval config label, copied from `retrieval_metadata.version`. Useful for correlating answer quality with retrieval config in eval/logs. |
| `metadata.llm_model` | OpenRouter id of the model that generated the answer. Format `openrouter/vendor/model`, e.g. `openrouter/anthropic/claude-haiku-4.5`. |
| `metadata.llm_tokens_in` / `llm_tokens_out` | Token counts from the LLM provider. `0` when the LLM was skipped. |
| `metadata.style` | Effective style applied to this request (resolved from request override or server default). One of `"auto"` / `"concise"` / `"detailed"`. |
| `metadata.retrieval_metadata` | Full `PipelineMetadata` from `/api/query`, embedded so consumers don't need a second round-trip. |

---

## Error responses

| Status | When |
|---|---|
| 422 | Pydantic validation: empty `query`, `top_k` out of range, malformed JSON. |
| 503 | Service still initialising (lifespan startup not complete). Client should retry with backoff. |
| 5xx | Upstream OpenRouter or Qdrant failure. Retry with backoff if 502/503/504; otherwise surface to user. |

---

## Backend modes

The endpoint behaves identically (same response shape) in both modes.
Selection via `Settings.rag_backend`:

| `RAG_BACKEND` | What runs |
|---|---|
| `stub` | `StubAnswerService` — deterministic fixture answer, ~2 ms, no OpenRouter call. Fixture cites `[mn10]`, `[sn56.11]`, `[dn22]`. **Frontend dev's default.** |
| `real` | `AnswerService` — full retrieval + Claude Haiku 4.5 via OpenRouter. Requires `OPENROUTER_API_KEY` in env. |

---

## Examples

### PowerShell — happy path

```powershell
$r = Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"что такое джхана?","top_k":3}' -ContentType 'application/json'; "QUERY    : $($r.query)"; "LATENCY  : $([math]::Round($r.latency_ms,1)) ms (retrieval=$([math]::Round($r.retrieval_latency_ms,1)) llm=$([math]::Round($r.llm_latency_ms,1)))"; "ANSWER   :"; $r.answer; "CITATIONS: $($r.citations -join ', ')"; "----- METADATA -----"; $r.metadata
```

### Override model for A/B

```powershell
$r = Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"what is dukkha?","model":"anthropic/claude-3.5-haiku"}' -ContentType 'application/json'; $r.answer; $r.metadata.llm_model
```

### Force-disable Pāli expansion

```powershell
$r = Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"что такое джхана?","expand_pali":false}' -ContentType 'application/json'; $r.metadata.retrieval_metadata.expand_pali
```

### Detailed answer (multi-paragraph)

```powershell
$r = Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"что такое джхана?","style":"detailed","top_k":5}' -ContentType 'application/json'; "STYLE: $($r.metadata.style)"; $r.answer
```

### Concise answer (2-4 sentences)

```powershell
$r = Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"что такое джхана?","style":"concise"}' -ContentType 'application/json'; $r.answer
```

---

## Backwards compatibility

* New optional fields may be added without a contract bump.
* Default values may change (e.g. `model` default flips to a newer Haiku) — clients should not hard-code expected models.
* `citations` order may change between server versions — clients sorting by appearance should not rely on a stable algorithm.
* `latency_ms` and friends are diagnostic — never gate UX on specific values; they shift with infrastructure.
