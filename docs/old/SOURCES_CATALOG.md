# Sources Catalog

> Полный каталог источников данных для Dharma RAG с лицензиями, объёмами и статусом.

---

## Phase 1 Sources (Public Domain / Clearly Licensed)

Эти источники могут быть ингестированы немедленно без дополнительных разрешений.

---

### 1. SuttaCentral — Bilara Data ⭐ [PRIORITY #1]

**URL:** https://suttacentral.net
**Data repo:** https://github.com/suttacentral/bilara-data (branch: `published`)
**License:** CC0 1.0 Universal (Public Domain Dedication)

> "All translations created in Bilara and supported by SuttaCentral are dedicated
> to the Public Domain by means of the Creative Commons Public Domain (CC0) license."

**Контент:**
| Collection | Translator | Suttas |
|---|---|---|
| Digha Nikaya (DN) | Bhikkhu Sujato | 34 |
| Majjhima Nikaya (MN) | Bhikkhu Sujato | 152 |
| Samyutta Nikaya (SN) | Bhikkhu Sujato | ~2,000+ |
| Anguttara Nikaya (AN) | Bhikkhu Sujato | ~8,122 |
| Khuddaka Nikaya | Bhikkhu Sujato | varies |

**Дополнительные языки:** немецкий, португальский, испанский, другие (community переводчики)
**Формат:** Segmented JSON

**RAG suitability:** ИДЕАЛЬНО
**Статус:** ✅ Processed (9,324 EN + 2,999 RU chunks)
**Consent ledger:** [public-domain/suttacentral-cc0.yaml](../consent-ledger/public-domain/suttacentral-cc0.yaml)

---

### 2. DhammaTalks.org — Thanissaro Bhikkhu [PRIORITY #2]

**URL:** https://www.dhammatalks.org
**License:** CC BY-NC 4.0

> "This work is licensed under the Creative Commons Attribution-NonCommercial 4.0 Unported."

**Контент:**
- Полные переводы сутт (DN, MN, SN, AN, KN)
- 70+ ebooks на дхарма-темы
- Тысячи транскрибированных вечерних/утренних лекций
- Переводы учителей тайской лесной традиции (Ajahn Lee, Ajahn Fuang, Ajahn Mun)

**Языки:** английский, тайский, французский, испанский, немецкий, португальский, русский, финский, шведский, украинский

**RAG suitability:** ОТЛИЧНО
**Статус:** ✅ Processed (19,425 chunks)
**Consent ledger:** [open-license/dhammatalks-org.yaml](../consent-ledger/open-license/dhammatalks-org.yaml)

**Ключевое ограничение:** "Any sale" запрещена — проект должен оставаться полностью бесплатным.

---

### 3. Access to Insight [PRIORITY #3]

**URL:** https://www.accesstoinsight.org
**License:** Custom free-distribution

> "You may download, print, share, copy to your own website, translate, redistribute
> electronically — provided that you do not charge any money for them."

**Контент:**
- ~1,000 курируемых переводов сутт (различные переводчики)
- ~700+ статей, эссе, книг
- Комплексный индекс по темам, учителям, номерам сутт

**Языки:** только английский
**Статус сайта:** не активно развивается с 2013, но остаётся онлайн и авторитетным

**RAG suitability:** ХОРОШО
**Статус:** ✅ Processed (25,842 chunks)
**Consent ledger:** [open-license/access-to-insight.yaml](../consent-ledger/open-license/access-to-insight.yaml)

---

### 4. Pa Auk Sayadaw — "Knowing and Seeing" [PRIORITY #4]

**URL:** https://archive.org/details/KnowingAndSeeing
**License:** Public Domain (явно указано автором)

**Контент:** 346 страниц — детальные инструкции по джхане и випассане. Один из самых подробных доступных мануалов по медитации.

**RAG suitability:** ОТЛИЧНО
**Статус:** ⏳ Pending (raw PDF в data/raw/pa_auk/)
**Consent ledger:** [public-domain/pa-auk-knowing-and-seeing.yaml](../consent-ledger/public-domain/pa-auk-knowing-and-seeing.yaml)

---

### 5. Pali Text Society — CC-Licensed Works [PRIORITY #5]

**URL:** https://palitextsociety.org/copyright-information/
**License:** CC BY-NC 3.0 (11 works) и CC BY-NC 4.0 (5 works)

**CC BY-NC 3.0 works (11):**
- Pali-English Dictionary (Rhys Davids & Stede)
- Vinaya (Horner translation, 6 vols)
- Majjhima Nikaya (Horner translation, 3 vols)
- Samyutta Nikaya (Rhys Davids & Woodward, 5 vols)
- Anguttara Nikaya (Woodward & Hare, 5 vols)
- и другие

