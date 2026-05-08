# 25 — BYOK UI (app-day-28)

> **⏸ Статус: deferred (отложен на неопределённый срок).** Решение
> 2026-05-02. BYOK-модель создаёт слишком высокий onboarding-барьер
> для дхарма-аудитории (не-tech): большинство не заведут OpenRouter-
> аккаунт ради одного приложения. В production пока крутится единый
> `OPENROUTER_API_KEY` владельца проекта. Концепт остаётся в репо как
> готовый design — вернёмся к нему когда public launch будет
> финансироваться через гранты / sponsorship / donations, и BYOK
> станет **опциональным** upgrade-path для power-users (а не
> единственным способом пользоваться сервисом). До этого приоритет —
> улучшение качества и охвата корпуса.

> **Исходный статус:** `proposed (concept review)`. Объединяет старые
> app-day-12 (validate), app-day-13 (cookie session), app-day-14
> (forward в RAG-слой) из `docs/APP_DEVELOPMENT_PLAN.md` в один день.
>
> **Что фиксируется здесь:** UX-flow ввода ключа, инвариант «ключ
> никогда не на сервере персистентно», шифрование cookie, валидация
> через реальный вызов в провайдер, маскирование в логах. Backend
> добавляет один middleware + два роутера; frontend — одну страницу
> настроек + баннер в layout.

## Зачем

Сейчас `OPENROUTER_API_KEY` лежит в `.env` сервера (см.
[src/config.py](../../src/config.py), строки около 37) и используется
для всех `/api/answer`-запросов. Это работает для **self-hosted**
(один разработчик поднял у себя — он же платит за свои вызовы).

Через несколько недель планируется **public launch** — открыть instance
для community (буддистов, исследователей канона). И вот тут начинается
проблема экономики. На community-pricing каждый ответ стоит ~$0.003
(модель + reranker + хост-косты). На объёме 10k запросов/месяц — это
30 USD; на объёме 100k — 300 USD. Для бесплатного некоммерческого
проекта это **разорение** или гонка за донатами.

Три варианта как из этого выйти:

1. **Сервер платит за всех.** Невозможно экономически (см. выше).
2. **Подписочная модель.** Нужны: биллинг (Stripe), KYC (anti-fraud),
   налоги, support по платежам. Это **отдельный 2-месячный проект** и
   совсем другая категория ответственности (хранить платёжные данные
   пользователей).
3. **BYOK** (Bring Your Own Key — «принеси свой ключ»). Пользователь
   приносит свой OpenRouter-ключ, мы только прокси с retrieval'ом и
   prompt'ом. Проект остаётся бесплатным, экономика сходится — каждый
   платит за свои запросы напрямую провайдеру. **Это путь.**

BYOK уже зашит в архитектуру как **жёсткий инвариант**. Из
[docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) (строки
281-285):

> «BYOK — жёсткий инвариант. Ключ никогда не персистится: только
> httpOnly cookie на фронте + `X-User-LLM-Key` header в internal вызов
> в RAG-слой. Логирование маскируется middleware-ом.»

И в [ADR-0001](../decisions/0001-phase1-architecture.md) BYOK помечен
как обязательное условие public launch'а.

Аналогия — как работает **Cursor** или **GitHub Copilot Custom**: ты
приносишь свой OpenAI API key, инструмент его использует, но никогда
не сохраняет на своих серверах. То же самое здесь.

## Что такое BYOK

Несколько терминов, которые встретятся ниже — расшифровываем сразу.

**API key** — длинная строка-секрет вида `sk-or-v1-1234567890abcdef...`,
которую LLM-провайдер (в нашем случае OpenRouter) выдаёт пользователю
при регистрации. По этому ключу провайдер опознаёт **кто платит**: за
каждый вызов через API списываются деньги со счёта владельца ключа.
Ключ — это в буквальном смысле **доступ к чужому кошельку**, поэтому
обращаться с ним надо как с паролем от банк-карты.

**httpOnly cookie** — кука (маленький файлик с данными, который
браузер хранит для конкретного сайта и автоматически прикладывает к
каждому запросу), помеченная флагом `HttpOnly`. Этот флаг означает:
**JavaScript не может прочитать значение** — только сервер видит его,
когда браузер прикладывает cookie к HTTP-запросу. Защищает от **XSS**
(cross-site scripting — атака, при которой злоумышленник внедряет на
страницу свой JS, например через комментарий с `<script>`; обычные
куки и localStorage он бы прочитал, httpOnly cookie — нет).

