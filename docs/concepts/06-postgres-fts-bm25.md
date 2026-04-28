# 06 — Postgres FTS / BM25

## Что это

**BM25** = «Best Match 25» — классический алгоритм лексического поиска
из 1990-х. Расшифровывает: «насколько релевантен документ запросу,
если учитывать **какие** слова в нём есть и **насколько они редкие**».

Простой принцип: если редкое слово (например, `Anāthapiṇḍika`)
встречается в документе А много раз, а в документе Б один раз — **А
релевантнее**. Если слово часто встречается во всём корпусе (например,
`buddha`) — оно даёт меньше сигнала.

**FTS** (Full-Text Search) — это **встроенная поисковая подсистема в
Postgres**. Использует BM25-подобный алгоритм `ts_rank_cd` для
оценки релевантности. Никакого внешнего сервиса не нужно — всё уже
есть в Postgres.

## Зачем у нас

Уже есть BGE-M3 dense и sparse — зачем третий канал?

**BGE-M3 sparse** работает на BPE-токенах (subword pieces). `satipaṭṭhāna`
он режет в `[sat, ##ip, ##aṭ, ##ṭ, ##hāna]` и ищет совпадения по
кускам. Если запрос `satipaṭṭhāna` — ловит. Если запрос
`Anāthapiṇḍika` (имя, которого почти нет в обучающих данных) — теряется.

**BM25 на целых словах** рассматривает `Anāthapiṇḍika` как один токен
с очень высокой IDF (rare word). Точное вхождение даёт высокий ранг.

Они **дополняют друг друга**, не дублируют. См. эксперименты дня 11
в `docs/RELEASE_v0.0.3.md`.

## Как работает

### tsvector — индексируемая структура

Postgres превращает текст в `tsvector` — список нормализованных
токенов с позициями:

```
"At Sāvatthī the Buddha taught."
  ↓ to_tsvector('simple', text_ascii_fold)
'at':1 'savatthi':2 'the':3 'buddha':4 'taught':5
```

**ASCII fold:** `Sāvatthī` → `Savatthi` → `savatthi`. Делаем это в
day-6 cleaner и индексируем по `text_ascii_fold` колонке. Так запрос
`savatthi` и `Sāvatthī` дают идентичный результат.

### Generated stored column

В миграции 003 мы добавили колонку, которую **Postgres сам считает**
при INSERT/UPDATE:

```sql
ALTER TABLE chunk
ADD COLUMN fts_vector tsvector
GENERATED ALWAYS AS (
    to_tsvector('simple', COALESCE(text_ascii_fold, ''))
) STORED;
```

Никаких триггеров, никакого ручного maintenance — Postgres сам
синхронизирует.

### GIN индекс

```sql
CREATE INDEX ix_chunk_fts_vector ON chunk USING gin(fts_vector);
```

**GIN** = Generalized Inverted iNdex. Это «наоборот»: вместо «строка
→ её токены» хранится «токен → строки, в которых он есть». Поиск по
любому токену становится O(log N).

### Запрос

```sql
SELECT *, ts_rank_cd(fts_vector, query) AS score
FROM chunk, websearch_to_tsquery('simple', 'four noble truths') AS query
WHERE fts_vector @@ query
  AND is_parent = false
ORDER BY score DESC
LIMIT 30;
```

`@@` — оператор «совпадает с tsquery». `ts_rank_cd` — cover-density
ранкинг (BM25-подобный).

## Конфиг `simple` vs `english`

Postgres FTS поддерживает **text-search configurations** — правила
токенизации + словарь стеммера.

| Config | Что делает | Подходит ли нам |
|---|---|---|
| `english` | Lowercase + split + **English stemmer** + stopwords | ❌ ломает Pāli |
| `simple` | Lowercase + split, **без стемминга** | ✅ выбрали |

`english` стеммер сделал бы `breathings` → `breath`. Полезно для
английского. Но он же может сделать `satipatthana` → `satipatthan`
(удалит «-a» как окончание множественного числа в английском —
эвристика). Pāli ломается непредсказуемо.

`simple` — токенизация и lowercase, **никаких словарей**. Pāli
остаётся как есть, английский остаётся как есть. Стемминг (английских
форм breathings/breath) делает за нас dense BGE-M3 — у него семантика
встроена.

## Известное ограничение нашего корпуса

**Sujato переводит большинство Pāli терминов в английский.**
`satipaṭṭhāna` в его переводе — это **«Mindfulness Meditation»**.
Поэтому BM25 на запрос `satipaṭṭhāna` возвращает **0 hits** — слова в
тексте просто нет.

Что **есть** в тексте Sujato и что BM25 ловит хорошо:

- ✅ Имена собственные: `Anāthapiṇḍika`, `Sāvatthī`, `Gotama`,
  `Ānanda`, `Bhaddā`
- ✅ Английская терминология: `noble eightfold path`, `four noble truths`,
  `mindfulness meditation`
- ✅ Места: `Kuru`, `Kammāsadamma`, `Jeta's Grove`
- ❌ Pāli догматические термины: `satipaṭṭhāna`, `anāpānassati`, `dukkha`

Этот gap закроет день 16 (Contextual Retrieval добавит Pāli uid +
title в эмбеддинг) и будущая многопереводчиковая ingestion (Bodhi,
Thanissaro оставляют Pāli транслитерацией).

## Альтернативы

- **`rank-bm25` библиотека** + pickle всего корпуса в памяти —
  отбросили: дубль БД, не масштабируется, нельзя фильтровать по
  metadata.
- **Elasticsearch / OpenSearch** — отбросили: отдельный сервис, JVM,
  большой docker-образ для одной фичи.
- **Lucene напрямую** — отбросили: Java-стек.
- **`pg_trgm`** (триграммы Postgres) — отбросили: для длинных
  технических терминов (Anāthapiṇḍika) триграммы шумят.

Postgres FTS = ноль новых сервисов, проверенный годами, GIN-индекс
быстрее любой Python-обёртки.

## Где в коде

- Миграция: [alembic/versions/20260423_003_chunk_fts_vector.py](../../alembic/versions/20260423_003_chunk_fts_vector.py)
- Wrapper: [src/retrieval/bm25.py](../../src/retrieval/bm25.py)
- Smoke test (10 запросов): [scripts/smoke_bm25.py](../../scripts/smoke_bm25.py)
