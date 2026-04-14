# Development Setup

> Полная инструкция по настройке локального окружения разработки.

---

## Требования

- **Python 3.11+** (рекомендуется 3.12)
- **Docker Desktop** (Windows/Mac) или **docker + docker-compose** (Linux)
- **Git**
- **Минимум 16 GB RAM** (8 GB Qdrant + 8 GB на Python/IDE)
- **50 GB свободного места** (модели + данные + Qdrant storage)
- **GPU желателен, но не обязателен** (NVIDIA с 8GB+ VRAM ускорит embedding в ~10 раз)
- **API ключ Anthropic** (получить на [console.anthropic.com](https://console.anthropic.com))

---

## Шаг 1: Клонирование репозитория

```bash
git clone git@github.com:toneruseman/dharma-rag.git
cd dharma-rag
```

## Шаг 2: Python окружение

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Mac/Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### С GPU (опционально)

```bash
# CUDA 12.x
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Проверка
python -c "import torch; print(torch.cuda.is_available())"
```

---

## Шаг 3: Переменные окружения

```bash
cp .env.example .env
```

Минимально необходимо заполнить:

```env
ANTHROPIC_API_KEY=sk-ant-...
QDRANT_URL=http://localhost:6333
```

Остальное — по мере прохождения фаз (см. [DAY_BY_DAY_PLAN.md](DAY_BY_DAY_PLAN.md)).

---

## Шаг 4: Запустить инфраструктуру

```bash
docker compose up -d qdrant langfuse-db langfuse
```

Проверка:

```bash
# Qdrant
curl http://localhost:6333/healthz
# Должно вернуть: ok

# Langfuse UI
open http://localhost:3000
```

При первом запуске Langfuse — создайте локальный аккаунт (только для вашего инстанса) и проект "dharma-rag", скопируйте ключи в `.env`.

---

## Шаг 5: Проверка установки

```bash
python scripts/test_setup.py
```

Должно вывести:
```
✓ Python 3.12.x
✓ Anthropic API key valid
✓ Qdrant connected (0 collections)
✓ Langfuse connected
✓ BGE-M3 model loaded
✓ All dependencies installed
```

---

## Шаг 6: Загрузка данных

См. [data/README.md](../data/README.md) для инструкций по загрузке исходных данных:

- SuttaCentral bilara-data (git clone)
- DhammaTalks.org epubs
- Access to Insight ZIP
- ... и т.д.

Затем:

```bash
# Запустить ингест (один источник за раз для отладки)
python -m src.ingest.suttacentral
python -m src.ingest.dhammatalks
# ... и т.д.
```

---

## Workflow разработки

### Создание новой фичи

```bash
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# ... разработка ...

ruff check src/
ruff format src/
mypy src/
pytest

git add .
git commit -m "feat: add my feature"
git push origin feature/my-feature
# Создать PR в dev на GitHub
```

### Локальный запуск API

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Открыть:
- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Запуск CLI

```bash
dharma-rag query "What is jhāna?"
dharma-rag eval --baseline
dharma-rag cache stats
```

### Запуск тестов

```bash
# Все тесты
pytest

# Только unit
pytest tests/unit/

# С coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Только один файл
pytest tests/unit/test_chunker.py -v

# С нечеткой выборкой
pytest -k "test_pali"
```

### Запуск eval

```bash
# Полный eval
python -m src.eval.runner

# С конкретной конфигурацией
python -m src.eval.runner --retriever hybrid --reranker bge_v2

# Сохранить результаты
python -m src.eval.runner --output tests/eval/results/$(date +%Y%m%d).json
```

---

## Полезные команды

### Очистка

```bash
# Очистить кеш
dharma-rag cache clear

# Сбросить Qdrant коллекцию
docker compose down -v qdrant
docker compose up -d qdrant
python scripts/build_index.py
```

### Дебаг

```bash
# Включить дебаг логи
export LOG_LEVEL=DEBUG  # Mac/Linux
$env:LOG_LEVEL = "DEBUG"  # Windows PowerShell

# Запустить с отладчиком
python -m pdb scripts/build_index.py
```

### Профилирование

```bash
python -m cProfile -o profile.stats scripts/test_query.py
snakeviz profile.stats  # pip install snakeviz
```

---

## Решение проблем

### Qdrant не стартует

```bash
docker compose logs qdrant
# Часто проблема в правах на volume:
docker compose down -v qdrant
docker compose up -d qdrant
```

### Out of memory при embedding

Уменьшить batch size в `src/embeddings/bge_m3.py`:
```python
BATCH_SIZE = 16  # вместо 64
```

Или включить mmap в Qdrant (см. docs/RAG_PIPELINE.md).

### torch не находит CUDA

Проверить версию CUDA:
```bash
nvidia-smi  # должно совпадать с версией torch
```

Переустановить torch с правильной версией:
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Anthropic API rate limit

В Tier 1 — 50 RPM. Решения:
- Запросить Tier 2 (требуется $40 spend)
- Использовать `tenacity` для exponential backoff
- Снизить параллельность в скриптах

### Langfuse не показывает traces

Проверить:
1. `LANGFUSE_PUBLIC_KEY` и `LANGFUSE_SECRET_KEY` в `.env`
2. `LANGFUSE_HOST=http://localhost:3000`
3. Перезапустить приложение
4. Проверить логи: `docker compose logs langfuse`

---

## IDE конфигурация

### VS Code

Файл `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.linting.enabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true,
      "source.fixAll": true
    }
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/.ruff_cache": true,
    "**/.mypy_cache": true
  }
}
```

Расширения:
- Python (Microsoft)
- Pylance
- Ruff
- Docker
- GitLens
- Markdown All in One
- YAML

### PyCharm

- File → Settings → Project → Python Interpreter → выбрать `.venv`
- Tools → Black formatter (или Ruff) включить format on save
- Run/Debug Configurations → создать "FastAPI" с скриптом `uvicorn` и параметрами `src.api.app:app --reload`

---

## Дополнительные ресурсы

- [Anthropic Claude docs](https://docs.claude.com)
- [Qdrant docs](https://qdrant.tech/documentation/)
- [BGE-M3 paper](https://arxiv.org/abs/2402.03216)
- [FastAPI docs](https://fastapi.tiangolo.com)
- [Langfuse docs](https://langfuse.com/docs)
- [HTMX docs](https://htmx.org/docs/)
- [Pipecat docs](https://docs.pipecat.ai)

---

## Получить помощь

- GitHub Issues: bugs, feature requests
- GitHub Discussions: вопросы, идеи
- README.md: общая информация о проекте
