# Transcription Pipeline

> Детали пайплайна транскрипции аудио-лекций. Phase 1.5 (дни 64-90).

---

## Обзор

Цель: транскрибировать ~35,000 часов аудио-лекций буддийского учения с высоким качеством Pāli-терминологии за разумную стоимость.

**Целевая стоимость:** <$2000 всего
**Целевое время:** 4-6 недель
**Целевое качество:** WER <12% на стандартном тексте, <20% на Pāli терминах

---

## Архитектура пайплайна

```
Audio file (MP3)
      │
      ▼
┌──────────────────────┐
│ 1. Format conversion │  ffmpeg → 16kHz mono WAV
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 2. Silero VAD        │  Remove silence >2s
│    pre-processing    │  (prevents hallucinations)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 3. Groq Batch API    │  Whisper Large v3 Turbo
│    with initial_     │  + Pāli initial_prompt
│    prompt            │  ~$700 for 35K hours
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 4. WhisperX forced   │  Word-level timestamps
│    alignment         │  via wav2vec2
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 5. LLM Pāli          │  GPT-4o-mini
│    correction        │  "sati patana" → "satipaṭṭhāna"
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 6. Diarization       │  pyannote (только Q&A lectures)
│    (optional)        │  ~20% corpus
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 7. Segmentation      │  Paragraph-level segments
│    for RAG           │  + metadata
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ 8. Hallucination     │  Filter artifacts
│    detection         │  "Subtitles by Amara.org"
└──────────┬───────────┘
           │
           ▼
  JSON + VTT output
```

---

## Компонент 1: Format Conversion

### Входной формат

- MP3 различного качества (80-320 kbps)
- Разные частоты дискретизации (22kHz - 48kHz)
- Моно/стерео

### Нормализация

```bash
ffmpeg -i input.mp3 \
    -ac 1 \                          # mono
    -ar 16000 \                      # 16kHz
    -af "loudnorm=I=-16:TP=-1.5:LRA=11" \  # нормализация громкости
    output.wav
```

Loudnorm критична — тихие участки иначе становятся "silent" для VAD.

---

## Компонент 2: Silero VAD

**Модуль:** `src/transcription/vad.py`

Voice Activity Detection — находит и удаляет длинные паузы (>2 сек), которые провоцируют галлюцинации Whisper ("Subtitles by Amara.org").

```python
from silero_vad import load_silero_vad, get_speech_timestamps

model = load_silero_vad()
speech_timestamps = get_speech_timestamps(
    audio,
    model,
    threshold=0.5,
    min_silence_duration_ms=2000,  # убираем паузы >2s
    speech_pad_ms=300,  # контекст по 300ms
)
```

**Эффект:** -80% non-speech hallucinations (Calm-Whisper paper arxiv:2505.12969).

---

## Компонент 3: Groq Batch API

**Модуль:** `src/transcription/groq_batch.py`

### Почему Groq Batch, а не OpenAI

| Provider | Cost | Speed | Quality |
|----------|------|-------|---------|
| **Groq Batch turbo** | **$0.02/hour** | Days | WER 11% |
| Groq Batch large-v3 | $0.055/hour | Days | WER 10.3% |
| OpenAI API | $0.36/hour | Days | WER 7.9% |
| AssemblyAI | $0.15/hour | Hours | WER 8.4% |
| SaladCloud DIY | $0.006/hour | 1-2 days | WER 7.9% |

**Решение:** Groq Batch turbo — оптимум cost/quality. 35,000 часов = ~$700.

### Pāli initial_prompt

Критический трюк: даём Whisper контекст через initial_prompt с 200+ Pāli терминами:

```python
PALI_PROMPT = """
This is a Buddhist dharma talk discussing meditation practice.
Common terms include: jhāna, samādhi, satipaṭṭhāna, vedanā, pīti,
sukha, ekaggatā, vitakka, vicāra, upekkhā, mettā, karuṇā, muditā,
paṭicca samuppāda, anicca, dukkha, anattā, nibbāna, ānāpānasati,
vipassanā, samatha, bhikkhu, bhikkhunī, saṅgha, dhamma, buddha,
nimitta, kasiṇa, dhyāna, bodhicitta, prajñā, śūnyatā, tathāgata,
and four noble truths.
""".strip()

batch_request = {
    "file": audio_url,
    "model": "whisper-large-v3-turbo",
    "language": "en",
    "response_format": "verbose_json",
    "timestamp_granularities": ["word"],
    "prompt": PALI_PROMPT,
    "temperature": 0.0,
}
```

