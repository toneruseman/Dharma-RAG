# 23 — Feedback widget 👍/👎 (app-day-26)

> **Статус:** реализовано в app-day-26 (2026-05-02).
> Один корректировка по сравнению с первоначальным концептом: в
> `FeedbackRequest` появилось обязательное вложенное поле
> `answer_snapshot` (фронт эхо-возвращает `query/answer/metadata`
> поля), потому что таблица `app.feedback` имеет `NOT NULL`
> snapshot-колонки, а audit_log для server-side lookup'а ещё не
> построен (запланирован на app-day-49). После audit_log поле
> `answer_snapshot` можно будет сделать optional или дропнуть.

## Зачем

Сейчас мы выкатили ответы (`POST /api/answer` + streaming-вариант
`POST /api/answer/stream`), но **не знаем, какие из них хорошие, а
какие плохие**. Метрики latency и token-counts показывают «как быстро
и сколько», а не «попал ли ответ в вопрос».

Без размеченных данных от живых пользователей мы не можем калибровать
**confidence indicator** (индикатор уверенности из app-day-24 —
пороги «низкая/средняя/высокая» нужно сверять с реальной оценкой),
сравнивать LLM-модели между собой, и строить regression-тест на
качество (если пересобрали индекс и доля 👎 поползла вверх — это
видно до жалоб).

Кнопки 👍/👎 + опциональный комментарий — самый дешёвый способ
собрать сигнал «понравилось / не помогло» end-to-end. Дешевле, чем
пятибалльная шкала (никто не различает 3 и 4), и переводимо в числа
без усилий: `+1` / `-1`.

## Что такое feedback widget

**Feedback widget** (виджет обратной связи — небольшой UI-блок,
который собирает короткую оценку прямо рядом с тем, что оценивают)
у нас состоит из трёх частей:

- две кнопки `👍` и `👎` (выбирается одна, вторая визуально гасится);
- опциональный `<textarea>` для свободного комментария;
- кнопка «отправить».

После успешной отправки виджет переходит в `disabled` состояние —
повторно проголосовать по тому же ответу нельзя (UI скрывает кнопки,
оставляет «спасибо за feedback»).

Важно различать **широкий** и **узкий** feedback. Широкий — это
пятибалльная шкала, эмоции, отдельные оси («полезно», «понятно»,
«дружелюбно»), таксономия причин. Это для зрелого продукта с
ML-командой, которая будет это разбирать. У нас — **узкий**
feedback: бинарная оценка плюс свободный комментарий. Этого хватает
для MVP-сигнала «куда копать».

## Архитектура

Полный поток одного feedback'а:

```
/chat → POST /api/answer/stream
       backend генерирует UUID trace_id
       retrieval_done → token* → done { ..., metadata.trace_id }
       frontend хранит trace_id в state рядом с answer'ом
user жмёт 👍 → (опционально) комментарий → submit
       POST /api/feedback { trace_id, thumb: +1, comment? }
       FeedbackService.submit() — upsert в app.feedback (Postgres)
       виджет показывает «спасибо за feedback»
```

Что здесь происходит. Backend ещё на этапе генерации ответа выпускает
уникальный `trace_id` и зашивает его в финальное событие `DoneEvent`.
Frontend, получив ID, привязывает его к конкретному пузырю ответа.
Когда пользователь жмёт 👍/👎, фронт шлёт отдельный POST, неся этот
ID как «адрес» — на него ложится оценка в БД.

## Что такое trace_id

**trace_id** (уникальный идентификатор одного запроса/ответа,
проходящий через весь стек — от backend-логов до строки feedback'а в
БД) — это «номер чека». Аналогия: получил ответ, на чеке стоит
уникальный номер; принёс назад жалобу — кассир по номеру находит твою
покупку в журнале и записывает «не понравилось».

Реализуется как **UUID** (Universally Unique Identifier — 128-битный
идентификатор, который можно генерировать без координации с сервером
и быть уверенным в отсутствии коллизий; на практике это строка из 32
hex-символов через дефисы: `f47ac10b-58cc-4372-a567-0e02b2c3d479`).
Используем **UUID4** — псевдослучайный, дефолт для большинства языков.

