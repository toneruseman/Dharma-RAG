# Consent Ledger

> **Публичный реестр разрешений на использование источников данных в Dharma RAG.**

Каждый источник в корпусе должен иметь соответствующий YAML-файл в этом каталоге, документирующий:
- Лицензионные условия
- Кто правообладатель
- Что разрешено (коммерческое использование, деривативы)
- Когда и от кого получено подтверждение
- Контактная информация

---

## Зачем Consent Ledger?

### Юридическая прозрачность

Пользователи, контрибьюторы и правообладатели могут **в любой момент проверить**, на каком основании используется каждый источник.

### Doctrinal integrity

Буддийское сообщество особенно ценит согласие и прозрачность. Учителя должны знать, что их учения используются с уважением и по правилам.

### Защита проекта

Documented consent → защита от claims о нарушении.

---

## Структура

```
consent-ledger/
├── README.md                       # этот файл
├── public-domain/                  # источники в public domain
│   ├── suttacentral-cc0.yaml
│   ├── pa-auk-knowing-and-seeing.yaml
│   └── visuddhimagga-pe-maung-tin.yaml
├── open-license/                   # CC/free-distribution лицензии
│   ├── dhammatalks-org.yaml
│   ├── access-to-insight.yaml
│   ├── pts-cc-works.yaml
│   ├── ancient-buddhist-texts.yaml
│   ├── academic-papers.yaml
│   └── mahasi-free-works.yaml
└── explicit-permission/            # требуют письменного разрешения
    └── (заполняется в Phase 2)
```

---

## Схема YAML

```yaml
# Уникальный ID источника
source_id: dhammatalks_org

# Человеко-читаемое название
name: DhammaTalks.org (Thanissaro Bhikkhu)

# URL источника
url: https://www.dhammatalks.org

# Лицензия
license:
  type: open-license           # public-domain | open-license | explicit-permission
  name: CC BY-NC 4.0
  url: https://creativecommons.org/licenses/by-nc/4.0/
  date_confirmed: 2026-01-15   # когда подтвердили лицензию
  text_at_source: |            # цитата с сайта источника
    "This work is licensed under the Creative Commons
     Attribution-NonCommercial 4.0 Unported."

# Правообладатель
copyright_holder: Metta Forest Monastery
copyright_contact: mmfm@dhammatalks.org

# Что разрешено
permissions:
  attribution_required: true
  commercial_use: denied
  derivative_works: allowed
  share_alike: false

# Чем мы пользуемся
usage_in_project:
  - Text of translated suttas
  - Dharma talk transcripts (Thanissaro Bhikkhu)
  - Books by Ajahn Lee, Ajahn Fuang, Ajahn Mun

# Какие ограничения мы соблюдаем
our_commitments:
  - Project is 100% free, no commercial offering
  - Sources attributed in every response with direct link
  - No redistribution of raw text — only semantic search
  - Original works directed to via citation

# Статистика использования
statistics:
  chunks_ingested: 19425
  first_ingest_date: 2026-02-01
  last_update: 2026-04-14

# Явное разрешение (если получали)
explicit_permission:
  requested: false               # для CC-лицензированного не требуется
  required: false
  granted_by: null
  granted_date: null
  communication_log: null

# Исключения
exclusions:
  - "Any materials from other authors with different licenses"
  - "Audio files (handled separately via Phase 1.5 transcription)"

# Заметки
notes: |
  CC BY-NC 4.0 is clear for our use case: non-commercial,
  attribution provided, derivatives allowed (our chunks + retrieval
  constitute derivative work).

  As good practice, we maintain active communication with Metta Forest
  Monastery about our usage.
```

---

## Процесс добавления источника

### Для public-domain / ясно-лицензированных

1. Найти источник и проверить лицензию на сайте
2. Скриншот/копия лицензионного текста
3. Создать YAML файл в соответствующей директории
4. Commit в git — это и есть запись реестра

### Для требующих явного разрешения

1. Найти контакт правообладателя
2. Отправить запрос (шаблон ниже)
3. Получить письменное разрешение
4. Сохранить переписку в encrypted backup
5. Создать YAML файл с `explicit_permission` данными
6. В случае отказа — source в проект НЕ попадает

### Шаблон запроса разрешения

```
Subject: Permission request: Dharma RAG non-commercial use

Dear [Teacher / Organization],

I'm building Dharma RAG (dharma-rag.org), an open-source,
free, non-commercial tool helping practitioners find relevant
Buddhist teachings through AI semantic search.

I'd like to request permission to include [specific source]
in the corpus. Commitments:

1. **Completely free, no ads, no subscriptions** —
   MIT-licensed, non-commercial forever.

2. **Every AI response cites the source** with direct
   link back. Users are always directed to the original.

3. **Raw text not redistributed** — only semantic embeddings
   and small quoted excerpts (<50 words) appear.

4. **Public Consent Ledger** documents every source's
   permissions for transparency.

5. **Doctrinal care** — system instructions require faithful
   representation, with dedicated metrics for accuracy.

Project details: github.com/toneruseman/dharma-rag

Questions I'd appreciate your input on:
- Is inclusion acceptable under your terms?
- Any specific works to exclude?
- Any attribution preferences?
- Any boundaries we should respect?

If you prefer not to be included, simply reply "no" and
we will not include your work.

With mettā,
[Name]
```

---

## Что делать если лицензия неясна?

1. **Default = запрашивать разрешение.** При сомнениях — отдельное письмо.
2. Избегать CC-NY-NC-**ND** (No Derivatives) если нет явного разрешения на RAG-использование.
3. Если автор не отвечает > 60 дней — источник НЕ включается.

---

## Изменения лицензий

Если правообладатель меняет условия или отзывает разрешение:

1. **Немедленное действие:** source marked `status: revoked` в YAML
2. **В течение 48 часов:** chunks этого источника удалены из Qdrant
3. **В течение 7 дней:** build обновлён в production
4. **Документация:** причина отзыва записана в YAML

---

## Public audit

Любой может:
- Проверить каждый файл в этом каталоге
- Поднять Issue о подозрении нарушения лицензии
- Запросить исключение своего материала (responsi@dharma-rag.org)

GitHub Actions автоматически:
- Проверяет валидность YAML-схемы каждого файла (CI)
- Считает общий chunks ingested vs licenses
- Alert на изменения в `explicit-permission/`

---

## Связано

- [docs/SOURCES_CATALOG.md](../docs/SOURCES_CATALOG.md) — полный каталог
- [docs/PRIVACY.md](../docs/PRIVACY.md) — приватность пользователей
- [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md) — как добавлять источники
