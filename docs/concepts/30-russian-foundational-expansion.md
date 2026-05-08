# 30 — Russian foundational expansion: добавляем ключевые термины в curated map

> **Статус:** реализовано (rag-day-30, 2026-05-08).
> Малый день, в основном data-curation. Расширили `foundational.yaml`
> 5 новыми entries + 2 расширения существующих с русскими aliases.
> Live-битва: 6/6 регрессий + 4 новых русских PASS, 2 INFO (corpus-gap).

## Что это простыми словами

После rag-day-29 базовый механизм работает: пользователь пишет
`Что такое X?` на русском, foundational mapping ловит термин и
поднимает каноническую первосутру в #1. Но есть условие — **термин
должен быть в `foundational.yaml`**.

Пример. Сейчас работает:
- `Что такое сатипаттхана?` → mn10 #1 ✅ (entry есть)
- `Что такое анапанасати?` → mn118 #1 ✅
- `Что такое метта?` → пусто (snp1.8 нет в корпусе, отдельная задача)

А вот этого **в `foundational.yaml` нет**, поэтому фолбэк на обычный retrieval:
- `Что такое самадхи?` → dn10 (валидно, но не каноническая первосутра)
- `Что такое сила?` → ???
- `Что такое боджжанга?` → ???

В rag-day-30 мы выбираем 5-8 терминов, у которых есть **чёткий
канонический первоисточник в каноне Палийских сутт**, и добавляем
их в `foundational.yaml`. С богатыми русскими aliases чтобы Russian
definitional-запросы их находили.

## Зачем у нас

Из rag-day-26 failure analysis категория **E (Russian lexical)** —
2/15 промахов на русских запросах. После rag-day-29 один из них
(`випассана`) починился через alias `vipassana → [mn10, dn22]`.
Второй (`самадхи`) остаётся без foundational-entry.

Plus — стратегически: проект дальше переезжает в Yoniso, **русско-
языковая аудитория ключевая**. Чем больше Russian definitional-
кейсов работают «канонически», тем меньше дыр в demo'е. Sahaya
не делает для Russian — это наш differentiator (см. memory
`project_dharma_rag_yoniso_split.md`).

## Что добавляем

Кандидаты на новые entries (короткий список с обоснованием):

### 1. samādhi (концентрация, сосредоточение)

- **Канонический источник:** AN 4.41 — *Samādhibhāvanā Sutta*,
  «Развитие сосредоточения». Будда перечисляет четыре способа
  развития самадхи. Это «учебник по самадхи» в одной короткой сутре.
- **Русские aliases:** самадхи, сосредоточение, концентрация,
  медитативное погружение
- **English aliases:** concentration, samadhi, meditative absorption,
  development of concentration

### 2. sīla (нравственность, заповеди)

- **Канонический источник:** Можно — DN 31 (Sigālovāda — этика
  для мирянина), который **уже есть** в YAML под термином
  `lay ethics`. Просто **расширяем aliases** русскими формами
  (нравственность, шила).
- Альтернатива: AN 8.39 (восемь источников заслуги через нравственность).

### 3. bojjhanga (семь факторов пробуждения)

- **Канонический источник:** SN 46.3 (или SN 46.51 — анализ всех
  семи факторов). В саньютте SN 46 эта тема — основная.
- **Русские aliases:** боджжанга, факторы пробуждения,
  семь факторов просветления

### 4. iddhipāda (основы достижения сверхсил / целеустремлённости)

- **Канонический источник:** SN 51.13 (*Chanda Samādhi Sutta*) —
  объяснение четырёх iddhipāda через chanda/viriya/citta/vīmaṃsā +
  samādhi.
- **Русские aliases:** иддхипада, основы могущества, основы достижений
- **Уверенность ниже** — может пропустить, тема нишевая для definitional.

### 5. brahmavihāra (четыре божественных пребывания)

- **Канонический источник:** MN 40 (*Cūḷa-Assapura*) — но не
  чисто-brahmavihāra. Лучше **DN 13** (*Tevijja*) — три знания, путь
  к брахма-миру через четыре brahmavihāra. Или просто рассеяно по
  канону без one «first source».
- **Русские aliases:** брахмавихара, четыре безмерных,
  четыре божественных пребывания

### 6. tisaraṇa (три прибежища)

- **Канонический источник:** AN 6.10 (*Mahānāma Sutta*) — описание
  убежища Будда + Дхамма + Сангха в первой части.
- **Русские aliases:** трисарана, три прибежища, прибежище
- Использование: кто-то спрашивает «что такое прибежище?», система
  показывает каноническое описание.

### 7. paṭiccasamuppāda — расширение

Уже есть entry с aliases `paticcasamuppada / dependent origination /
взаимозависимое возникновение`. Добавим ещё `обусловленное
возникновение`, `12 нидан`, `двенадцать звеньев`.

### Итого

5-7 новых entries + 1 расширение существующего. ~30 минут curation,
тесты добавляются автоматически (battery already exists).

## Как работает (без изменения кода)

После rag-day-28 + 29 механизм такой:

```
   Russian query: "Что такое самадхи?"
                │
                ▼
       definitional regex matches
                │
                ▼
   FoundationalMatcher.match() ищет alias `самадхи`
   → находит entry { term: "samadhi", works: [an4.41], aliases: [...] }
                │
                ▼
   bm25_aliases() возвращает English aliases:
   ["concentration", "samadhi", "meditative absorption"]
                │
                ▼
   bm25_query: "Что такое самадхи? or concentration or samadhi or ..."
                │
                ▼
   BM25 находит chunks со словом "concentration" → many chunks of an4.41
                │
                ▼
   foundational_boost: an4.41 floor-to-top → an4.41 #1
```

**Никакого кода менять не надо.** Только данные в YAML.

