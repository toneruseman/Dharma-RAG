# 24 — Pull-quote side panel (app-day-27)

> **Статус:** реализовано в app-day-27 (2026-05-02). Бэкенд править не
> нужно — поле `citations` уже есть в `AnswerResponse` (см.
> [13 — RAG-service contract](13-rag-service-contract.md),
> [15 — Answer generation](15-answer-generation.md)).
>
> **Решение по клику-семантике (зафиксировано):** клик по citation-бейджу
> сохраняет текущее поведение — открывает Reading Room. Прыжок к
> pull-quote инициируется **наведением** (`onMouseEnter`) — то же
> событие, что уже триггерит существующий tooltip-preview, теперь
> дополнительно скроллит соответствующий pull-quote в видимую область
> панели и кратко подсвечивает его. Никакой Cmd/Ctrl-семантики, ничего
> не ломаем в существующих линках.

## Зачем

Мы работаем с **каноническими религиозными текстами** — Majjhima Nikaya,
Samyutta Nikaya, Dhammapada и так далее. Для верующего пользователя
ошибка вида «модель приписала Будде то, чего он не говорил» — это не
баг, это **подрыв доверия к корпусу**. Хуже, чем выдумать факт про
JavaScript: про сутру у пользователя нет своего знания, чтобы поймать.

Сейчас в чате есть две защиты от **галлюцинаций** (когда LLM выдумывает
факт, которого нет в источниках):

- citation-бейджи `[mn10]` в тексте ответа (app-day-22) — кликом ведут
  в Reading Room.
- hover-preview на бейдже (app-day-23) — наведение показывает
  **snippet** (короткий фрагмент 1-3 строки, обрезанный по
  `line-clamp-3`) с матчем по запросу.

Этого мало для verification (проверки утверждения по источнику). Snippet
обрезан, иногда ровно перед той фразой, которая подтверждает claim. А
hover требует попадать курсором в маленький бейдж, что неудобно когда
хочется параллельно читать ответ и сверяться с цитатами.

**Pull-quote panel** (панель «вытащенных цитат» — те самые куски
источника, которые модель реально использовала, лежат рядом с ответом
и видны постоянно) решает это: справа от ответа панель показывает
**полный пассаж** (не snippet) для каждой цитаты, **в том порядке**, в
котором они встречаются в тексте ответа. Пользователь читает ответ
сверху вниз, глаз скользит вправо к pull-quote — verification занимает
2 секунды, без клика, без перехода.

Аналогия — академическая bilingual-edition Bible: на левой странице
перевод с комментарием, на правой — параллельный греческий текст. Когда
комментарий говорит «здесь Павел использует слово ἀγάπη», ты сдвигаешь
глаз на правую страницу и видишь то самое слово в контексте, не
переворачивая страницу. Pull-quote panel — то же самое для нашего
чата.

## Что такое pull-quote panel — и чем отличается от текущего SourcesPanel

Сейчас справа от ответа стоит `<SourcesPanel/>`
([web/components/chat/SourcesPanel.tsx](../../web/components/chat/SourcesPanel.tsx)),
который показывает **все retrieved sources** (top_k=5) — каждый
карточкой со snippet'ом (3 строки `line-clamp-3`), score'ом и ссылкой
в Reading Room.

