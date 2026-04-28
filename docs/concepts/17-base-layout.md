# 17 — Базовый layout web/ (app-day-04)

> **Статус:** реализовано в app-day-04. `web/` получает theme-провайдер,
> shell-компоненты (Header / Footer), типографику под Pāli-диакритику и
> landing-page со ссылками на главные surface'ы. Reading Room сами по
> себе ещё не реализован — он Phase 2 (app-day-21+).

## Зачем

После app-day-03 у нас был type-safe API-клиент, но **web-приложение
оставалось default-stub'ом next.js**: вики-страница со ссылками на
Vercel templates. Прежде чем строить Reading Room / Search / Chat,
нужен общий каркас:

- единая `<Header/>` + `<Footer/>` на всех страницах,
- light/dark тема, переключающаяся без flash-of-unstyled-content,
- font-stack под палийские диакритики (`ā ī ū ṃ ṇ ñ ṭ ḍ ṅ ṣ ḷ`),
- landing-page, объясняющий что это и куда идти.

Это «строительные леса» — не фичи. Без них каждый следующий day
пришлось бы заново реализовывать basics.

## Что сделано

### 1. Theme provider (`next-themes`)

Установлен `next-themes@0.4.6`. Обёртка
[`web/components/theme-provider.tsx`](../../web/components/theme-provider.tsx) —
thin wrapper над `NextThemesProvider`, чтобы клиент-only-impоrt был
явным. Конфиг:

- `attribute="class"` — переключение через `<html class="dark">` (и
  Tailwind `dark:` варианты, и наши CSS-переменные на `.dark`)
- `defaultTheme="system"` — следуем за `prefers-color-scheme`
- `enableSystem` + `disableTransitionOnChange` — без мерцаний

Toggle-кнопка [`web/components/theme-toggle.tsx`](../../web/components/theme-toggle.tsx) —
sun/moon из `lucide-react`. Иконки переключаются CSS-only через
`dark:` классы (без условного рендера → нет hydration-проблем →
react-hooks lint доволен).

### 2. Layout shell

[`web/components/layout/Header.tsx`](../../web/components/layout/Header.tsx) —
sticky-header с logo + nav (Read / Search / Chat) + theme toggle.
Backdrop-blur эффект: header полупрозрачен, контент проступает при
скролле.

[`web/components/layout/Footer.tsx`](../../web/components/layout/Footer.tsx) —
disclaimer placeholder («not a substitute for a qualified teacher»)
плюс ссылки на Sources / Audit / Privacy / GitHub. Disclaimer тут —
до Phase 5, где будет полноценная deference-language pass.

### 3. `web/app/layout.tsx` — корневой layout

Загружает 3 шрифта через `next/font/google`:

- **Inter** (`--font-sans`) — UI текст
- **Noto Serif** (`--font-serif`) — для дхарма-текстов в reading-room.
  Пока используется только через класс `.dharma-text`, но font-stack
  загружен с `latin`/`latin-ext`/`vietnamese` subsets — full coverage
  Pāli-диакритики
- **JetBrains Mono** (`--font-mono`) — code / chunk_id

Иерархия провайдеров:

```tsx
<ThemeProvider> <TooltipProvider> <Header /> {children} <Footer /> </>
```

`TooltipProvider` (shadcn / `@base-ui/react`) — глобально, чтобы
любая страница могла использовать `<Tooltip>` без локальной обёртки.
Параметр **`delay={150}`** (не `delayDuration` как в radix — это
`@base-ui` API).

### 4. shadcn-компоненты

Через `pnpm dlx shadcn@latest add button card sheet dialog tooltip
separator scroll-area --yes` добавлены 6 новых компонентов в
`web/components/ui/`. `button.tsx` уже существовал из app-day-01.

### 5. Landing-page

[`web/app/page.tsx`](../../web/app/page.tsx) переписан с нуля:

- hero-блок: краткое объяснение «open retrieval over Buddhist texts»
- 3 surface-карточки (Reading Room / Search / Chat) — клик ведёт на
  `/read`, `/search`, `/chat` (страницы появятся в Phase 2-4)
- блок «note on use» — мягкий disclaimer без алармизма

Карточки используют `<Card>` из shadcn, hover-состояния через
`group-hover:` Tailwind-класс.

### 6. Типографика для дхарма-текстов

В [`web/app/globals.css`](../../web/app/globals.css) добавлен класс
`.dharma-text`:

```css
.dharma-text {
  font-family: var(--font-serif), Georgia, "Times New Roman", serif;
  font-feature-settings: "kern", "liga", "calt";
  line-height: 1.75;
  letter-spacing: 0.005em;
}
```

`font-feature-settings` включает kerning + ligatures + contextual
alternates — критично для красивого рендера сочетаний типа `ñ` или
`ṭ` в Noto Serif. Используется в Reading Room (Phase 2); сейчас
объявлен заранее, чтобы не дублировать стиль.

Также fix `--font-mono` mapping (ранее `var(--font-geist-mono)` —
осталось от next-app scaffold; теперь `var(--font-mono)` →
JetBrains Mono).

## Чего НЕ делаем

- **i18n / `next-intl`** — план говорит «по умолчанию только en, RU
  добавим в Phase 7». Преждевременно сейчас.
- **SideNav / breadcrumbs** — нет страниц с глубокой навигацией пока.
- **Prose styling** для конкретных паттернов (стихи Dhp, AN nikāya
  numbering) — это часть Reading Room (app-day-21).
- **Mobile menu (hamburger)** — Header пока в один ряд, на mobile
  ссылки сжимаются. Полноценный mobile-nav когда будут реальные
  страницы для навигации.

## Как проверить

```bash
# 1. Активировать venv (нужен только если меняли Pydantic-схемы)
# В PowerShell: .\.venv\Scripts\activate.ps1

# 2. Поднять оба сервера
pnpm dev   # → web :3001 + api :8000

# 3. Открыть http://localhost:3001
#    Ожидаем:
#    - landing-page с тремя карточками (Read / Search / Chat)
#    - Header sticky сверху, Footer снизу
#    - тема переключается кнопкой sun/moon — без flash
#    - все ссылки в nav и карточках кликабельны (404 на /read|/search|/chat
#      пока ОК — страницы Phase 2-4)
```

Также:

```bash
pnpm --filter web tsc --noEmit   # типы корректны
pnpm --filter web lint            # eslint clean
pnpm --filter web build           # production build green
```

## Файлы

| файл | роль |
|---|---|
| `web/app/layout.tsx` | RootLayout: шрифты + ThemeProvider + TooltipProvider + Header/Footer shell |
| `web/app/page.tsx` | landing с тремя surface-карточками |
| `web/app/globals.css` | font mappings + `.dharma-text` typography |
| `web/components/theme-provider.tsx` | `next-themes` обёртка |
| `web/components/theme-toggle.tsx` | sun/moon toggle button |
| `web/components/layout/Header.tsx` | sticky header + nav |
| `web/components/layout/Footer.tsx` | disclaimer + links |
| `web/components/ui/{card,sheet,dialog,tooltip,separator,scroll-area}.tsx` | shadcn additions |

## Связанные документы

- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — план app-трека
- [docs/concepts/16-openapi-typegen.md](16-openapi-typegen.md) — type-safe API клиент
- [docs/FEATURE_ROADMAP.md](../FEATURE_ROADMAP.md) — куда движется проект
