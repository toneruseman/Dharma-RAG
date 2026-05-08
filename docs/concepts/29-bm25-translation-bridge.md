# 29 — BM25 translation bridge: соединить английский перевод с pāli-запросом

> **Статус:** реализовано (rag-day-29 closed 2026-05-08).
> Закрывает 2 из 3 промахов rag-day-28 (`dukkha→sn56.11`,
> `anatta→sn22.59`). Третий — `metta→snp1.8` — корпусная задача
> (Khuddaka Nikāya не загружена), не лечится retrieval'ом.

## Что это простыми словами

Пользователь спрашивает «**What is dukkha?**». Это слово на pāli.
Но в нашем корпусе sutta-тексты переведены Sujato на английский,
и слово `dukkha` он почти везде заменил на `suffering`. Поэтому
**в body-тексте** sutta SN 56.11 (Dhammacakkappavattana — Первая
проповедь, базовый текст про четыре истины и страдание) **слова
`dukkha` нет вообще**.

Когда пользователь пишет `dukkha`, наш BM25-канал
(словесно-точный поиск через Postgres) не находит ни одного
chunk'а с таким словом. SN 56.11 невидим для retrieval'а
несмотря на то что это **именно та сутта** про которую
спрашивают.

**Что делает rag-day-29:** когда foundational-mapping ловит
«это про dukkha», мы расширяем BM25-запрос английскими алиасами
из словаря: `dukkha or "4 noble truths" or suffering`. Теперь
BM25 ищет любой из этих терминов. SN 56.11 находится мгновенно —
там полно слов «suffering» и «noble truths».

## Зачем у нас

После rag-day-28 (definitional + foundational mapping) **3 из 6
английских foundational-кейсов остались провалены**:

| Запрос | Ожидаем | До rag-day-29 | Причина |
|---|---|---|---|
| What is dukkha? | sn56.11 | mn9, an4.x, ... | body на английском, нет слова `dukkha` |
| What is anatta? | sn22.59 | sn22.145, sn22.16 | body на английском, нет `anatta` |
| Что такое метта? | snp1.8 | an11.15, sn42.13 | **самой sn-pi.1.8 нет в корпусе** |

**Диагностика** (sub-agent смотрел на чанки в Postgres):
- В корпусе только английские переводы Sujato (3413 expressions, все `language_code='eng'`)
- `dukkha`, `anatta`, `metta` встречаются **0 раз** в `chunk.text`
- Зато `suffering` находит sn56.11 на BM25 #1, `not-self` — sn22.59 на #3

Решение — прокинуть английские алиасы в BM25-запрос. Foundational
mapping уже знает синонимы: каждая запись в YAML имеет поле
`aliases`, в котором сидит и `dukkha`, и `suffering`, и
`дуккха`. Берём английские (не pāli, не cyrillic) — отдаём BM25.

> **Почему snp1.8 не лечится этим фиксом.** В корпусе вообще
> нет ни одного работа из Khuddaka Nikāya (snp/kp/dhp/thig/thag/ud/iti).
> Хоть какой запрос — нечего находить. Это **загрузка корпуса**,
> отдельная задача (см. backlog).

## Как работает

### Поток запроса

```
   user: "What is dukkha?"
              │
              ▼
   ┌──────────────────────┐
   │ definitional rewrite │  rag-day-28
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Pāli expansion       │  rag-day-23
   └──────────┬───────────┘
              │ 
              │ encoded_query → dense + sparse каналы
              │ raw query     → BM25 канал
              │
   ┌──────────┼──────────────────┐
   ▼          ▼                  ▼
 dense      sparse              BM25
   │          │                  │
   │          │   ← rag-day-29: bm25_query расширяется до:
   │          │     "What is dukkha? or 4 noble truths or suffering"
   │          │     (берём aliases из foundational.yaml)
   │          │                  │
   └──────────┼──────────────────┘
              ▼
        RRF fusion (top-100)
              │
              ▼
   ┌──────────────────────┐
   │ foundational boost   │  ← rag-day-29: floor-to-top
   │  rrf_score *= boost  │     гарантирует sn56.11 #1
   │  + floor at top      │
   └──────────────────────┘
```

### Два изменения в коде

**1. Метод `FoundationalMatcher.bm25_aliases(query)`** — выдаёт
английские aliases из matched-entries:

```python
# для запроса "What is dukkha?" возвращает:
['4 noble truths', 'dukkha', 'suffering']
```

