# rag-day-32 — cumulative re-eval (synthetic golden v0.0_extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers come from `golden_v0.0_extended.yaml` (100 synthetic QA without buddhologist review — B-001 still open). Deltas between configurations remain valid even on synthetic data.

## Headline

- **A** (pre-rag-day-28 baseline, glossary only): `ref_hit@5 = 0.450`, MRR = 0.307
- **B** (rag-day-28+29+30 full stack): `ref_hit@5 = 0.480`, MRR = 0.360
- **Δ ref_hit@5**: `+0.030` (+3.0 pp)

### Decision

**MARGINAL** — `B.ref_hit@5 = 0.480` ∈ [0.45, 0.5). Inspect language breakdown; if Russian wins clearly, frame release as Russian-coverage milestone.

## Run metadata

- **Generated**: 2026-05-08T10:46:59+00:00
- **Git commit**: `e5af3d7`
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
| ref_hit@1 | 0.190 | 0.260 | +0.070 | +7.0 |
| ref_hit@5 | 0.450 | 0.480 | +0.030 | +3.0 |
| ref_hit@10 | 0.540 | 0.590 | +0.050 | +5.0 |
| ref_hit@20 | 0.650 | 0.690 | +0.040 | +4.0 |
| MRR | 0.307 | 0.360 | +0.053 | +5.3 |

## Breakdown by language

| language | n | A ref_hit@5 | B ref_hit@5 | Δ | A MRR | B MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.473 | 0.484 | +0.011 | 0.329 | 0.367 |
| pli | 2 | 0.000 | 1.000 | +1.000 | 0.000 | 0.600 |
| ru | 7 | 0.286 | 0.286 | +0.000 | 0.104 | 0.198 |

## Breakdown by difficulty

| difficulty | n | A ref_hit@5 | B ref_hit@5 | Δ |
|---|---:|---:|---:|---:|
| easy | 30 | 0.533 | 0.600 | +0.067 |
| hard | 35 | 0.314 | 0.314 | +0.000 |
| medium | 35 | 0.514 | 0.543 | +0.029 |

## Fixed / regressed at top-5

- Fixed by stack: **9**
- Regressed: **6**

### Fixed (B found, A missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_001 | What is mindfulness of breathing? | mn118 | an10.60, sn54.13, sn54.1, sn54.5, mn62 | mn118, mn118, mn118, mn118, mn118 |
| qa_040 | What is satipaṭṭhāna? | mn10, dn22 | sn47.18, sn47.44, sn47.4, sn47.3, sn52.2 | mn10, dn22, dn22, mn10, dn22 |
| qa_042 | What is the gradual training? | mn39, dn2 | mn65, mn70, mn107, an3.86, an8.20 | mn65, mn39, mn107, mn94, sn12.93-213 |
| qa_049 | Что такое самадхи? | an4.41, sn40.10 | an3.101, dn10, dn10, an11.11, dn10 | an4.41, an5.27, an10.6, dn10, dn10 |
| qa_050 | What is anatta? | sn22.59, mn22 | sn22.145, sn18.1, sn35.219-221, sn35.210-212, sn22.143 | sn22.59, sn22.145, sn22.16, sn22.77, sn23.17 |
| qa_053 | What is the role of generosity in spiritual progress? | an4.61, an5.36, an8.36 | an7.57, an8.50, an7.6, an5.31, sn2.23 | an7.6, an6.45, an5.31, an8.36, sn1.42 |
| qa_067 | What is dukkha-nirodha? | sn56.11, sn22.59, an3.61 | sn35.226, mn9, mn63, sn56.20, sn23.15 | sn56.11, sn56.11, mn9, an4.102, mn63 |
| qa_096 | dukkha samudaya nirodha magga | sn56.11, sn56.13 | sn56.32, sn38.1, mn31, sn45.157, dn16 | sn56.11, sn56.11, sn56.32, mn141, mn9 |
| qa_100 | paṭiccasamuppāda anuloma paṭiloma | sn12.1, sn12.2 | dn15, sn35.113, mn60, dn24, sn35.106 | dn15, sn35.113, an10.92, sn22.37, sn12.1 |

### Regressed (A found, B missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_036 | What is the simile of the cowherd? | mn33, mn34 | an11.22-29, mn34, dn23, an3.70, mn33 | dn23, an11.22-29, sn20.12, dn13, sn20.4 |
| qa_044 | What is the simile of the elephant's footprint? | mn28 | mn27, mn27, mn28, mn27, sn45.140 | mn27, sn45.140, mn27, sn3.17, mn27 |
| qa_047 | What is the simile of foam? | sn22.95 | dn23, sn22.95, dn23, dn23, sn35.248 | dn23, an9.15, dn13, sn35.236, dn23 |
| qa_062 | Teachings on right effort | mn117, an4.13 | an4.13, mn141, sn49.1-12, an4.275, an4.69 | an6.55, an6.55, sn45.8, an10.114, an10.147 |
| qa_029 | Что такое страдание в буддизме? | sn56.11, dn22, mn141 | sn35.67, mn103, mn141, mn103, sn38.14 | sn4.13, an5.137, sn35.67, sn1.6, sn38.14 |
| qa_082 | What is right concentration in detail? | mn117, an5.28, dn22 | an5.28, dn22, an7.45, an11.8, an5.27 | an10.138, sn12.55, sn22.23, sn47.20, an7.41 |

---

Regenerate with `python scripts/eval_rag_day_32.py` 
(needs Qdrant + Postgres + GPU, ~2 min wallclock).