Один `trace_id` живёт в трёх местах: в поле `AnswerMetadata.trace_id`
ответа, в контексте **structlog** (структурированное логирование —
каждая запись лога это JSON-объект с named-полями, не голая строка;
все логи внутри запроса автоматически носят `trace_id`, чтобы можно
было `grep` по инциденту) и в Phoenix span attribute (наша
**observability**-платформа — практика собирать трейсы/метрики/логи
так, чтобы по ним можно было реконструировать поведение системы).

## Ключевые решения

### 1. Trace ID генерируется на бэке, идёт во фронт через DoneEvent

Один источник истины. Альтернативу «генерировать на фронте и слать
с запросом» отвергаем по трём причинам:

- backend всё равно вынужден генерить **какой-то** ID для логов и
  Phoenix-спанов; иметь два разных ID на один запрос — двойной учёт;
- фронт может потерять/перепутать ID при reconnect или при горячей
  перезагрузке страницы;
- единый источник = меньше сценариев «поле пустое» / «поле не
  совпадает».

Реализация на бэке: на входе в `AnswerService.answer()` и
`AnswerService.stream_answer()` генерим `trace_id = uuid.uuid4()`,
кладём его в `structlog.contextvars.bind_contextvars(trace_id=...)`
для логов и в `AnswerMetadata.trace_id` для ответа. Frontend получает
его в `DoneEvent.metadata.trace_id` (для streaming) и в
`AnswerResponse.metadata.trace_id` (для buffered single-shot), хранит
рядом с answer'ом в state'е чата.

### 2. Postgres-таблица в schema `app`

**Postgres** (PostgreSQL — наша основная SQL-база, в которой уже
живёт корпус: works/expressions/instances/chunks). У Postgres есть
понятие **schema** (логический неймспейс внутри одной БД, способ
группировать таблицы — аналогия: «папки внутри одного жёсткого
диска»). До этого момента мы использовали только дефолтный `public`,
куда лёг весь корпус через миграции 001-004.

Вводим конвенцию: **корпусные** таблицы (FRBR — Work, Expression,
Instance, Chunk + lookups) живут в `public`, **app**-таблицы (всё
что относится к работающему приложению — feedback, в будущем
audit_log, sessions, rate_limit_buckets) — в `app`. Это не рефакторинг
существующих таблиц, а правило для новых; миграция этого дня создаёт
schema `app` если её нет (`CREATE SCHEMA IF NOT EXISTS app`) и кладёт
туда первую таблицу `app.feedback`.

#### Схема таблицы `app.feedback`

```sql
CREATE TABLE app.feedback (
    trace_id        UUID         PRIMARY KEY,
    ts              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    thumb           SMALLINT     NOT NULL CHECK (thumb IN (-1, 1)),
    comment         TEXT,
    query_text      TEXT         NOT NULL,
    answer_text     TEXT         NOT NULL,
    pipeline_version VARCHAR(64) NOT NULL,
    llm_model       VARCHAR(128) NOT NULL,
    style           VARCHAR(16)  NOT NULL,
    latency_ms      INTEGER      NOT NULL,
    llm_tokens_in   INTEGER      NOT NULL,
    llm_tokens_out  INTEGER      NOT NULL
);

CREATE INDEX idx_feedback_ts          ON app.feedback (ts DESC);
CREATE INDEX idx_feedback_thumb_ts    ON app.feedback (thumb, ts DESC);
CREATE INDEX idx_feedback_llm_model   ON app.feedback (llm_model);
```

Что здесь происходит. `trace_id` стоит как **primary key** — один
feedback на один ответ; повторный POST с тем же `trace_id` обновляет
запись, а не создаёт новую (см. решение №3). Колонки `query_text` и
`answer_text` дублируют то, что уже было в логах — это сделано
сознательно, чтобы review feedback'а через `psql` одной строкой не
требовал join'а с audit_log (которого пока вообще нет — он в
app-day-49). Колонки `pipeline_version`, `llm_model`, `style` снимают
вопрос «а на какой конфигурации тебе не понравилось» — без них
сравнивать модели бессмысленно.