Это «откуда модель искала» — отличная для **transparency**
(прозрачность — видно, что подняли из индекса, можно проверить почему
конкретный источник попал в кандидаты). Но это **надмножество**
(больше, чем нужно для проверки конкретного claim'а): из 5 retrieved
LLM могла процитировать только 2, остальные были «рядом по теме, но
ответ построен на других».

**Pull-quote panel** — это другое:

| | SourcesPanel (текущий) | Pull-quote panel (новый) |
|---|---|---|
| Что показывает | retrieved sources (top_k=5) | **только cited** (которые LLM реально упомянул `[mn10]` в тексте) |
| Сколько | 5 (или сколько вернул retrieval) | 0..5 (subset, обычно 2-3) |
| Порядок | по score (релевантность) | **по первому появлению в тексте ответа** |
| Текст | snippet, обрезан до 3 строк | **полный пассаж** (`Source.text`, ~1024-2048 токенов) |
| Связь с ответом | нет | **two-way anchoring** (см. ниже) |

**two-way anchoring** (двусторонняя привязка — клик в одном месте
скроллит и подсвечивает связанный кусок в другом, как сноски в
бумажной книге, только в обе стороны): клик по `[mn10]` в тексте
ответа → pull-quote `mn10` скроллится в видимую область панели и
подсвечивается на ~1.5 секунды; клик по pull-quote `mn10` в панели
→ скроллится первое появление `[mn10]` в тексте ответа и тоже
подсвечивается.

Это превращает ответ + панель в **связанный документ** — глаз сам
находит соответствие.

## Архитектура

```
ChatPage (web/app/chat/page.tsx)
  ├─ AnswerView                              # рендерит текст ответа со citation-бейджами
  │    └─ CitationBadge[] (id="cite-mn10-0") # бейдж с уникальным id для anchor scroll
  │
  └─ PullQuotePanel                          # новая панель
       │
       │  inputs: response.citations[]       # ['mn10', 'sn56.11'] — already extracted by backend
       │          response.sources[]         # full Source objects
       │
       │  computed: cited_sources_in_order   # subset, ordered by first [mn10] in answer
       │
       ├─ <CitedQuote workId="mn10" />       # для каждой
       │    ├─ заголовок: mn10 · mn10:8.1 · score
       │    ├─ полный текст (или collapsed для длинных)
       │    └─ link "Open in Reading Room"
       │
       └─ <details> "Other retrieved (2)"    # collapsed disclosure для НЕ-cited
            └─ slim-cards для оставшихся retrieved (transparency)
```

Что здесь происходит на пальцах. Backend в `AnswerResponse` отдаёт два
поля: `citations: string[]` (массив `work_canonical_id`, который LLM
реально написал в `[...]`-маркерах ответа — backend это уже извлекает
из текста, см. поле в `web/lib/api-types.ts`) и `sources: Source[]`
(полные пассажи, **в порядке** который видела LLM).

Frontend на их основе строит `cited_sources_in_order` —
**пересечение** (intersection — общие элементы между двумя множествами;
здесь: source'ы, чей `work_canonical_id` есть в `citations`),
переупорядоченное по **first-appearance** в тексте ответа (не по
backend-порядку и не по score). Это важно: если в ответе сначала
упоминается `[sn56.11]`, потом `[mn10]`, то и в панели наверху должен
быть `sn56.11`, чтобы глаз не делал лишнее движение.

Backend менять не нужно — поле `citations` уже есть с app-day-22.

## Ключевые решения

### 1. Заменяем SourcesPanel или дополняем?

Главная развилка дня. Два варианта:

- **A. Дополнить.** Поставить PullQuotePanel **сверху** SourcesPanel'а,
  оба видны одновременно. Плюс: ничего не теряем. Минус: правая
  колонка из 280px превращается в простыню; cited-источник дублируется
  (один раз сверху как pull-quote, один раз ниже как карточка) — мозг
  путается «это разное или одно и то же?».
- **B. Заменить.** PullQuotePanel занимает место SourcesPanel'а,
  retrieved-but-not-cited прячется в `<details>`-секцию «Other
  retrieved (n)». Плюс: основной фокус — на cited (anti-hallucination
  цель достигнута), transparency не теряется (один клик по disclosure
  и видно retrieved'ы). Минус: один лишний клик для тех, кто хочет
  посмотреть «а что ещё подняли».

**Берём B.** Anti-hallucination важнее «сразу видно retrieved'ы». Доля
случаев, когда пользователю интересен retrieved-but-not-cited
(«почему этот тоже подняли, но не использовали?»), мала — это
debugging-сценарий, а не основной use case. Disclosure
(`<details><summary>Other retrieved (2)</summary>...`) даёт это
бесплатно: интересно — кликнул, не интересно — не отвлекает.

**Disclosure** — стандартный HTML-элемент `<details>`. Без JavaScript
сворачивает/разворачивает блок по клику на `<summary>`. Аналогия:
papka в файловом менеджере с треугольничком — кликнул, видно
содержимое.

### 2. Порядок — first-appearance, не score

В `<SourcesPanel/>` сейчас порядок — по score (где-то это RRF, где-то
sigmoid-rerank, для пользователя — «насколько релевантно»). Это
правильно для **retrieval**-режима: «какой источник самый похожий».

Для pull-quote это **неправильно**. Логика другая: LLM **уже выбрала**,
какие источники использовать (раз она их процитировала). Score'ы
теперь не нужны — LLM решила что mn10 более важен чем sn56.11, или
наоборот, и записала это **порядком в тексте**. Если в ответе
сначала «[mn10] говорит X, [sn56.11] добавляет Y», а в панели
`sn56.11` сверху (потому что score выше), глаз делает лишний прыжок
сверху-вниз-сверху.

Реализация — pure-function:

```typescript
function citedSourcesInOrder(
  answer: string,
  sources: Source[],
  citations: string[],
): Source[] {
  // Первое появление каждого work_id в тексте ответа.
  const firstIdx = new Map<string, number>();
  for (const cite of citations) {
    const idx = answer.indexOf(`[${cite}`);
    if (idx >= 0) firstIdx.set(cite, idx);
  }
  // Highest-score source per work_id (как в AnswerView для hover-preview).
  const bestByWorkId = new Map<string, Source>();
  for (const s of sources) {
    const cur = bestByWorkId.get(s.work_canonical_id);
    if (!cur || s.score > cur.score) {
      bestByWorkId.set(s.work_canonical_id, s);
    }
  }
  return citations
    .filter((c) => bestByWorkId.has(c))
    .sort((a, b) => (firstIdx.get(a) ?? Infinity) - (firstIdx.get(b) ?? Infinity))
    .map((c) => bestByWorkId.get(c)!);
}
```

Прозой: для каждого work_id из `citations` находим первый индекс
`[mn10` в строке ответа; параллельно строим best-source-per-work_id
(как в `AnswerView` для hover-preview, см. концепт 20); фильтруем
citations по тем что мы реально нашли в sources, сортируем по
first-appearance, мапим в Source-объекты. **Pure** (чистая функция —
выход зависит только от входов, никаких побочных эффектов; легко
тестировать unit-тестом без React-окружения).

Если `[mn10` найдётся два раза — нас интересует **первое**
(`indexOf` возвращает первый индекс), потому что глаз пользователя
поедет сверху вниз и встретит сначала первое.

### 3. Полный текст vs snippet

**Snippet** — это короткий child-фрагмент, который матчился на запрос
(см. `Source.snippet` в `web/lib/api-types.ts`: «precise child
fragment»). **Text** — это broader passage, который реально подавался
в LLM (parent-чанк, ~1024-2048 токенов, см. концепт
[12 — Parent/child retrieval](12-parent-child-retrieval.md)).

Для pull-quote показываем **`text`** (полный пассаж). Зачем: модель
строила утверждение **по этому контексту**, не по обрезанному snippet'у.
Если пользователь хочет проверить «а правда ли это в источнике» —
нужен тот же объём текста, который видела модель.

Но parent-чанк — это иногда полстраницы. Если выложить 5 таких подряд
— боковая панель станет простынёй на 3 экрана. Решение —
**collapse** (свернуть текст в прокручиваемый блок с
`max-height` и `overflow-y: auto`):

- если `text.length` ≤ ~400 символов — показываем целиком,
- если больше — показываем первые ~200 символов + `…` + кнопка
  «Развернуть» (`<details><summary>`); при клике видно весь пассаж
  внутри блока с `max-height: 60vh; overflow-y: auto`.

Альтернатива «всегда скроллящийся блок ~12em» рассматривалась — даёт
консистентный визуал, но для коротких пассажей (200 символов) пустое
место внизу выглядит странно. Adaptive выгоднее.

### 4. Two-way anchoring через CSS scroll + transient highlight

Чтобы клик связывал ответ и панель, нужны три вещи:

1. **Уникальный `id`** на каждом элементе. У `CitationBadge` сейчас
   нет id — добавляем `id="cite-${workId}-${occurrenceIndex}"`
   (`occurrenceIndex` для случая если `[mn10]` встречается дважды).
   У `<CitedQuote>` ставим `id="quote-${workId}"`.
2. **Скролл** — `element.scrollIntoView({ behavior: "smooth", block:
   "center" })`. **scrollIntoView** — встроенный метод браузера,
   плавно скроллит контейнер так, чтобы элемент попал в viewport;
   `block: "center"` ставит элемент в центр экрана.
3. **Transient highlight** (кратковременная подсветка — состояние
   живёт ~1.5 секунды, потом возвращается к normal'у; помогает глазу
   найти куда «приехало»). Делаем через React state + setTimeout:
   при клике ставим `highlightedId="mn10"`, через 1500ms сбрасываем
   обратно в `null`. CSS-класс с подсветкой (например
   `bg-accent/40 transition-colors duration-300`) применяется только
   когда `id` совпадает.

Реализация на пальцах:

```typescript
// в page.tsx (lifted state — общий state, который живёт у общего
// родителя двух компонентов; иначе они не знают друг о друге)
const [highlightedQuote, setHighlightedQuote] = useState<string | null>(null);
const [highlightedCite, setHighlightedCite] = useState<string | null>(null);

function jumpToQuote(workId: string) {
  document.getElementById(`quote-${workId}`)?.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
  setHighlightedQuote(workId);
  setTimeout(() => setHighlightedQuote(null), 1500);
}

function jumpToCite(workId: string) {
  document.getElementById(`cite-${workId}-0`)?.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
  setHighlightedCite(workId);
  setTimeout(() => setHighlightedCite(null), 1500);
}
```

`<CitationBadge onClick={() => jumpToQuote(workId)}>` и
`<CitedQuote onClick={() => jumpToCite(workId)}>` получают эти
коллбеки.

Важная деталь — **клик-семантика бейджа сохраняется как есть**:
обычный клик = открыть Reading Room (через существующий `<Link>`).
Прыжок к pull-quote триггерится **наведением** (`onMouseEnter`) — то
же событие, что уже триггерит tooltip-preview из app-day-23. Оба
поведения сосуществуют: за полсекунды наведения tooltip всплывает над
бейджем (быстрый peek без скролла), параллельно pull-quote панель
прокручивает соответствующий пассаж в центр (для тех, кто хочет
читать пассаж рядом). Кому нужна **полная** работа — клик ведёт в
Reading Room, как и раньше.

Симметрия в обратную сторону: в pull-quote panel **клик** на
карточке скроллит к первому появлению `[mn10]` в тексте ответа и
кратко подсвечивает бейдж. Здесь клик уместен — карточка не несёт
своей нагрузки «открыть Reading Room» (для этого внутри карточки
есть отдельная ссылка «Open in Reading Room»).

### 5. Fallback при пустом citations[]

Что если LLM ответила, но не процитировала ничего? Два сценария:

- **No-sources answer** (retrieval не нашёл релевантного — LLM
  декларирует «не могу ответить по корпусу»). `response.answer === ""`.
  В этом случае `<AnswerView/>` уже сам показывает заглушку «No
  sources matched this query». PullQuotePanel рендерим как `null` —
  показывать нечего.
- **LLM declined to cite** (есть answer, но в нём ни одного `[xyz]`-
  маркера; редкий сбой prompt'а). `citations.length === 0`, но
  `sources.length > 0`. Показываем строку: «No quotes used in the
  answer — see retrieved sources below» и **по умолчанию открываем**
  disclosure-секцию retrieved'ов. Так transparency не теряется.

```typescript
if (response.answer.trim() === "") return null;
if (cited.length === 0) {
  return (
    <aside>
      <p className="text-xs text-muted-foreground">No quotes used in the answer.</p>
      <details open>
        <summary>Retrieved sources ({sources.length})</summary>
        {/* slim cards */}
      </details>
    </aside>
  );
}
```

### 6. Mobile responsive

Сейчас в `web/app/chat/page.tsx` есть `<section className="grid gap-8
lg:grid-cols-[1fr_280px]">` — на узком экране (`< lg`, ~1024px) grid
схлопывается в одну колонку и `SourcesPanel` уезжает **под** ответ.
Это поведение оставляем для PullQuotePanel: на mobile панель — это
просто блок ниже ответа.

Two-way anchoring продолжает работать, потому что `scrollIntoView`
работает с любым layout'ом — он просто скроллит **страницу**
(на mobile у нас один общий вертикальный поток, scroll просто едет
вниз к pull-quote). Highlight-подсветка тоже ничему не противоречит.

Один тонкий момент: на mobile «справа от ответа» становится «после
ответа», и pull-quote panel **дублирует** контент, который уже виден
рядом с citation-бейджем при tap (мобильный аналог hover'а из
app-day-23 — пока не реализован, но запланирован, см. концепт 20).
До реализации mobile-tooltip это **наоборот хорошо**: на mobile
hover'а нет, а pull-quote-блок ниже — это и есть способ verification.

## Что НЕ делаем в этом дне

| Тема | Куда |
|---|---|
| Quote highlighting в Reading Room (приехал по `#segment_id` — сразу подсвечен) | отдельный день, app-day-30+; здесь только в чате |
| Per-citation feedback («edit this quote» / «contest this claim») | вне MVP, после Reading Room highlighting |
| ML-faithfulness scoring (автоматическая оценка «совпадает ли claim с pull-quote») | rag-day-30+ — это отдельный пайплайн с NLI-моделью, см. roadmap |
| Pull-quote highlight внутри passage'а (подсветить точное предложение, на котором держится claim) | требует span-level annotation от LLM; rag-day-32+ |
| Multi-quote с разных segment'ов одной работы | сейчас берём highest-score segment per work_id (как в hover-preview); если важно показать оба mn10:8.1 и mn10:12.3 — отдельный день, обсуждаемо |
| Copy-quote button (скопировать пассаж в буфер) | mini-feature, можно сделать вместе если время есть; иначе app-day-29 polish |
| Print-friendly layout (печать с сохранением pull-quote'ов) | вне scope MVP |

## Тесты

В проекте сейчас **нет vitest-инфраструктуры на frontend'е** — только
jsdom через storybook у компонентов нет, и vitest-config не настроен.
Это **намеренный gap** (см. `web/package.json`): первый день, который
требует frontend-unit-теста — поднимет vitest. Этот день — **не он**:
unit-тестируем только pure-function через node, остальное проверяем
вручную по чеклисту в «Как проверить локально».

| # | Что | Где | Тип |
|---|---|---|---|
| 1 | `parseAnswerCitations` уже даёт корректный subset (regression-check) | `web/lib/__tests__/citations.test.ts` (если есть) | существующий, не меняется |
| 2 | `citedSourcesInOrder(answer, sources, citations)` — pure-function | `web/lib/__tests__/citedSourcesInOrder.test.ts` (новый) | **node script**, без vitest: запуск через `tsx` или `node --import tsx/esm` |
| 3 | `citedSourcesInOrder` — fallback `[mn99]` (галлюцинация в citations, нет в sources) → отфильтрован | там же | unit |
| 4 | Click-anchor scroll/highlight | вручную по чеклисту | manual |
| 5 | Mobile responsive — панель уезжает вниз | вручную по чеклисту | manual |

**Follow-up** (на отдельный день, не блокирует merge): поднять vitest
+ jsdom + react-testing-library, превратить #2-3 в полноценные unit'ы,
добавить #4 как integration-тест с jsdom + `scrollIntoView` mock'ом.
Зафиксировать в roadmap'е.

## Как проверить локально

В обоих окнах PowerShell single-line.

Backend в stub-режиме (фиксированный ответ с заведомо `[mn10]` и
`[sn56.11]` в тексте; см. `src/api/_answer_stub.py`):

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

В отдельном окне — frontend:

```
cd C:\Users\PChia\Dharma-RAG; pnpm --filter web dev
```

Открой `http://localhost:3001/chat`, отправь любой запрос (например
«what is mindfulness?»). После завершения streaming'а проверяем
по пунктам:

1. **Subset cited.** В правой панели видно **только** те `work_id`,
   что встречаются в тексте ответа в `[...]`. Если top_k=5 retrieved'ов,
   но процитировано 2 — в панели 2 pull-quote'а наверху + disclosure
   «Other retrieved (3)» внизу.
2. **Порядок — first-appearance.** Если в ответе сначала `[sn56.11]`,
   потом `[mn10]` — в панели сверху `sn56.11`, под ним `mn10`. Если
   наоборот — баг в `citedSourcesInOrder`.
3. **Полный текст.** В каждом pull-quote'е виден **полный пассаж** (не
   обрезанные 3 строки snippet'а). Для длинных — collapse-кнопка
   «Развернуть».
4. **Click bage → scroll quote.** Кликни в тексте ответа на бейдж
   `[mn10]` — pull-quote `mn10` плавно прокручивается в центр панели,
   на ~1.5 секунды подсвечивается фоном. Cmd/Ctrl-клик или
   middle-click на том же бейдже — открывает `/read/mn10` в новом
   табе (Reading Room).
5. **Click quote → scroll cite.** В панели кликни по pull-quote
   `mn10` — страница плавно скроллит к первому `[mn10]` в тексте
   ответа, бейдж кратко подсвечивается.
6. **Other retrieved disclosure.** Кликни по `<details>`-блоку «Other
   retrieved (n)» внизу панели — раскрывается список slim-карточек
   retrieved'ов которые **не** были процитированы. Кликни ещё раз —
   сворачивается.
7. **No-cite fallback.** Задай запрос, на который stub отвечает без
   `[xyz]`-маркеров (если такой stub-сценарий есть; иначе пропускаем
   и проверяем на реальном backend'е). Ожидание: панель показывает
   «No quotes used in the answer» и open-by-default список retrieved'ов.
8. **Mobile.** Сожми окно браузера до ширины ≤1024px (или DevTools
   → Toggle device toolbar) — панель уезжает **под** ответ. Click-
   anchor продолжает работать (page scrolls).

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| `web/components/chat/PullQuotePanel.tsx` | **новый** | основная панель, рендерит cited + disclosure для retrieved |
| `web/components/chat/CitedQuote.tsx` | **новый** | одна карточка pull-quote'а с adaptive-collapse полного текста |
| `web/lib/citedSourcesInOrder.ts` | **новый** | pure-function: subset по `citations`, sort по first-appearance в answer |
| `web/lib/__tests__/citedSourcesInOrder.test.ts` | **новый** | unit-тест pure-function (node-runner, без vitest) |
| `web/components/chat/CitationBadge.tsx` | изменён | добавлен `id` для anchor scroll, опциональный `onClick` для jump-to-quote |
| `web/components/chat/AnswerView.tsx` | изменён | прокидывает `onCitationClick` callback, считает `occurrenceIndex` для дубликатов |
| `web/app/chat/page.tsx` | изменён | заменяет `<SourcesPanel/>` на `<PullQuotePanel/>`, держит lifted state `highlightedQuote` / `highlightedCite` |
| `web/components/chat/SourcesPanel.tsx` | **не удаляем**, не используем в `/chat` | оставляем в репо — может пригодиться для admin/debug-страницы; помечаем JSDoc-комментарием «replaced in chat by PullQuotePanel, kept for debug views» |

Backend и OpenAPI **не трогаем** — поле `citations` уже есть в
`AnswerResponse` с app-day-22 (см. `web/lib/api-types.ts:210`).

## Связанные документы

- [docs/concepts/19-chat-mvp.md](19-chat-mvp.md) — chat MVP (база для
  любого chat-polish дня).
- [docs/concepts/20-citation-hover-preview.md](20-citation-hover-preview.md)
  — hover-preview через `<Tooltip>`. Tooltip **остаётся** — он хорош
  для быстрого peek'а на бейдже без скролла; pull-quote — для
  параллельного чтения. Они не конфликтуют, дополняют.
- [docs/concepts/21-confidence-indicator.md](21-confidence-indicator.md)
  — confidence-индикатор тоже про anti-hallucination, но другой
  подход: «насколько модель уверена в целом», а не «откуда конкретный
  claim». Оба сигнала рядом дают хорошую общую картину.
- [docs/concepts/22-sse-streaming.md](22-sse-streaming.md) — pull-quote
  panel рендерится **после** done-event (ему нужен финальный
  `citations[]`); во время streaming'а panel либо пустая, либо
  показывает текущий частичный subset (поведение под review).
- [docs/concepts/12-parent-child-retrieval.md](12-parent-child-retrieval.md)
  — почему `Source.text` это broader passage (parent-chunk), а не
  snippet.
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) —
  app-day-27 в общем плане.
