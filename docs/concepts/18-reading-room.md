# 18 — Reading Room MVP (app-day-21)

> **Статус:** реализовано в app-day-21 как MVP. Минимум для того,
> чтобы по `[mn10]` из чата можно было кликнуть и **прочитать всю
> сутту**. Outline, hover-glossary, bookmarks, split-view —
> отдельные дни (app-day-22..30).

## Зачем

До этого дня у нас было:

- `POST /api/query` — top-k passages по релевантности
- `POST /api/answer` — LLM-ответ с citations `[mn10]`

Но **открыть всю сутту** возможности не было. Кликнул по citation
`[mn10]` — и некуда идти. Это противоречит нашей фундаментальной
философии «**тексты — это святое**, AI вторичен»: пользователь
*должен* иметь возможность верифицировать ответ против источника.

Reading Room — главный surface проекта. MVP закрывает «нулевую»
функцию: отображение полного документа.

## Архитектура

```
GET /api/sources/{canonical_id}
            ↓
   SourceDocument {
     canonical_id, title, title_pali,
     tradition_code, is_restricted,
     translation: { author, language_code, license, year, title },
     paragraphs: [{ sequence, segment_id, text }, ...]
   }
            ↓
   web/app/read/[uid]/page.tsx  (Next.js server component)
            ↓
   <SourceHeader/> + <SourceBody/>  (rendered with .dharma-text font-stack)
```

Backend и frontend связаны через `openapi.json` → `web/lib/api-types.ts` →
`web/lib/api-client.ts::getSource(uid)`. См. концепт
[16 — OpenAPI typegen](16-openapi-typegen.md).

## Ключевые решения

### 1. Отдельный schema от `Source`

`Source` (из `/api/query`) — это **результат поиска**: один parent-chunk
+ snippet + score. Одна сутта = много `Source` если несколько chunks
матчнули.

`SourceDocument` (новый) — это **полный документ**: title, translation
metadata, **все** paragraphs в порядке `sequence`. Концептуально другое.
Поэтому отдельный type, не `list[Source]`.

Files: [`src/rag/schemas.py`](../../src/rag/schemas.py) — секция
"Reading Room" с тремя моделями.

### 2. Один translation, не множественный

В FRBR-модели у одной Work много Expressions (Bodhi 1995, Sujato 2018,
Thanissaro 2002). Для MVP сервер выбирает **одну** детерминированно:

```sql
ORDER BY (language_code = 'eng') DESC,    -- English first
         publication_year DESC NULLS LAST, -- newest
         created_at ASC                    -- stable tiebreak
LIMIT 1
```

Параллельные переводы (split-view) — app-day-27, не сейчас.

### 3. `None` для не-найдено, не exception

Protocol-сигнатура: `async def get_source(uid: str) -> SourceDocument | None`.

```python
@router.get("/sources/{canonical_id}")
async def get_source(...):
    document = await _service.get_source(canonical_id)
    if document is None:
        raise HTTPException(404, ...)
    return document
```

Чище чем raising в сервисе и catching в роутере.

### 4. Stub: полные тексты, не snippet

`StubRAGService.get_source` возвращает фиктивные multi-paragraph тексты
для `mn10`, `sn56.11`, `dn22` (с пометкой `[stub fixture]` в каждом
параграфе чтобы dev никогда не путал с реальным корпусом). Любой
другой ID → `None`.

Это позволяет frontend dev'у строить Reading Room без Postgres.

Files: [`src/api/_rag_stub.py`](../../src/api/_rag_stub.py) —
`_FIXTURE_DOCUMENTS` dict.

### 5. Reuse singleton, не отдельный сервис

`/api/sources/{uid}` использует тот же `RAGServiceProtocol` что и
`/api/query`. Sources router устанавливается **после** query router —
переиспользует уже инициализированный singleton (encoder, Qdrant,
session_maker). Никаких дублей heavy resources.

Files: [`src/api/sources.py`](../../src/api/sources.py).

### 6. Frontend: server component, не client

`web/app/read/[uid]/page.tsx` — async server component. Fetch
`getSource(uid)` происходит **на сервере** (в Next.js process), HTML
рендерится со всем контентом. Преимущества:

- LCP быстрее: первая отрисовка — уже с текстом
- SEO: документ в HTML с самого начала
- `notFound()` → 404 page Next.js'а без extra round-trip
- `generateMetadata` → правильный `<title>` для каждой сутты