**encrypted** (зашифровано) — значение cookie не лежит plaintext'ом, а
шифруется симметричным ключом сервера. Аналогия — **запечатанный
конверт** (sealed envelope): на конверте написано «Bob, mailbox 7», но
прочитать содержимое можно только тем ключом, который у нас в сейфе.
Если cookie утечёт (через дыру в browser extension, через cloud
sync между устройствами, через публичный wifi с прокси — реальные
сценарии), злоумышленник получит зашифрованный blob, не plaintext
OpenRouter-ключ. Без серверного secret'а расшифровать нельзя.

**Validate-эндпойнт** — наш `POST /api/keys/validate`, в который
пользователь отдаёт ключ, мы делаем **реальный** запрос в OpenRouter
(`GET /models` с этим ключом) и проверяем что ответ 200 OK. Аналогия —
**пропуск в библиотеку**: библиотекарь не верит на слово, что у тебя
есть читательский билет, он берёт его и сверяет с базой. Если база
говорит «билет валиден» — пропускает. Если 401 — отказывает.

## User flow

Пошагово, от первой загрузки `/chat` до отправки запроса.

1. **Первый визит.** Пользователь открывает `/chat`. Cookie
   `dharma_byok` нет → backend на любой запрос к чату вернул бы 402.
   Frontend это знает (запросив `GET /api/keys/me` на mount layout'а)
   и в шапке (`SiteHeader` или верхушка layout'а) рендерит **баннер**:
   красная полоска «Add your OpenRouter key to start chatting →».
2. **Клик по баннеру** ведёт на `/settings/keys` — отдельную страницу
   настроек ключа.
3. **Форма на странице настроек:**
   - Provider dropdown — на MVP единственный пункт `OpenRouter`.
   - Key input — `<input type="password">` (значение скрыто звёздочками
     при вводе, как пароль).
   - Кнопка **Validate**.
4. **Backend `POST /api/keys/validate`** делает реальный вызов
   `GET https://openrouter.ai/api/v1/models` с
   `Authorization: Bearer <key>`. ~200ms на round-trip. Если 401/403
   — ключ битый. Если 200 — принимаем.
5. **Если valid:** backend ставит httpOnly cookie `dharma_byok`
   (encrypted JSON `{provider, key_encrypted, key_hash_prefix}`) и
   возвращает `{valid: true, masked: "sk-or-v1-•••a23"}`. Frontend
   делает `router.push('/chat')`.
6. **На `/chat`** баннер сменяется на зелёную пилюлю:
   «Using your OpenRouter key (sk-or-v1-•••a23)» с кнопкой «Change
   key».
7. **Запрос в чате** (`POST /api/answer/stream`) браузер автоматически
   прикладывает cookie `dharma_byok` → middleware расшифровывает →
   кладёт в request-scoped contextvar → `AnswerService.answer()`
   достаёт ключ из contextvar и передаёт в `AsyncOpenRouterLLM` через
   per-call параметр.

Если на шаге 4 backend вернул `valid: false` — форма показывает
красный alert «OpenRouter rejected this key (401). Check that you
copied it fully, no spaces.» Cookie не ставится, пользователь
остаётся на `/settings/keys`.

## Архитектура и поток ключа

```
browser cookie dharma_byok (encrypted)
        ↓ (на каждом запросе автоматически)
FastAPI middleware (src/api/byok.py)
        ↓ decrypt → plaintext key
request-scoped contextvar (byok_key)
        ↓ get() в endpoint
AnswerService.answer(api_key_override=byok_key)
        ↓
AsyncOpenRouterLLM.complete(api_key=byok_key)
        ↓
https://openrouter.ai/api/v1/chat/completions
        Authorization: Bearer <user's key>
```

Ключевой момент — **request-scoped contextvar**. Что это и почему не
глобальная переменная.

**ContextVar** (из стандартной библиотеки `contextvars`) — переменная,
значение которой автоматически изолируется по «контексту исполнения».
В FastAPI/asyncio каждый HTTP-запрос обрабатывается в своём asyncio
task'е, и каждый task имеет **свой** view на ContextVar. Если в task'е
A установить `byok_key.set("alice's key")`, то из task'а B (другого
запроса, который идёт параллельно) `byok_key.get()` вернёт **не**
ключ Алисы, а либо default, либо то что туда положил task B.

Аналогия — **столики в ресторане**. Глобальная переменная — это общий
стол посередине зала, куда все официанты кладут заказы; в час пик
заказ Алисы случайно отнесут Бобу. ContextVar — это **отдельный
поднос для каждого столика**: у каждого официанта свой поднос для
своего стола, перепутать невозможно.

Почему именно contextvar, а не передача параметром через все слои:
ключ нужен в `AsyncOpenRouterLLM.complete()`, до которого 3-4 уровня
вызовов от endpoint'а (`endpoint → AnswerService → answer pipeline →
LLM client`). Тащить `api_key` через каждый уровень — много
копипасты и легко забыть в одной из перегрузок. ContextVar заводит
«невидимый канал» от middleware'а напрямую к LLM-клиенту.

## Ключевые решения

### 1. Какие провайдеры поддерживаем на MVP?

**Только OpenRouter.** Причины:

- В коде уже есть **единственный** LLM-клиент —
  [`AsyncOpenRouterLLM`](../../src/answer/llm.py). Он работает по
  OpenAI-совместимому протоколу, который OpenRouter эмулирует. Не
  нужны новые клиенты.
- OpenRouter — это **роутер** (router — посредник, который под одним
  ключом даёт доступ к 100+ моделям разных провайдеров: Anthropic
  Claude, OpenAI GPT, DeepSeek, Moonshot, Mistral и т.д.). Пользователь
  получает **весь зоопарк** моделей с одним секретом и одним
  биллинг-аккаунтом. Это удобнее, чем заводить отдельные ключи в
  каждом провайдере.
- Не пишем provider-specific форматы. У Anthropic свой header
  (`x-api-key`), у OpenAI свой (`Authorization: Bearer`), у каждого
  свои quirk'и в request/response shape'ах. Поддержка трёх провайдеров
  напрямую = три отдельных клиента + три validate-эндпойнта + сложная
  fallback-логика «если у юзера Anthropic-ключ, выбираем Claude;
  если OpenAI-ключ — GPT». На MVP это лишний код.

**На будущее (app-day-44+):** если найдётся пользователь, который
принципиально не хочет идти через OpenRouter (privacy concerns: «не
хочу чтобы запрос шёл через посредника»), добавим прямые
Anthropic/OpenAI клиенты. Но это **после** public launch'а, когда
будет реальный спрос.

### 2. Cookie или localStorage?

**httpOnly cookie.** Причины:

- **localStorage** доступен из JavaScript (`localStorage.getItem`).
  Любой XSS вытягивает ключ одной строчкой. На странице чата с
  user-generated контентом (пусть даже только в виде запросов в
  textarea) поверхность атаки достаточная.
- **Cookie с флагами `HttpOnly + Secure + SameSite=Lax`:**
  - `HttpOnly` — JS читать не может → XSS-устойчивость.
  - `Secure` — кука отправляется только по HTTPS, не утечёт через
    plaintext-запрос.
  - `SameSite=Lax` — защита от **CSRF** (cross-site request forgery —
    когда вредоносный сайт заставляет браузер тихо сделать запрос на
    наш сайт от имени залогиненного пользователя; cookie бы автоматом
    приложилась). С `Lax` cookie не отправится при cross-site POST.
- Браузер автоматически кладёт cookie в каждый запрос на наш origin —
  не нужно дополнительно прокидывать через JavaScript.

Минус cookie — **сложнее тестировать**: для интеграционных тестов
нужен настоящий браузер или TestClient с управлением сессией. Но
плюсы (security) перевешивают.

### 3. Шифровать значение в cookie?

**Да.** Используем **Fernet** из библиотеки `cryptography` —
высокоуровневая обёртка над AES-128-CBC + HMAC-SHA256, рекомендуемый
default для symmetric encryption (симметричное шифрование — один и
тот же ключ и шифрует, и расшифровывает; противоположность
асимметричному с public/private key parами). Fernet добавляет
встроенную проверку integrity (HMAC), так что подделка значения
невозможна без серверного секрета.

Серверный ключ — env var `BYOK_COOKIE_SECRET` (32 байта, base64-url
encoded; генерируется один раз через `Fernet.generate_key()`).

Зачем шифровать, если уже httpOnly:

- **Browser extension с broad permissions** может видеть cookie
  (расширения работают на уровне выше, чем JS страницы).
- **Cloud sync между устройствами** (Chrome Sync, iCloud Keychain)
  переносит cookies. Если у пользователя другой девайс
  компрометирован — cookie-store туда уехал.
- **Local backup** браузерного профиля попадает в облачный backup
  ноутбука. Утекает зашифрованный blob — не plaintext API key.

Без секрета сервера расшифровать нельзя. Это **defense in depth**
(многослойная защита: даже если внешний слой пробит, внутренний
держит).

Проверить надо: библиотека `cryptography` уже в `pyproject.toml`? Если
нет — добавить в этот же day.

### 4. Validation strategy

Не паттерн-чек регуляркой (`^sk-or-v1-[a-z0-9]{48}$`), а **реальный
вызов**: `GET https://openrouter.ai/api/v1/models` с
`Authorization: Bearer ${key}`.

Плюсы реального вызова:

- Ловим **expired** ключи (которые пользователь отозвал у себя в
  OpenRouter dashboard).
- Ловим **typo'нутые** ключи (скопировал с лишним пробелом или потерял
  символ — паттерн прошёл бы, реальный API скажет 401).