Индексы покрывают три типичных запроса: «весь feedback за неделю»
(`ts DESC`), «все 👎 за неделю для разбора» (`thumb, ts DESC`),
«сравнить долю 👎 у разных моделей» (`llm_model`).

### 3. POST /api/feedback — контракт

**Идемпотентный** (idempotent — свойство операции: вызвать её
дважды с теми же входными данными приводит к тому же результату,
что и один вызов; никаких побочных эффектов от повтора). Аналогия:
лифт. Нажимаешь кнопку «5 этаж» один раз или десять — всё равно
поедешь на 5-й, никаких новых лифтов от повторных нажатий не
заводится. У нас: повторный feedback на тот же `trace_id` просто
перезаписывает первый, новые строки в таблице не создаёт.

```python
class FeedbackRequest(BaseModel):
    trace_id: UUID
    thumb: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    saved: bool
```

Что здесь происходит. `trace_id` обязателен (без него мы не знаем
к какому ответу привязать оценку). `thumb` — `Literal[1, -1]`, что
автоматически даёт **422 Unprocessable Entity** на любые другие
значения через Pydantic-валидацию (проверка типов в runtime; FastAPI
сам конвертирует ошибки валидации в HTTP 422). `comment` ограничен
2000 символами — рамка, чтобы не пускать в БД мегабайтные
текстовые портянки.

Реализуется как **upsert** (insert or update — одна SQL-операция,
которая вставляет строку если её нет, и обновляет если уже есть; в
Postgres делается через `INSERT ... ON CONFLICT (trace_id) DO UPDATE
SET ...`). На каждый POST `saved=true` возвращается всегда — для
клиента нет разницы между «первый раз» и «обновил».

Валидацию `trace_id` против реально существовавшего запроса
**не делаем на MVP** — для этого нужен audit_log, которого пока
нет. Его заведём в app-day-49 и тогда же добавим проверку «trace_id
должен существовать в audit_log не старше 24h». До тех пор
теоретически можно засорить таблицу поддельными UUID'ами через curl
— но это самохостед-сервис без аутентификации, мы это переживём.

### 4. Stub-режим — in-memory лог

В **stub mode** (режим заглушки — backend поднят без реальных
Qdrant/Postgres/OpenRouter, всё подменено на in-memory mocks; нужен
для frontend-разработки) Postgres недоступен. Заводим
`StubFeedbackService` — модуль-уровневый `list[dict]`, который ведёт
себя как таблица: при `submit()` ищет запись по `trace_id`, если есть
— перезаписывает, если нет — append'ит. Возвращает `saved=True` всегда.

Этого frontend-разработчику хватает на три проверки: виджет переходит
в disabled-state после первого POST, повторный submit обновляет
существующую запись, ошибка от бэка корректно отображается в UI.
Stub 500-ки сам не мокает — для тестов error-state'а используется
MSW (mock service worker — библиотека для перехвата HTTP-вызовов в
браузере) на стороне фронта.

### 5. Frontend — `<FeedbackWidget/>` controlled component

**Controlled component** (контролируемый компонент в React — все
значения inputs хранятся не в DOM, а в React-state'е через
`useState`/`useReducer`; React — единственный источник истины). Иначе
не получится дёрнуть `disabled` после successful submit'а синхронно с
приходом ответа.

State: `thumb: 1 | -1 | null`, `comment: string`, `isSubmitting: bool`,
`submitted: bool`, `error: string | null`. Пока `thumb=null` — обе
кнопки нейтральные. После клика одна подсвечивается, появляется поле
комментария и кнопка «отправить». `isSubmitting` блокирует двойной
клик во время in-flight POST'а. `submitted=true` — терминал, виджет
заменяется на «спасибо за feedback» (без «отменить» — multi-vote
покрывается серверным upsert'ом, UI-сценарий «передумал» осознанно
не делаем).

