# 35 — Failure-driven curation: English titles + samatha-vipassana

> **Статус:** реализовано (rag-day-35, 2026-05-08).
> Закрываем 3 actionable retrieval-gap из failure analysis post-rag-day-34:
> Fire Sermon → SN 35.28, Vajirā chariot simile → SN 5.10, samatha-yānika
> vs vipassanā-yānika → AN 4.94 + SN 12.70. ref_hit@5 0.560 → 0.590
> (+3pp). Plus DeepSeek V4 Flash A/B (отвергнут — 30% null rate).

## Что это простыми словами

После rag-day-34 у нас осталось **12/100** провалов на synthetic golden
(было 24 в rag-day-26). Failure analysis показал:

- **9/12 — golden-narrow** (artifact synthetic-разметки, не реальный gap)
- **3/12 — actionable** через английские title-aliases в `foundational.yaml`

Это **самый дешёвый возможный fix**: 3 entries в YAML (~15 минут
кураторской работы), zero code change, **+3pp на @5, +0.030 MRR**.

Параллельно проверили DeepSeek V4 Flash как замену Haiku 3.5 для
Contextual Retrieval — отказались из-за 30% null rate.

## Что добавили

### 1. Fire Sermon → SN 35.28

Sujato переводит Ādittapariyāya Sutta как "All Burning". Запросы
типа `What is the Fire Sermon?` не находили sn35.28 — слово
`Fire Sermon` встречается 0 раз в body Sujato.

```yaml
- term: fire sermon
  aliases: [all burning, all is burning, ādittapariyāya, ...]
  works: [sn35.28]
  boost: 1.5
```

BM25 на `burning` → sn35.28 #1 (rank=1.9 vs second 0.6) — strong
signal через alias.

### 2. Simile of the Chariot → SN 5.10

Vajirā Therī's chariot simile (диалог с Mara, anatta proof: «колесница
называется по сборке частей»). **Distinct от MN 24** (Chariots at the
Ready — relay-chariot training metaphor).

```yaml
- term: simile of the chariot
  aliases: [chariot simile, vajirā, vajira, ваджира, with vajira, ...]
  works: [sn5.10]
  boost: 1.4
```

