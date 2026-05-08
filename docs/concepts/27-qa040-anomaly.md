# 27 — qa_040 anomaly investigation (rag-day-27)

> **Статус:** реализовано в rag-day-27 (2026-05-06). Скрипт
> [scripts/investigate_qa040.py](../../scripts/investigate_qa040.py) +
> отчёт [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md).
> **Root cause найден** (multi-causal: H4 + H5 + H3); H1 опровергнута;
> generalisation подтверждена (sn56.11 / sn22.59 — same pattern;
> mn117 — exception). Recommendations пересмотрели приоритет
> rag-day-28+ в пользу definitional query expansion + foundational
> sutta mapping + BM25 diacritics fix.

> **GPU нужна.** BGE-M3 запускается на GPU для encoding ~5 вариантов
> запроса. Прогон ~30 секунд при свободной GTX 1080 Ti, ~2 минуты под
> Whisper-contention'ом. Сообщить заранее, чтобы освободить GPU от
> dharmaseed-транскрипции (см. memory `feedback_gpu_declaration.md`).

## Что это за день

**rag-day-27** — это **анализ-день**, как и rag-day-26, но
**ультра-узкий**. Если 26-й разбирал топ-10 худших запросов **в целом**
и категоризировал их в кластеры, то 27-й — это **deep-dive в одну
аномалию** из этого списка: **qa_040 «What is satipaṭṭhāna?»**.

> **аномалия (anomaly)** — здесь значит «случай, который выпадает из
> общей картины». Большинство failures из rag-day-26 укладываются в
> понятные категории (Pali bare-romanized, Russian lexical, multi-hop,
> и т.д.) — для них известно, **что фиксит**. qa_040 — выпавший
> из всех понятных категорий случай: запрос на нормальном английском
> с полной диакритикой, foundational термин, но retrieval промахивается.

**В этот день мы НЕ пишем фикс.** Мы только **диагностируем** причину:
запускаем диагностический скрипт, смотрим per-channel ranking,
читаем content чанков mn10 / dn22 в БД, формулируем root cause.
Output — план фикса для rag-day-28+, не сам фикс.

Аналогия — **врач-диагност**. Пациент жалуется на одну странную боль
(qa_040). Терапевт назначает анализы (диагностический скрипт),
смотрит результаты (per-channel ranks + chunk content), ставит
диагноз (root cause), пишет назначение (recommendations). **Лечение
— уже другая глава**, у другого врача.

## Что такое аномалия qa_040

Из [docs/FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md), категория **F —
definitional anomaly**:

| Поле | Значение |
|---|---|
| Query | «What is satipaṭṭhāna?» |
| Язык | English |
| Сложность | easy (definitional, single-canon) |
| Expected works | `mn10`, `dn22` (foundational сутры по сатипаттхане) |
| Retrieved top-5 | `sn47.3`, `sn47.18`, `sn52.2`, `sn47.14`, `sn47.34` |
| ref_rank (mn10) | глубже top-5 |
| ref_rank (dn22) | глубже top-5 |

> **foundational sutta** — «корневая», базовая сутра по теме. Для
> сатипаттханы это **MN 10 (Satipaṭṭhāna Sutta)** и **DN 22
> (Mahāsatipaṭṭhāna Sutta)** — две сутты, к которым отсылает любой
> учебник, любой учитель и любой комментарий, когда тема заходит про
> «mindfulness foundations». Sutta-saṃyutta `sn47` — это **отдельная
> книга** про ту же тему, но это «вторичный» материал: разные эпизоды,
> диалоги, расширения. Если пользователь спрашивает «what is
> satipaṭṭhāna?», эталонный ответ — отослать его к MN 10 / DN 22, не
> к сборнику эпизодов.

Что особенно странно — **на русском запросе из соседней QA встречается
обратная картина**:

| QA | Query | mn10 ref_rank | dn22 ref_rank |
|---|---|:---:|:---:|
| qa_040 | «What is satipaṭṭhāna?» (en) | глубоко | глубоко |
| qa_061 | «Что Будда говорит о медитации випассана?» (ru) | #4 | #3 |

То есть embedding **знает** mn10 и dn22 — на русском запросе они
выходят в топ-5. На английском буквальном термине foundational уровня
— нет.

