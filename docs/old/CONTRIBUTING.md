# Contributing to Dharma RAG

> Спасибо за интерес к участию в проекте! Этот документ объясняет, как внести вклад.

---

## Кодекс поведения

Этот проект следует духу буддийской этики (sīla):

- **Mettā** (доброжелательность) — относиться к каждому участнику с теплом
- **Satya** (правдивость) — честность в обсуждениях, признание ошибок
- **Khanti** (терпение) — особенно к новичкам и при разногласиях
- **Anattā** (не-эго) — критика идей, не личностей

Любые формы харassment, дискриминации, троллинга — запрещены и ведут к бану.

---

## Способы участия

### 1. 💻 Код

- **Новые фичи** — обсудите в Issue перед началом работы
- **Bug fixes** — сразу PR, описание проблемы в commit message
- **Refactoring** — обоснуйте улучшение
- **Tests** — всегда приветствуются

### 2. 📚 Документация

- Исправление опечаток
- Уточнения и дополнения
- Переводы на другие языки
- Туториалы и cookbook examples

### 3. 🌐 Переводы

- UI переводы (Phase 4+)
- Перевод документации
- Палийский глоссарий — добавление терминов в `data/glossary/pali.yaml`

### 4. 📊 Данные

- Поиск новых open-licensed источников
- Помощь в установлении контактов с учителями для разрешений
- Improvement палийского глоссария
- Курирование golden eval test set

### 5. 🐛 Тестирование

- Reporting bugs
- Тестирование на разных платформах
- Beta-тестирование релизов
- Создание новых eval queries

### 6. 🎨 Дизайн

- UI/UX для веб и мобильного
- Иконки и иллюстрации (CC лицензия)
- Документационные диаграммы

---

## Process

### Reporting Bugs

Используйте шаблон Issue "Bug Report":

1. **Заголовок:** краткое описание ("Retriever returns empty for queries with diacritics")
2. **Шаги воспроизведения:** что вы сделали
3. **Ожидаемое поведение**
4. **Фактическое поведение**
5. **Окружение:** OS, Python version, версия проекта
6. **Логи** (если есть)

### Предложение фичи

Используйте шаблон Issue "Feature Request":

1. **Use case:** какую проблему решает?
2. **Предлагаемое решение**
3. **Альтернативы:** что ещё рассматривали?
4. **Контекст:** связь с другими частями проекта

### Pull Request Workflow

```bash
# 1. Fork репозитория на GitHub

# 2. Клонировать ваш fork
git clone git@github.com:YOUR_USERNAME/dharma-rag.git
cd dharma-rag

# 3. Добавить upstream
git remote add upstream git@github.com:toneruseman/dharma-rag.git

# 4. Создать ветку
git checkout -b feature/my-feature

# 5. Разработка
# ... код, тесты, документация ...

# 6. Проверки
ruff check src/ tests/
ruff format src/ tests/
mypy src/
pytest

# 7. Commit (см. соглашения ниже)
git add .
git commit -m "feat(rag): add HyDE query expansion"

# 8. Push
git push origin feature/my-feature

# 9. Создать PR на GitHub в ветку `dev` (не main!)
```

### Commit Message Convention

