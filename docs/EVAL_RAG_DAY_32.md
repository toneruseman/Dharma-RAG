# rag-day-32 — cumulative re-eval (synthetic golden v0.0_extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers come from `golden_v0.0_extended.yaml` (100 synthetic QA without buddhologist review — B-001 still open). Deltas between configurations remain valid even on synthetic data.

## Headline

- **A** (pre-rag-day-28 baseline, glossary only): `ref_hit@5 = 0.460`, MRR = 0.312
- **B** (rag-day-28+29+30 full stack): `ref_hit@5 = 0.520`, MRR = 0.395
- **Δ ref_hit@5**: `+0.060` (+6.0 pp)

### Decision

**RELEASE** — `B.ref_hit@5 = 0.520` ≥ 0.5 threshold. Cut `v0.2.0`.

## Run metadata

- **Generated**: 2026-05-08T14:44:03+00:00
- **Git commit**: `61788f2`
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
| ref_hit@1 | 0.190 | 0.290 | +0.100 | +10.0 |
| ref_hit@5 | 0.460 | 0.520 | +0.060 | +6.0 |
| ref_hit@10 | 0.560 | 0.630 | +0.070 | +7.0 |
| ref_hit@20 | 0.670 | 0.710 | +0.040 | +4.0 |
| MRR | 0.312 | 0.395 | +0.082 | +8.2 |

## Breakdown by language

| language | n | A ref_hit@5 | B ref_hit@5 | Δ | A MRR | B MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.473 | 0.516 | +0.044 | 0.324 | 0.394 |
| pli | 2 | 0.000 | 1.000 | +1.000 | 0.000 | 0.600 |
| ru | 7 | 0.429 | 0.429 | +0.000 | 0.247 | 0.341 |

## Breakdown by difficulty

| difficulty | n | A ref_hit@5 | B ref_hit@5 | Δ |
|---|---:|---:|---:|---:|
| easy | 30 | 0.567 | 0.700 | +0.133 |
| hard | 35 | 0.314 | 0.314 | +0.000 |
| medium | 35 | 0.514 | 0.571 | +0.057 |

## Fixed / regressed at top-5

- Fixed by stack: **11**
- Regressed: **5**

### Fixed (B found, A missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_001 | What is mindfulness of breathing? | mn118 | an10.60, sn54.13, sn54.1, sn54.5, mn62 | mn118, mn118, mn118, mn118, mn118 |
| qa_003 | What is the Mahāsatipaṭṭhāna Sutta about? | dn22 | dn16, dn20, ud7.8, mn119, mn138 | dn22, mn10, dn22, sn52.15, sn52.20 |
| qa_033 | What is metta meditation? | snp1.8, sn46.54 | an8.1, an11.16, an11.15, sn42.13, mn97 | snp1.8, an8.1, kp9, mn119, an8.63 |
| qa_040 | What is satipaṭṭhāna? | mn10, dn22 | sn47.18, sn47.44, sn47.4, sn47.3, sn52.2 | mn10, dn22, dn22, mn10, dn22 |
| qa_042 | What is the gradual training? | mn39, dn2 | mn65, mn70, mn107, an3.86, an8.20 | mn65, mn39, mn107, mn94, sn12.93-213 |
| qa_049 | Что такое самадхи? | an4.41, sn40.10 | an3.101, dn10, dn10, an11.11, dn10 | an4.41, an5.27, an10.6, dn10, dn10 |
| qa_050 | What is anatta? | sn22.59, mn22 | sn22.145, sn18.1, sn35.219-221, sn35.210-212, sn23.17 | sn22.59, sn22.145, snp1.8, sn22.16, sn23.17 |
| qa_053 | What is the role of generosity in spiritual progress? | an4.61, an5.36, an8.36 | an7.57, an8.50, an7.6, an5.31, sn2.23 | an7.6, an6.45, an5.31, an8.36, sn1.42 |
| qa_067 | What is dukkha-nirodha? | sn56.11, sn22.59, an3.61 | snp3.12, sn35.226, mn9, mn63, sn56.20 | sn56.11, sn56.11, mn9, snp3.12, an4.102 |
| qa_096 | dukkha samudaya nirodha magga | sn56.11, sn56.13 | sn56.32, sn38.1, mn31, sn45.157, dn16 | sn56.11, sn56.11, sn56.32, mn9, sn22.104 |
| qa_100 | paṭiccasamuppāda anuloma paṭiloma | sn12.1, sn12.2 | dn15, sn35.113, mn60, ud1.2, dn24 | dn15, sn35.113, an10.92, sn22.37, sn12.1 |

### Regressed (A found, B missed)

| id | query | expected | A top-5 | B top-5 |
|---|---|---|---|---|
| qa_031 | What is the Discourse to the Kalamas? | an3.65 | snp5.18, an7.53, an4.76, snp5.19, an3.65 | snp1.8, an4.139, dn13, snp2.1, snp5.1 |
| qa_036 | What is the simile of the cowherd? | mn33, mn34 | an11.22-29, ud4.3, mn34, dn23, an3.70 | dn23, an11.22-29, sn20.12, dn13, sn20.4 |
| qa_044 | What is the simile of the elephant's footprint? | mn28 | mn27, mn27, mn28, mn27, sn45.140 | mn27, sn45.140, mn27, sn3.17, sn48.54 |
| qa_029 | Что такое страдание в буддизме? | sn56.11, dn22, mn141 | sn35.67, mn103, mn141, mn103, snp3.12 | sn4.13, an5.137, sn35.67, sn1.6, sn38.14 |
| qa_082 | What is right concentration in detail? | mn117, an5.28, dn22 | an5.28, dn22, an7.45, an11.8, an5.27 | snp1.8, an10.138, sn12.55, sn22.23, sn47.20 |

---

Regenerate with `python scripts/eval_rag_day_32.py` 
(needs Qdrant + Postgres + GPU, ~2 min wallclock).
