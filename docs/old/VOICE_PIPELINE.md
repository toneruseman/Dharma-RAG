# Voice Pipeline

> Архитектура live voice chat. Phase 3 (месяцы 5-9).

---

## Видение

Пользователь говорит голосом с AI-гидом о медитации. AI находит релевантные учения в корпусе, отвечает голосом, с цитатами в UI, с поддержкой медитативных сессий (ambient audio, паузы, прерывания).

**Latency target:** <800ms (сравнимо с human conversation)
**Cost target:** <$0.05/min

---

## Архитектурный выбор: Pipeline, не Native S2S

Варианты:
1. **Native Speech-to-Speech** (OpenAI Realtime, Gemini Live) — низкая latency, но нет RAG
2. **Pipeline** STT → Text RAG → TTS ✅ **наш выбор**
3. **Hybrid S2S с function calling** — компромисс, но ограничения

### Почему Pipeline

- ✅ Полный контроль над RAG injection
- ✅ Кастомные voices для медитации (спокойные, ровные)
- ✅ Pāli pronunciation через SSML
- ✅ Точные timestamps citations
- ✅ Независимая замена каждого компонента

### Компромисс

- ⚠️ Выше latency (но достижимо <800ms)
- ⚠️ Более сложная оркестрация

---

## Pipeline диаграмма

```
┌──────────────┐
│ User speaks  │
└──────┬───────┘
       │ WebRTC
       ▼
┌──────────────────────┐
│ VAD + Turn Detection │  50-200ms
│ (LiveKit turn-det.)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ STT                  │  150-200ms
│ Deepgram Nova-3      │
│ (streaming)          │
└──────────┬───────────┘
           │ transcript
           ▼
┌──────────────────────┐
│ RAG Pipeline         │  100-300ms
│ (semantic cache      │
│  → retrieve →        │
│  → rerank)           │
└──────────┬───────────┘
           │ context
           ▼
┌──────────────────────┐
│ LLM Generation       │  150-300ms first token
│ Claude Haiku         │
│ (streaming)          │
└──────────┬───────────┘
           │ response tokens
           ▼
┌──────────────────────┐
│ TTS                  │  40-200ms first byte
│ ElevenLabs Flash /   │  (streaming)
│ Cartesia Sonic /     │
│ Kokoro (self-host)   │
└──────────┬───────────┘
           │ audio chunks
           ▼
┌──────────────────────┐
│ Audio Mixer          │  <10ms
│ (ambient + TTS       │
│  via Web Audio API)  │
└──────────┬───────────┘
           │
           ▼
┌──────────────┐
│ User hears   │
└──────────────┘

TOTAL: 490-1200ms (best-worst case)
TARGET: <800ms average
```

---

## Компонент 1: Transport (WebRTC)

**Framework:** LiveKit (Phase 3.2) или Pipecat (Phase 3.1 MVP)

### Phase 3.1 (Pipecat)

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.transports.services.daily import DailyTransport

transport = DailyTransport(
    room_url="https://...",
    token="...",
    bot_name="Dharma Guide",
    params=DailyParams(
        audio_out_enabled=True,
        audio_in_enabled=True,
        vad_enabled=True,
    )
)
```

**Плюсы:** быстрый старт, Python-native, transport-agnostic
**Минусы:** не такой robust для production voice

### Phase 3.2 (LiveKit)

```python
from livekit import agents

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    agent = VoiceAgent(
        stt=deepgram.STT(model="nova-3"),
        llm=anthropic.LLM(model="claude-haiku-4-5"),
        tts=elevenlabs.TTS(voice_id="..."),
        vad=silero.VAD.load(),
        turn_detection="model",  # превосходная модель detection
    )
    await agent.start(ctx.room)
