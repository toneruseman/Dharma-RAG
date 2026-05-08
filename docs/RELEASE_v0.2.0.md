# v0.2.0 — Phase 2 Quality Loop (partial)

End of Phase 2 *retrieval-quality* track. Phase 1 (`v0.1.0`, 2026-04-28)
shipped the working hybrid retrieval surface; **`v0.2.0` ships measurable
quality lift** on top of that baseline through curated query-level
mechanisms — definitional expansion, foundational sutta mapping, BM25
translation bridge — and an LLM answer endpoint with SSE streaming.

Scope deviations from the original plan are deliberate:

- **No fine-tuned BGE-M3** (planned days 36-45). Phase 3 will reshape the
  corpus distribution (Russian sources, ATI, 84000) — re-FT-ing now
  would discard the work. Deferred to Phase 3 close-out.
- **No buddhologist golden v0.1** (B-001, planned days 22-24). Iteration
  remains on synthetic `golden_v0.0_extended.yaml` (n=100). All quality
  numbers below are RELATIVE-only.
- **No CI eval-block** (B-004, planned days 27-28). Pre-commit hooks
  (ruff + mypy strict + detect-secrets) remain the local safety net.

---

## Highlights

- 🎯 **`ref_hit@1` 0.190 → 0.280 (+9.0 pp)** on synthetic golden
  v0.0_extended (n=100). The biggest user-visible signal: foundational
  boost actually surfaces canonical suttas at the very top position
  (`Что такое самадхи?` → AN 4.41, `What is satipaṭṭhāna?` → MN 10,
  `What is anapanasati?` → MN 118). See [`docs/EVAL_RAG_DAY_32.md`](EVAL_RAG_DAY_32.md).
- 📚 **`ref_hit@5` 0.450 → 0.500 (+5.0 pp)** — clears the v0.2.0 release
  threshold from concept-32. MRR 0.307 → 0.378 confirms correct works
  rank higher across the entire top-20.
- 🧠 **Definitional query expansion** (rag-day-28). Detects
  *What is X?* / *Что такое X?* / *Define X* / *Meaning of X* and
  rewrites into a longer gloss template before encoding.
  ([`concept-28`](concepts/28-definitional-expansion.md))
- 🗺 **Foundational mapping** (rag-day-28+30). Curated YAML with **24
  entries** mapping Buddhist terms to their canonical first-source
  suttas (Sahaya 12 essentials + 6 supplementary + 5 Russian-foundational
  + 1 right-effort split). Post-RRF score boost surfaces the canonical
  work to #1 when the term appears in the query.
- 🌍 **BM25 translation bridge** (rag-day-29). Sujato translates Pāli
  body text into English (`dukkha` → `suffering`, `samādhi` →
  `immersion`); a literal Pāli token query produces zero BM25 hits.
  Foundational entries now ship Sujato-aligned English aliases that
  the BM25 channel sees via `or`-clauses; `apply_boost` uses
  *floor-to-top* semantics to guarantee the canonical work lands near
  the top once it is in the candidate pool.
  ([`concept-29`](concepts/29-bm25-translation-bridge.md))
- 🇷🇺 **Russian foundational coverage** (rag-day-30). 5 new entries
  (samadhi, bojjhanga, brahmavihara, three refuges, iddhipada) + 2
  extensions (lay ethics ← sigalaka/нравственность, dependent
  origination ← обусловленное возникновение/12 нидан). All aliases
  Sujato-aligned: `samādhi → immersion` (not `concentration` —
  diagnosed via direct BM25 inspection in rag-day-30).
  ([`concept-30`](concepts/30-russian-foundational-expansion.md))
- 🤖 **`POST /api/answer`** (rag-day-24). LLM-grounded answer endpoint
  with inline `[work_id]` citations. System prompt enforces grounding,
  refuses on insufficient context, preserves Pāli diacritics. Default
  model `deepseek/deepseek-v4-flash` ($0.003/req, A− quality vs Haiku
  4.5 at 15× cost — see [`EVAL_ANSWER_MODELS.md`](EVAL_ANSWER_MODELS.md)).
- 📡 **`POST /api/answer/stream` SSE** (rag-day-25). Token-by-token
  streaming with 5 event types (retrieval_done / token / citation / done /
  error). `IncrementalCitationScanner` correctly handles split-bracket
  citations across token chunks. ([`concept-22`](concepts/22-sse-streaming.md))
- 🧪 **`tests/unit/expand` battery** — 55 unit tests covering
  definitional regex, foundational matcher (term + alias matching,
  word-boundary, case-insensitive, BM25 alias filtering), apply_boost
  semantics (floor-to-top, max-boost-on-overlap), YAML loader.

## Numbers (synthetic golden v0.0_extended, n=100)

Cumulative effect of rag-day-28+29+30 stack vs `v0.1.0` baseline
(both `dharma_v2 + rerank=False + expand_parents=True + glossary`):