Фильтр пропускает: cyrillic-алиасы, pāli-варианты того же
слова (типа `satipatthana` для `satipaṭṭhāna` — они уже
покрываются ASCII-fold'ом). Кепаем максимум 3 алиаса чтобы
BM25-запрос не разросся.

**2. В `RAGService.query()`** строим `bm25_query`:

```python
bm25_query = "What is dukkha? or \"4 noble truths\" or suffering"
```

И отдаём отдельным параметром в `hybrid_search`. Encoder-стороне
по-прежнему уходит длинный gloss-template, BM25-стороне — раздутый
запрос с английскими синонимами.

### Третье изменение: floor-to-top boost

На реальном стеке мы обнаружили что **умножения rrf_score на 1.5
недостаточно**. Если sn56.11 имеет сигнал только в одном канале
(BM25), её `rrf_score` ~0.013. Умножаем на 1.5 → 0.020. А топ
(mn9) — 0.048. sn56.11 всё равно где-то в середине.

**Floor-to-top:** для matched foundational works ставим **полку**
на уровне `top_original * boost`. То есть foundational-сутта
гарантированно поднимается в один ряд с топом, не ниже.

```python
new_score = max(
    rrf_score * boost,           # обычный multiplicative bump
    top_original_score * boost,  # пол: не ниже топа
)
```

Если foundational уже была близко к топу — multiplicative выигрывает.
Если она была глубоко — пол держит её на верху. **Curatorial
intent**: «когда юзер спрашивает про dukkha — sn56.11 ВИДНА
в выдаче», а не «может быть слегка приподнята».

### Пример до/после

**Запрос:** `What is dukkha?`

**До rag-day-29 (только rag-day-28 boost):**
| # | Work | rrf_score |
|---|---|---|
| 1 | mn9 | 0.048 |
| 2 | an4.104 | 0.034 |
| ... | ... | ... |
| 31 | sn56.11 | 0.014 (1.5x = 0.020) |

**После rag-day-29 (BM25 aliases + floor):**
| # | Work | rrf_score |
|---|---|---|
| 1 | **sn56.11** | 0.072 (floor: 0.048 × 1.5) |
| 2 | sn56.11 | 0.072 (тот же work, второй chunk) |
| 3 | mn9 | 0.048 |
| 4 | an4.104 | 0.034 |

## Альтернативы (что отвергли)

**1. `unaccent` Postgres extension.**
Был первый план. Но `to_ascii_fold()` уже делает то же — нормализует
диакритику симметрично на индексе и запросе. Проблема не в
диакритике, а в **переводе**: Sujato меняет pāli → английский.
`unaccent` это не лечит.

**2. Хардкодить большой boost (e.g. 5x вместо 1.5x).**
Может перестать работать на других запросах. Floor-to-top
безопаснее: foundational всегда не ниже топа, не выше топа на
random коэффициент.

**3. Включать title/canonical_id в FTS-vector.**
Помогло бы только когда юзер пишет `Dhammacakkappavattana` или
`sn56.11` напрямую. Никто так не пишет. Узкое решение, не основной gap.

**4. Re-ingest с pāli-Instance параллельно к английскому.**
SuttaCentral раздаёт pāli root-text. Загрузить его как отдельный
Instance дало бы full pāli-token coverage. **Большая работа** —
~50k chunks × encoder = ~6 ч GPU + storage. Отложено в Phase 3.
Текущий fix — query-side рerwrite, дешёвый.

## Что НЕ делаем в rag-day-29

- **Не загружаем Khuddaka Nikāya** — это решает только snp1.8/dhp/etc.
  Отдельная задача `corpus-loader: khuddaka` в backlog'е.
- **Не правим `to_ascii_fold`** — он работает корректно.
- **Не добавляем new FTS config** — `simple` config хватает после
  alias-расширения.
- **Не правим Phoenix span'ы** — boost-span от rag-day-28 уже логирует
  `before/after`.

## Где в коде

| Файл | Что | Тип |
|---|---|---|
| `src/expand/foundational.py` | `bm25_aliases(query)` метод + `_looks_pali_term()` helper | новые публичные API |
| `src/expand/foundational.py` | `apply_boost` floor-to-top semantics | изменена логика |
| `src/rag/service.py` | wire `bm25_query` сборку из aliases | вкручено в pipeline |
| `tests/unit/expand/test_foundational.py` | 7 новых тестов на bm25_aliases + 2 на floor | расширены |
| [docs/concepts/06 — Postgres FTS / BM25](06-postgres-fts-bm25.md) | базовый канал | смежный |
| [docs/concepts/27 — qa_040 anomaly](27-qa040-anomaly.md) | анализ дал план recommendation 3 | предшественник |
| [docs/concepts/28 — definitional + foundational](28-definitional-expansion.md) | foundational mapping без BM25-bridge | предшественник |

## Live-результат на real-стеке

| Запрос | Top-1 | Status |
|---|---|---|
| What is dukkha? | **sn56.11** | ✅ FIXED (был mn9) |
| What is anatta? | **sn22.59** | ✅ FIXED (был sn22.145) |
| What is satipaṭṭhāna? | mn10 | ✅ (rag-day-28 уже работал) |
| What is dependent origination? | sn12.2 | ✅ |
| What is anapanasati? | mn118 | ✅ |
| What is right view? | mn117 | ✅ |
| Что такое метта? | an11.15 | ❌ — snp1.8 не в корпусе (Khuddaka gap) |
| How do I work with anger? | an7.64 (`defn0-fnd0`) | ✅ no false positive |

**6/7 foundational-кейсов в #1.** Седьмой — корпусная задача.

## Связанные документы

- [docs/concepts/27 — qa_040 anomaly](27-qa040-anomaly.md) — анализ который вёл к этому фиксу
- [docs/concepts/28 — definitional + foundational](28-definitional-expansion.md) — без 29 был неполный
- [docs/concepts/06 — Postgres FTS / BM25](06-postgres-fts-bm25.md) — базовый канал
- [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md) — recommendation 3
- backlog: `corpus-loader: Khuddaka Nikāya` — для snp1.8 / dhammapada / udāna