Это «один кейс», но **foundational class**: если в нём нашёлся
системный баг — он может скрыто проседать на десятках других
definitional-запросов, которые мы пока **не заметили в golden** (потому
что у golden v0.0 покрытие узкое — n=100).

> **systemic bug** vs **isolated bug.** Разница принципиальная.
> Isolated — пациент один, лечим симптомом. Systemic — много пациентов
> с похожей этиологией, лечим причину, эффект на много кейсов сразу.
> Цель rag-day-27 — понять, какой это баг.

## Гипотезы (что мы будем проверять)

Ниже — пять гипотез, каждая с inline-расшифровкой жаргона. На каждую
есть **наблюдаемое следствие**, которое мы можем проверить
диагностическим скриптом.

### H1 — Contextual prefix drift

> **Contextual Retrieval (CR)** — техника из rag-day-15..17 (см.
> [11 — Contextual Retrieval](11-contextual-retrieval.md)). Перед
> ingest'ом каждый child-chunk обрабатывается LLM (Claude Haiku),
> которая дописывает к нему 50-100-токеновый префикс — **context_text** —
> объясняющий «где в документе эта цитата находится» и «о чём в
> большой картине». В embedding идёт уже `context_text + chunk_text`,
> не голый chunk.

> **child-chunk** — это маленький фрагмент сутты (~200 токенов), который
> мы реально кладём в Qdrant как embeddable unit. **Parent** — это
> большая «обёртка» (~1500 токенов) для UI; см.
> [12 — Parent/child retrieval](12-parent-child-retrieval.md).

**H1 говорит:** при rag-day-16 industrial run для каждого child-chunk'а
mn10 / dn22 LLM сгенерила context_text **обобщённо** — типа
«mindfulness practice», «awareness of body». Без буквального слова
«satipaṭṭhāna» в этом префиксе.

В sn47-чанках наоборот — каждый чанк начинается с заголовка типа
«Satipaṭṭhāna Saṃyutta: Konuto Sutta», и context_text это
повторяет. Embedding на запрос «satipaṭṭhāna» сильнее тянет к
sn47.x.

**Что проверим:** вытащим из БД `Chunk.context_text` для топ-5 child-
чанков mn10 и dn22, посмотрим — есть ли там буквально слово «satipaṭṭhāna».

### H2 — Chunk-level pollution

> **chunk-level pollution** (загрязнение на уровне чанка) — ситуация,
> когда retrieval возвращает технически правильный work, но **не тот
> чанк**. У сутты mn10 ~50 child-chunk'ов: «introduction», «выход в
> лес», «формула четырёх foundations», «contemplation of breath», и
> т.д. **Релевантные** — это формула + contemplation. **Generic** —
> introduction, epilog. Если retrieval возвращает только generic-фрагменты
> — `work_id=mn10`, но **в top-5 этого work_id может вообще не быть**,
> потому что более конкретные sn47-чанки обходят его по similarity.

**H2 говорит:** дело не в context_text, а в самих текстах child-чанков.
Чанки mn10 / dn22 которые **должны** «звенеть» на satipaṭṭhāna —
например, формула «cattāro satipaṭṭhānā... katame cattāro...» — могут
быть **не в первой пятёрке** по similarity, потому что они проигрывают
sn47-чанкам в **частоте слова** в маленьком окне.

**Что проверим:** прочитать `Chunk.text` (без context_text) топ-5 в
БД для mn10/dn22; посмотреть, насколько **термин-насыщенные** эти
чанки в сравнении с sn47.x.

### H3 — Foundational vs derivative bias

**H3 говорит:** проблема **архитектурная** в смысле «embedding-similarity
по определению**" не отличает foundational от derivative".** Sutta-
saṃyutta sn47 — это **сборник** (saṃyutta = «связанная коллекция»)
про сатипаттхану, в нём 50+ сутт, и **в каждой второй фразе термин
повторяется**. mn10 / dn22 — это **большие prose-сутты с подробным
пояснением практики**, в них термин в title и в ~3-5 ключевых местах,
а основная масса текста — пояснения, мета-наблюдения, переходы,
формулировки шагов.

> **derivative** — производный, расширяющий. sn47-сутры — это
> production-варианты на тему, заданную в mn10/dn22.

Когда такие чанки попадают в embedding-усреднение, **термин-плотные»
sn47-чанки получают преимущество** в similarity. Это математическая
особенность cosine similarity на short-context, не баг.