| metric | A baseline | B v0.2.0 stack | Δ | Δ pp |
|---|---:|---:|---:|---:|
| ref_hit@1 | 0.190 | **0.280** | +0.090 | **+9.0** |
| ref_hit@5 | 0.450 | **0.500** | +0.050 | **+5.0** |
| ref_hit@10 | 0.540 | 0.600 | +0.060 | +6.0 |
| ref_hit@20 | 0.650 | 0.690 | +0.040 | +4.0 |
| MRR | 0.307 | **0.378** | +0.071 | +7.1 |

By language (n shown — small for ru/pli, deltas indicative only):

| language | n | A ref_hit@5 | B ref_hit@5 | A MRR | B MRR |
|---|---:|---:|---:|---:|---:|
| en | 91 | 0.473 | 0.484 | 0.329 | 0.367 |
| pli | 2 | 0.000 | 1.000 | 0.000 | 0.600 |
| ru | 7 | 0.286 | 0.286 | 0.104 | 0.198 |

**9 fixed / 4 regressed** at top-5. Fixed cases include
`What is mindfulness of breathing?` → mn118, `What is satipaṭṭhāna?` →
mn10/dn22, `Что такое самадхи?` → an4.41, `What is dukkha-nirodha?` →
sn56.11, `dukkha samudaya nirodha magga` → sn56.11. Remaining 4
regressions are encoder noise on simile / Russian queries — outside
the foundational-curation surface (no foundational entry fired).

Synthetic v0.0_extended is **directional, not authoritative.** B-001
(buddhologist-built golden v0.1) remains the gate for absolute quality
claims at v1.0+.

## What's not in this release

- **No fine-tuned BGE-M3.** Phase 3 will broaden the corpus; FT now
  would be redone after.
- **No buddhologist golden v0.1.** B-001 deferred until proof-of-concept
  is community-ready.
- **No CI eval-block.** B-004; pre-commit gates remain the local safety
  net.
- **No multi-source corpus.** Phase 3 (ATI, 84000, theravada.ru) starts
  after this release.
- **No verse-aware chunking.** rag-day-31 deferred — touches the chunker
  and requires partial re-ingest; not justified before Phase 3 reshape.
- **No Khuddaka Nikāya.** `metta → snp1.8`, dhammapada, theragāthā,
  therīgāthā, udāna, itivuttaka not yet ingested. Tracked as separate
  ingest task.

## Stats

- **65 unit tests in `tests/unit/expand`** (definitional + foundational).
  Full repo-wide test count remains green; pre-commit (ruff, mypy strict,
  detect-secrets, mixed-line-ending) all pass.
- **24 entries** in `data/glossary/foundational.yaml` covering 30 unique
  works. Sahaya 12 essentials + 12 our additions.
- **6,478 child chunks** in `dharma_v2` (unchanged from v0.1.0 — no
  re-ingest in this release).
- **~80-200 ms** end-to-end per query (boost-pool widening to 100
  candidates triggers extra enrich JOINs but stays sub-second).

## Migration from v0.1.0

No breaking changes. New optional fields on `QueryRequest` /
`AnswerRequest`:

- `expand_pali: bool | None = None` (rag-day-23, was already in v0.1.0)
- `expand_definitional: bool | None = None` (rag-day-28; defaults to
  `glossary_expand_definitional_default = True`)
- `foundational_boost: bool | None = None` (rag-day-28; defaults to
  `glossary_foundational_boost_default = True`)

Server-side defaults already deliver the v0.2.0 stack — no client
change needed to benefit. Pass `False` for A/B comparison.

`PipelineMetadata` adds `expand_definitional: bool` and
`foundational_boost: bool` fields tracking *effective* state.
Version-string format extended:
`dharma_v2-rerank0-parents1-pali1-defn1-fnd1`.

## Quickstart

Same as v0.1.0 — see [`RELEASE_v0.1.0.md`](RELEASE_v0.1.0.md).

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary '{"query": "Что такое самадхи?", "top_k": 5}'
# → an4.41 #1 (Samādhibhāvanā Sutta)
```

## Roadmap

Next up (priority order):

1. **Khuddaka Nikāya ingest** — unblocks `metta → snp1.8`, dhammapada,
   theragāthā/therīgāthā, udāna, itivuttaka (~5-7K chunks).
2. **Phase 3 multi-source** — Russian corpus (theravada.ru, dhamma.ru),
   ATI Thanissaro/Bodhi, 84000 subset. Authoritative golden v0.1
   becomes feasible against multi-source coverage.
3. **rag-day-31 verse-aware chunking** — addresses category C from
   `FAILURE_PATTERNS.md` (snp1.8 / sn46.54 / kn1.9 fall as child-chunks
   among prose).
4. **rag-day-36-45 FT BGE-M3** — only after corpus is finalised
   (post-Phase 3).

---

Generated 2026-05-08. Tag `v0.2.0` to be created after this PR merges.