В Next.js 16 `params` теперь async (`Promise<{uid: string}>`) — это
учтено.

### 7. Типографика: `.dharma-text` класс

Body рендерится с `<article className="dharma-text">`:

- `font-family: var(--font-serif)` — Noto Serif с latin-ext +
  vietnamese subsets для **полного покрытия Pāli-диакритики**
  (`ā ī ū ṃ ṇ ñ ṭ ḍ ṅ ṣ ḷ`)
- `font-feature-settings: kern, liga, calt` — kerning + ligatures +
  contextual alternates (важно для красивого `ṭṭ`, `ñc`, etc.)
- `line-height: 1.85` — комфортно для длинного reading'а
- `letter-spacing: 0.005em` — слегка раскрывает текст для serif

См. концепт [17 — Базовый layout](17-base-layout.md) — там этот
класс был объявлен заранее ровно под этот use-case.

### 8. Segment ID anchors

Каждый параграф рендерится с `id={segment_id}` (например `mn10:8.1`).
URL `/read/mn10#mn10:8.1` ведёт прямо к параграфу. Hover на
segment-метку слева → можно скопировать deep-link.

Это базис для будущих фич: citations из chat ведут на конкретный
параграф, не просто на документ.

## Что **НЕ** делаем в MVP

| Фича | Где |
|---|---|
| Outline / sticky-sidebar | app-day-22 |
| Hover-glossary для палийских терминов | app-day-23 |
| Bookmarks (localStorage) | app-day-24 |
| Highlights (3 цвета) | app-day-25 |
| Adjacent-chunks explorer | app-day-26 |
| Split-view параллельных переводов | app-day-27 |
| Print-friendly CSS | app-day-28 |
| Shareable links + copy citation | app-day-29 |
| Performance pass (Lighthouse ≥ 90) | app-day-30 |

## Как проверить

### Backend (stub-режим)

```powershell
$env:RAG_BACKEND = "stub"
uvicorn src.api.app:app --reload

# В другом окне:
curl.exe http://localhost:8000/api/sources/mn10
curl.exe -i http://localhost:8000/api/sources/doesnotexist  # 404
```

### Frontend

```powershell
pnpm dev   # web :3001 + api :8000

# Открыть:
#   http://localhost:3001/read           — index с тремя карточками
#   http://localhost:3001/read/mn10      — Satipaṭṭhāna Sutta
#   http://localhost:3001/read/sn56.11   — Dhammacakkappavattana
#   http://localhost:3001/read/dn22      — Mahāsatipaṭṭhāna
#   http://localhost:3001/read/foo       — Next.js 404 page
```

Ожидаемое:

- Заголовок `mn10 · Theravāda` (uppercase, разрядка)
- Title `The Establishings of Mindfulness` (большой шрифт sans)
- Pāli title `Satipaṭṭhāna Sutta` (italic, serif)
- Provenance: `Bhikkhu Sujato · 2018 · CC0`
- Параграфы: serif Noto, line-height 1.85, monospace segment-метка слева

## Files

| файл | роль |
|---|---|
| `src/rag/schemas.py` | `SourceDocument` / `SourceParagraph` / `SourceTranslation` |
| `src/rag/protocol.py` | `RAGServiceProtocol.get_source()` добавлено |
| `src/api/_rag_stub.py` | `_FIXTURE_DOCUMENTS` для mn10/sn56.11/dn22 |
| `src/rag/service.py` | `RAGService.get_source()` через Postgres |
| `src/api/sources.py` | router `GET /api/sources/{canonical_id}` |
| `src/api/app.py` | install_sources_router после query |
| `web/lib/api-client.ts` | `getSource(uid)` — `null` на 404 |
| `web/app/read/page.tsx` | index с тремя suggested works |
| `web/app/read/[uid]/page.tsx` | server component + generateMetadata |
| `web/components/reader/SourceHeader.tsx` | заголовок документа |
| `web/components/reader/SourceBody.tsx` | параграфы с `.dharma-text` |

## Связанные документы

- [docs/concepts/13-rag-service-contract.md](13-rag-service-contract.md) — контракт `/api/query`
- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — LLM-генерация
- [docs/concepts/16-openapi-typegen.md](16-openapi-typegen.md) — type-safe API клиент
- [docs/concepts/17-base-layout.md](17-base-layout.md) — `.dharma-text` typography
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — Phase 2 целиком