Расположение: под `<AnswerView/>`, выше `<SourcesPanel/>` на desktop;
на mobile — после `<SourcesPanel/>`. Подписи кнопок: 👍 «Полезно»,
👎 «Не помогло» — нейтральные, без эмоциональной нагрузки.
Placeholder комментария: «Что не так? (необязательно)».

### 6. Fail-soft на ошибках POST /api/feedback

**Fail-soft** (тип обработки ошибок: при сбое продолжить работу, не
обваливать остальной поток; противоположность fail-hard, где ошибка
останавливает всё). Аналогия: если телефон жалоб занят — опросник
просто закрывается без модальной ошибки на пол-экрана. Пользователю
уже показали ответ, его опыт не должен зависеть от наших проблем со
сбором статистики.

Конкретно: если `POST /api/feedback` вернул 500 / network failure /
timeout, виджет показывает inline-ошибку «не удалось отправить,
попробуйте ещё раз» прямо в своём блоке, остаётся в editable-режиме
(пользователь может ткнуть «отправить» снова), но **не** показывает
toast/modal/error boundary. Chat продолжает работать; следующий
вопрос можно задать как обычно.

### 7. PII и self-hosted vs SaaS

**PII** (Personally Identifiable Information — персональные данные,
по которым можно идентифицировать человека). В `query_text`
пользователь может написать «меня зовут Иван, я 5 лет занимаюсь
медитацией» — мы храним это открытым текстом.

Для **open-source self-hosted instance** (пользователь развернул
проект у себя локально, доступа к БД больше ни у кого нет) это норма
— данные на твоей машине, у тебя самого. Если запустим SaaS-вариант
(общий сервер) — добавим в `Settings` флаг
`feedback_store_pii: bool = True`, в false-режиме будем класть
SHA-256 хэш вместо текста. Сейчас не нужно, но контракт дешёво
заложить.

## Что НЕ делаем