- Ловим **rate-limited** аккаунты (если у пользователя баланс 0 —
  узнаем сразу, а не через 30 секунд после первого запроса в чат).

Минус — **~200ms задержка** на validate-кнопке. Это нормально:
пользователь нажал «Validate» один раз, готов подождать; UX —
кнопка показывает spinner «Checking…» в течение этого времени.

### 5. «Demo limited» fallback?

Старый план (app-day-44 в `APP_DEVELOPMENT_PLAN.md`) предлагал
fallback-режим: **без BYOK** — 15 запросов в день на IP, наш ключ.
Своего рода «попробуй, и если понравится — заведи свой ключ».

Рекомендация — **выкидываем**. Причины:

- Требует **rate-limit middleware** (app-day-45) — отдельный слой с
  Redis-counter'ом по IP. Не делается одновременно с BYOK.
- Сервер **всё равно платит** за demo-запросы. Экономика та же что
  без BYOK, только ограниченная сверху. На 1000 уникальных IP в день
  ⋅ 15 запросов = 15k/день, ~$45/день, $1350/месяц. Не сходится.
- **Open-source self-hosted** instance — не наша забота. Каждый кто
  хочет «попробовать без своего ключа» может склонировать репо и
  поднять у себя со своим OPENROUTER_API_KEY в `.env`. Это уже
  **есть** как путь.