```

**Плюсы:** production-ready WebRTC, отличный turn detection, scale
**Минусы:** сложнее setup, меньше гибкость

---

## Компонент 2: VAD + Turn Detection

**Критический скрытый bottleneck!**

Наивная VAD добавляет 500-800ms (wait for silence to confirm "user done speaking").

### LiveKit turn-detection model

ML-модель предсказывает "end of turn" вероятность по семантике + просодии → 200-300ms.

```python
turn_detector = turn_detection.EOUModel()
```

### Tuning

```python
# Для медитации — более terpeливые параметры
vad_config = VADConfig(
    min_speaking_duration_ms=250,  # короче — активнее
    min_silence_duration_ms=500,   # длиннее — меньше interruptions
    speech_pad_ms=200,
)
```

---

## Компонент 3: STT (Speech-to-Text)

### Cloud: Deepgram Nova-3

```python
stt = deepgram.STT(
    model="nova-3",
    language="multi",  # multilingual support
    interim_results=True,
    smart_format=True,
    punctuate=True,
    diarize=False,
    endpointing=200,
    keywords=["jhāna:10", "satipaṭṭhāna:10", "nibbāna:10"],  # bias
)
```

**Cost:** $0.0043/minute
**Latency:** 150-200ms

### On-device: Sherpa-ONNX

Phase 3.3: Whisper-tiny/Zipformer на устройстве.

```python
# mobile (через Capacitor plugin)
import { SherpaOnnxRecognizer } from 'capacitor-sherpa-onnx';

const recognizer = await SherpaOnnxRecognizer.create({
    model: 'whisper-tiny-en',
    provider: 'cpu',
});
```

**Cost:** $0 (runs locally)
**Latency:** +100-200ms vs cloud
**Memory:** 45MB на iPhone 15 Pro
**Privacy:** audio не покидает устройство ✨

---

## Компонент 4: RAG Pipeline

**Модуль:** re-used from text pipeline (`src/rag/pipeline.py`)

### Оптимизации для voice

1. **Агрессивное кеширование** — voice queries ещё повторяемее
2. **Меньше top_k** — voice answers короче (top-5 вместо top-10)
3. **Haiku приоритет** — cost важнее для voice
4. **Skip reranking** для быстрых вопросов (под flag)

```python
async def voice_rag(query: str) -> str:
    # Быстрый путь
    if cached := await semantic_cache.lookup(query, threshold=0.88):  # looser
        return cached.response

    # Hybrid retrieval, меньше candidates
    candidates = await retriever.search(query, top_k=30)  # vs 100

    # Опциональный rerank (skip для простых)
    if is_complex_query(query):
        top_chunks = reranker.rerank(query, candidates, top_k=5)
    else:
        top_chunks = candidates[:5]

    # Claude Haiku с voice-specific prompt
    response = await generator.generate(
        query=query,
        context=top_chunks,
        system_prompt=VOICE_SYSTEM_PROMPT,
        max_tokens=200,  # короче для voice
    )

    return response
```

### Voice-specific system prompt

```
You are speaking in a live voice conversation with a meditation
practitioner. Adapt your style:

1. Keep answers short (2-4 sentences). User will ask follow-ups.
2. Natural spoken language, not written prose.
3. Pāli terms: use canonical spelling in citations, but pronounce
   naturally in speech (e.g., "jhāna" as "jā-nuh").
4. Citations at the end: "This is from MN 39" not "[source: MN 39]".
5. When unsure: "I don't have a clear source for that, could you
   ask differently?" — don't hallucinate.
```

---

## Компонент 5: LLM Generation

### Модель: Claude Haiku 4.5

**Зачем Haiku:** voice требует скорости. Quality difference меньше для коротких ответов.

```python
async with anthropic.messages.stream(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    system=VOICE_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": context_message}],
) as stream:
    async for text in stream.text_stream:
        yield text  # feeds TTS в реальном времени
```

### Streaming критичен

TTS начинает синтезировать, как только пришёл первый sentence. Пользователь слышит ответ через ~500ms после окончания вопроса.

### Sentence boundary detection

```python
buffer = ""
async for text in llm_stream:
    buffer += text
    # Отправляем в TTS по границам предложений
    while match := re.search(r'^(.*?[.!?])\s', buffer):
        sentence = match.group(1)
        await tts_queue.put(sentence)
        buffer = buffer[match.end():]
