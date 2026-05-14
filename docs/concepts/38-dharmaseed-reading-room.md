# 38. Dharmaseed Reading Room — Browse по учителям

**Статус:** черновик · **Дата:** 2026-05-11
**Трек:** app-day (Frontend + Backend)

---

## Что делаем

Расширяем существующую страницу `/read` двумя уровнями навигации:

```
/read                        — лендинг: Pāli Canon + блок «Dharma Talks»
/read/teachers/[slug]        — список лекций одного учителя
/read/[uid]                  — Reading Room отдельной лекции (уже работает)
```

Переводы и саммари — **не в этом MVP**, отдельный день.

---

## Почему именно так устроен роутинг

`/read` уже работает как лендинг и как `/read/[uid]` для конкретного текста.
Вместо отдельного `/talks` мы добавляем `/read/teachers/[slug]` — тогда вся
«читалка» живёт под одним префиксом, браузерная кнопка «назад» ведёт на лендинг,
а хлебные крошки строятся естественно.

---

## Слои изменений

### 1. Backend: два новых эндпоинта

#### `GET /api/works/teachers`

Возвращает список учителей у которых есть лекции в корпусе.

```
Ответ: [{ slug, name, talk_count, tradition_code }]
```

*Реализация:* JOIN `Work` → `Expression` → `Author`,
фильтр `Work.source_type = 'dharmaseed_talk'`,
GROUP BY `Author.slug, Author.name`, COUNT.

Зачем нужен отдельный эндпоинт, а не `/api/works?group_by=teacher`?
Потому что это принципиально другой уровень агрегации — он возвращает
сущность «учитель», а не сущность «работа». Смешивать их в одном эндпоинте
означает вечно расширять query-параметры и ломать кэш.

#### `GET /api/works?source_type=dharmaseed_talk&teacher_slug=rob_burbea&limit=50&offset=0`

Возвращает постраничный список работ одного учителя.

```
Ответ: {
  items: [{ canonical_id, title, talk_date, tradition_code }],
  total: int,
  limit: int,
  offset: int
}
```

*Реализация:* SELECT из `Work` JOIN `Expression` JOIN `Author`,
фильтр по `source_type` и `Author.slug`,
`talk_date` — из `Work.metadata_json["date"]` (строка ISO 8601 "YYYY-MM-DD"),
сортировка по `talk_date DESC NULLS LAST`.

**Термин «постраничность» (pagination):** возвращаем не все записи сразу,
а порцию `limit` штук начиная с позиции `offset`. Например, первые 50 лекций —
`?limit=50&offset=0`, следующие — `?offset=50`. Нужно, чтобы страница
с 458 лекциями Burbea не грузила всё в браузер сразу.

#### Схемы Pydantic

```python
class TeacherCard(BaseModel):
    slug: str          # "rob_burbea"
    name: str          # "Rob Burbea"
    talk_count: int
    tradition_code: str | None

class WorkCard(BaseModel):
    canonical_id: str  # "rob_burbea_60869"
    title: str
    talk_date: str | None   # "2005-11-05"
    tradition_code: str

class WorkListResponse(BaseModel):
    items: list[WorkCard]
    total: int
    limit: int
    offset: int
```

Новый роутер: `src/api/works.py`, подключается в `src/api/router.py`.

---

### 2. Frontend: три изменения

#### 2a. Лендинг `/read` — расширение

Текущий `web/app/read/page.tsx` — Server Component (нет `"use client"`),
статический, с захардкоженными SUGGESTED_WORKS.

Делаем его **async Server Component**: при загрузке страницы сервер Next.js
сам вызывает `GET /api/works/teachers`, получает список учителей и рендерит HTML.
Браузер получает готовую страницу без лишних клиентских запросов.

```
Структура новой страницы /read:
─ header ("Reading Room")
─ section "Pāli Canon"          ← существующий блок (3 карточки)
─ section "Dharma Talks"        ← новый блок
    TeacherCard × N             ← по одной на учителя
```

`TeacherCard` показывает: имя учителя, количество лекций, ссылка → `/read/teachers/[slug]`.

#### 2b. Новая страница `/read/teachers/[slug]`

Файл: `web/app/read/teachers/[slug]/page.tsx`

Тоже async Server Component. При загрузке:
1. Получает `slug` из URL-параметра (например `rob_burbea`)
2. Вызывает `GET /api/works?source_type=dharmaseed_talk&teacher_slug=rob_burbea&limit=50`
3. Рендерит список карточек лекций

Каждая карточка лекции: заголовок, дата, ссылка → `/read/[canonical_id]`.

Хлебные крошки: `Reading Room → Rob Burbea → [название лекции]`

**Пагинация UI:** на первом этапе — «Load more» кнопка (клиентский Client Component),
которая делает fetch следующей порции при клике.
Почему не полные URL-страницы (`?page=2`)? Для читалки «Load more» естественнее —
пользователь скроллит список лекций, а не переходит на другую страницу.

#### 2c. Обновление stub-заглушки

Убираем сообщение «In stub mode the corpus exposes the three works above.» —
оно больше не актуально, в БД уже 458 лекций Burbea.

---

## Файлы которые меняются / создаются

```
src/api/works.py               (новый)   — роутер с двумя эндпоинтами
src/api/router.py              (изменение) — подключение нового роутера
web/app/read/page.tsx          (изменение) — добавить секцию Dharma Talks
web/app/read/teachers/         (новая директория)
web/app/read/teachers/[slug]/page.tsx  (новый) — страница учителя
web/components/reader/TeacherCard.tsx  (новый) — карточка учителя
web/components/reader/TalkCard.tsx     (новый) — карточка лекции
web/lib/api-client.ts          (изменение) — добавить fetchTeachers, fetchWorks
```

---

## Что НЕ входит в этот MVP

- Перевод абзацев на русский
- LLM-саммари лекций
- Поиск по лекциям (есть через `/chat`)
- Фильтры по дате/традиции
- Аудиоплеер (mp3_url в metadata_json, но плеер — отдельная фича)

---

## Зависимости и риски

| Риск | Вероятность | Решение |
|------|------------|---------|
| `Author.slug` = NULL для некоторых учителей | низкая (Rob Burbea slug = 'rob_burbea' установлен при ingest) | fallback: использовать `canonical_id`-prefix |
| `metadata_json["date"]` отсутствует | низкая для Burbea | показываем «—» вместо даты |
| 458 лекций → медленный JOIN | низкая (indexed source_type + author_id) | индекс уже есть на source_type |

---

## Порядок реализации

1. Backend: `src/api/works.py` + подключение в router
2. Тест эндпоинтов через curl/Swagger
3. Frontend: `api-client.ts` → `TeacherCard` → расширение `/read` лендинга
4. Frontend: `TalkCard` → страница `/read/teachers/[slug]`
5. Ручная проверка: `/read` → Rob Burbea → лекция → Reading Room