| Фича | Куда |
|---|---|
| Email-уведомления о новом feedback | manual review через `psql` пока |
| Admin UI для просмотра feedback'а | app-day-49 (audit log + admin) |
| Аналитика «top causes 👎» | вручную на этапе MVP |
| Анонимизация (хэширование) query/answer | settings-flag в SaaS-фазе |
| Валидация `trace_id` против audit_log | app-day-49 |
| Multi-vote «передумал, теперь 👍» | upsert уже даёт это поведение, UI-флоу не делаем |
| **Rate limit** (ограничение частоты запросов с одного IP/ключа — чтобы один клиент не мог завалить эндпойнт миллионом POST'ов) на `/api/feedback` | app-day-45 (общий rate-limit middleware) |
| Phoenix span specifically для feedback-submit | использует существующий FastAPI middleware |
| Привязка feedback'а к user_id | у нас пока нет аутентификации; добавим вместе с auth в Phase 4 |

## Тесты

Семь тестов покрывают backend, миграцию и frontend:

1. **Migration forward + downgrade.** `alembic upgrade head` → schema
   `app` и таблица `app.feedback` видны в `information_schema`.
   `alembic downgrade -1` → таблица и schema исчезли.
2. **POST /api/feedback happy path.** `thumb=1, comment=null` →
   `saved=true`, в БД одна строка с `comment IS NULL`.
3. **POST /api/feedback с комментарием.** `thumb=-1, comment="too short"`
   → строка с `comment="too short"`.
4. **Idempotent upsert.** Два POST'а с одним `trace_id`; второй меняет
   `thumb` с `+1` на `-1` → одна строка, поля обновлены.
5. **Invalid thumb (например `5`).** Pydantic возвращает HTTP 422,
   POST не доходит до сервиса.
6. **AnswerService возвращает `trace_id`.** `answer()` и
   `stream_answer()` оба кладут UUID в `metadata.trace_id`, разный
   между двумя последовательными вызовами.
7. **Frontend FeedbackWidget unit (Vitest).** Клик 👍 → submit → POST
   с правильным телом → `submitted=true`. Backend 500 → inline-ошибка,
   виджет остаётся editable.

## Как проверить локально (PowerShell single-line)

После apply миграции и поднятия backend'а:

Сначала применяем миграцию против локального Postgres'а:

```
docker compose up -d dharma-db; alembic upgrade head
```

Проверяем что таблица создалась — одной строкой через `docker compose
exec`:

```
docker compose exec -T dharma-db psql -U dharma -d dharma -c "SELECT to_regclass('app.feedback') AS exists;"
```

Ожидаем: одна строка с `exists = app.feedback`. Если `exists` пустое
(NULL) — миграция не доехала.

В **stub-режиме** запускаем uvicorn и шлём тестовый feedback (UUID
любой, главное что валидный):

```
$env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

В отдельном окне (UUID для теста — фиксированный, чтобы можно было
послать второй раз):

```
Invoke-RestMethod -Uri http://localhost:8000/api/feedback -Method POST -Body '{"trace_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","thumb":1,"comment":"works"}' -ContentType 'application/json'
```

Ожидаем: `saved : True`. Повторяем тот же вызов с `thumb=-1` —
снова `saved : True`, в stub-store одна запись, обновлённая.

В **real-режиме** проверяем что строка появилась в Postgres:

```
docker compose exec -T dharma-db psql -U dharma -d dharma -c "SELECT trace_id, thumb, comment, ts FROM app.feedback ORDER BY ts DESC LIMIT 5;"
```

Ожидаем: новые строки сверху, поле `thumb` в виде `1` или `-1`.

Frontend проверка — `pnpm --filter web dev`, открыть
`http://localhost:3001/chat`, отправить запрос, дождаться ответа,
кликнуть 👍, нажать «отправить». В DevTools → Network виден
`POST /api/feedback` с 200, виджет схлопнулся в «спасибо за feedback».
Refresh страницы — feedback не возвращается (это сознательно: state
живёт только в течение сессии, постоянство хранения — на серверной
стороне).

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| `alembic/versions/20260429_005_app_feedback.py` | новая | schema `app` + таблица `app.feedback` + 3 индекса |
| `src/db/models/app.py` | новый | SQLAlchemy-модель `Feedback` |
| `src/feedback/{schemas,protocol,service}.py` | новые | request/response, Protocol, реальный upsert |
| `src/api/_feedback_stub.py` | новый | `StubFeedbackService` (in-memory list) |
| `src/api/feedback.py` | новый | `POST /api/feedback` router + `install_router` |
| `src/api/app.py` | изменён | `install_feedback_router(app)` в lifespan |
| `src/answer/schemas.py` | изменён | поле `trace_id: str` в `AnswerMetadata` |
| `src/answer/service.py` | изменён | `uuid.uuid4()` на входе `answer()` / `stream_answer()`, прокидывать в metadata + structlog context |
| `src/api/_answer_stub.py` | изменён | `trace_id` в стабе |
| `web/lib/api-client.ts` | изменён | `sendFeedback(req)` + типы |
| `web/components/chat/FeedbackWidget.tsx` | новый | UI-виджет |
| `web/app/chat/page.tsx` | изменён | `<FeedbackWidget traceId={...} />` под `<AnswerView/>` |
| `web/openapi.json` + `web/lib/api-types.ts` | re-gen | новый эндпойнт + поле `trace_id` |

## Связанные документы

- [docs/concepts/15-answer-generation.md](15-answer-generation.md) —
  `/api/answer` baseline, тут добавляется `trace_id`.
- [docs/concepts/19-chat-mvp.md](19-chat-mvp.md) — chat-flow, в
  который встраивается виджет.
- [docs/concepts/21-confidence-indicator.md](21-confidence-indicator.md)
  — feedback калибрует пороги confidence-индикатора в перспективе.
- [docs/concepts/22-sse-streaming.md](22-sse-streaming.md) —
  `DoneEvent.metadata` несёт `trace_id`.
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) —
  app-day-49 (audit log) использует `trace_id` из этого дня для
  обратной связи feedback ↔ запрос.