**CC BY-NC 4.0 works (5, Bhikkhu Nanamoli):**
- Dispeller of Delusion, The Guide, The Minor Readings, The Path of Discrimination, The Pitaka Disclosure

**RAG suitability:** ХОРОШО
**Статус:** ⏳ Pending (нужен OCR с PDF сканов, 450 MB)
**Consent ledger:** [open-license/pts-cc-works.yaml](../consent-ledger/open-license/pts-cc-works.yaml)

---

### 6. Ancient Buddhist Texts [PRIORITY #6]

**URL:** https://ancient-buddhist-texts.net
**License:** CC BY (большинство материалов от Anandajoti Bhikkhu)

**Контент:** Пали тексты с переводами, сравнительные исследования, анализ просодии.

**RAG suitability:** ХОРОШО — CC BY максимально permissive с атрибуцией.
**Статус:** ⏳ Pending (3,712 HTML файлов в data/raw/)
**Consent ledger:** [open-license/ancient-buddhist-texts.yaml](../consent-ledger/open-license/ancient-buddhist-texts.yaml)

---

### 7. Open Access Academic Papers [PRIORITY #7]

**Источники:**
- PubMed Central (pmc.ncbi.nlm.nih.gov) — CC BY 4.0
- MDPI journals (open access)
- PLoS ONE, Frontiers

**Поисковые термины:** "vipassana", "mindfulness meditation", "jhana", "Buddhist meditation", "contemplative neuroscience"

**RAG suitability:** ОТЛИЧНО для CC BY
**Статус:** ✅ Processed (1,294 chunks из 59 papers)
**Consent ledger:** [open-license/academic-papers.yaml](../consent-ledger/open-license/academic-papers.yaml)

---

### 8. Mahasi Sayadaw — Free Distribution Works [PRIORITY #8]

**Available free-distribution works:**
- "Practical Insight Meditation"
- "Progress of Insight"
- "Satipatthana Vipassana"

**Важно:** "Manual of Insight" (Wisdom Publications) — copyrighted, НЕ ингестировать.

**RAG suitability:** ХОРОШО
**Статус:** ✅ Processed (235 chunks)
**Consent ledger:** [open-license/mahasi-free-works.yaml](../consent-ledger/open-license/mahasi-free-works.yaml)

---

### 9. Visuddhimagga — Pe Maung Tin Translation [PRIORITY #9]

**URL:** https://archive.org/details/pathofpuritybein01budduoft
**Translation:** "The Path of Purity" by Pe Maung Tin (1923-1931)
**License:** Public Domain (автор умер в 1973; life + 50 years в большинстве юрисдикций)

**RAG suitability:** USABLE (архаичный английский)
**Статус:** ✅ Processed (564 chunks)
**Consent ledger:** [public-domain/visuddhimagga-pe-maung-tin.yaml](../consent-ledger/public-domain/visuddhimagga-pe-maung-tin.yaml)

---

## Phase 1 — Итого корпус

| Источник | License | Chunks | Приоритет | Статус |
|---|---|---|---|---|
| SuttaCentral EN | CC0 | 6,325 | #1 | ✅ |
| SuttaCentral RU | CC0 | 2,999 | #1 | ✅ |
| DhammaTalks.org | CC BY-NC 4.0 | 19,425 | #2 | ✅ |
| Access to Insight | Free distribution | 25,842 | #3 | ✅ |
| Pa Auk "Knowing & Seeing" | Public Domain | ~500-800 | #4 | ⏳ |
| PTS CC works | CC BY-NC 3.0/4.0 | ~40,000 | #5 | ⏳ |
| Ancient Buddhist Texts | CC BY | ~5,000-10,000 | #6 | ⏳ |
| Academic papers | CC BY 4.0 | 1,294 | #7 | ✅ |
| Mahasi free works | Free distribution | 235 | #8 | ✅ |
| Visuddhimagga (Pe Maung Tin) | Public Domain | 564 | #9 | ✅ |
| **ИТОГО Phase 1** | | **~100,000-130,000 chunks** | | |

**Текущий статус:** 56,684 chunks обработано (процесс частично завершён).

---

## Phase 1.5 — Audio Transcription (CC BY-NC)

### DhammaTalks.org Audio — Special Opportunity

**License:** CC BY-NC 4.0 (НЕ ND!)
- Транскрипция разрешена
- Включение в RAG разрешено
- Единственный крупный аудио-источник с чёткой разрешённостью

**Объём:** Тысячи вечерних лекций, утренних лекций, гайд-медитаций Thanissaro Bhikkhu.
**Формат:** MP3 на сайте
**Рекомендация:** Транскрибировать в Phase 1.5 после текстового ингеста.

---

## Phase 2 Sources (Require Written Permission)

### CC BY-NC-ND — "No Derivatives" проблема

Самый частый блокер — CC BY-NC-**ND** ("No Derivatives"). Вопрос: является ли RAG derivative work?