- Public launch с явным сообщением «BYOK only» — это **честно**.
  Альтернатива (15 запросов demo) ставит юзера в ситуацию «я
  попробовал, мне понравилось, но дальше нужно куда-то регистрироваться
  — а зачем тогда я пробовал». Frustration-loop.

**Что вместо** — `/chat` для незалогиненного пользователя показывает
**landing-секцию** «To start, add your OpenRouter key» с:
- объяснением зачем это (одна короткая строка про экономику);
- ссылкой на регистрацию в OpenRouter (deeplink на их signup);
- кнопкой «Add key» ведущей на `/settings/keys`.

Self-hosted сценарий покрывается env-переменной `BYOK_REQUIRED=false`
— тогда сервер использует свой `OPENROUTER_API_KEY` из `.env`.

**Если решение пересмотрено** — добавить fallback можно постфактум
без изменения public API: middleware проверяет
`if byok_key.get() is None and rate_limit_ok(ip): use_server_key()`.

### 6. UI индикатор какой ключ используется

В шапке (top-level layout) — **пилюля** (компактный закруглённый
бейдж): «OpenRouter • sk-or-v1-•••a23» с кнопкой «×» для logout-key.

**Маска** показывает первые 8 символов (`sk-or-v1`) + последние 3
(`a23`), середина свёрнута в `•••`. Зачем такой формат:

- **Префикс** `sk-or-v1` визуально подтверждает что это
  OpenRouter-ключ (а не случайно вставленный Anthropic'овский).
- **Последние 3 символа** позволяют пользователю **сверить** что это
  «тот самый» ключ который он добавил (не подменили middleware'ом, не
  взяли стрый из cookie cache).
- Полностью **не показываем** — защита от **shoulder surfing**
  (подсматривание через плечо в кафе/самолёте) и от случайных
  скриншотов.

Кнопка «×» вызывает `POST /api/keys/clear` → cookie удаляется → баннер
снова красный «Add key».

### 7. Маскирование в логах

Если в логи случайно попадёт plaintext-ключ — это **утечка**, по
серьёзности равная утечке пароля пользователя. Логи имеют свойство
уезжать в LogDNA / Sentry / Loki / GitHub Actions stdout, и ключ из
них не вытащить обратно.

**Защита:** добавляем **structlog processor** в
[src/logging_config.py](../../src/logging_config.py). Processor —
функция, которая получает `event_dict` (словарь со всеми полями
лог-события) перед сериализацией в JSON и может его преобразовать.

Наш processor рекурсивно обходит event_dict и для ключей из
sensitive-списка (`api_key`, `byok_key`, `Authorization`, `x-api-key`,
`X-User-LLM-Key`) заменяет значение на маску `sk-•••a23` (первые 4 +
последние 3 символа).

Тест:

```python
log.info("answer.llm_call", api_key="sk-or-v1-1234567890abcdef")
# ожидаемый JSON output:
# {"event": "answer.llm_call", "api_key": "sk-o•••def", ...}
```

Прозой: пишется обычный structured log с полем `api_key`, в выходе
JSON значение поля **уже** замаскировано. Дополнительной осторожности
от автора кода не требуется — processor работает автоматически.

## API контракт

Три endpoint'а под `/api/keys`.

### `POST /api/keys/validate`

Pydantic-схемы:

```python
class ValidateKeyRequest(BaseModel):
    provider: Literal["openrouter"]  # MVP: только openrouter
    key: str = Field(min_length=20, max_length=200)

class ValidateKeyResponse(BaseModel):
    valid: bool
    message: str | None = None  # human-readable если invalid
    masked: str | None = None   # "sk-or-v1-•••a23" — для UI индикатора
```

Поведение:

- Делаем `httpx.AsyncClient.get('https://openrouter.ai/api/v1/models',
  headers={'Authorization': f'Bearer {key}'}, timeout=5.0)`.
- Если 200 → шифруем `key` через Fernet, пакуем в JSON
  `{provider, key_encrypted, masked}`, ставим как cookie
  `dharma_byok` с флагами `HttpOnly + Secure + SameSite=Lax + Path=/`,
  возвращаем `{valid: true, masked: "sk-or-v1-•••a23"}`.
- Если 401/403 → возвращаем `{valid: false, message: "OpenRouter
  rejected this key (401). Check that you copied it fully."}`. Cookie
  не ставится. **HTTP-статус ответа = 200** (не 401), потому что наш
  endpoint работает корректно — это **результат проверки**, не ошибка
  endpoint'а. Если бы мы вернули 401, frontend-обработка ошибок
  спутала бы это с «у тебя нет доступа к нашему API».
- Если timeout / 5xx у OpenRouter → возвращаем `{valid: false,
  message: "OpenRouter is unreachable. Try again in a moment."}`.

### `POST /api/keys/clear`

Тело пустое. Backend ставит `Set-Cookie: dharma_byok=; Max-Age=0;
Path=/; HttpOnly; Secure; SameSite=Lax` (стандартный способ удалить
cookie — переустановить с прошедшим сроком). Возвращает 200 с пустым
body.

Frontend вызывает после клика на «×» в пилюле → перерендерит баннер
в красное «Add key».

### `GET /api/keys/me`

Если cookie есть — расшифровывает, отдаёт `{provider: "openrouter",
masked: "sk-or-v1-•••a23"}`.
Если нет — отдаёт `{provider: null, masked: null}` (не 404 — это
**нормальное** состояние, не ошибка).

Frontend дёргает на mount layout'а, чтобы понять какой баннер
показывать.

## Frontend

Файлы:

- [`web/app/settings/keys/page.tsx`](../../web/app/settings/keys/page.tsx)
  — server-component-обёртка, рендерит `<KeyForm/>`. Можно сделать и
  чисто client component — без разницы для MVP.
- [`web/components/byok/KeyForm.tsx`](../../web/components/byok/KeyForm.tsx)
  — controlled component (controlled — react-форма где value и
  onChange управляются state'ом, а не DOM'ом; противоположность —
  uncontrolled с `useRef`). Provider dropdown + key input
  `type="password"` + Validate button + alert-area для ошибок. После
  `valid: true` → `router.push('/chat')`.
- [`web/components/byok/KeyBanner.tsx`](../../web/components/byok/KeyBanner.tsx)
  — баннер для shell'а. На mount → `getKeyStatus()`. Render:
  - Если `provider === null` — красный баннер «Add your OpenRouter key
    to start chatting →» (link на `/settings/keys`).
  - Если `provider === 'openrouter'` — зелёная пилюля «OpenRouter •
    sk-or-v1-•••a23» + кнопки «Change key» (link) и «×» (`clearKey()`).
- [`web/lib/api-client.ts`](../../web/lib/api-client.ts) — добавляем
  `validateKey(req)`, `clearKey()`, `getKeyStatus()`.

### Где разместить баннер

Два варианта:

- **A. Только в `/chat`-странице.** Минимально, баннер не отвлекает на
  Reading Room и Search. Минус: пользователь приходит на сайт через
  главную, видит чат-promo, кликает «Try chat» — попадает на чат, и
  только там узнаёт что нужен ключ. Поздно.
- **B. Top-level layout (`web/app/layout.tsx`).** Виден на всех
  страницах. Плюс: пользователь в любой момент знает «я залогинен»
  или «нет ключа». Минус: если читаешь Reading Room и не собираешься
  использовать чат — баннер раздражает.

**Рекомендация — B (top-level), dismissable** (закрываемый — у баннера
есть «×», после клика прячется до конца сессии через
`sessionStorage`). При попытке отправить запрос на `/chat` без ключа
backend вернёт **402 Payment Required** → frontend ловит, **сбрасывает**
dismiss-флаг и снова показывает баннер. То есть в основном flow «без
ключа в чате не дашь забыть», но не мешает на других страницах.

## Backend

Файлы:

- **[`src/api/_byok_crypto.py`](../../src/api/_byok_crypto.py)** —
  утилитный модуль. Две функции:
  - `encrypt(plaintext: str) -> str` — Fernet.encrypt с серверным
    ключом из settings.
  - `decrypt(token: str) -> str | None` — Fernet.decrypt; на
    `InvalidToken` возвращает `None` (а не raise) — потому что cookie
    может быть подделана/устарела, это **ожидаемая ошибка**, не
    crash-condition.

- **[`src/api/byok.py`](../../src/api/byok.py)** — middleware. Один
  ContextVar:

  ```python
  byok_key: ContextVar[str | None] = ContextVar("byok_key", default=None)
  ```

  Middleware на каждом запросе:
  1. Читает cookie `dharma_byok` из `request.cookies`.
  2. Если есть — `_byok_crypto.decrypt()` → `dict` с `provider, key`.
  3. `byok_key.set(key)` → ключ доступен через `byok_key.get()` в
     любом downstream-коде до конца этого запроса.
  4. После `await call_next(request)` reset (хотя contextvar и так
     изолируется per-task, явный reset — good hygiene).

- **[`src/api/keys.py`](../../src/api/keys.py)** — router с тремя
  endpoint'ами выше. Зависит от `httpx.AsyncClient` (для validate-
  вызова в OpenRouter) — инжектируется через FastAPI Depends, чтобы в
  тестах подменять моком.

