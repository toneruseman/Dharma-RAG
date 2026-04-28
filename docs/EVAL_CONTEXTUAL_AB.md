# Contextual Retrieval A/B — `dharma_v1` vs `dharma_v2`

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from the
> synthetic golden v0.0; absolute quality claims require a buddhologist-
> curated v0.1 (see B-001 in `docs/STATUS.md`). The *deltas* between
> pipeline versions remain valid when the authoritative golden lands.

## Run metadata

- **Generated**: 2026-04-28T08:35:08+00:00
- **Git commit**: `6478174`
- **Golden set**: `docs\eval\golden_v0.0_synthetic.yaml` (version `0.0-synthetic`, n=30)
- **top_k (eval)**: 20
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Recommendation

**Winner on `ref_hit@5`: `v2_no_rerank` (0.567, Δ=+0.167 vs `v1_rerank` baseline 0.400).**

Contextual Retrieval **alone** outperforms both the day-12 baseline and the day-13 baseline-with-reranker. The cross-encoder reranker *degrades* quality on contextualized embeddings — likely because BGE-reranker-v2-m3 was trained on raw chunk text and now scores the context↔query similarity rather than chunk↔query.

**Suggested production default**: `dharma_v2` collection + `rerank=False`. This is also ~115× faster per query than the rerank path.

## Headline numbers

| Metric | v1 no-rerank | v1 rerank | v2 no-rerank | v2 rerank | Δ (v2-rerank − v1-rerank) |
|---|---:|---:|---:|---:|---:|
| ref_hit@1 | 0.133 | 0.133 | 0.233 | 0.167 | +0.033 |
| ref_hit@5 | 0.367 | 0.400 | 0.567 | 0.467 | +0.067 |
| ref_hit@10 | 0.433 | 0.433 | 0.633 | 0.600 | +0.167 |
| ref_hit@20 | 0.533 | 0.600 | 0.767 | 0.767 | +0.167 |
| MRR | 0.247 | 0.244 | 0.368 | 0.305 | +0.061 |

## Latency (totals across 30 queries)

| Run | total_latency_s | rerank_total_s |
|---|---:|---:|
| v1_no_rerank | 2.92 | 0.00 |
| v1_rerank | 223.71 | 221.74 |
| v2_no_rerank | 2.15 | 0.00 |
| v2_rerank | 226.10 | 224.18 |

## Breakdown — v1_rerank

### By difficulty

| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| easy | 10 | 0.100 | 0.500 | 0.500 | 0.600 | 0.264 |
| hard | 10 | 0.100 | 0.200 | 0.200 | 0.500 | 0.173 |
| medium | 10 | 0.200 | 0.500 | 0.600 | 0.700 | 0.294 |

### By language

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 28 | 0.143 | 0.393 | 0.429 | 0.571 | 0.240 |
| ru | 2 | 0.000 | 0.500 | 0.500 | 1.000 | 0.295 |

## Breakdown — v2_rerank

### By difficulty

| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| easy | 10 | 0.200 | 0.500 | 0.500 | 0.700 | 0.342 |
| hard | 10 | 0.100 | 0.300 | 0.500 | 0.800 | 0.222 |
| medium | 10 | 0.200 | 0.600 | 0.800 | 0.800 | 0.349 |

### By language

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 28 | 0.143 | 0.464 | 0.607 | 0.750 | 0.288 |
| ru | 2 | 0.500 | 0.500 | 0.500 | 1.000 | 0.533 |

## Failure analysis (production-best): v2_no_rerank vs v1_rerank (fixed n=7, regressed n=2)

Queries where v1+rerank (day-13 production) missed the expected sutta in top-5 but v2_no_rerank (production candidate) found it.

| id | query | expected | v1+rerank top-5 | v2_no_rerank top-5 |
|---|---|---|---|---|
| qa_002 | Where did the Buddha first teach the four noble truths? | sn56.11 | mn141, mn141, dn16, sn56.21, sn56.15 | an3.61, sn56.28, sn56.16, sn56.14, sn56.11 |
| qa_003 | What is the Mahāsatipaṭṭhāna Sutta about? | dn22 | sn6.5, mn133, an2.32-41, sn35.132, sn21.3 | mn133, mn84, mn84, dn22, mn18 |
| qa_016 | What does the Buddha say about wealth? | an4.61, an4.62, dn31 | an5.41, an7.7, dn30, sn3.19, dn30 | dn31, an7.5, an7.7, an5.47, mn96 |
| qa_017 | Teachings about karma and its results | mn135, mn136, an3.34 | sn42.13, an10.188, sn42.13, an10.144, sn42.13 | mn135, mn136, mn57, an10.217, sn42.13 |
| qa_023 | What is nibbāna in the suttas? | sn43.14, ud8.1, ud8.3, an3.55 | an8.91-117, mn80, mn141, an8.48, sn5.9 | an9.34, an9.48, an3.55, sn38.1, mn24 |
| qa_025 | What is the role of faith in the Buddhist path? | an5.38, sn55.1, mn70 | an4.52, dn19, mn120, an11.14, sn48.44 | an5.32, an4.152, an5.38, mn70, an4.52 |
| qa_030 | Учение о четырёх благородных истинах | sn56.11, sn56.13, mn141 | sn56.29, sn56.27, sn56.23, sn56.28, sn56.26 | sn56.4, sn56.38, mn141, an10.148, sn56.27 |

**Production-best regressions** (v1+rerank hit, v2_no_rerank missed):

| id | query | expected | v1+rerank top-5 | v2_no_rerank top-5 |
|---|---|---|---|---|
| qa_020 | Teachings on impermanence | sn22.59, sn22.45, sn35.1 | sn55.3, sn22.147, sn35.76, sn35.162, sn35.1 | an6.98, mn146, sn22.102, sn18.2, an7.16 |
| qa_022 | Did the Buddha say there is a self? | sn44.10, mn22, sn22.59 | mn22, sn44.7, sn22.49, mn35, sn35.121 | mn12, sn35.121, an4.21, an4.8, mn102 |

## Failure analysis (rerank-vs-rerank): queries v2 fixed (n=2)

Queries where v1+rerank missed the expected sutta in top-5 but 
v2+rerank found it. The headline payoff of Contextual Retrieval is 
exactly this set.

| id | query | expected | v1 top-5 | v2 top-5 |
|---|---|---|---|---|
| qa_017 | Teachings about karma and its results | mn135, mn136, an3.34 | sn42.13, an10.188, sn42.13, an10.144, sn42.13 | sn42.13, an8.40, mn136, sn12.46, sn1.49 |
| qa_021 | What is the relationship between sati and samādhi? | mn117, an4.41, sn47.4 | an11.11, an11.11, mn122, mn38, mn101 | an11.11, sn55.40, an5.23, sn47.4, mn38 |

## Regressions: queries v2 broke (n=0)

(none — v2 did not regress any v1+rerank hits)

---

Regenerate with `python scripts/eval_contextual_ab.py` (needs Qdrant + Postgres + GPU running).
