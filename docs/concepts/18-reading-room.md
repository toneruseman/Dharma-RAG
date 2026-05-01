# 18 — Reading Room MVP (app-day-21)

> **Статус:** реализовано в app-day-21 как MVP. Самый минимум — чтобы
> по `[mn10]` из ответа чата можно было кликнуть и **прочитать всю
> сутту целиком**. Outline (оглавление сбоку), hover-glossary
> (всплывающие пояснения палийских терминов), bookmarks (закладки),
> highlights (подсветка маркером) и split-view (две колонки с
> параллельными переводами) — отдельные дни в плане (app-day-22..30).

## Зачем

До этого дня в системе было два API:

- `POST /api/query` — поиск по релевантности, возвращает top-k
  кусочков текста (snippet'ов).
- `POST /api/answer` — ответ LLM с цитатами в скобках типа `[mn10]`.

Проблема: пользователь читает ответ модели, видит ссылку на `[mn10]`
(Сатипаттхана-сутту) — а **открыть и прочитать её целиком негде**.
Клик в никуда. Это противоречит главной философии проекта: «**тексты
первичны, AI вторичен**». Пользователь должен иметь возможность
проверить ответ модели, сверившись с оригинальным переводом.

Аналогия: представь книжный обзор, в котором автор пишет «как
показывает Достоевский в "Идиоте"...» — и нет никакой возможности
открыть саму книгу. Только пересказ. Доверять такому пересказу
сложно. **Reading Room** — это «открытая библиотека» рядом с
обзором: любую упомянутую книгу можно взять с полки и прочитать
полностью.

Reading Room — главный surface проекта (surface = «поверхность
взаимодействия», основной экран, через который пользователь
работает с продуктом). MVP закрывает «нулевую» функцию:
показать полный документ по его идентификатору.

## Что такое Reading Room и FRBR — простыми словами

**Reading Room** — страница `/read/{id}`, где пользователь читает
полный текст одной сутты с правильной типографикой и метаданными
о переводе.

**FRBR** (Functional Requirements for Bibliographic Records) — это
модель из библиотечного дела для описания изданий. У нас она —
четырёхуровневая «многослойная карточка каталога»:

- **Work** — абстрактная «работа», идея текста как такового.
  Например, MN10 = «Сутта об основах внимательности» как замысел
  Будды. Не привязана ни к языку, ни к переводчику.
- **Expression** — конкретная реализация Work в виде перевода.
  «Бхиккху Суджато, английский, 2018» — это одна Expression.
  «Бхиккху Бодхи, английский, 1995» — другая. Та же Work, разные
  Expressions.
- **Instance** — физическая копия конкретной Expression. HTML-файл
  с SuttaCentral, скачанный на дату `2025-06-15` — это одна
  Instance. Если SuttaCentral поправит опечатку и мы пере-скачаем
  файл — это новая Instance.
- **Chunk** — фрагмент Instance, нарезанный для поиска (~200-400
  слов). По нему ходит retrieval (поиск релевантных кусков из
  большого корпуса; «достать карточки из библиотечного каталога»).

Аналогия библиотечной карточки:

```
Work:       «Война и мир» Толстого              ← идея
  ↓
Expression: перевод на английский Pevear/Volokhonsky 2007  ← перевод
  ↓
Instance:   издание Knopf 2008, ISBN 978-0307266934        ← конкретное издание
  ↓
Chunk:      страницы 142-145 этого издания                  ← страницы
```

Этот документ — про MVP-уровень: одна Work, одна выбранная Expression,
одна Instance, и список её paragraphs (параграфов — фактически тех же
chunks, но в исходном порядке для чтения).

Ещё два термина, которые встретятся ниже:

- **canonical_id** — стабильный человекочитаемый идентификатор Work:
  `mn10`, `sn56.11`, `dn22`. Аналог инвентарного шифра книги в
  библиотеке: не меняется при переиздании, не зависит от языка
  перевода. Любой URL Reading Room строится вокруг него:
  `/read/mn10`.
- **segment_id** — идентификатор фрагмента внутри Instance, в формате
  SuttaCentral: `mn10:8.1` означает «параграф 8.1 в сутте mn10».
  Используется как HTML-якорь (anchor) для глубоких ссылок:
  `/read/mn10#mn10:8.1` ведёт прямо к нужному параграфу.

## Архитектура

Поток данных от пользователя до отрисованного HTML:

```
Browser:  GET /read/mn10
            ↓
Next.js server component (page.tsx)
            ↓
api-client.getSource("mn10")
            ↓
Backend: GET /api/sources/mn10
            ↓
RAGService.get_source("mn10")
            ↓
Postgres SELECT (FRBR join: works × expressions × paragraphs)
            ↓
SourceDocument {
  canonical_id, title, title_pali,
  tradition_code, is_restricted,
  translation: { author, language_code, license, year, title },
  paragraphs: [{ sequence, segment_id, text }, ...]
}
            ↓
Server-rendered HTML с полным текстом
            ↓
Browser получает готовую страницу
```

Что здесь происходит на пальцах: пользователь набирает в браузере
`/read/mn10`. Запрос идёт на Next.js (наш frontend-фреймворк). Там
живёт **server component** — страница, которая выполняется на сервере
и возвращает в браузер уже готовый HTML, без необходимости что-то
дорисовывать на клиенте JavaScript'ом. Аналогия: «страница уже
распечатана на принтере и ждёт тебя на столе — не клеишь сам». Эта
страница вызывает `api-client.getSource("mn10")`, который делает
HTTP-запрос на FastAPI-backend. Backend дёргает `RAGService`, тот
ходит в Postgres, собирает все нужные данные по FRBR-схеме (Work
+ выбранная Expression + все paragraphs) и возвращает наружу один
объект `SourceDocument`. Этот объект сериализуется в JSON, прилетает
обратно в Next.js, и server component рендерит из него HTML с
параграфами.

Backend и frontend связаны через автогенерируемые типы: Python-схемы
→ `openapi.json` → `web/lib/api-types.ts`. Описано в концепте
[16 — OpenAPI typegen](16-openapi-typegen.md).

## Ключевые решения

### 1. Отдельная Pydantic-схема `SourceDocument`, не переиспользование `Source`

`Source` (из `/api/query`) — это **результат поиска**: один
parent-chunk + snippet (короткая выдержка) + score (релевантность).
Одна сутта может вернуться как несколько `Source` если разные её
куски попали в top-k.

`SourceDocument` (новый) — это **полный документ**: title, метаданные
о переводе, **все** paragraphs в порядке `sequence` (последовательного
номера в сутте). Концептуально другой объект — другой смысл, другой
жизненный цикл, другой набор полей. Поэтому отдельный type, не
`list[Source]`.

**Pydantic schema** = модель данных в Python (через библиотеку
Pydantic). Описывает какие поля есть, каких они типов, какие
обязательные. Pydantic в runtime проверяет что данные соответствуют
этой схеме, и заодно умеет генерить JSON-схему — её мы скармливаем
typegen'у чтобы получить TypeScript-типы для frontend'а.

Файл: [`src/rag/schemas.py`](../../src/rag/schemas.py) — секция
"Reading Room" с тремя моделями: `SourceDocument`, `SourceParagraph`,
`SourceTranslation`.

### 2. Один translation на документ для MVP, не множественный

В FRBR у одной Work много Expressions: для MN10 в корпусе есть
Bodhi 1995, Sujato 2018, Thanissaro 2002. Парллельный показ
(split-view: две колонки, два перевода рядом) — задача отдельного
дня (app-day-27).

Для MVP backend выбирает **одну** Expression детерминированно
(одинаково при каждом запросе) по простому правилу:

```sql
ORDER BY (language_code = 'eng') DESC,    -- сначала английские
         publication_year DESC NULLS LAST, -- потом — самые свежие
         created_at ASC                    -- стабильный tiebreak
LIMIT 1
```

Что делает этот SQL: сортирует все доступные Expressions для
данной Work так, чтобы английские оказались выше неанглийских;
внутри английских — сначала более новые годы публикации; если и
год одинаковый, побеждает та запись, которая раньше попала в нашу
БД (стабильный порядок при перезапусках). Берём первую строку.

Зачем детерминированно: чтобы один и тот же `/read/mn10` всегда
возвращал один и тот же перевод. Иначе пользователь поделится
ссылкой, а у получателя откроется другой Sujato/Bodhi — disaster
(катастрофа) для UX.

### 3. `None` для не-найдено, не exception в сервисе

Сигнатура метода в `RAGServiceProtocol`:

```python
async def get_source(uid: str) -> SourceDocument | None
```

В роутере (FastAPI-эндпойнте):

```python
@router.get("/sources/{canonical_id}")
async def get_source(canonical_id: str, ...):
    document = await _service.get_source(canonical_id)
    if document is None:
        raise HTTPException(404, ...)
    return document
```

Что здесь происходит: сервис возвращает `None` если документ не
найден. Роутер сам решает, как этот `None` превратить в HTTP-ответ —
у нас это HTTP 404. Чище, чем raising exception в сервисе и
отлавливание его в роутере: бизнес-логика не привязана к транспорту
(HTTP), её можно вызвать из CLI или другого сервиса без
HTTP-семантики.

### 4. Stub-режим: полные multi-paragraph fixtures, не одна заглушка

`StubRAGService.get_source` возвращает **фиктивные multi-paragraph
тексты** для трёх ID: `mn10`, `sn56.11`, `dn22`. В каждом параграфе
явная пометка `[stub fixture]` — чтобы dev никогда не перепутал
заглушку с реальным текстом из корпуса. Любой другой ID → `None`
(404 в роутере).

Зачем: frontend-разработчик строит Reading Room и тестирует
типографику без необходимости поднимать Postgres, миграции, заливать
реальный корпус. `RAG_BACKEND=stub` — и можно работать с UI
изолированно. Реальный корпус подключается переключением переменной
окружения.

Файл: [`src/api/_rag_stub.py`](../../src/api/_rag_stub.py) —
константа `_FIXTURE_DOCUMENTS` (словарь dict).

### 5. Реальная имплементация: один Postgres-запрос с join'ами

`RAGService.get_source()` делает **один** SQL-запрос с join'ами по
FRBR-таблицам:

- `works` — таблица Work-уровня (canonical_id, title_pali,
  tradition_code, ...)
- `expressions` — таблица Expression-уровня (translator, language,
  year, license, ...)
- `paragraphs` — таблица параграфов одной Instance в порядке
  sequence (segment_id, text).

Всё агрегируется в один `SourceDocument`. Никакого N+1 (плохой
паттерн когда для одного документа делается много мелких запросов в
БД, например по одному на каждый параграф — медленно). Один SELECT,
один resultset.

### 6. Frontend: server component, не client

`web/app/read/[uid]/page.tsx` — это **async server component**.
Async — потому что внутри `await getSource(uid)`. Server — потому
что Next.js выполняет эту функцию на сервере и присылает в браузер
готовый HTML с уже подставленным текстом сутты.

Преимущества по сравнению с client-side fetch:

- **LCP** (Largest Contentful Paint — метрика, через сколько мс
  виден основной контент) быстрее: первая отрисовка — уже с текстом,
  не «спиннер → потом текст».
- **SEO**: текст в HTML с самого начала, поисковый бот его видит.
- `notFound()` — функция Next.js, которая показывает встроенную 404
  страницу. Если `getSource(uid)` вернул `null`, мы зовём
  `notFound()` и Next.js отдаёт 404 без лишнего round-trip
  (хождения туда-сюда между браузером и сервером).
- `generateMetadata` — функция Next.js, которая вычисляет
  `<title>` и `<meta>` теги для каждой страницы. У нас она
  возвращает что-то типа `MN10 — The Establishings of Mindfulness`
  для красивого таб-title и share-preview в соцсетях.

Аналогия: client-side fetch = «приходишь в библиотеку, у тебя в
руках только пустая папка, и ты сам бегаешь между стеллажами и
ксероксом». Server component = «библиотекарь уже подобрал материал
и положил тебе на стол при входе».

В Next.js 16 есть один нюанс — **async params**. Параметры маршрута
теперь приходят в страницу как Promise (`Promise<{uid: string}>`),
их надо `await`-ить:

```tsx
export default async function ReadPage(
  { params }: { params: Promise<{ uid: string }> }
) {
  const { uid } = await params;     // ← await обязателен
  const doc = await getSource(uid);
  if (!doc) notFound();
  return <ReadingRoom doc={doc} />;
}
```

В Next.js 15 и раньше параметры были обычным объектом, без Promise.
Если забыть `await`, TypeScript ругается, runtime падает. Это
тонкость current-version, которую полезно зафиксировать.

### 7. Reuse singleton, не отдельный сервис

`/api/sources/{uid}` использует тот же `RAGServiceProtocol`, что и
`/api/query`. **Singleton** = один общий инстанс на всё приложение
(не создаётся заново для каждого запроса). У `RAGService` тяжёлый
конструктор: грузит embedding-модель, открывает соединение с Qdrant,
создаёт session_maker для Postgres. Поднимать всё это второй раз
для нового роутера — расточительство.

Sources router устанавливается **после** query router в
`src/api/app.py`, переиспользует уже готовый singleton. Никаких
дублей heavy resources (тяжёлых ресурсов).

Файл: [`src/api/sources.py`](../../src/api/sources.py).

### 8. Типографика: класс `.dharma-text`

Body документа рендерится с `<article className="dharma-text">`.
**Typography** = искусство оформления текста: шрифт, размер,
межстрочное расстояние, кернинг, лигатуры. Палийские тексты с
тяжёлой диакритикой (специальные знаки над буквами: `ā ī ū ṃ ṇ ñ
ṭ ḍ ṅ ṣ ḷ`) выглядят плохо в большинстве дефолтных шрифтов — буквы
прыгают, акценты ломают вертикальный ритм.

Состав класса:

- `font-family: var(--font-serif)` — Noto Serif с подгруженными
  subset'ами latin-ext + vietnamese, чтобы покрыть **всю**
  Pāli-диакритику.
- `font-feature-settings: kern, liga, calt` — kerning (правильные
  расстояния между парами букв), ligatures (слитные глифы для
  пар типа `fi`), contextual alternates (альтернативные глифы по
  контексту, важно для красивого `ṭṭ`, `ñc` и т.д.).
- `line-height: 1.85` — большой межстрочный интервал, комфортно
  для long-form чтения.
- `letter-spacing: 0.005em` — лёгкий tracking, раскрывает текст в
  serif-шрифте.

Класс был объявлен заранее в общем layout'е (концепт
[17 — Базовый layout](17-base-layout.md)) ровно в расчёте на этот
use-case. Reading Room только применяет его к контейнеру параграфов.