Disambiguation: alias `simile of the chariot` НЕ срабатывает на
"Chariots at the Ready" (MN 24 имеет другой текст title'а) — проверено
матчером.

### 3. samatha-yānika vs vipassanā-yānika → AN 4.94 + SN 12.70

Specific concept — **сравнение двух типов практиков** (calm-bound vs
insight-bound), не общая vipassana practice. Уже существует
`vipassana → mn10/dn22` для broad vipassana queries — этот entry
catches the **comparison**.

Sujato bridges:
- `samatha` → "internal serenity of heart"
- `vipassanā` → "higher wisdom of discernment of principles"

Susīma — interlocutor в SN 12.70.

```yaml
- term: samatha-yanika
  aliases:
    - samatha-yānika
    - vipassanā-yānika
    - susīma
    - internal serenity of heart
    - higher wisdom of discernment
    - calm and insight
    - serenity and insight
    - саматха-яника
    - випассана-яника
  works: [an4.94, sn12.70]
  boost: 1.3
```

## DeepSeek V4 Flash A/B — отвергнут

Параллельный эксперимент: попробовать заменить Haiku 3.5 (Contextual
Retrieval default) на DeepSeek V4 Flash для cost savings на Phase 3
ingest'ах (~63K chunks).

`scripts/compare_context_models.py --n 10` на mixed EN/RU sample.

**Качество** (когда DeepSeek успешен): **B лучше A** на 6/7 не-ERROR
кейсах:
- Точные sutta-titles (Asibandhakaputta Sutta, Loka Sutta, Bhava Sutta)
- Корректно следует prompt'у "omit Pāli title when uncertain"
- Конкретика (5 losses, 7 vows, 8 causes vs обобщения Haiku)
- Russian text handling работает

**Reliability катастрофа**: **3/10 (30%) DeepSeek вернул `content=None`**
— likely safety-filter или routing-issue OpenRouter. Plus 1 rate-limit
retry. Haiku — 10/10 success, 1 hallucination (puññakkhetta-out-of-context).

**Cost analysis** (extrapolation на ATI 25K chunks):
- Haiku 3.5: ~$34-50
- DeepSeek V4: ~$5-7 raw, ~$10-15 effective с retry overhead

**Decision**: остаётся `anthropic/claude-3.5-haiku`. Savings $20-40 не
окупают 30% retry rate на one-shot ingest. Возможные кандидаты на
будущий A/B: `deepseek/deepseek-chat-v3.1` (predecessor, доказан),
`google/gemini-2.5-flash`, `anthropic/claude-haiku-4-5`.

Полный отчёт A/B: `docs/EVAL_CONTEXT_MODELS.md`. Decision-record:
memory `project_dharma_rag_context_model_plan.md`.

## Re-eval cumulative effect

После rag-day-35 на golden v0.0_extended (n=100):

| Metric | A v0.1.0 baseline | B v0.2.0 stack (post-34) | B post-35 (now) | Δ vs v0.1.0 |
|---|---:|---:|---:|---:|
| ref_hit@1 | 0.190 | 0.360 | **0.390** | **+20.0 pp** |
| ref_hit@5 | 0.450 | 0.560 | **0.590** | **+14.0 pp** |
| ref_hit@10 | 0.540 | 0.680 | 0.710 | +17.0 pp |
| ref_hit@20 | 0.650 | 0.750 | 0.780 | +13.0 pp |
| MRR | 0.307 | 0.453 | **0.483** | **+0.176** |

12 fixed / 2 regressed at top-5 (was 9/2 post-34 → +3 fixed от 3 new
entries). Approaching plan target ref_hit@5 ≥ 0.60.

## Failure analysis takeaway

Главное открытие — **bottleneck не retrieval, а golden quality**. После
rag-day-28→35 RAG **уже находит правильную по теме сутту в 9/12 «провалов»**,
просто synthetic golden их не размечал. Authoritative buddhologist
golden v0.1 unblock'нет реальное измерение качества (B-001).

Подтверждается, что foundational.yaml curation подход работает: каждый
рассмотренный actionable case закрывается одним entry, 0 code changes,
~15 min curation, +1pp@5 на каждые 2-3 entries.

## Что НЕ сделали (отложено)

- **B-001 buddhologist outreach** — non-code task, отдельным шагом
- **ATI Thanissaro ingest** — Phase 3 multi-source, отложен до B-001
  (без authoritative golden эффект ATI не измерим)
- **Pāli root ingest** — добавляет cross-language retrieval, на текущем
  golden 100% pli queries уже passing
- **Verse-aware chunker** (rag-day-31) — verse cases уже не в worst-12

## Где в коде

| Файл | Что |
|---|---|
| `data/glossary/foundational.yaml` | +3 новых entries (fire sermon / chariot / samatha-yanika), 24 → 27 entries |
| `scripts/compare_context_models.py` | новый — A/B Contextual моделей on N random chunks |
| `scripts/eval_failure_analysis.py` | +`--full-stack` флаг для post-rag-day-34 анализа |
| `tests/unit/expand/test_foundational.py` | bump count check 24 → 27 |
| `docs/EVAL_CONTEXT_MODELS.md` | A/B Haiku vs DeepSeek (auto-gen, ~12KB) |
| `docs/EVAL_RAG_DAY_32.md` | regenerated post-rag-day-35 |

## Связанные документы

- [docs/concepts/26 — Failure analysis](26-failure-analysis.md) — methodology
- [docs/concepts/28 — Definitional + foundational](28-definitional-expansion.md)
- [docs/concepts/30 — Russian foundational](30-russian-foundational-expansion.md)
- [docs/concepts/32 — Cumulative re-eval](32-cumulative-eval.md)
- [docs/concepts/34 — Russian SC ingest](34-russian-sc-ingest.md)
- memory `project_dharma_rag_context_model_plan.md` — A/B результаты
