# Ablation matrix — Phase 2 day-22 (synthetic golden v0.0-extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from
> ``golden_v0.0_extended.yaml`` (100 synthetic QA). Absolute quality
> claims require a buddhologist-curated v0.1 — see B-001 in
> ``docs/STATUS.md``. Deltas between configurations remain valid even
> on synthetic data; this is the use case the file was built for.

## Run metadata

- **Generated**: 2026-04-28T15:46:18+00:00
- **Git commit**: `3346dbd`
- **Golden set**: `docs\eval\golden_v0.0_extended.yaml` (version `0.0-synthetic-extended`, n=100)
- **top_k (eval)**: 20
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Headline — 8-cell matrix

| collection | rerank | expand | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR | latency_s | rerank_s |
|---|:--:|:--:|---:|---:|---:|---:|---:|---:|---:|
| v1 | — | — | 0.170 | 0.400 | 0.480 | 0.550 | 0.270 | 7.57 | 0.00 |
| v1 | — | ✓ | 0.170 | 0.400 | 0.480 | 0.550 | 0.270 | 6.26 | 0.00 |
| v1 | ✓ | — | 0.170 | 0.410 | 0.500 | 0.610 | 0.274 | 748.98 | 742.21 |
| v1 | ✓ | ✓ | 0.170 | 0.410 | 0.500 | 0.610 | 0.274 | 749.62 | 742.69 |
| v2 | — | — | 0.190 | 0.450 | 0.540 | 0.650 | 0.308 | 6.73 | 0.00 |
| v2 | — | ✓ | 0.190 | 0.450 | 0.540 | 0.650 | 0.308 | 6.53 | 0.00 |
| v2 | ✓ | — | 0.200 | 0.440 | 0.560 | 0.650 | 0.302 | 754.63 | 747.95 |
| v2 | ✓ | ✓ | 0.200 | 0.440 | 0.560 | 0.650 | 0.302 | 754.94 | 748.25 |

## Best configuration

- **Best on `ref_hit@5`**: `v2_norerank_child` (0.450)
- **Current production** (`v2_norerank_expand`): 0.450, Δ=+0.040 vs day-13 baseline (`v1_rerank_expand` 0.410)
- **Note**: a different cell (`v2_norerank_child`) outperforms current production. Consider the latency / cost tradeoff before changing defaults.

## Marginal effects (Δ on `ref_hit@5`)

Each row holds two of {collection, rerank, expand} fixed and reports the third.

### Effect of Contextual Retrieval (v1 → v2)

| rerank | expand | v1 ref_hit@5 | v2 ref_hit@5 | Δ |
|:--:|:--:|---:|---:|---:|
| — | — | 0.400 | 0.450 | +0.050 |
| — | ✓ | 0.400 | 0.450 | +0.050 |
| ✓ | — | 0.410 | 0.440 | +0.030 |
| ✓ | ✓ | 0.410 | 0.440 | +0.030 |

### Effect of cross-encoder reranker (off → on)

| collection | expand | no-rerank ref_hit@5 | rerank ref_hit@5 | Δ |
|:--:|:--:|---:|---:|---:|
| v1 | — | 0.400 | 0.410 | +0.010 |
| v1 | ✓ | 0.400 | 0.410 | +0.010 |
| v2 | — | 0.450 | 0.440 | -0.010 |
| v2 | ✓ | 0.450 | 0.440 | -0.010 |

### Effect of parent expansion (child → parent)

| collection | rerank | child-only ref_hit@5 | parent-expanded ref_hit@5 | Δ |
|:--:|:--:|---:|---:|---:|
| v1 | — | 0.400 | 0.400 | +0.000 |
| v1 | ✓ | 0.410 | 0.410 | +0.000 |
| v2 | — | 0.450 | 0.450 | +0.000 |
| v2 | ✓ | 0.440 | 0.440 | +0.000 |

## Production-best vs day-13 baseline — top-5 failure analysis (`v2_norerank_expand` vs `v1_rerank_expand`)

- Fixed by production: **14**
- Regressed: **10**

### Fixed (production found, baseline missed)