- **[`src/api/app.py`](../../src/api/app.py)** — register middleware и
  router в FastAPI app.

- **[`src/api/answer.py`](../../src/api/answer.py)** — endpoint
  `/api/answer` и `/api/answer/stream`. На входе:

  ```python
  byok = byok_key.get()
  if byok is None and settings.byok_required:
      raise HTTPException(
          status_code=402,
          detail="BYOK required for /api/answer",
      )
  return await service.answer(req, api_key_override=byok)
  ```

  Статус **402 Payment Required** — нестандартный, но семантически
  идеальный: «доступ есть, метод есть, но нужна оплата». Frontend
  ловит 402 → редирект на `/settings/keys`.

- **[`src/answer/service.py`](../../src/answer/service.py)** —
  `AnswerService.answer(req, *, api_key_override: str | None = None)`.
  Передаёт в LLM-клиент.

- **[`src/answer/llm.py`](../../src/answer/llm.py)** —
  `AsyncOpenRouterLLM.complete(messages, *, api_key: str | None =
  None)`. Per-call параметр (а не построение нового клиента
  per-request) — клиент инициализируется один раз при старте app, и
  per-call просто override'ит header `Authorization`. Это дешевле:
  переиспользуется HTTP-pool, не пересоздаются TCP-соединения.