```

---

## Компонент 6: TTS (Text-to-Speech)

### Cloud options

| Provider | First byte | Cost | Quality | Pāli? |
|----------|-----------|------|---------|-------|
| **ElevenLabs Flash v2.5** | 75ms | $0.18/1K chars | ELO 1290 | ⚠️ medium |
| Cartesia Sonic Turbo | 40ms | $0.15/1K chars | ELO 1200 | ❌ |
| OpenAI TTS (gpt-4o-mini-tts) | 200ms | $15/1M chars | ELO 1100 | ⚠️ |
| Google Cloud TTS | 300ms | $16/1M chars | ELO 1050 | ⚠️ |

### Self-hosted: Kokoro-82M ⭐

- **ELO:** 1059 (#9 in TTS Arena)
- **Size:** 82M params, ~160MB
- **Cost:** $0 ongoing (GPU time)
- **Quality:** превосходное для размера

```python
from kokoro import KPipeline

pipeline = KPipeline(lang_code='a')  # 'a' for American English
audio = pipeline(text, voice="af_nova", speed=1.0)
```

**Recommendation:** ElevenLabs Flash для Phase 3.1 → Kokoro self-hosted для Phase 3.3.

### SSML для Pāli

```xml
<speak>
According to the sutta, the practice of
<phoneme alphabet="ipa" ph="saːtipəʈːʰaːnə">satipaṭṭhāna</phoneme>
involves four foundations of mindfulness.
<break time="500ms"/>
These are...
</speak>
```

### Voice selection

Для медитации — спокойные, low-register голоса:
- ElevenLabs: "Paul" или "Charlie" (male), "Rachel" (female)
- Kokoro: "af_nova", "am_adam"
- Избегать слишком энергичных "radio host" голосов

---

## Компонент 7: Audio Mixer

**Модуль:** client-side Web Audio API

Создаёт ambient layer под TTS для:
- Сокрытия latency gap
- Медитативной атмосферы
- Плавных переходов

```javascript
const audioCtx = new AudioContext();

// TTS audio from WebRTC
const ttsGain = audioCtx.createGain();
ttsSource.connect(ttsGain).connect(audioCtx.destination);
ttsGain.gain.value = 1.0;

// Ambient loop (singing bowl, nature)
const ambientGain = audioCtx.createGain();
ambientSource.connect(ambientGain).connect(audioCtx.destination);
ambientGain.gain.value = 0.2;  // low background

// During TTS gap — подсвечиваем ambient
function onSilence() {
    ambientGain.gain.linearRampToValueAtTime(0.4, audioCtx.currentTime + 0.1);
}
function onTtsStart() {
    ambientGain.gain.linearRampToValueAtTime(0.2, audioCtx.currentTime + 0.1);
}
```

---

## Medical/Meditation-Specific Features

### 1. Push-to-Talk

По умолчанию для медитации. Предотвращает случайные активации:

```javascript
button.addEventListener('pointerdown', () => agent.startListening());
button.addEventListener('pointerup', () => agent.stopListening());
```

### 2. Guided Meditation Mode

Состояния: `idle → setup → practicing → reflecting`.

```python
class MeditationSession:
    async def run(self, duration_min: int, practice: str):
        await self.guide("Let's begin. Close your eyes...")
        await self.ambient_only(duration_sec=60)  # silence

        for phase in meditation_script(practice, duration_min):
            await self.guide(phase.instruction)
            await self.ambient_only(phase.silence_sec)

        await self.guide("Gently bring your attention back...")
