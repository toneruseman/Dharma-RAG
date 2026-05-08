# 33 — Khuddaka Nikāya ingest: закрываем corpus-gap

> **Статус:** реализовано (rag-day-33, 2026-05-08).
> Загружаем 5-ю Nikāya — 754 файла, 1770 новых chunks. Закрывает
> long-standing gap rag-day-28: `metta → snp1.8` (Mettā Sutta) теперь
> поднимается на #1. Cumulative ref_hit@5 после rag-day-33: 0.450 →
> 0.520 (+7.0pp vs v0.1.0). MRR 0.307 → 0.395 (+0.088).

## Что это простыми словами

В Phase 1 (rag-day-04) загрузили 4 главных Nikāya: MN, DN, SN, AN —
~12K файлов. **Khuddaka Nikāya** (KN, «Малое собрание») — пятый
сборник, в нём verse-тексты и короткие истории — **намеренно
исключили** в Phase 1, потому что:

1. Verse-тексты короткие (Sutta Nipāta = 4-8 строк на сутру),
   parent/child chunker рассчитан на 1024-2048 токенов parent.
2. Jātaka — длинные нарративы, beletristics > doctrinal.
3. Phase 1 scope discipline.

В rag-day-33 закрываем этот gap. Verse-aware chunker всё ещё нужен
(rag-day-31 в backlog'е), но даже flat-chunking Khuddaka достаточно
чтобы ключевые сутры (snp1.8 metta, dhp короткие изречения)
попадали в retrieval-pool — где их подхватывает foundational boost
из rag-day-28.

## Что добавили

754 файла → 1770 chunks (1001 child + 769 parent). Распределение:

| Под-коллекция | Files | Что |
|---|---:|---|
| `kn/snp` | 73 | Sutta Nipāta — incl. snp1.8 Mettā Sutta |
| `kn/dhp` | 26 | Dhammapada — 423 verses в 26 главах |
| `kn/ud` | 80 | Udāna — inspired utterances |
| `kn/iti` | 112 | Itivuttaka |
| `kn/thag` | 264 | Theragāthā — verses of senior monks |
| `kn/thig` | 73 | Therīgāthā — verses of senior nuns |
| `kn/kp` | 9 | Khuddakapāṭha |
| `kn/ja` | 82 | Jātaka stories |
| `kn/cp` | 35 | Cariyāpiṭaka |
| **Total** | **754** | |

## Pipeline (без изменения кода)

```
1. ingest_sc.py --nikayas kn       → 754 files → 1770 chunks (Postgres)
                                     22s wallclock
2. (rechunk пропущен — idempotent skip, верс-тексты уже короткие)
3. contextualize_corpus.py          → 1001 children → 1001 contexts
                                     11 min wallclock, $1.36 (Haiku 3.5)
4. reindex_qdrant_v2.py             → 7479 points (incremental upsert)
                                     17 min wallclock, GPU 1080 Ti
```

Все три скрипта **idempotent** — re-run не дублирует. Контекстуализация
автоматически выбирает только pending children (где `context_text IS NULL`).

## Что выяснилось при verify

### snp1.8 Mettā Sutta — главный win

```
Q: What is loving-kindness?  → snp1.8 #1
Q: Что такое метта?           → snp1.8 #1
Q: Karaṇīya Mettā Sutta       → snp1.8 #1
```

Foundational entry `metta → snp1.8` существовал с rag-day-28, но
работа не была в pool кандидатов. Сейчас попадает — boost'ится и
поднимается. Пример того как **корпусная курация × retrieval
механизм** дают эффект.

### KN reachability проба

```
PASS  Verses of the Senior Monks   → thag1.1 #1
PASS  Verses of the Senior Nuns    → thig13.1 #1
PASS  Inspired Utterances          → ud7.4 #1
FAIL  Itivuttaka                   → mn35 (expected iti.*)
FAIL  Discourse on the Elephants   → an9.40 (expected dhp)
```

«Itivuttaka» — название Pāli-сборника, в body тексте не появляется
(Sujato переводит каждую sutta заголовком). «Discourse on the
Elephants» — Sujato использует это для AN 9.40 чаще чем для dhp 320-333.
Это не баги — естественные ограничения title-based search'а.

## Re-eval cumulative effect (rag-day-32 baseline)

После KN ingest re-run rag-day-32 eval (golden v0.0_extended n=100):

| Metric | A v0.1.0 baseline | B v0.2.0 stack pre-KN | B post-KN | Δ vs v0.1.0 |
|---|---:|---:|---:|---:|
| ref_hit@1 | 0.190 | 0.280 | **0.290** | **+10.0pp** |
| ref_hit@5 | 0.450 | 0.500 | **0.520** | **+7.0pp** |
| ref_hit@10 | 0.540 | 0.600 | 0.630 | +9.0pp |
| ref_hit@20 | 0.650 | 0.690 | 0.710 | +6.0pp |
| MRR | 0.307 | 0.378 | **0.395** | **+0.088** |

11 fixed / 5 regressed (было 9/4). Net +2 fixed от KN присутствия.

## Что НЕ сделали (отложено)

- **Verse-aware chunker** (rag-day-31). Сейчас все KN-тексты в одном
  chunk'е независимо от длины. Для коротких verse-collections
  (snp/thag/thig) это OK — целая sutta попадает целиком. Но
  Theragāthā с 264 файлами имеет на каждого theras несколько отдельных
  стихов — было бы лучше чанковать по логическим vagga (главам).
- **Pāli root в Instance параллельно EN.** Сейчас только Sujato EN.
  Phase 3 multi-source задача.
- **Dhammapada по главам.** Каждая глава = один файл (26 глав), но
  стихи внутри не разделены. Не критично пока — глава целиком
  retrievable.

## Стоимость

- **Контекстуализация**: $1.36 (Haiku 3.5 через OpenRouter, 1.16M
  input + 105K output tokens, ~31% cache-hit rate).
- **Хранилище**: ~7.5MB новых embeddings в Qdrant + ~5MB в Postgres
  text. Negligible.
- **GPU**: ~17 минут BGE-M3 fp16 на 1080 Ti для 7479 chunks (full
  re-encode — incremental, сам upsert по UUID).

Для сравнения, всю Phase 3 (ATI 25K + DhammaTalks 20K + 84000 10K +
theravada.ru 8K = ~63K chunks) на Haiku обойдётся ~$50-80; на
DeepSeek V4 — потенциально 5-10× меньше (см. memory
`project_dharma_rag_context_model_plan.md`).

## Где в коде

| Файл | Что |
|---|---|
| `scripts/ingest_sc.py` | (без изменений) ingest с `--nikayas kn` |
| `scripts/contextualize_corpus.py` | (без изменений) idempotent на pending children |
| `scripts/reindex_qdrant_v2.py` | (без изменений) idempotent UUID upsert |
| `scripts/smoke_kn.py` | новый — 11 KN reachability проб + 3 регрессии |
| `docs/EVAL_RAG_DAY_32.md` | re-generated после KN ingest'а |

## Связанные документы

- [docs/concepts/02 — FRBR корпусная модель](02-frbr-corpus-model.md)
- [docs/concepts/03 — Чанкинг parent/child](03-chunking-parent-child.md)
- [docs/concepts/11 — Contextual Retrieval](11-contextual-retrieval.md)
- [docs/concepts/28 — Definitional + foundational](28-definitional-expansion.md) — snp1.8 был corpus gap здесь
- [docs/concepts/32 — Cumulative re-eval](32-cumulative-eval.md) — methodology re-run на rag-day-33
- [docs/RELEASE_v0.2.0.md](../RELEASE_v0.2.0.md) — Khuddaka в roadmap'е (next up)