## Альтернативы (что не делаем)

**1. Pāli glossary → BM25 bridge.**
Идея: автоматически использовать meanings из cyrillic.yaml как
BM25 aliases — ту же логику что rag-day-29, но шире. **Отвергнуто**
для rag-day-30: cyrillic.yaml имеет 155 entries, BM25 будет
получать слишком много aliases — увеличит false-positive ranking.
Curated mapping безопаснее. (Можем вернуться позже отдельным днём.)

**2. Машинный перевод EN→RU → автогенерация aliases.**
Risk: incorrect Russian terms (e.g. mindfulness → внимательность
vs памятование — есть выбор стилистический). Лучше курировать
руками.

**3. Загрузить русский корпус (theravada.ru или подобные).**
Большая задача (Phase 3 multi-source), не для дня curation.

**4. Расширять cyrillic.yaml.**
Уже 155 entries, покрытие хорошее. Не нужно.

## Что НЕ делаем в этом дне

- **Не правим код** — только YAML
- **Не загружаем новый корпус** (Khuddaka, Russian translations)
- **Не делаем sensitivity-sweep boost-фактора** (rag-day-32 еval)
- **Не добавляем редкие термины** (saraṇa-pāli, kasiṇa-objects) —
  они не definitional-target'ы

## Где в коде

| Файл | Что |
|---|---|
| `data/glossary/foundational.yaml` | +5-7 entries, +1 расширение |
| `tests/unit/expand/test_foundational.py` | +3-5 тестов на новые Russian aliases |
| docs/concepts/INDEX.md | Row для 30 |
| CHANGELOG.md / STATUS.md | Стандартная запись |

**Никаких изменений** в `src/expand/`, `src/rag/service.py`,
`src/retrieval/hybrid.py`. Это data-only день.

## Live-проверка (после implementation)

```
Что такое самадхи?     → an4.41 #1   (was: dn10)
Что такое нравственность? → dn31 #1  (lay ethics)
Что такое боджжанга?  → sn46.3 #1
Что такое прибежище?  → an6.10 #1
```

Регрессионная проверка — все ранее работавшие foundational кейсы
(satipaṭṭhāna, dukkha, anatta, dependent origination, anapanasati,
right view) остаются #1.

## Что выяснилось при live-проверке

При первой попытке `Что такое самадхи?` вернул `dn10`, а не `an4.41`.
Диагностика BM25 на `chunk.fts_vector`:

- `concentration` → 3 hits (Сужато использует слово редко)
- `samādhi` → 0 (`fts_vector` строится через `to_tsvector('simple', text_ascii_fold)`)
- `samadhi` → 264 hits, но **`an4.41` не в топ-10** (короткая сутра)
- `immersion` → **1 706 hits**, и `an4.41` поднимается в топ
- `ways of developing immersion` → `an4.41` #1

**Главный урок:** EN-aliases должны соответствовать **актуальным
переводческим решениям Сужато**, а не словарным эквивалентам.
Sujato переводит:

| Pāli | словарный EN | Sujato EN |
|---|---|---|
| samādhi | concentration | **immersion** |
| sīla | virtue / morality | **ethics** / Sigālaka (для DN 31) |
| bojjhaṅga | factors of awakening | **awakening factors** |
| brahmavihāra | divine abodes | **divine abodes** ✓ |
| iddhipāda | bases of psychic power | **bases of psychic power** ✓ |
| tisaraṇa | three refuges | **going for refuge** |

Поэтому YAML был обновлён: `samadhi.aliases` теперь содержит
`immersion`, `immersion further`, `ways of developing immersion`,
а `lay ethics.aliases` получило `sigalaka`, `advice to sigalaka`.

## Live-результаты

После двух итераций (первый прогон → диагностика → правка aliases →
повторный прогон) — 10/10 PASS на основной батарее, 2 INFO с
ожидаемым промахом:

```
PASS  sn56.11   What is dukkha?            #1=sn56.11
PASS  sn22.59   What is anatta?            #1=sn22.59
PASS  mn10      What is satipaṭṭhāna?      #1=mn10
PASS  sn12.2    What is dependent origination?  #1=sn12.2
PASS  mn118     What is anapanasati?       #1=mn118
PASS  mn117     What is right view?        #1=mn117
PASS  an4.41    Что такое самадхи?         #1=an4.41   ← rag-day-30
PASS  dn31      Что такое нравственность?  #1=dn31     ← rag-day-30
PASS  sn46.3    Что такое факторы пробуждения?  #1=sn46.3   ← rag-day-30
PASS  dn13      Что такое брахмавихара?    #1=dn13     ← rag-day-30
INFO  -         Что такое 12 нидан?        #1=an4.144  (corpus-gap)
INFO  -         Что такое три прибежища?   #1=sn40.10  (corpus-gap)
```

**Почему 12 нидан и три прибежища промахиваются:** matcher
сопоставляет термин с правильной канонической суттой (sn12.2 / an6.10),
но эта сутта **не попадает в pool из 100 кандидатов** через текущие
каналы retrieval — Russian-текст на dense-канале находит другие
сутты, а английские aliases (`12 links`, `three jewels`) дают 0
hits в теле Сужато. Boost-механизм работает только для works,
которые уже в pool. Эти случаи — кандидаты на app-day по русскому
корпусу (theravada.ru) или citation-verification.

## Связанные документы

- [docs/concepts/14 — Pāli глоссарий](14-pali-glossary.md) — cyrillic.yaml уже здесь
- [docs/concepts/28 — Definitional + foundational mapping](28-definitional-expansion.md)
- [docs/concepts/29 — BM25 translation bridge](29-bm25-translation-bridge.md) — механизм который активирует новые entries
- [docs/FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) — категория E (Russian lexical)