**Наша позиция:** Относимся к ND как к запрету и запрашиваем явное разрешение независимо, потому что:
1. Юридическая двусмысленность не стоит репутационного риска
2. Дхарма-сообщество ценит прозрачность и согласие
3. Consent Ledger подход строит доверие

### Требуют явного разрешения

| Источник | License issue | Объём | Действие |
|---|---|---|---|
| **Dharmaseed.org** | CC BY-NC-ND 4.0 | 46,219 лекций, 418 учителей | Email contact@dharmaseed.org |
| **AudioDharma.org** | CC BY-NC-ND 4.0 | Тысячи лекций (Gil Fronsdal+) | Contact Insight Meditation Center |
| **Forest Sangha** | CC BY-NC-ND 4.0 | Ajahn Chah, Sumedho, Amaro, 50+ книг | Contact forestsangha.org |
| **Amaravati** | CC BY-NC-ND 4.0 | Ajahn Sumedho collected works | Contact amaravati.org |
| **Abhayagiri** | CC BY-NC-ND 4.0 | Ajahn Pasanno, Amaro, 50+ titles | Contact abhayagiri.org |
| **BPS Online Library** | Free distribution, "not altered" | Wheel Publications (350+), книги | Contact bps.lk |
| **MCTB (Daniel Ingram)** | Full copyright | Pragmatic dharma manual | Contact Daniel Ingram |
| **Bhikkhu Bodhi** | Wisdom Publications copyright | Gold-standard translations | Contact Wisdom Publications |
| **Rob Burbea** | Estate/Gaia House | Jhana & emptiness teachings | Contact Gaia House / Hermes Amāra |
| **Leigh Brasington** | Personal copyright | Jhana instructions | leigh@leighb.com |
| **Shaila Catherine** | Published books | Jhana & concentration | Direct contact |

---

## Ingestion Priority Order

```
Phase 1a (немедленно — текст, структурировано):
  1. SuttaCentral bilara-data (JSON, готово к ингесту)
  2. DhammaTalks.org тексты + переводы сутт (scraping)
  3. Pa Auk "Knowing and Seeing" (один PDF → text)

Phase 1b (далее — текст, больше обработки):
  4. Access to Insight (HTML → text, per-text license tracking)
  5. PTS CC translations (OCR с PDF)
  6. Ancient Buddhist Texts (HTML → text)

Phase 1.5 (audio transcription, легально):
  7. DhammaTalks.org audio → Whisper → text

Phase 1c (дополнительно):
  8. Mahasi free works
  9. Visuddhimagga Pe Maung Tin (OCR)
  10. Selected academic papers

Phase 2 (после письменных разрешений):
  11. Dharmaseed.org
  12. Forest Sangha / Amaravati / Abhayagiri
  13. Individual teachers (Burbea, Brasington, etc.)
```

---

## Шаблон запроса разрешения

```
Subject: Permission request: Dharma RAG non-commercial use

Dear [contact],

I'm building Dharma RAG (dharma-rag.org), an open-source, free,
non-commercial tool that helps practitioners find relevant teachings
across Buddhist sources using AI retrieval.

I'd like to request permission to include [source] in our corpus.

**Usage commitment:**
- Project is 100% free, MIT-licensed, no ads, no subscriptions
- Every response cites sources with links back to the original
- Users are directed to originals for full teachings
- [Source] will be prominently attributed throughout

**Technical safeguards:**
- Source material is not distributed verbatim
- Only semantic embeddings + short quotations in responses
- Full Consent Ledger documents every source and its terms

**Boundaries respected:**
- Understanding ND restrictions — requesting explicit permission
- Will not include if you decline
- Can exclude specific works if preferred

Full project details and governance: github.com/toneruseman/dharma-rag

May we have your permission? Any boundaries we should respect?

With mettā,
[Name]
```

---

## Consent Ledger Structure

Каждый источник → YAML файл в `consent-ledger/`:

```yaml
# consent-ledger/public-domain/suttacentral-cc0.yaml
source_id: suttacentral
name: SuttaCentral Bilara Translations
url: https://suttacentral.net
license:
  type: public-domain
  name: CC0 1.0 Universal
  url: https://creativecommons.org/publicdomain/zero/1.0/
  date_confirmed: 2026-01-15
copyright_holder: SuttaCentral
attribution_required: false
commercial_use: allowed
derivative_works: allowed
notes: |
  All translations dedicated to public domain.
  We attribute as good practice, not legal requirement.
chunks_ingested: 9324
languages: [en, ru, de, pt, es]
last_updated: 2026-04-14
```

---

## Ссылки

- [Consent Ledger README](../consent-ledger/README.md)
- [Architecture Review](ARCHITECTURE_REVIEW.md)
- [Transcription Pipeline](TRANSCRIPTION_PIPELINE.md)