| id | query | expected | baseline top-5 | production top-5 |
|---|---|---|---|---|
| qa_002 | Where did the Buddha first teach the four noble truths? | sn56.11 | mn141, mn141, dn16, sn56.21, sn56.15 | an3.61, sn56.28, sn56.16, sn56.14, sn56.11 |
| qa_003 | What is the Mahāsatipaṭṭhāna Sutta about? | dn22 | sn6.5, mn133, an2.32-41, sn35.132, sn21.3 | mn133, mn84, mn84, dn22, mn18 |
| qa_046 | Who was Mahā Moggallāna? | mn37, sn40.1 | sn8.10, an6.34, an5.100, sn51.14, an7.56 | sn51.31, sn40.1, sn51.14, an6.34, an6.34 |
| qa_016 | What does the Buddha say about wealth? | an4.61, an4.62, dn31 | an5.41, an7.7, dn30, sn3.19, dn30 | dn31, an7.5, an7.7, an5.47, mn96 |
| qa_017 | Teachings about karma and its results | mn135, mn136, an3.34 | sn42.13, an10.188, sn42.13, an10.144, sn42.13 | mn135, mn136, mn57, an10.217, sn42.13 |
| qa_052 | Teachings on the four divine abidings | dn13, an4.125, sn46.54 | dn33, dn11, an4.165, an4.182, mn83 | dn33, sn55.35, an4.125, dn11, dn13 |
| qa_068 | How should a king rule justly? | dn26, an5.131 | an7.62, an5.133, sn4.20, mn83, dn30 | an5.133, dn26, an3.14, mn83, an7.62 |
| qa_075 | Teachings on the dangers of sensual pleasures | mn13, mn14, an5.7 | an6.23, an8.56, mn22, mn67, mn45 | an8.56, an6.23, an5.55, mn14, mn45 |
| qa_023 | What is nibbāna in the suttas? | sn43.14, ud8.1, ud8.3, an3.55 | an8.91-117, mn80, mn141, an8.48, sn5.9 | an9.34, an9.48, an3.55, sn38.1, mn24 |
| qa_025 | What is the role of faith in the Buddhist path? | an5.38, sn55.1, mn70 | an4.52, dn19, mn120, an11.14, sn48.44 | an5.32, an4.152, an5.38, mn70, an4.52 |
| qa_030 | Учение о четырёх благородных истинах | sn56.11, sn56.13, mn141 | sn56.29, sn56.27, sn56.23, sn56.28, sn56.26 | sn56.4, sn56.38, mn141, an10.148, sn56.27 |
| qa_076 | Did the Buddha approve of severe asceticism? | mn36, mn85, dn8 | mn13, dn21, mn117, sn22.50, an4.196 | an4.87, mn40, mn100, mn36, sn12.71 |
| qa_081 | Teachings on the conditioned vs the unconditioned | sn43.14, an3.47 | sn43.12, sn43.1, sn43.2, sn43.11, mn115 | sn43.12, an3.47, sn22.81, sn22.81, sn43.1 |
| qa_085 | Teachings on the cessation of perception and feeling | mn44, an9.32 | sn36.17, sn36.15, an5.166, dn14, sn28.9 | sn22.56, mn44, an6.63, dn9, sn41.6 |

### Regressed (baseline found, production missed)

| id | query | expected | baseline top-5 | production top-5 |
|---|---|---|---|---|
| qa_020 | Teachings on impermanence | sn22.59, sn22.45, sn35.1 | sn55.3, sn22.147, sn35.76, sn35.162, sn35.1 | an6.98, mn146, sn22.102, sn18.2, an7.16 |
| qa_070 | What is the difference between virtuous and unvirtuous conduct? | mn41 | an4.47, mn41, an10.75, an10.220, mn41 | an8.50, an4.229, sn2.21, an4.223, an8.49 |
| qa_072 | How does mindfulness develop concentration? | sn54.13, sn54.10, an6.115 | sn54.9, an8.73, sn54.13, an6.19, mn118 | dn22, an11.12, dn22, sn54.20, mn119 |
| qa_022 | Did the Buddha say there is a self? | sn44.10, mn22, sn22.59 | mn22, sn44.7, sn22.49, mn35, sn35.121 | mn12, sn35.121, an4.21, an4.8, mn102 |
| qa_077 | What is the relationship between consciousness and rebirth? | mn38, sn22.59, sn12.39 | sn55.28, dn15, an10.92, mn38, dn14 | sn12.64, sn12.38, dn15, dn34, sn12.65 |
| qa_083 | How does the Buddha respond to those who claim there is no self at all? | sn44.10, mn22, sn22.81 | sn22.82, mn22, mn109, sn22.71, sn22.91 | an4.8, mn12, mn8, mn12, sn22.49 |
| qa_084 | Is the Eightfold Path a sectarian dogma or universal? | dn16, an3.65, mn11 | dn19, dn8, dn16, dn6, sn45.180 | dn8, sn45.40, dn19, sn38.3, sn45.133 |
| qa_086 | How does the Buddha refute eternalism and annihilationism? | dn1, mn22, sn22.81 | dn28, mn22, sn42.9, an10.93, mn63 | dn28, dn2, sn6.4, an10.95, an3.61 |
| qa_088 | Teachings on supernormal powers | dn11, mn12, sn51.11 | sn51.19, dn28, mn12, an5.14, an10.21 | an6.64, an5.23, an3.101, sn51.27, sn51.28 |
| qa_095 | What is the simile of the moon? | sn16.3 | dn23, sn56.38, dn13, sn16.3, sn56.37 | sn45.146-148, an5.31, sn49.13-22, dn23, sn48.83-92 |

## Production-best breakdown (`v2_norerank_expand`)

### By difficulty

| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| easy | 30 | 0.233 | 0.567 | 0.600 | 0.700 | 0.381 |
| hard | 35 | 0.086 | 0.286 | 0.457 | 0.657 | 0.195 |
| medium | 35 | 0.257 | 0.514 | 0.571 | 0.600 | 0.359 |

### By language

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.209 | 0.473 | 0.560 | 0.681 | 0.330 |
| pli | 2 | 0.000 | 0.000 | 0.500 | 0.500 | 0.071 |
| ru | 7 | 0.000 | 0.286 | 0.286 | 0.286 | 0.095 |

---

Regenerate with `python scripts/eval_ablation_v0.0e.py` 
(needs Qdrant + Postgres + GPU, ~50 min wallclock).