### 9. Segment-anchors для deep-link'ов

Каждый параграф рендерится как HTML-элемент с `id={segment_id}`:

```html
<p id="mn10:8.1" data-segment="mn10:8.1">
  <span class="segment-marker">8.1</span>
  ... текст параграфа ...
</p>
```

URL `/read/mn10#mn10:8.1` ведёт прямо к этому параграфу. Браузер
сам прокручивает страницу к элементу с указанным `id` после знака
решётки в URL.

**Deep-link** = ссылка, которая ведёт не на начало страницы, а на
конкретное место внутри неё. Аналогия: «закладка между страницами
12 и 13 в книге — открываешь сразу там, не листаешь с обложки».

Зачем это в MVP: будущая фича — citation `[mn10]` в ответе чата —
будет указывать не просто на документ, а на **конкретный параграф**,
из которого LLM взяла факт. Аналогия: «ссылка в книжном обзоре
ведёт прямо на нужную страницу первоисточника, а не на оглавление».
Без segment-anchors сейчас этой фичи потом не будет — пришлось бы
рефакторить весь HTML. Поэтому закладываем сразу.

Hover на segment-метку слева от параграфа открывает кнопку «copy
deep-link» — пользователь может поделиться ссылкой на конкретный
параграф.

## Что **НЕ** делаем в этом дне