- **[`src/config.py`](../../src/config.py)** — добавить:
  - `byok_cookie_secret: str = ""` — Fernet-ключ. Если пустой и
    `byok_required=True` — startup hook поднимает `RuntimeError`
    («BYOK_COOKIE_SECRET must be set when BYOK_REQUIRED=true»).
  - `byok_required: bool = True` — default `True` для production,
    можно отключить для self-hosted dev (тогда сервер работает на
    своём `OPENROUTER_API_KEY`).

- **[`src/logging_config.py`](../../src/logging_config.py)** —
  masking-processor (см. решение 7).

## Что НЕ делаем в этом дне

| Тема | Куда |
|---|---|
| Multiple providers (Anthropic, OpenAI direct) | app-day-44+ (после launch'а если нужно) |
| «Demo limited» fallback на IP | выбросили, см. решение #5 |
| Per-user usage tracking / billing | вне scope (мы не платим — нечего трекать) |
| Key rotation alerts («твой ключ устарел, обнови») | вне MVP, требует cron + state на сервере |
| Server-side key vault (HashiCorp Vault, AWS KMS) | сервер не хранит ключ вообще, vault не нужен |
| Mobile (PWA / Capacitor) — secure storage через Keychain/Keystore | Phase 7+ |
| Rate-limit per BYOK key (защита от abuse-аккаунтов) | app-day-45 |
| OAuth-flow с OpenRouter (без копипасты ключа) | если OpenRouter заведёт — отдельный day; пока вручную |

## Тесты

| # | Что | Где | Тип |
|---|---|---|---|
| 1 | `_byok_crypto.encrypt → decrypt` round-trip | `tests/unit/api/test_byok_crypto.py` | unit |
| 2 | `_byok_crypto.decrypt(invalid)` → None (не raise) | там же | unit |
| 3 | `validate_key` happy path с моком httpx (200 OK) | `tests/unit/api/test_keys.py` | unit |
| 4 | `validate_key` invalid (httpx 401) → `valid=False, message=...` | там же | unit |
| 5 | masking processor — `api_key="sk-or-v1-1234567890abcdef"` → `"sk-o•••def"` в JSON | `tests/unit/test_logging_config.py` | unit |
| 6 | middleware: cookie set → contextvar populated в downstream-обработчике | `tests/integration/api/test_byok_middleware.py` | integration (TestClient) |
| 7 | `/api/answer` без cookie в real-mode + `byok_required=true` → 402 | там же | integration |
| 8 | `KeyForm` submit happy/error path | follow-up vitest | manual для MVP |

Тест #5 важен: легко **забыть** маскирование при добавлении нового
поля. Лучше зафиксировать список masked-keys тестом, чтобы любое
регрессионное изменение processor'а ловилось CI.

## Как проверить локально

PowerShell single-line, как везде в проекте.

```
.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Скопируй вывод (44-char base64-url-encoded) в `.env` как
`BYOK_COOKIE_SECRET=...`.

Запусти backend:

```
$env:RAG_BACKEND="real"; $env:BYOK_REQUIRED="true"; .\.venv\Scripts\activate.ps1; uvicorn src.api.app:app --reload --port 8000
```

Validate своим OpenRouter-ключом:

```
Invoke-RestMethod -Uri http://localhost:8000/api/keys/validate -Method POST -Body '{"provider":"openrouter","key":"sk-or-v1-..."}' -ContentType 'application/json' -SessionVariable s
```

Проверь что cookie установилась:

```
$s.Cookies.GetAllCookies() | Where-Object { $_.Name -eq "dharma_byok" }
```

Сделай `/api/answer` с этой же сессией → должно работать без 402:

```
Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"what is dukkha?"}' -ContentType 'application/json' -WebSession $s
```

Без сессии (без cookie) → ожидаем 402:

```
try { Invoke-RestMethod -Uri http://localhost:8000/api/answer -Method POST -Body '{"query":"x"}' -ContentType 'application/json' } catch { $_.Exception.Response.StatusCode }
```

Frontend: `pnpm --filter web dev`, открой `http://localhost:3001/chat`
— баннер красный. Перейди на `/settings/keys`, введи валидный ключ,
жми Validate — редирект на `/chat`, баннер сменился на зелёную пилюлю
с маской. Отправь запрос — работает. Жми «×» в пилюле — баннер снова
красный, следующий запрос на `/chat` упадёт в 402.

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| `src/api/_byok_crypto.py` | **новый** | Fernet encrypt / decrypt с server-secret'ом |
| `src/api/byok.py` | **новый** | middleware: cookie → ContextVar |
| `src/api/keys.py` | **новый** | router с `/validate`, `/clear`, `/me` |
| `src/api/app.py` | изменён | register middleware + router |
| `src/api/answer.py` | изменён | read contextvar, pass to service, 402 if required+missing |
| `src/answer/service.py` | изменён | `api_key_override` параметр |
| `src/answer/llm.py` | изменён | per-call `api_key` параметр в `complete()` / `stream()` |
| `src/config.py` | изменён | `byok_cookie_secret`, `byok_required` |
| `src/logging_config.py` | изменён | masking processor |
| `tests/unit/api/test_byok_crypto.py` | **новый** | tests #1-2 |
| `tests/unit/api/test_keys.py` | **новый** | tests #3-4 |
| `tests/unit/test_logging_config.py` | изменён или новый | test #5 |
| `tests/integration/api/test_byok_middleware.py` | **новый** | tests #6-7 |
| `web/app/settings/keys/page.tsx` | **новый** | страница настроек |
| `web/components/byok/KeyForm.tsx` | **новый** | форма validate |
| `web/components/byok/KeyBanner.tsx` | **новый** | баннер для layout'а |
| `web/app/layout.tsx` | изменён | render `<KeyBanner/>` сверху |
| `web/lib/api-client.ts` | изменён | `validateKey`, `clearKey`, `getKeyStatus` |
| `openapi.json` | регенерируется | через `make openapi` |
| `web/lib/api-types.ts` | регенерируется | через `make typegen` |

## Открытые вопросы для approval

Эти три решения нужно подтвердить перед началом реализации.

1. **Только OpenRouter на MVP, или сразу Anthropic/OpenAI direct?**
   Рекомендация: **только OpenRouter**. Один LLM-клиент в коде, один
   роутер на 100+ моделей, не пишем provider-specific quirk'и.
   Anthropic/OpenAI direct — на app-day-44+ если будет реальный спрос.

2. **Выкидываем «demo limited» fallback или оставляем?**
   Рекомендация: **выкидываем**. Без BYOK = «no chat», на `/chat` —
   landing-секция «Add your OpenRouter key to start» с deeplink на
   регистрацию. Self-hosted сценарий покрывается env-переменной
   `BYOK_REQUIRED=false`. Альтернатива (15 запросов/день/IP) требует
   rate-limit middleware (app-day-45), сервер всё равно платит за
   demo, экономика не сходится.

3. **Где живёт KeyBanner — root layout или только `/chat`?**
   Рекомендация: **root layout, dismissable**. Виден на всех
   страницах, можно закрыть через «×» (запоминается в
   `sessionStorage` до конца сессии). При попытке отправить запрос на
   `/chat` без ключа backend вернёт 402, frontend сбросит
   dismiss-флаг — баннер всплывёт снова.

## Связанные документы

- [13 — RAG-service contract](13-rag-service-contract.md) — контракт
  `/api/query`; BYOK-ключ передаётся **между** API-слоем и RAG-слоем
  через header `X-User-LLM-Key`, не через query-вызов.
- [15 — Answer generation](15-answer-generation.md) — где
  `AsyncOpenRouterLLM` берёт api_key (после этого дня — через
  `api_key_override` параметр из contextvar'а).
- [19 — Chat MVP](19-chat-mvp.md) — chat flow в который упирается
  BYOK; без ключа `/chat` отдаёт 402.
- [22 — SSE streaming](22-sse-streaming.md) — `/api/answer/stream`
  тоже берёт ключ из contextvar (одинаково с не-streaming endpoint'ом).
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md), строки
  281-285 (инвариант BYOK) и 567-598 (старый план app-day-12/13/14,
  объединяется в этот day-28).
- [docs/decisions/0001-phase1-architecture.md](../decisions/0001-phase1-architecture.md)
  — ADR-0001, BYOK как обязательное условие public launch.