Следуем [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat` — новая функциональность
- `fix` — исправление бага
- `docs` — изменения в документации
- `refactor` — рефакторинг без изменения поведения
- `test` — добавление/изменение тестов
- `perf` — улучшение производительности
- `chore` — рутинные задачи (deps, build)
- `ci` — изменения CI/CD

**Scopes (примеры):**
- `rag` — RAG pipeline
- `embeddings` — embedding модели
- `api` — FastAPI
- `bot` — Telegram bot
- `voice` — voice pipeline
- `transcription` — транскрипция
- `eval` — evaluation
- `docs` — документация

**Примеры:**

```
feat(rag): add HyDE query expansion

Generates hypothetical document embedding for conceptual queries,
improving topic_hit@5 by ~7pp on philosophical questions.

Closes #42
```

```
fix(retriever): handle empty Qdrant collection

Prevents crash when collection has no points yet during initialization.
```

```
docs(privacy): clarify GDPR voice data handling
```

---

## Code Review

Все PR проходят review. Что мы проверяем:

1. **Корректность** — код делает то, что должен
2. **Тесты** — покрытие новой функциональности
3. **Стиль** — соответствие ruff/mypy
4. **Документация** — обновлена при необходимости
5. **Производительность** — нет регрессий
6. **Безопасность** — нет утечек секретов, инъекций
7. **Совместимость** — работает на Python 3.11+

Время review: обычно 2-7 дней. Не стесняйтесь пинговать через 7+ дней.

---

## Стандарты кода

### Python

- **Форматирование:** ruff (auto)
- **Линтинг:** ruff check
- **Type checking:** mypy strict mode
- **Docstrings:** Google style
- **Тесты:** pytest, минимум для критических путей

Пример хорошей функции:

```python
from typing import Sequence

def rerank_chunks(
    query: str,
    chunks: Sequence[Chunk],
    top_k: int = 10,
) -> list[Chunk]:
    """Rerank chunks by cross-encoder relevance.

    Args:
        query: The user query string.
        chunks: Candidate chunks to rerank.
        top_k: Number of top chunks to return.

    Returns:
        Top-k chunks sorted by relevance score (descending).

    Raises:
        ValueError: If chunks is empty.

    Example:
        >>> chunks = retriever.search("what is jhana", top_k=100)
        >>> top_chunks = rerank_chunks("what is jhana", chunks, top_k=10)
    """
    if not chunks:
        raise ValueError("chunks must not be empty")
    # ... implementation ...
```

### Markdown

- 100 символов в строке (мягкий лимит)
- Заголовки `#`, `##`, `###` — без `====` подчёркиваний
- Code blocks с указанием языка: ` ```python `

### YAML

- 2 пробела отступ
- Кавычки только когда нужно

---

## Тестирование

### Минимум для PR

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
pytest
```

### Покрытие

Цель: 70%+ для критических модулей (`src/rag/`, `src/embeddings/`).

```bash
pytest --cov=src --cov-report=term-missing
```

### Eval regression testing

Если изменения затрагивают retrieval/generation — прогнать eval:

```bash
python -m src.eval.runner --output tests/eval/results/pr_$(git rev-parse --short HEAD).json
```

И сравнить с baseline. Регрессии >5% по ref_hit@5 или topic_hit@5 — блокер.

---

## Документация

Если ваш PR:

- Добавляет новую API endpoint → обновить `docs/API.md`
- Меняет пайплайн → обновить `docs/RAG_PIPELINE.md`
- Добавляет новую фичу → пример в `docs/COOKBOOK.md`
- Меняет конфиг → обновить `.env.example`

---

## Ваш первый PR

Хорошие задачи для начала:

- Issues с меткой `good first issue`
- Опечатки в документации
- Добавление test queries в `tests/eval/test_queries.yaml`
- Добавление палийских терминов в `data/glossary/pali.yaml`
- Перевод одного раздела документации

---

## Контакты

- GitHub Issues: для багов и feature requests
- GitHub Discussions: для вопросов и идей
- Email: (создаётся для проекта)

---

## Лицензия вашего вклада

Контрибутируя код в этот репозиторий, вы соглашаетесь, что ваш код будет распространяться под MIT лицензией. Ваш контрибушн сохранит атрибуцию через git history.

Контрибутируя данные (новые источники), вы должны указать их лицензию в `consent-ledger/`. Не контрибутируйте данные, которые не имеете права распространять.

---

## Признание

Все контрибьюторы будут перечислены в:
- README.md
- AUTHORS.md (после v0.5.0)
- Release notes для каждой версии

> Sabbe sattā sukhitā hontu — Пусть все существа будут счастливы.