| Фича | Куда переехало |
|---|---|
| Outline / sticky-sidebar (оглавление сбоку, прилипшее к экрану при скролле) | app-day-22 |
| Hover-glossary (всплывающие пояснения для палийских терминов типа `sati`, `dukkha`) | app-day-23 |
| Bookmarks через localStorage (закладки, сохранённые в браузере) | app-day-24 |
| Highlights в трёх цветах (подсветка маркером по выделенному фрагменту) | app-day-25 |
| Adjacent-chunks explorer (соседние chunks: «показать что было до/после») | app-day-26 |
| Split-view параллельных переводов (Bodhi и Sujato в двух колонках рядом) | app-day-27 |
| Print-friendly CSS (правильная вёрстка для распечатки) | app-day-28 |
| Shareable links + copy citation (сгенерировать citation в академическом формате одной кнопкой) | app-day-29 |
| Performance pass — Lighthouse ≥ 90 (комплексная проверка производительности через Google Lighthouse) | app-day-30 |

## Как проверить

Все команды — single-line, чтобы корректно работать в Windows
PowerShell.

### Backend в stub-режиме

Запустить uvicorn (ASGI-сервер для FastAPI) с переменной
`RAG_BACKEND=stub`, что переключит сервис на фикстуры:

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload
```

В отдельном окне дёрнуть документ, ожидая JSON со всеми параграфами:

```
curl.exe http://localhost:8000/api/sources/mn10
```

Проверить 404 на несуществующем ID — ожидается HTTP-статус 404 и
JSON `{"detail":"..."}`:

```
curl.exe -i http://localhost:8000/api/sources/doesnotexist
```

`curl.exe` (а не `curl`) — потому что в PowerShell `curl` это
alias для `Invoke-WebRequest`, который ведёт себя иначе. Реальный
curl лежит в `C:\Windows\System32\curl.exe`.

### Frontend

Запустить dev-сервер обоих процессов (Next.js на :3001 + uvicorn
на :8000) одной командой через pnpm:

```
pnpm dev
```

Открыть в браузере:

- `http://localhost:3001/read` — index с тремя suggested works
- `http://localhost:3001/read/mn10` — Сатипаттхана-сутта
- `http://localhost:3001/read/sn56.11` — Дхаммачаккаппаваттана
- `http://localhost:3001/read/dn22` — Махасатипаттхана
- `http://localhost:3001/read/foo` — Next.js 404 page

