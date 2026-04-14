# Data Directory

> Данные НЕ хранятся в git (см. .gitignore). Этот файл объясняет, как их получить.

## Структура

```
data/
├── README.md                   ← вы здесь
├── raw/                        ← сырые файлы от источников
│   ├── suttacentral/
│   ├── dhammatalks/
│   ├── access_to_insight/
│   ├── pa_auk/
│   ├── pts/
│   ├── ancient_buddhist_texts/
│   ├── academic_papers/
│   ├── mahasi/
│   └── visuddhimagga/
├── processed/                  ← обработанные JSONL чанки
│   └── {source}/{lang}.jsonl
├── audio/                      ← MP3 (Phase 1.5)
│   └── dharmaseed/
├── transcripts/                ← транскрипты
├── glossary/
│   └── pali.yaml
├── bm25_index.pkl              ← построенный BM25 index (gitignored)
└── ...
```

## Загрузка по источникам

### 1. SuttaCentral (CC0)

```bash
cd data/raw
git clone --depth 1 --branch published \
    https://github.com/suttacentral/bilara-data.git suttacentral
```

Размер: ~500 MB. Это Git репозиторий с JSON переводами.

### 2. DhammaTalks.org (CC BY-NC 4.0)

Использовать scraper скрипт:

```bash
python scripts/scrape_dhammatalks.py --output data/raw/dhammatalks/
```

Размер: ~300 MB. ePub + HTML файлы.

### 3. Access to Insight (Free Distribution)

Скачать полный архив:

```bash
cd data/raw
wget https://www.accesstoinsight.org/dl/ati-20130107.zip
unzip ati-20130107.zip -d access_to_insight
rm ati-20130107.zip
```

Размер: ~150 MB.

### 4. Pa Auk — "Knowing and Seeing" (Public Domain)

```bash
cd data/raw/pa_auk
wget https://archive.org/download/KnowingAndSeeing/knowing_and_seeing.pdf
```

Размер: ~5 MB.

### 5. Pali Text Society CC works (CC BY-NC 3.0/4.0)

Список из palitextsociety.org/copyright-information/, скачивание PDF вручную или через:

```bash
python scripts/download_pts.py --output data/raw/pts/
```

Размер: ~450 MB (PDF сканы, требуют OCR).

### 6. Ancient Buddhist Texts (CC BY)

```bash
# Scrape HTML файлы
python scripts/scrape_ancient_buddhist_texts.py --output data/raw/ancient_buddhist_texts/
```

Размер: ~200 MB, 3712 HTML файлов.

### 7. Academic papers (CC BY 4.0)

Курирование через скрипт:

```bash
python scripts/fetch_academic_papers.py \
    --query "vipassana mindfulness meditation jhana" \
    --output data/raw/academic_papers/
```

Размер: ~50 MB.

### 8. Mahasi Sayadaw free works

```bash
python scripts/download_mahasi.py --output data/raw/mahasi/
```

**⚠️ ВНИМАНИЕ:** НЕ скачивать "Manual of Insight" (copyrighted Wisdom Publications).

### 9. Visuddhimagga — Pe Maung Tin (Public Domain)

```bash
cd data/raw/visuddhimagga
wget https://archive.org/download/pathofpuritybein01budduoft/pathofpuritybein01budduoft.pdf
```

Размер: ~30 MB.

### 10. Dharmaseed (Phase 1.5, требует разрешения)

Скачивание аудио — после получения разрешения от dharmaseed.org (см. SOURCES_CATALOG.md).

```bash
python scripts/download_dharmaseed.py --output data/audio/dharmaseed/
```

Размер: ~500 GB для 46,219 лекций.

## Общий размер

| Фаза | Данные | Размер |
|------|--------|--------|
| Phase 1 raw | текстовые источники | ~1.7 GB |
| Phase 1 processed | JSONL chunks | ~500 MB |
| Phase 1.5 audio | MP3 файлы | ~500 GB |
| Phase 1.5 transcripts | JSON транскрипты | ~2 GB |
| Qdrant storage | embeddings | ~4-8 GB |
| BM25 index | pickle | ~500 MB |
| **TOTAL** | | **~510 GB** |

Для Phase 1 только: **~10 GB**.
Для Phase 1.5+: рекомендуется **Hetzner Storage Box 1TB** (€4/мес).

## Инструменты управления

```bash
# Audit: проверить целостность данных
python scripts/audit_sources.py

# Export processed для backup
python scripts/export_processed.py --output /mnt/backup/

# Import processed из backup
python scripts/import_processed.py --input /mnt/backup/
```

## Legal обязательства

- **Все данные** используются согласно `consent-ledger/` (см. корневую папку проекта)
- **Ваши копии** — ваша ответственность соблюдать лицензии
- **НЕ распространять** raw данные публично (это копии чужих работ)
- **OK распространять** processed chunks в составе проекта, если это нарушает лицензию

Вопросы по лицензиям: см. [docs/SOURCES_CATALOG.md](../docs/SOURCES_CATALOG.md).