```

### 3. Natural Pauses

```xml
<speak>
Notice the breath coming in.
<break time="5s"/>
And the breath going out.
<break time="5s"/>
</speak>
```

5-секундные паузы SSML обрабатываются правильно и НЕ прерываются как "silence".

### 4. Interruption Handling

Пользователь может прервать гида:
- "Wait, can you repeat that?"
- "Actually, let me ask something else"
- "Stop"

LiveKit native interruption detection. При срабатывании — TTS немедленно останавливается, запускается STT listen mode.

### 5. Session State

```python
session_state = {
    "practice": "breath_awareness",
    "duration_min": 20,
    "elapsed_sec": 480,
    "phase": "main_practice",  # setup | main | closing
    "reported_state": "calm",  # user self-report
    "interruptions": 3,
    "last_guidance_sec": 450,
}
```

Сохраняется для adaptive guidance ("Ты говорил, что беспокойство. Давай вернёмся к дыханию...").

---

## Cost Model

### Per-minute breakdown

| Component | Budget config | Balanced | Premium |
|-----------|--------------|----------|---------|
| STT (Deepgram) | $0.0043 | $0.0043 | $0.0043 |
| LLM Haiku (~200 tokens) | $0.0003 | - | - |
| LLM Sonnet | - | $0.003 | - |
| LLM Opus | - | - | $0.015 |
| TTS Kokoro (self-host) | $0.0001 | - | - |
| TTS ElevenLabs Flash | - | $0.02 | - |
| TTS ElevenLabs v3 | - | - | $0.06 |
| **TOTAL** | **$0.005** | **$0.027** | **$0.079** |
| **+ margin 80%** | **$0.009** | **$0.049** | **$0.142** |

### Scale

100 DAU × 10 min/day = 1000 min/day = 30K min/month:
- Budget: **$270/mo**
- Balanced: **$1470/mo**
- Premium: **$4260/mo**

Сравнение: OpenAI Realtime API на том же масштабе = **$9000/mo**.

---

## Latency Budget

### Target: <800ms

| Component | Target | Best case | Notes |
|-----------|--------|-----------|-------|
| WebRTC capture | 30ms | 20ms | Browser / WebRTC overhead |
| VAD + turn det. | 250ms | 200ms | LiveKit turn-detection |
| STT first final | 180ms | 150ms | Deepgram Nova-3 |
| RAG retrieval | 80ms | 50ms | With cache + co-location |
| LLM first token | 200ms | 150ms | Claude Haiku |
| TTS first byte | 60ms | 40ms | ElevenLabs Flash |
| **TOTAL** | **800ms** | **610ms** | |

### Скрытые трюки

1. **Pre-fetch ambient** при начале listen → если latency spike, пользователь не слышит "dead air"
2. **Speculative TTS** — начать синтез на первом предложении, пока LLM генерирует остальное
3. **Edge STT** через Deepgram's edge regions (если доступно)
4. **Co-located Qdrant** — на том же VPS, не cross-region

---

## Privacy (критично для voice)

См. [PRIVACY.md](PRIVACY.md) для полных деталей.

Ключевое:
- **По умолчанию on-device** (Phase 3.3+)
- Zero-retention у всех cloud providers
- DPIA проведён перед public launch
- User consent explicit перед первой voice session
- Push-to-talk > always-on VAD

---

## Тестирование

### Latency measurement

```python
class LatencyTracker:
    def mark(self, event: str):
        self.events[event] = time.time()

    def report(self):
        return {
            "capture_to_stt": self.events["stt_start"] - self.events["user_speech_start"],
            "stt_to_rag": self.events["rag_start"] - self.events["stt_final"],
            "rag_to_llm": self.events["llm_start"] - self.events["rag_end"],
            "llm_to_tts": self.events["tts_first_byte"] - self.events["llm_first_token"],
            "total": self.events["tts_first_byte"] - self.events["user_speech_end"],
        }
```

Langfuse трейсит каждый voice turn.

### Load testing

**Tool:** [Artillery](https://artillery.io/) + custom WebSocket scenarios

Target: 100 concurrent voice sessions без деградации latency.

---

## Roadmap

### Phase 3.1 (месяц 6) — MVP

- Pipecat + Deepgram + Claude Haiku + ElevenLabs Flash
- WebSocket в FastAPI, simple HTML UI
- Proof-of-concept <1s latency
- **Budget config,** 10-20 тестовых users

### Phase 3.2 (месяц 7-8) — Production

- Миграция на LiveKit Agents
- Proper WebRTC, turn detection, interruptions
- Mobile integration через Capacitor
- Medical meditation features (guided sessions, ambient, pauses)
- Open для 100 users

### Phase 3.3 (месяц 9) — Scale & Privacy

- Sherpa-ONNX on-device STT/TTS
- Self-hosted Kokoro на GPU VPS
- A/B тестирование cloud vs on-device
- 1000+ users, $500/mo budget

---

## Ссылки

- [Pipecat docs](https://docs.pipecat.ai)
- [LiveKit Agents](https://docs.livekit.io/agents)
- [Deepgram API](https://developers.deepgram.com)
- [ElevenLabs API](https://elevenlabs.io/docs)
- [Kokoro TTS](https://huggingface.co/hexgrad/Kokoro-82M)
- [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