**Что проверим:** увидим ли это в per-channel breakdown — если **во
всех каналах** (dense, sparse, BM25) sn47.x обходит mn10/dn22 — это
H3.

### H4 — Per-channel split (RRF фьюзит «вниз»)

> **RRF (Reciprocal Rank Fusion)** — алгоритм, который усредняет три
> разных канала retrieval'а: dense (semantic), sparse (lexical), BM25
> (keyword) — см. [07 — RRF hybrid fusion](07-rrf-hybrid-fusion.md).
> Усреднение идёт **по rank'ам**, не по score'ам: дешевле, симметричнее,
> устойчивее к разности шкал. Минус — **если только один канал
> «прав»**, RRF его сглаживает: rank=1 в dense + rank=87 в sparse +
> rank=43 в BM25 → усреднённый rank ~30, и в final top-5 не попадёт.

> **per-channel rank** — позиция work'а в **каждом** канале по
> отдельности до RRF-усреднения. Например, мы можем увидеть: dense
> rank mn10 = 2 (близко!), а sparse rank = 250 (BM25 не находит
> вообще), и финальный RRF = 30. Это «канал-конфликт».

**H4 говорит:** возможно один из каналов **видит** mn10 / dn22 хорошо
(top-5), но другие два их хоронят, и RRF-fusion усредняет результат
до глубокого ранга.

**Что проверим:** распечатать per-channel rank mn10/dn22 для каждого
варианта query. Если dense=3, sparse=200, BM25=180, final=40 — это
H4. Решение — пересмотр weights / channel-balance в
[src/retrieval/rrf.py](../../src/retrieval/rrf.py).

### H5 — Query length / specificity

**H5 говорит:** «What is satipaṭṭhāna?» — это **4 токена**, очень
короткий запрос. BGE-M3 на коротких definitional queries имеет
известное смещение к **topical-spread**: вместо «найди мне точно про
этот термин» возвращает «всё, что **рядом** с этим термином в
embedding-пространстве». Длинная цитата с контекстом отрабатывает
лучше.

> **topical-spread** — embedding на короткий запрос как бы
> «расходится по топику», а не цепляется к конкретному термину.
> Поведение модели, не баг pipeline'а.

**Что проверим:** пробуем разные длины query — короткий, расширенный
(«What is the four foundations of mindfulness?»), descriptive
(«Mindfulness meditation in early Buddhism — what is it?»). Если на
длинных вариантах mn10/dn22 поднимаются в top-5 — это H5.

## Методология (3 шага)

### Шаг 1 — диагностический скрипт `scripts/investigate_qa040.py`

**One-off**, ~80-150 строк. Не production-код, не unit-тестируется.

Что делает (прозой):

1. **Берёт пять вариантов query** (потому что одна гипотеза проверяется
   через варьирование):
   - оригинал «What is satipaṭṭhāna?»
   - без диакритик «What is satipatthana?»
   - расширенный «What is the four foundations of mindfulness?»
   - русский «Что такое сатипаттхана?»
   - synonym «Mindfulness meditation in early Buddhism»

2. **Для каждого варианта вызывает hybrid_search** (из
   [src/retrieval/hybrid.py](../../src/retrieval/hybrid.py)) с
   параметрами: `top_k=20`, `rerank=False`, `expand_parents=True`,
   `collection_name="dharma_v2"` — это **production-конфиг**.

3. **Хитрость:** обычный `hybrid_search` возвращает уже **финальный**
   ranked list. Нам же нужны **per-channel ranks ДО RRF-fusion'а**.
   Скрипт либо хукается во внутрь функции через monkey-patching, либо
   вручную дёргает `dense_search`, `sparse_search`, `bm25_search`
   отдельно с тем же query, считает rank mn10 и dn22 в каждом
   списке.

4. **Печатает таблицу** в stdout — для каждого варианта и для каждого
   из mn10/dn22:

   ```
   === Variant: "What is satipaṭṭhāna?" ===
                  dense  sparse  BM25  RRF-final
   mn10            #12    #87    #45     #34
   dn22            #18    #110   #52     #41
   sn47.3          #1     #1     #2      #1
   ...
   ```

5. **Дополнительно** — выгружает **content** из БД для топ-5 child-
   чанков mn10 и dn22 (через прямой SQL `SELECT text, context_text
   FROM chunks WHERE work_id IN ('mn10', 'dn22') ORDER BY id LIMIT 5`),
   печатает первые ~300 символов каждого. Это нужно для H1/H2 (что
   реально ингествовано).