### Batch workflow

```python
# 1. Upload audio files
batch_file_id = groq.files.upload("batch_input.jsonl")

# 2. Create batch
batch = groq.batches.create(
    input_file_id=batch_file_id,
    endpoint="/v1/audio/transcriptions",
    completion_window="24h",
)

# 3. Poll status
while batch.status not in ["completed", "failed"]:
    time.sleep(300)
    batch = groq.batches.retrieve(batch.id)

# 4. Download results
results = groq.files.download(batch.output_file_id)
```

**Rate limits:** 50,000 requests per batch, 24h window, ~$700 для 35K часов.

---

## Компонент 4: WhisperX Alignment

**Модуль:** `src/transcription/alignment.py`

Groq Whisper даёт приблизительные timestamps на уровне фраз. WhisperX через wav2vec2 делает word-level alignment:

```python
import whisperx

model_a, metadata = whisperx.load_align_model(language_code="en", device="cuda")
result_aligned = whisperx.align(
    result["segments"],
    model_a,
    metadata,
    audio,
    device="cuda",
    return_char_alignments=False,
)
```

**Зачем:** для UI подсветки текущего слова при audio playback, точная навигация "перейти к моменту где упомянута концепция X".

**Latency:** ~0.1 RTFx на GPU (не bottleneck).

---

## Компонент 5: LLM Pāli Correction

**Модуль:** `src/transcription/correction.py`

Whisper даже с initial_prompt иногда промахивается. LLM с глоссарием чинит:

```python
CORRECTION_PROMPT = """
You are correcting a transcription of a Buddhist dharma talk.
Standardize Pāli terms to their canonical spellings with proper diacritics.

Common corrections:
- "sati patana" → "satipaṭṭhāna"
- "jana" → "jhāna"
- "newbanna" → "nibbāna"
- "meta" → "mettā" (when referring to loving-kindness)
- "doka" → "dukkha"

Preserve everything else verbatim. Return corrected transcript.

Transcript:
{transcript}
"""

async def correct_pali(transcript: str) -> str:
    response = await openai.chat.completions.create(
        model="gpt-4o-mini",  # $0.15/1M input tokens
        messages=[{"role": "user", "content": CORRECTION_PROMPT.format(transcript=transcript)}],
        temperature=0.0,
    )
    return response.choices[0].message.content
```

**Cost:** ~$0.003/1K tokens → $200-500 для всего корпуса.

**Batching:** обрабатываем по 4000 токенов за раз (~5 минут аудио).

---

## Компонент 6: Speaker Diarization

**Модуль:** `src/transcription/diarization.py`

Только для Q&A лекций (~20% корпуса, идентифицируем по длительности + ручной classification).

```python
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HF_TOKEN,
)

diarization = pipeline(audio_file)

# Результат: list of (start, end, speaker_id)
for turn, _, speaker in diarization.itertracks(yield_label=True):
    print(f"{turn.start:.1f} - {turn.end:.1f}: {speaker}")
```

**Метаданные:** speaker_0 = lecturer, speaker_1+ = questioners.

**Требует HF_TOKEN** с доступом к pyannote.

**Cost:** GPU-компьют, ~$100-150 для 7000 часов Q&A.

---

## Компонент 7: Segmentation for RAG

**Модуль:** `src/transcription/segmentation.py`

Транскрипт → parent chunks (600 слов) → child chunks (150 слов).

Отличие от текстового pipeline:
- Сохраняем timestamps в каждом chunk
- Сохраняем speaker info (если диаризация была)
- Метаданные: teacher name, lecture title, retreat, year

```python
chunk = {
    "id": "ch_burbea_2019_jhana_001",
    "parent_id": "par_burbea_2019_jhana_p1",
    "text": "...",
    "metadata": {
        "teacher": "Rob Burbea",
        "lecture_title": "The Art of Jhāna",
        "retreat": "Dharma Seed 2019-03",
        "audio_url": "https://dharmaseed.org/...",
        "start_time_sec": 1245.3,
        "end_time_sec": 1298.7,
        "speaker": "Rob Burbea",
        "language": "en",
        "source": "dharmaseed",
        "license": "CC-BY-NC-ND",
        "consent_ledger_id": "dharmaseed-rob-burbea",
    }
}
```

---

## Компонент 8: Hallucination Detection

**Модуль:** `src/transcription/hallucinations.py`

Проверка на типичные артефакты:

```python
KNOWN_HALLUCINATIONS = [
    r"Subtitles by (the )?Amara\.org",
    r"Translated by",
    r"♪.*♪",  # music markers
    r"\[.*applause.*\]",
    r"Thank you for watching",
    r"Please subscribe",
    r"^\.{3,}$",  # только точки
]

def detect_hallucinations(segment: str) -> bool:
    for pattern in KNOWN_HALLUCINATIONS:
        if re.search(pattern, segment, re.IGNORECASE):
            return True
    # Проверка повторяющихся фраз
    if has_repetition(segment, min_repeats=4):
        return True
    return False
```

Подозрительные сегменты помечаются для human review, не удаляются автоматически.

---

## Выходные форматы

### JSON (для RAG)

```json
{
    "lecture_id": "burbea_2019_jhana_001",
    "metadata": {...},
    "segments": [
        {
            "id": 0,
            "text": "...",
            "start_time": 0.0,
            "end_time": 53.2,
            "speaker": "Rob Burbea",
            "words": [
                {"word": "jhāna", "start": 1.2, "end": 1.8},
                ...
            ]
        },
        ...
    ],
    "full_text": "...",
    "duration_sec": 3456.7,
    "language": "en",
    "pali_terms_detected": ["jhāna", "satipaṭṭhāna", "pīti"],
    "processing": {
        "model": "whisper-large-v3-turbo",
        "provider": "groq",
        "timestamp": "2026-05-01T14:30:00Z",
        "corrections_applied": 12,
        "hallucinations_filtered": 2
    }
}
```

### VTT (для UI playback)

```
WEBVTT

00:00:01.200 --> 00:00:05.800
Welcome everyone. Today we're going to explore the jhāna states.

00:00:06.100 --> 00:00:12.400
The word jhāna comes from the Pāli root meaning "to meditate" or "to absorb".
```

---

## Pilot run (дни 67-70)

**Scope:** 1000 лекций / ~750 часов

**Цель:** проверить pipeline, измерить качество, найти edge cases.

**Метрики:**
- WER на 20 случайных лекциях (manual check)
- Pāli term accuracy (ручная проверка глоссария)
- Cost per hour
- Processing throughput

**Acceptance criteria:**
- WER на стандартном тексте < 12%
- Pāli term error rate < 20% ПОСЛЕ LLM коррекции
- Stоимость < $0.05 за час аудио

---

## Full run (дни 71-80)

**Scope:** 46,219 лекций / ~35,000 часов

**Timeline:** 7-10 дней фонового выполнения

**Monitoring:**
- Ежедневный progress report
- Автоматические алерты на failures
- Rate limit management

**Backup plan:** если Groq Batch queue слишком длинная — параллелить через несколько проектов/ключей.

---

## Post-processing (дни 81-83)

**Scope:** 46,219 транскриптов → chunks → embeddings → Qdrant

**Этапы:**
1. Parent-child chunking (~48 hours compute)
2. Contextual retrieval preprocessing (~$200 Claude Haiku)
3. BGE-M3 embedding generation (~1 week CPU или $50 cloud GPU)
4. Qdrant upsert

---

## LoRA fine-tuning Whisper (опционально)

### Зачем

Даже с initial_prompt + LLM correction Whisper промахивается в Pāli. LoRA fine-tuning на curated Buddhist dataset даёт -30-50% Pāli term errors.

### Dataset

**Hermes Amāra Foundation** (hermesamara.org) имеет ручные транскрипты 458 лекций Роба Бёрбиа с правильными Pāli spellings. Идеальный training set.

### Training

```python
from peft import LoraConfig, get_peft_model
from transformers import WhisperForConditionalGeneration

model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-large-v3")

lora_config = LoraConfig(
    r=32,
    lora_alpha=64,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
)
model = get_peft_model(model, lora_config)

# Training on Burbea dataset
# 458 lectures, ~450 hours
# 3 epochs, A100 GPU
# ~5 hours training, ~$50 cost
```

### Deployment

- Merged weights → ~1.5GB
- Not compatible с Groq Batch (требует custom endpoint)
- Вариант: self-host через Modal.com on-demand GPU
- Или использовать только для "critical" Pāli talks (Burbea, Pa Auk)

---

## Ссылки

- [Groq Batch API docs](https://console.groq.com/docs/batch)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [WhisperX](https://github.com/m-bain/whisperX)
- [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- [Calm-Whisper paper (arxiv:2505.12969)](https://arxiv.org/abs/2505.12969)
- [Hermes Amāra Foundation](https://hermesamara.org)