Что должно быть на странице `/read/mn10`:

- Заголовок `mn10 · Theravāda` (uppercase, разрядка букв).
- Title `The Establishings of Mindfulness` (большой sans-шрифт).
- Pāli-title `Satipaṭṭhāna Sutta` (italic, serif).
- Provenance (метаданные перевода): `Bhikkhu Sujato · 2018 · CC0`.
- Параграфы: serif Noto, line-height 1.85, monospace
  segment-метка слева от каждого параграфа.

Проверить deep-link: открыть `http://localhost:3001/read/mn10#mn10:8.1`
— страница должна автоматически проскроллиться к параграфу 8.1.

## Файлы

| файл | роль |
|---|---|
| `src/rag/schemas.py` | три Pydantic-модели: `SourceDocument` / `SourceParagraph` / `SourceTranslation` |
| `src/rag/protocol.py` | `RAGServiceProtocol.get_source()` добавлен в Protocol |
| `src/api/_rag_stub.py` | `_FIXTURE_DOCUMENTS` для mn10 / sn56.11 / dn22 |
| `src/rag/service.py` | реальная имплементация `get_source()` через Postgres-запрос с join'ами |
| `src/api/sources.py` | router `GET /api/sources/{canonical_id}` |
| `src/api/app.py` | install_sources_router после query router (reuse singleton) |
| `web/lib/api-client.ts` | TS-функция `getSource(uid)`, возвращает `null` на 404 |
| `web/app/read/page.tsx` | index-страница с тремя suggested works |
| `web/app/read/[uid]/page.tsx` | server component + `generateMetadata` + `notFound()` |
| `web/components/reader/SourceHeader.tsx` | заголовок документа (canonical_id, title, pāli-title, provenance) |
| `web/components/reader/SourceBody.tsx` | параграфы с классом `.dharma-text` и segment-anchors |

## Связанные документы

- [docs/concepts/13-rag-service-contract.md](13-rag-service-contract.md) — контракт `/api/query`, основа `RAGServiceProtocol`
- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — LLM-генерация и citation-формат `[mn10]`
- [docs/concepts/16-openapi-typegen.md](16-openapi-typegen.md) — type-safe API-клиент, через который Reading Room ходит на backend
- [docs/concepts/17-base-layout.md](17-base-layout.md) — класс `.dharma-text` и базовая типографика
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — Phase 2 целиком, dependencies между app-day-NN