**Чего скрипт не делает:** не пишет в файл, не правит prod, не меняет
БД. Только stdout.

### Шаг 2 — manual analysis

Открываем stdout, смотрим. Логика разбора:

- Если **per-channel ranks везде глубокие** (dense, sparse, BM25 все
  показывают mn10/dn22 в #30+) → подтверждена **H3** (foundational
  bias). Все каналы согласны, что sn47.x «звучит больше про
  satipaṭṭhāna».
- Если **dense высокий (top-5), sparse/BM25 глубокие** → **H4**
  (channel-split). RRF тащит вниз правильный канал.
- Если **на расширенном query mn10/dn22 поднимаются** → **H5** (query
  length).
- Если **в context_text mn10/dn22 нет слова `satipaṭṭhāna`**, а в
  sn47.x — есть → **H1** (CR-prefix drift).
- Если **сами child-chunks mn10/dn22 — это intro/epilog без основной
  формулы** → **H2** (chunk-level pollution).

Гипотезы **не взаимоисключающие**: может быть смесь, например H1+H4
вместе.

### Шаг 3 — generalization check

Если найдена root cause — проверяем, **затрагивает ли она другие
foundational термины**. Прогоняем тот же diagnostic скрипт на:

- «What is dukkha?» → expected `sn56.11` (Dhammacakkappavattana —
  First Noble Truth foundational)
- «What is anatta?» → expected `sn22.59` (Anattalakkhaṇa) или `mn22`
- «What is Right View?» → expected `mn117` (Mahācattārīsaka) или `mn41`

Если на них видим тот же паттерн (foundational не в top-5, derivative
выше) — **H3 / H1 systemic**, фикс затронет много скрытых failures.
Если только qa_040 — **isolated**, фикс точечный.

### Шаг 4 — recommendations

Output идёт в **новый документ**
[docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md). Структура:

1. **Краткая постановка задачи** (1 параграф).
2. **Per-channel breakdown table** — для каждого варианта query.
3. **Chunk-content samples** — что лежит в БД для топ-5 mn10/dn22.
4. **Diagnosis** — какая гипотеза подтвердилась (или микс).
5. **Generalization check** — эффект на другие foundational термины.
6. **Fix recommendations** с приоритетом, в формате таблицы:

| Если подтвердилась | Recommended fix | Priority | Day |
|---|---|---|---|
| H1 (CR-prefix drift) | Re-run Contextual Retrieval с новым prompt'ом, явно учитывающим foundational role в meta-context. Не дешёво (~$150 на rerun, ~6 часов compute) | **High если systemic, Medium если isolated** | rag-day-29+ |
| H2 (chunk-level pollution) | Audit chunking границ для mn10/dn22; пересмотр child-size; metadata-boost для центральных секций | Medium | rag-day-30+ |
| H3 (foundational bias) | Добавить `is_foundational: true` flag в metadata sutta; при ranking — boost. Расширить `data/foundational_works.yaml` | **High если systemic** | rag-day-29 |
| H4 (RRF channel-split) | Пересмотреть weights в `src/retrieval/rrf.py`; A/B на golden | Medium | rag-day-29 |
| H5 (query length) | Query expansion для коротких definitional queries: «What is X?» → «What is X? Definition, foundations, central teaching» | Low (не критично) | rag-day-30+ |

## Что мы НЕ делаем в этом дне

- **Не фиксим** root cause. Этот день — diagnosis only.
- **Не запускаем re-ingest** Contextual Retrieval. Это дорого (~$150
  + 6h compute), и это **результат** анализа, не его метод.
- **Не меняем prompt** Contextual Retrieval'а. Тоже — следствие.
- **Не расширяем golden set**. Мы и так работаем на одном QA + 3
  generalization-кейсах.
