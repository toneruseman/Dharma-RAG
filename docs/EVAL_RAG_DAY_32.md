# rag-day-32 — cumulative re-eval (synthetic golden v0.0_extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers come from `golden_v0.0_extended.yaml` (100 synthetic QA without buddhologist review — B-001 still open). Deltas between configurations remain valid even on synthetic data.

## Headline

- **A** (pre-rag-day-28 baseline, glossary only): `ref_hit@5 = 0.490`, MRR = 0.341
- **B** (rag-day-28+29+30 full stack): `ref_hit@5 = 0.560`, MRR = 0.453
- **Δ ref_hit@5**: `+0.070` (+7.0 pp)

### Decision

**RELEASE** — `B.ref_hit@5 = 0.560` ≥ 0.5 threshold. Cut `v0.2.0`.

## Run metadata

- **Generated**: 2026-05-08T16:20:56+00:00
- **Git commit**: `20eb9f7`
- **Golden set**: `docs\eval\golden_v0.0_extended.yaml` (version `0.0-synthetic-extended`, n=100)
- **top_k (eval)**: 20
- **Collection**: `dharma_v2` (Contextual Retrieval, rag-day-16)
- **Fixed knobs**: `rerank=False`, `expand_parents=True`, `expand_pali=True`, `glossary_max_meanings=1`
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Configurations

| Cell | expand_pali | expand_definitional | foundational_boost | bm25_aliases |
|---|:--:|:--:|:--:|:--:|
| **A** pre-28 baseline | ✓ | — | — | — |
| **B** post-30 stack | ✓ | ✓ | ✓ | ✓ |

## Headline metrics

| metric | A baseline | B stack | Δ | Δ pp |
|---|---:|---:|---:|---:|
| ref_hit@1 | 0.230 | 0.360 | +0.130 | +13.0 |
| ref_hit@5 | 0.490 | 0.560 | +0.070 | +7.0 |
| ref_hit@10 | 0.590 | 0.680 | +0.090 | +9.0 |
| ref_hit@20 | 0.690 | 0.750 | +0.060 | +6.0 |
| MRR | 0.341 | 0.453 | +0.111 | +11.1 |

## Breakdown by language

| language | n | A ref_hit@5 | B ref_hit@5 | Δ | A MRR | B MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.516 | 0.560 | +0.044 | 0.356 | 0.439 |
| pli | 2 | 0.000 | 1.000 | +1.000 | 0.000 | 1.000 |
| ru | 7 | 0.286 | 0.429 | +0.143 | 0.253 | 0.470 |

## Breakdown by difficulty

| difficulty | n | A ref_hit@5 | B ref_hit@5 | Δ |
|---|---:|---:|---:|---:|
| easy | 30 | 0.600 | 0.700 | +0.100 |
| hard | 35 | 0.343 | 0.429 | +0.086 |
| medium | 35 | 0.543 | 0.571 | +0.029 |

## Fixed / regressed at top-5

- Fixed by stack: **9**
- Regressed: **2**

### Fixed (B found, A missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_003 | What is the Mahāsatipaṭṭhāna Sutta about? | dn22 | dn16, mn138, dn20, ud7.8, mn131 | dn22, mn10, dn22, mn10, dn22 |
| qa_033 | What is metta meditation? | snp1.8, sn46.54 | an8.1, an11.16, an11.15, sn42.13, mn97 | snp1.8, an8.1, kp9, mn119, an8.63 |
| qa_042 | What is the gradual training? | mn39, dn2 | mn65, mn70, mn107, an3.86, an8.20 | mn65, mn39, mn107, mn94, sn12.93-213 |
| qa_049 | Что такое самадхи? | an4.41, sn40.10 | an3.101, dn10, dn10, an11.11, dn10 | an4.41, an10.6, an5.27, dn10, mn7 |
| qa_050 | What is anatta? | sn22.59, mn22 | sn22.145, sn18.1, sn35.219-221, sn35.210-212, sn23.17 | sn22.59, sn22.145, snp1.8, sn22.16, sn22.77 |
| qa_067 | What is dukkha-nirodha? | sn56.11, sn22.59, an3.61 | snp3.12, sn35.226, mn9, mn63, sn56.20 | sn56.11, sn56.11, mn9, snp3.12, an4.102 |
| qa_096 | dukkha samudaya nirodha magga | sn56.11, sn56.13 | sn56.32, sn38.1, sn4.6, mn31, dn16 | sn56.11, sn56.11, sn56.32, mn9, sn22.104 |
| qa_099 | What is the role of the Sangha as refuge? | dn16, sn55.1, sn11.3 | sn40.10, kp1, sn40.10, sn47.9, mn72 | kp1, mn135, mn100, sn11.3, mn150 |
| qa_100 | paṭiccasamuppāda anuloma paṭiloma | sn12.1, sn12.2 | dn15, sn35.113, mn60, ud1.2, mn60 | sn12.2, dn15, sn35.113, mn38, mn38 |

### Regressed (A found, B missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_031 | What is the Discourse to the Kalamas? | an3.65 | snp5.18, an4.76, snp5.19, an3.65, an3.65 | snp1.8, an4.139, dn13, snp2.1, snp5.1 |
| qa_036 | What is the simile of the cowherd? | mn33, mn34 | an11.22-29, ud4.3, mn34, dn23, an3.70 | dn23, sn20.12, an11.22-29, dn13, an4.107 |

---

Regenerate with `python scripts/eval_rag_day_32.py` 
(needs Qdrant + Postgres + GPU, ~2 min wallclock).