- **Не правим src/retrieval/**. Скрипт — read-only, дёргает существующие
  функции.
- **Не дообучаем** ни embedding, ни reranker.
- **Не меняем production config**. Анализируем именно её
  (`dharma_v2 + rerank=False + expand_parents=True`).

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| [scripts/investigate_qa040.py](../../scripts/investigate_qa040.py) | новый | one-off диагностический скрипт, ~80–150 строк |
| [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md) | новый | результат анализа: per-channel breakdown + diagnosis + recommendations |
| [docs/STATUS.md](../STATUS.md) | обновлён | rag-day-27 → ✅ Done после merge'а |
| [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) | возможно изменён | если diagnosis перетряхнёт priority дней 28+ |
| `src/retrieval/*.py` | **не изменяется** | day строго read-only по коду |
| `src/api/*.py` | **не изменяется** | — |
| `data/glossary/*.yaml` | **не изменяется** | — |

## Тесты

Для скрипта **unit-тесты не пишем** — он one-off, manual analysis,
не production code (см. концепт 26, тот же принцип).

> **one-off скрипт** — утилита для одно-двух запусков. Не покрывается
> тестами, не интегрируется в CI. Если придётся запускать регулярно —
> переписать как нормальный модуль с тестами.

Smoke-проверка:

- `scripts/investigate_qa040.py` запускается без ошибок;
- stdout содержит per-channel rank table для всех 5 вариантов query;
- chunk-content sample секция непустая.

## Как проверить локально

PowerShell single-line с активацией venv (см. memory
`feedback_powershell_terminal.md`):

```
.venv\Scripts\python.exe scripts/investigate_qa040.py > tmp/qa040_investigation_raw.txt
```

После — вручную:

1. Открыть `tmp/qa040_investigation_raw.txt`.
2. Найти per-channel rank table — посмотреть, **где** mn10/dn22.
3. Прочитать chunk-content sample — есть ли в `context_text` слово
   «satipaṭṭhāna».
4. Сопоставить с гипотезами H1–H5 (см. секцию выше).
5. Перенести diagnosis + recommendations в
   `docs/QA040_INVESTIGATION.md`.

> **Опционально:** если на основном qa_040 диагноз неоднозначный,
> расширить скрипт generalization-check'ом — добавить «What is
> dukkha?», «What is anatta?», «What is Right View?» к списку
> вариантов. Потребует ещё ~30 секунд GPU.

## Связанные документы

- [09 — Eval и golden set](09-eval-and-golden-set.md) — как устроен
  golden, ref_hit@K, MRR
- [11 — Contextual Retrieval](11-contextual-retrieval.md) — что такое
  context_text, как он генерируется (ключевое для H1)
- [12 — Parent/child retrieval](12-parent-child-retrieval.md) — child-
  chunk vs parent, expand_parents=True
- [14 — Pāli глоссарий](14-pali-glossary.md) — query expansion для
  термина satipaṭṭhāna; уже частично в работе
- [26 — Retrieval failure analysis](26-failure-analysis.md) —
  родительский анализ-день, из которого qa_040 выделена как **F:
  definitional anomaly**
- [docs/FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) — таблица failure
  modes, см. строку qa_040 (категория F)
- [docs/EVAL_ABLATION_v0.0e.md](../EVAL_ABLATION_v0.0e.md) — текущая
  baseline для контекста (`ref_hit@5 = 0.450`)

## Открытые вопросы для ревью

1. **Generalization check — обязателен в этом же дне или отложить?**
   План говорит «обязателен», но на практике если диагностика qa_040
   уже занимает 2-3 часа manual analysis, generalization можно
   вынести в **первый час rag-day-28** перед фиксом. Экономит время,
   но риск — фикс уйдёт без понимания systemic-эффекта. **Default:
   делаем в этом дне.**

2. **Если ВСЕ гипотезы частично подтвердились?** Возможно, qa_040 —
   это «multi-causal» случай: H1 + H3 одновременно. Тогда recommendations
   будут **множественные**, и приоритет фиксов нужно дополнительно
   ранжировать по cheap-wins (что дешевле).

3. **Стоит ли смотреть `dharma_v1` коллекцию (без CR) для контраста?**
   Если на dharma_v1 (raw embeddings без context_text) qa_040 работает
   лучше — это **сильный сигнал H1**. Если хуже — H1 отпадает. Это
   ~5 секунд дополнительно к diagnostic скрипту, стоит включить.

4. **Что с per-channel rank на сильно разных weights?** RRF имеет
   tunable parameter `k=60` (smoothing constant). Стоит ли в скрипте
   попробовать `k=10` и `k=120` — увидеть, sensitive ли ranking? Это
   относится больше к H4. **Default: пробуем только default `k=60`,
   tuning — отдельный rag-day.**
