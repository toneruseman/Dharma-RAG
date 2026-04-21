# Dharma-RAG: Comprehensive Educational Research

**For readers with basic IT knowledge but no AI/ML experience**

*Version: April 2026. Based on documents from the toneruseman/Dharma-RAG repository*

---

## Table of Contents

- [Part I. Introduction](#part-i-introduction)
- [Part II. Foundational Concepts](#part-ii-foundational-concepts)
- [Part III. Essence of Dharma-RAG](#part-iii-essence-of-dharma-rag)
- [Part IV. Overall System Architecture](#part-iv-overall-system-architecture)
- [Part V. Data Layer: Sources, Licenses, Legal Framework](#part-v-data-layer-sources-licenses-legal-framework)
- [Part VI. Text Processing Pipeline (ingest and processing)](#part-vi-text-processing-pipeline-ingest-and-processing)
- [Part VII. RAG Pipeline: How a Query Flows](#part-vii-rag-pipeline-how-a-query-flows)
- [Part VIII. Technology Choices: Deep Rationale](#part-viii-technology-choices-deep-rationale)
- [Part IX. Audio Transcription](#part-ix-audio-transcription)
- [Part X. Voice Pipeline](#part-x-voice-pipeline)
- [Part XI. Privacy, Security, Ethics](#part-xi-privacy-security-ethics)
- [Part XII. Quality Evaluation](#part-xii-quality-evaluation)
- [Part XIII. Deployment and Infrastructure](#part-xiii-deployment-and-infrastructure)
- [Part XIV. Roadmap and Current Status](#part-xiv-roadmap-and-current-status)
- [Part XV. Critical Comments and Open Questions](#part-xv-critical-comments-and-open-questions)
- [Part XVI. Wellbeing and AI Ethics in Meditation](#part-xvi-wellbeing-and-ai-ethics-in-meditation)
- [Part XVII. Summary and Conclusion](#part-xvii-summary-and-conclusion)

---

## Part I. Introduction

### What Dharma-RAG is in one paragraph

**Dharma-RAG** is an open-source research system for question-answering over Buddhist teachings. A user asks a natural-language question (in Russian, English, or other languages), and the system finds relevant passages from the Pāli Canon, lectures by contemporary meditation teachers, and academic works, then uses artificial intelligence to form a coherent answer **with mandatory source citations**. The project is being built by a solo developer following principles of pragmatic minimalism: first a working prototype on a basic €9/month server, then gradual expansion to mobile app, voice assistant, and knowledge graph. Code is distributed under MIT License, documents under CC-BY-SA 4.0.

### Who this document is for

This document is written for an **IT specialist without AI/ML experience**. The reader is expected to know:

- what APIs and HTTP requests are
- what SQL databases are
- how client-server applications work
- basics of Docker and command line

The reader does **not** need to know in advance:

- what large language models (LLMs) are
- what embeddings, vector databases, RAG are
- what chunking, reranking, hybrid search are
- specifics of Buddhist texts and Pāli language

All these concepts are explained in Part II before we move to the specific project implementation.

### Why the project exists — essence, problem, solution

**Problem #1: Volume of Buddhist texts exceeds human capacity.** The Pāli Canon is approximately 20,000 pages of canonical texts composed over centuries. Added to these are commentaries (*aṭṭhakathā*), academic translations into different languages, thousands of lectures by modern teachers (Ajahn Chah, Thanissaro Bhikkhu, Mahasi Sayadaw, Pa-Auk Sayadaw, Rob Burbea), and retreat recordings. The Dharmaseed archive alone contains about 46,000 lectures totaling approximately 35,000 hours — that's roughly 4 years of continuous listening.

**Problem #2: Standard ChatGPT or Claude doesn't work.** If you ask ChatGPT "what is *jhāna*?", it gives an approximate answer from its training data, but **cannot cite a specific sutta**, may confuse traditions (Theravāda/Mahāyāna/Vajrayāna), and sometimes simply "hallucinates" — making up citations that don't exist in original texts. For a practicing Buddhist, researcher, or teacher, this is unacceptable.

**Problem #3: Linguistic barriers.** Original texts are in Pāli and Sanskrit with diacritics: *ṃ, ñ, ṭ, ḍ, ā, ī, ū*. Online, the same term can appear as *satipaṭṭhāna*, *satipatthana*, *sati-patthana* — and standard search engines don't link them. Plus many texts exist only as unindexed PDFs or audio recordings.

**Dharma-RAG's solution:** build a system that (a) indexes all available corpus, (b) finds relevant passages for any question even with variations of Pāli term spelling, (c) uses artificial intelligence to form coherent answers, but (d) mandatorily cites specific sources so answers can be verified.

### Why "Dharma" — connection to Buddhism

The word *dharma* (Pāli: *dhamma*) in Buddhist tradition has several interrelated meanings:

1. **Buddha's teaching** — the totality of what Buddha transmitted to students over 45 years of teaching
2. **Nature of things** — how reality is arranged (*anicca* — impermanence, *dukkha* — unsatisfactoriness, *anattā* — non-self)
3. **Phenomenon** — element of experience (thought, sensation, perception)

The project's name emphasizes that this is not merely a technological exercise — it's an attempt to make the corpus of Buddhist teachings more accessible for study and practice.

The project documents explicitly prescribe a code of conduct based on Buddhist ethics (*sīla*):

- **Mettā** (loving-kindness) — treating each participant with warmth
- **Satya** (truthfulness) — honesty in discussions, acknowledging mistakes
- **Khanti** (patience) — especially with newcomers and disagreements
- **Anattā** (non-self) — criticism of ideas, not personalities

The project ends its `CONTRIBUTING.md` file with: *"Sabbe sattā sukhitā hontu — May all beings be happy"*.

---

## Part II. Foundational Concepts

### 1. What is an LLM (Large Language Model)

**LLM** is a large language model — a program trained to predict the next word in text based on a huge volume of data. Examples: ChatGPT (OpenAI), Claude (Anthropic), Gemini (Google), Llama (Meta), Qwen (Alibaba).

**How LLM works (simplified):**

```
Input text:          "The capital of France is "
                              ↓
                    ┌─────────────────┐
                    │   Neural net    │
                    │  with billions  │
                    │  of parameters  │
                    └─────────────────┘
                              ↓
Word probabilities:  "Paris"   (95%)
                     "Lyon"    (2%)
                     "Marseille" (1%)
                     ...
                              ↓
Output:                     "Paris"
```

LLMs learn from texts collected from the internet, books, and code. By the end of training, the model "knows" — i.e., can accurately continue — a huge number of facts, styles, and languages.

**Important to understand:** LLMs **do not store facts explicitly** like a database. They store *statistical patterns* between words. So when you ask about a fact, the model actually "reconstructs" it from patterns, and sometimes reconstructs incorrectly.

### 2. The LLM hallucination problem

**Hallucination** is when LLM produces a plausible but factually incorrect answer. The model confidently says: *"The Buddha spoke this phrase in MN 10, paragraph 7"* — but actually in MN 10 there is no such phrase.

**Why hallucinations are inevitable in a pure LLM:**

1. **Data compression.** Billions of pages of text are compressed into hundreds of billions of parameters. Details are inevitably lost.
2. **No verification.** The model cannot "check" its answer — it generates what statistically fits patterns.
3. **Aging.** The model is trained on data up to a certain date and doesn't know later events.
4. **Poor coverage of rare topics.** Buddhist texts in Pāli are a rare topic. The model saw less of them than English Wikipedia.

**For casual chat**, hallucinations are an annoying but not critical flaw. **For Buddhist teachings**, this can be spiritually dangerous: an incorrect citation attributed to the Buddha can mislead a practitioner.

### 3. What is RAG (Retrieval-Augmented Generation)

**RAG** is Retrieval-Augmented Generation. The idea is simple:

```
Classical LLM:
Question → LLM → Answer (possibly hallucinated)

RAG:
Question → Search in database → Retrieved documents
                              ↓
              Question + Documents → LLM → Answer (with citations)
```

**Analogy:** imagine an erudite person answering from memory (this is the LLM) versus an erudite with an open encyclopedia (this is RAG). The second is always more accurate — they don't *try to remember* a fact, they *look in the book* and paraphrase.

**Main advantages of RAG:**

- **Verifiability.** Every fact in the answer relies on a specific document that can be opened and checked.
- **Currency.** The document base is updated independently of the model — no need to retrain the LLM every time a new text appears.
- **Narrow expertise.** You can load specialized documents (Buddhist suttas) into the base and get answers specifically about them, not the model's "general knowledge".

**Classical RAG pipeline:**

```
┌─────────────────────────────────────────────────────┐
│                    INDEXING                         │
│       (done once in advance, not per request)       │
│                                                     │
│   Documents → Chunking                              │
│           → Embeddings (vectorization)              │
│           → Save to vector DB                       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   USER QUERY                        │
│                                                     │
│   Question → Query embedding                        │
│        → Search similar chunks in vector DB         │
│        → Top-10 relevant chunks                     │
│        → Question + chunks → LLM                    │
│        → Answer with citations                      │
└─────────────────────────────────────────────────────┘
```

### 4. What are embeddings

**Embedding** is a way to turn a piece of text into a set of numbers such that texts with similar meanings produce similar sets of numbers.

**Analogy (very simplified):** imagine we describe each word with two numbers — "how food-related it is" and "how technology-related":

```
              Food   Technology
"apple"    [  0.9,    0.1  ]
"pear"     [  0.9,    0.1  ]
"computer" [  0.1,    0.9  ]
"laptop"   [  0.1,    0.9  ]
"pizza"    [  0.8,    0.2  ]
```

"Apple" and "pear" are close — both are food. "Computer" and "laptop" are close. But "apple" and "computer" are far apart.

**In reality**, embeddings use not 2 but **768, 1024, 3072 or even more dimensions**. Each dimension is some automatically learned "latent characteristic" of text. A specific dimension's value alone has no human interpretation, but together they describe meaning very precisely.

**How embeddings are obtained:** a special model (called *embedding model* or *encoder*) takes text and outputs a vector. Examples:

- OpenAI `text-embedding-3-large` (3072 dimensions, paid)
- BGE-M3 by BAAI (1024 dimensions, free, open-source)
- Cohere Embed, Voyage, Jina, Nomic — other options

**Critical feature:** embeddings from different models **are incompatible**. A vector from BGE-M3 cannot be compared to a vector from OpenAI — it's like trying to measure distance between points where one is given in meters and another in degrees of latitude.

### 5. Vectors and vector space in ML

A **vector** in machine learning context is simply a list of numbers. If BGE-M3's embedding has 1024 dimensions, it's a vector of 1024 numbers, e.g.:

```
[0.234, -0.112, 0.456, 0.003, -0.887, 0.121, 0.556, ..., 0.078]
  ↑       ↑      ↑      ↑       ↑       ↑      ↑           ↑
  1st    2nd    3rd    4th     5th     6th    7th       1024th
```

**Vector space** is the abstract "space" where all such vectors live. In two-dimensional space (2 dimensions), we can draw points on paper. In 1024-dimensional — cannot visualize, but math works the same.

**Proximity in this space = semantic proximity.** If the embedding of the question "*what is meditation?*" is close to the embedding of the passage "*meditation is the practice of developing mindfulness...*", it's a good candidate for the answer.

### 6. What is a vector database

A regular **SQL database** searches well by exact match: "*find all records where name = 'Ivan'*". But it searches poorly by meaning: "*find records similar in meaning to text X*".

**A vector DB** is specifically optimized for one task: **quickly find N nearest vectors** to a given vector in high-dimensional space.

```
Regular SQL DB:              Vector DB:
┌────────────────┐          ┌──────────────────────┐
│ id │ name │... │          │ id │ text │ vector   │
├────┼──────┼────┤          ├────┼──────┼──────────┤
│ 1  │ Ivan │    │          │ 1  │ ...  │ [0.1..]  │
│ 2  │ Anna │    │          │ 2  │ ...  │ [-0.3..] │
└────────────────┘          └──────────────────────┘
                                          ↑
Query:                      Query: find 10 vectors
SELECT * WHERE             nearest to vector
name = 'Ivan'              [0.234, -0.112, ...]
```

**Main difficulty** — with millions or billions of vectors, naive iteration is impossible. So vector DBs use special indices (HNSW, IVF, ScaNN) that find approximately nearest vectors in microseconds, sacrificing a fraction of a percent of accuracy.

**Popular vector DBs:**

| DB | License | Features |
|------|----------|-------------|
| **Qdrant** | Apache 2.0 | Good performance, native hybrid search |
| **Weaviate** | BSD-3 | Modular, multimodal |
| **Milvus** | Apache 2.0 | Scales to billions, complex |
| **pgvector** | PostgreSQL | Postgres extension — vector right in relational DB |
| **Chroma** | Apache 2.0 | Simple, for prototypes |
| **LanceDB** | Apache 2.0 | Embedded, no separate service |
| **Pinecone** | Proprietary | Cloud-only |

### 7. Similarity search / cosine similarity

Given a query vector and a candidate document vector, **how do we measure their proximity?**

**Cosine similarity** is the standard metric. It measures the angle between two vectors:

```
Vectors point in
same direction:           cos(0°)  = 1.0   (max similarity)
Perpendicular:            cos(90°) = 0.0   (unrelated)
Opposite:                 cos(180°) = -1.0  (opposite)
```

In practice, in RAG systems good matches have cosine similarity **0.7–0.95**. Anything below 0.5 is usually noise.

Other metrics: *Euclidean distance* (straight-line distance in space), *dot product*. For normalized vectors they're equivalent to cosine.

### 8. Chunking — why cut documents into pieces

If you take all of MN 10 sutta (about the four foundations of mindfulness) whole and turn it into one embedding, you get an "average" vector describing the sutta generally. But if the question is specific — *"how to meditate on breathing?"* — you don't need the sutta's average vector, you need the vector **exactly of the paragraph** describing breathing.

**Chunking** is cutting long documents into pieces ("chunks") so embeddings describe local meaning.

**Types of chunking:**

```
1. Fixed-size (by characters/tokens):
   [-------- 500 tokens --------][-------- 500 tokens --------]
   ❌ May cut in mid-sentence
   ✅ Simple and fast

2. Sentence-based:
   [Sentence 1. Sentence 2.][Sentence 3. Sentence 4.]
   ✅ Natural boundaries
   ❌ Uneven size

3. Semantic (by meaningful blocks):
   [Paragraph about breath.] [Paragraph about body.] [...]
   ✅ Self-contained by meaning
   ❌ Requires LLM for separation

4. Parent-child (hierarchical):
   Parent-chunk (500 words): full context
     └─ Child-chunk (150 words): for precise search
     └─ Child-chunk (150 words): for precise search
   ✅ Precise search + rich context
   ❌ More complex to implement
```

**Dharma-RAG uses parent-child:** searches by small "children" (150 words), and feeds larger "parents" (600 words) to LLM for context.

### 9. Hybrid search (dense + sparse + BM25)

**Dense search** is what's described above: query embedding is compared with document embeddings. It understands **meaning** but can miss documents with rare terms the embedding model didn't see during training.

**Sparse search** looks at specific **words** in query and documents. If query has "*satipaṭṭhāna*" — search for documents with this word. Classic example — **BM25** (formula from 1990s search engines).

**Hybrid search** combines both approaches. This is critically important for Buddhist texts:

```
Question: "what is satipaṭṭhāna?"
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
Dense search          Sparse search / BM25
"concept of          (exact words:
mindfulness"         "satipaṭṭhāna",
                     "satipatthana")
    │                       │
    └─────────┬─────────────┘
              ↓
        Merge (RRF)
              ↓
        Top-30 documents
```

**Problem with dense-only for Dharma:** BGE-M3 tokenizer's subword vocabulary cuts *satipaṭṭhāna* into strange pieces, embedding becomes "blurred". Sparse/BM25 catches such terms directly.

**RRF (Reciprocal Rank Fusion)** — a simple algorithm for merging two ranked lists. If a document is 3rd in dense and 5th in sparse, its final rank = 1/(60+3) + 1/(60+5). The number 60 is a standard smoothing parameter.

### 10. Reranking

After the first search stage we have top-50 or top-100 candidates. But many may be irrelevant, merely similar. A **reranker** is a second stage where a heavier, more accurate model re-examines candidates and selects truly best 5–10.

```
User:
"what is jhāna?"
        ↓
┌────────────────┐
│  Retrieval     │  Fast model,
│  (hybrid)      │  selects top-100
│                │  in milliseconds
└────────────────┘
        ↓
[100 candidates]
        ↓
┌────────────────┐
│  Reranker      │  Slow but
│  (cross-       │  accurate model,
│   encoder)     │  re-examines each
│                │  (query, document) pair
└────────────────┘
        ↓
[Top-10 best]
        ↓
    To LLM
```

**Model differences:**

- **Bi-encoder** (retrieval): gives query and document separate vectors, compares by cosine. Fast but loses nuances.
- **Cross-encoder** (reranker): looks at (query, document) pair **together**, outputs one number — relevance. More accurate but slower.

**Popular reranker models:**

- `ms-marco-MiniLM-L-6-v2` — old baseline, outdated (~62% Hit@1)
- `BGE-reranker-v2-m3` — modern, multilingual, MIT (~78% Hit@1)
- `Cohere Rerank 3.5/4 Pro` — paid, high-accuracy
- `Qwen3-Reranker` — new from 2025, Apache 2.0

### 11. What is a knowledge graph

A **knowledge graph** is an explicit model of relationships between concepts.

Vector search finds **semantically similar**, but doesn't know **structural relationships**:

```
Vector doesn't "know":
  Is jhāna a factor of the path (magga-aṅga)?     ❓
  Was Ajahn Chah a teacher of Thanissaro Bhikkhu? ❓
  Are Anapanasati and Satipaṭṭhāna related?       ❓

Graph knows:
  [jhāna] ──factor-of-path→ [ariya-aṭṭhaṅgika-magga]
  [Ajahn Chah] ──teacher→ [Ajahn Sumedho]
  [Ajahn Sumedho] ──teacher→ [Thanissaro Bhikkhu]
  [anapanasati] ──method-of→ [satipaṭṭhāna]
```

**When graph is needed:**

- "Who are Thanissaro Bhikkhu's teachers?" — needs teacher-student chain
- "Which factor of the path leads to *nibbāna*?" — needs doctrine structure
- "Parallel passages of MN 10 in MA (Chinese Āgama)?" — links between corpora

**Popular graph frameworks:**

- **Neo4j** — classical graph DB, industry standard
- **Microsoft GraphRAG** — LLM automatically extracts graph (expensive, sometimes worse than plain RAG)
- **LightRAG** — cheaper alternative to GraphRAG
- **PropertyGraphIndex in LlamaIndex** — flexible tool
- **Postgres + pgvector** — graph via SQL tables, vectors alongside

### 12. LLM context window

**Context window** is the maximum amount of text (measured in tokens ≈ 0.75 words) an LLM can process at once. Examples:

- Claude Haiku 4.5: up to 200,000 tokens (≈ 150,000 words, ≈ 500 pages)
- Claude Sonnet 4.6: up to 1,000,000 tokens (≈ 3000 pages)
- GPT-4o: 128,000 tokens
- Llama 3.3 70B: 128,000 tokens

**Why can't we just dump all 20,000 pages of the Pāli Canon into context?**

1. Technical limit — even 1M tokens isn't enough
2. Cost — paying for every token in request
3. Quality — LLM works worse with long context ("lost in the middle")

**RAG solves this:** feed only 5–10 most relevant chunks to context.

### 13. Transcription (Whisper) and why

**Whisper** is OpenAI's model for converting speech to text (Speech-to-Text, STT). An open-source model working with 99+ languages. Used to turn **35,000 hours of Dharmaseed audio lectures** into indexable text.

**Whisper variants:**

- `whisper-large-v3` — most accurate, slow
- `whisper-large-v3-turbo` — new, 8× faster with minimal quality loss
- `distil-whisper` — English only, but faster

**Providers running Whisper:**

- **OpenAI API** — expensive (~$0.006/min, ~$12,600 for 35k hours)
- **Groq Batch API** — their "LPU" chips, 100× faster, ~$700 for 35k hours
- **Self-host on GPU** — cheap if you have GPU, slow

### 14. VAD, diarization, forced alignment

Audio processing for RAG isn't just transcription.

**VAD (Voice Activity Detection)** — determining where there's speech in audio versus silence/noise. Needed to:
- Cut long pauses (Whisper "hallucinates" on silence — outputs random phrases)
- Split long audio into shorter segments

**Diarization (speaker separation)** — determining "who speaks when". Needed for Q&A lectures:

```
Without diarization:
"...the four noble truths. Yes, please. Thank you for your question..."

With diarization:
[Teacher]  "...the four noble truths."
[Student]  "Yes, please."
[Teacher]  "Thank you for your question..."
```

**Forced alignment** — binding **every word** to a timestamp in audio. Needed for lecture navigation.

**Popular tools:**

- **Silero VAD** — lightweight, fast VAD
- **pyannote** — standard for diarization
- **WhisperX** — wrapper around Whisper with forced alignment
- **Calm-Whisper** — modified against silence hallucinations

### 15. Voice AI pipeline (STT + LLM + TTS)

Voice assistant is a sequence of three components:

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Micro-  │ → │   STT    │ → │   LLM    │ → │   TTS    │ → │ Speaker  │
│  phone   │   │ (speech  │   │ (answer) │   │ (text to │   │          │
│          │   │ to text) │   │          │   │ speech)  │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

**STT (Speech-to-Text):** Whisper, Deepgram Nova-3, Google Speech, AssemblyAI.

**LLM:** processes recognized text and generates response.

**TTS (Text-to-Speech):** turns response back into speech. Popular engines:
- **ElevenLabs** — very high quality, paid
- **Cartesia Sonic** — fast, low latency
- **Kokoro-82M** — open-source, self-hostable
- **Piper** — lightweight, on-device

**Alternative — speech-to-speech (S2S)** models like OpenAI Realtime and Gemini Live: directly listen to voice and respond with voice without intermediate text. Faster, but **cannot insert RAG** between them.

### 16. Observability (Langfuse) and evaluation (Ragas)

**Observability** — the ability to see what's happening inside the system in real-time. Critical for RAG: why did the system answer this question poorly? Which documents did it retrieve? Which LLM did it choose?

**Langfuse** is an open-source tool for tracing LLM applications. Records every request, response, intermediate steps, cost. Similar to regular logs but specifically for LLMs.

**Evaluation** is automatic quality assessment. Needed so that when settings change (different embedding model, different reranker), we understand: did it get better or worse?

**Key metrics:**

- **ref_hit@k** — was the correct citation among first k results?
- **faithfulness** — does the answer match retrieved documents?
- **answer_relevancy** — does the answer address the question?
- **doctrinal_accuracy** (specific to Dharma-RAG) — is Buddhist doctrine correctly represented?

**Tools:**

- **Ragas** — standard library of RAG metrics
- **DeepEval** — metrics + CI-integration (tests break if metrics drop)
- **HHEM (Vectara)** — hallucination detector

---

## Part III. Essence of Dharma-RAG

### Buddhist context

**Dharma** (Pāli: *dhamma*, Sanskrit: *dharma*) is a central concept in Buddhism with several meanings:

1. **Buddha's teaching** — the totality of what Buddha transmitted to students over 45 years of teaching
2. **Nature of things** — how reality is arranged (*anicca* — impermanence, *dukkha* — unsatisfactoriness, *anattā* — non-self)
3. **Phenomenon** — element of experience (thought, sensation, perception)

**The Pāli Canon (Tipiṭaka, "Three Baskets")** is the oldest preserved Buddhist canonical corpus:

- **Vinaya-piṭaka** — monastic discipline (~6 volumes)
- **Sutta-piṭaka** — Buddha's discourses (~25 volumes, ~20,000 pages): Dīgha-nikāya, Majjhima-nikāya, Saṃyutta-nikāya, Aṅguttara-nikāya, Khuddaka-nikāya
- **Abhidhamma-piṭaka** — philosophical psychology (~7 volumes)

Beyond the canon are **commentaries** (*aṭṭhakathā*) by Buddhaghosa (5th century CE), **sub-commentaries** (*ṭīkā*), manuals like Visuddhimagga, and a gigantic corpus of modern teachers.

### What corpus Dharma-RAG processes

Per `PROJECT_STRUCTURE.md` and `consent-ledger/`, the project works with three categories of sources:

**Public Domain:**
- **suttacentral-cc0.yaml** — SuttaCentral translations under CC0 (Bhikkhu Sujato, Bhikkhu Brahmali)
- **pa-auk-knowing-and-seeing.yaml** — works by Pa-Auk Sayadaw
- **visuddhimagga-pe-maung-tin.yaml** — Pe Maung Tin's Visuddhimagga translation (1923)

**Open License:**
- **dhammatalks-org.yaml** — works by Thanissaro Bhikkhu (Metta Forest Monastery)
- **access-to-insight.yaml** — John Bullitt's historical archive — about 1000 suttas with commentary
- **pts-cc-works.yaml** — Pali Text Society translations under CC
- **ancient-buddhist-texts.yaml** — Bhikkhu Anandajoti's site
- **academic-papers.yaml** — open academic articles
- **mahasi-free-works.yaml** — works by Mahasi Sayadaw

**Explicit Permission (Phase 2):**
- The **explicit-permission/** folder fills as letters from rights holders arrive
- Special situation: **Dharmaseed.org** contains 46,000+ lectures under **CC-BY-NC-ND** (No Derivatives). Transcription may be considered derivative work — legally ambiguous.

### Target audience

From documentation, several groups emerge:

1. **Practicing Buddhists** — seeking specific teachings on meditation, working with hindrances (*nīvaraṇa*), developing mindfulness
2. **Researchers** — academics studying Buddhist texts
3. **Translators and Dharma teachers** — needing fast corpus search
4. **Curious people** — wanting to understand fundamentals without reading thousands of pages

### Why regular ChatGPT/search doesn't work

**ChatGPT problems:**
- No precise citations, only paraphrasing from memory
- Confuses traditions (Theravāda/Mahāyāna/Vajrayāna)
- May insert non-Buddhist concepts ("soul", "God")
- Data stale by model cutoff date

**Regular search (Google) problems:**
- Doesn't connect spelling variants: *satipaṭṭhāna* ≠ *satipatthana*
- No semantic proximity: question "*how to get rid of restlessness?*" doesn't find suttas about *uddhacca-kukkucca*
- No multilingual understanding
- Doesn't work with audio lectures

**Key project challenges:**

- **Multilingual:** questions in English, Russian, Spanish; texts in Pāli, Sanskrit, Tibetan, Chinese, their translations
- **Pāli diacritics:** *ṃ, ñ, ṭ, ḍ, ā, ī, ū* — need normalization
- **Doctrinal accuracy:** highest priority; incorrect citation can spiritually mislead
- **Citation reproducibility:** every fact must reference specific sutta, paragraph, lecture timestamp

### Ethical specifics

Document `PRIVACY.md` states explicitly: **"Voice meditation data is biometric per GDPR, context of vulnerable persons"**. A practitioner in meditation is a person in **psychological vulnerability state**. Poorly designed system can:

- Disrupt meditation session with inappropriate voice assistant intervention
- Give doctrinally incorrect advice exacerbating "dark night" (*dukkha ñāṇa*)
- Create illusion of "AI-teacher" replacing living mentor
- Leak audio data (biometrics) to third parties

The project prescribes specific measures against this — we'll examine them in Parts X-XI.

---

## Part IV. Overall System Architecture

Dharma-RAG's architecture unfolds in stages. Below is the big picture of **final state (Phase 3+)**.

```
┌──────────────────────────────────────────────────────────────────────┐
│                             USERS                                    │
│                                                                      │
│   ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────────┐  │
│   │   Web   │  │  Mobile  │  │  Telegram  │  │  Voice (mic)     │  │
│   │(browser)│  │(iOS/And) │  │    bot     │  │  on-device or    │  │
│   │         │  │Capacitor │  │            │  │  via WebRTC      │  │
│   └────┬────┘  └────┬─────┘  └─────┬──────┘  └────────┬─────────┘  │
│        │            │              │                   │            │
└────────┼────────────┼──────────────┼───────────────────┼────────────┘
         │            │              │                   │
         └────────────┴──────────────┴───────────────────┘
                      │
                      ▼ HTTPS / WebRTC
┌──────────────────────────────────────────────────────────────────────┐
│                       CLOUDFLARE (CDN, DDoS)                         │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    CADDY 2.x (reverse proxy, auto-SSL)               │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND (Python 3.12)                  │
│                                                                      │
│   ┌────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│   │   /api/    │  │ /api/query/  │  │ WebSocket for voice        │  │
│   │   query    │  │   stream     │  │ (Pipecat → LiveKit Agents) │  │
│   └─────┬──────┘  └──────┬───────┘  └──────────────┬─────────────┘  │
│         │                │                          │                 │
│         └────────────────┴──────────────────────────┘                 │
│                          │                                            │
│                          ▼                                            │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                      RAG PIPELINE                              │  │
│  │                                                                │  │
│  │  [Semantic Cache] → [Lang Detect] → [Query Expansion]          │  │
│  │       ↓                                        ↓               │  │
│  │  [LLM Router]                       [Hybrid Retrieval]         │  │
│  │       ↓                         (Dense + Sparse + BM25)        │  │
│  │  [Context Builder]   ←   [Reranker]   ←   (top-100)            │  │
│  │       ↓                                                        │  │
│  │  [Generator (Claude)] → [Citation Verify] → Response           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────┬──────────────────────────┬────────────────────────────────┬────┘
      │                          │                                │
      ▼                          ▼                                ▼
┌──────────┐         ┌──────────────────┐         ┌────────────────────┐
│ QDRANT   │         │    POSTGRES      │         │  Langfuse          │
│ vector   │         │  ┌─────────────┐ │         │  (observability)   │
│ DB       │         │  │ Langfuse DB │ │         │  + Phoenix for     │
│          │         │  ├─────────────┤ │         │  metrics           │
│ 900k+    │         │  │ Knowledge   │ │         └────────────────────┘
│ chunks   │         │  │ Graph       │ │
│ dense    │         │  │ (Phase 2+)  │ │                  │
│ +sparse  │         │  └─────────────┘ │                  ▼
│ +ColBERT │         └──────────────────┘         ┌────────────────────┐
└──────────┘                  │                   │  CLAUDE API        │
                              │                   │  (Anthropic)       │
                              ▼                   │  Haiku/Sonnet/Opus │
                   ┌──────────────────┐           │  routing           │
                   │ Semantic Cache   │           └────────────────────┘
                   │ (separate        │
                   │  Qdrant coll.)   │
                   └──────────────────┘
```

### User interfaces

- **Web** (Phase 4): first server-rendered Jinja2 + HTMX with Server-Sent Events (SSE) for streaming, then migration to SvelteKit (Phase 7)
- **Mobile** (Phase 7): Capacitor wrapper over the same SvelteKit — 95% code reuse
- **Telegram bot** (Phase 5): aiogram 3.x, built-in FSM for meditation guide flows, webhook-based in production
- **Voice** (Phase 8–9): first Pipecat + cloud services, then LiveKit Agents + on-device Sherpa-ONNX

### Network layer

- **Cloudflare** as first level: DNS, DDoS protection, CDN. Free plan
- **Caddy 2.x** on VPS as reverse proxy, automatic SSL via Let's Encrypt
- DNS records: `@` and `api` through Cloudflare proxy (IP hiding), `bot` without proxy (Telegram requires direct HTTPS for webhook)

### Backend

- **FastAPI** on Python 3.12, run through **Uvicorn** with two workers
- Serves: HTTP API, SSE streaming, WebSocket for voice sessions

### Storage layers

- **Qdrant** (vector DB) — all corpus embeddings, semantic cache
- **Postgres** — Langfuse database + (Phase 2+) knowledge graph via pgvector and separate tables
- **VPS filesystem** — logs, glossary, snapshots

### External services

- **Claude API** (Anthropic) — primary LLM for generation. Routing: Haiku (fast/cheap) → Sonnet (default) → Opus (complex philosophical questions)
- **Groq Batch API** (for transcription, Phase 6) — turning 35,000 hours of audio into text
- **Deepgram** (optional, for voice) — cloud STT with low latency

### Observability

- **Langfuse** (self-hosted) — tracing every request
- **Prometheus + Grafana** (Phase 4) — system metrics for FastAPI, Qdrant, VPS resources
- **UptimeRobot** — free external monitoring

### Deployment

- **Hetzner Cloud** (Helsinki, EU-friendly): CX32 (Phase 1) → CCX33 (Phase 2 after ~1000 DAU) → GEX44 with GPU (Phase 3 for voice)
- **Docker Compose** for orchestration (author explicitly rejected Kubernetes as "excessive")
- **GitHub Actions** for CI/CD: build → push to GHCR → SSH-deploy to VPS

---

## Part V. Data Layer: Sources, Licenses, Legal Framework

### Text corpus sources

#### SuttaCentral

- **URL:** `suttacentral.net`
- **Content:** Pāli Canon + parallels in Chinese Āgamas + Tibetan texts, translations into English and other languages
- **Format:** bilara-data JSON on GitHub (`suttacentral/bilara-data`)
- **License:** Bhikkhu Sujato and Bhikkhu Brahmali translations under **CC0** (public domain)
- **Volume:** ~6,000 suttas of main nikayas + thousands of parallels

**bilara-data structure:**

```
bilara-data/
├── translation/
│   ├── en/
│   │   ├── sujato/
│   │   │   ├── sutta/
│   │   │   │   ├── dn/       # Dīgha-nikāya
│   │   │   │   ├── mn/       # Majjhima-nikāya
│   │   │   │   ├── sn/       # Saṃyutta-nikāya
│   │   │   │   ├── an/       # Aṅguttara-nikāya
│   │   │   │   └── kn/       # Khuddaka-nikāya
│   │   │   └── vinaya/
│   │   └── brahmali/
│   │       └── vinaya/
│   └── ru/
│       └── ...
└── root/
    └── pli/           # original in Pāli
```

**What it gives the project:** clean, structured corpus with **UID system** (`mn10` = Majjhima-nikāya sutta 10, `an3.65` = Aṅguttara-nikāya, Book of Threes, sutta 65). These are canonical identifiers that all citations rely on.

#### DhammaTalks.org

- **URL:** `dhammatalks.org`
- **Content:** works by Ajahn Thanissaro (Geoffrey DeGraff), founder of Metta Forest Monastery in California
- **Format:** EPUB books and text articles
- **License:** free distribution
- **Key works:** *"Wings to Awakening"*, *"The Mind Like Fire Unbound"*, multi-volume collection of sutta translations, hundreds of *dhamma talks*

#### Access to Insight

- **URL:** `accesstoinsight.org`
- **Content:** John Bullitt's historical archive, one of the first Buddhist sites (since 1993)
- **Format:** ZIP archive of entire site
- **Special feature:** contains unique translations by Bhikkhu Thanissaro, Nyanaponika Thera, Bhikkhu Bodhi, not on SuttaCentral

#### Visuddhimagga

- **Content:** "Path of Purification" by Buddhaghosa (5th century CE) — classical guide to Buddhist practice and philosophy
- **Translation:** Pe Maung Tin (1923), in public domain

#### Dharmaseed.org (Phase 1.5 / Phase 6)

- **URL:** `dharmaseed.org`
- **Content:** about **46,000 audio lectures** from 600+ teachers (Joseph Goldstein, Sharon Salzberg, Tara Brach, Mark Epstein, Rob Burbea, etc.), total length ~35,000 hours
- **License:** **CC-BY-NC-ND** (Attribution, Non-Commercial, No Derivatives)
- **Problem:** transcription may be considered derivative work — prohibited
- **Project's solution:** obtain explicit permissions from teachers or (fallback) use only for internal search, without publishing transcripts

### Consent Ledger — legal artifact

File `PROJECT_STRUCTURE.md` introduces the **Consent Ledger** concept:

```
consent-ledger/
├── README.md
├── public-domain/
│   ├── suttacentral-cc0.yaml
│   ├── pa-auk-knowing-and-seeing.yaml
│   └── visuddhimagga-pe-maung-tin.yaml
├── open-license/
│   ├── dhammatalks-org.yaml
│   ├── access-to-insight.yaml
│   ├── pts-cc-works.yaml
│   ├── ancient-buddhist-texts.yaml
│   ├── academic-papers.yaml
│   └── mahasi-free-works.yaml
└── explicit-permission/
    └── (fills as received)
```

Each YAML file describes:

```yaml
source: dharmaseed.org/teacher/42
teacher: "Ajahn Sucitto"
license: "CC BY-NC-ND 3.0"
consent_status: "explicit_email_2025-11-03"
consent_evidence: "ledger/emails/sucitto_2025-11-03.md.gpg"
scope: "transcription, indexing, RAG-Q&A, no-redistribution-verbatim"
revocation_contact: "dharma-rag@..."
updated: 2026-02-15
```

**Why this is needed:**

1. **Good-faith documentation** for DMCA workflow
2. **Revocation endpoint:** if teacher writes — their materials excluded from next reindex within ≤7 days
3. **Transparency** — Consent Ledger under version control in git, visible to everyone
4. **Moral standing** — shows the project respects intellectual property

Analogs: Mozilla Common Voice (per-contribution consent), C2PA provenance metadata, Linux Foundation DCO.

### License strategy

Document `DHARMA_RAG_TECHNICAL_AUDIT.pdf` notes a critical point: **the project is under MIT, but uses Claude (paid) at the center of generation**. This contradicts the "100% free-to-user" promise. Solutions:

1. **BYOK (Bring Your Own Key)** — user enters their API key Claude/OpenRouter, server doesn't store
2. **Open default + Claude premium** — Llama 3.3 70B through DeepInfra by default, Claude as option
3. **Self-hosted Qwen3-32B** — on own GPU infrastructure (€184/mo Hetzner GEX44)

---

## Part VI. Text Processing Pipeline (ingest and processing)

### General ingest pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                   INGESTION PIPELINE                           │
│                                                                │
│  1. Source download (SuttaCentral git, DhammaTalks ZIP)        │
│                               ↓                                │
│  2. Parser (src/ingest/*.py) — one for each source             │
│                               ↓                                │
│  3. Cleaner (src/processing/cleaner.py)                        │
│     • Unicode NFC normalization                                │
│     • HTML strip                                               │
│     • Pāli diacritics normalized                               │
│                               ↓                                │
│  4. Metadata extraction                                        │
│     • sutta_uid, nikaya, translator, language, teacher,        │
│       audience, pericope_id, source_file                       │
│                               ↓                                │
│  5. Chunker (src/processing/chunker.py)                        │
│     • Structural chunking by sutta/section boundaries          │
│     • Parent-child: 600 words parent / 150 words child         │
│                               ↓                                │
│  6. Contextual Retrieval (Anthropic)                           │
│     • Claude Haiku generates 50-100 tokens of context          │
│       for each child chunk                                     │
│                               ↓                                │
│  7. Embeddings (BGE-M3, optionally MITRA-E)                    │
│     • dense (1024 dim)                                         │
│     • sparse (lexical)                                         │
│     • ColBERT multi-vector (optional)                          │
│                               ↓                                │
│  8. Upsert to Qdrant                                           │
│     • Collection dharma_v1 (or vN)                             │
│     • payload: text, text_contextual, metadata                 │
│                                                                │
│  9. Parallel: BM25 index (rank-bm25)                           │
│     • Custom tokenizer with Pāli normalization                 │
│     • Saved as pickle                                          │
└────────────────────────────────────────────────────────────────┘
```

### Cleaner — text normalization

Per `PROJECT_STRUCTURE.md`, module `src/processing/cleaner.py` does:

**Unicode NFC.** Pāli term *satipaṭṭhāna* can be encoded two ways:
- composite: single character `ṭ`
- decomposed: `ṭ` as t + combining dot below

Visually identical, but bytes different — search won't match. NFC (Canonical Composition) brings them to a single format.

**HTML strip.** Sources like DhammaTalks EPUB contain tags `<p>`, `<i>`, `<span class="pali">`. Need to remove them, keeping only text.

**Pāli diacritics.** Module `src/processing/normalizer.py` creates two representations:

```
Original:           satipaṭṭhāna
Canonical:           satipaṭṭhāna (with diacritics, for precision)
ASCII-fold:          satipatthana (without diacritics, for BM25 fallback)
```

This is needed because users write queries differently.

### Chunker — parent-child strategy

```
Sutta MN 10 (~5000 words):
│
├─ Parent chunk 1 (600 words): introduction + general instruction
│   ├─ Child 1.1 (150 words): "Evaṃ me sutaṃ..."
│   ├─ Child 1.2 (150 words): audience context
│   ├─ Child 1.3 (150 words): start of instruction
│   └─ Child 1.4 (150 words): four foundations
│
├─ Parent chunk 2 (600 words): kāyānupassanā (contemplation of body)
│   ├─ Child 2.1 (150 words): ānāpānasati (breathing)
│   ├─ Child 2.2 (150 words): postures of body
│   ├─ Child 2.3 (150 words): awareness of actions
│   └─ Child 2.4 (150 words): parts of body
│
├─ Parent chunk 3: vedanānupassanā (contemplation of feelings)
│   └─ ...
│
└─ ...
```

**How it's used:**

1. Query *"how to meditate on breathing?"* → searched among **child chunks**
2. Finds **Child 2.1** (150 words about *ānāpānasati*) — very precise match
3. Feeds **Parent chunk 2** (600 words) to LLM — with context *"this is part of body contemplation"*

**Why this matters:** if we only fed child (150 words), LLM would lose context. If we only searched by parent (600 words), search precision would drop.

**Critical problem with old chunking:** result of **2% ref_hit@5** — meant correct citation landed in top-5 in only 2% of cases. That's a failure. Reasons:

1. Dense-only retrieval without sparse
2. Chunks could cut pericopes (repeating formulas) in the middle
3. Boilerplate like *"Evaṃ me sutaṃ..."* repeats in thousands of suttas and "pollutes" dense search

### Contextual Retrieval — Anthropic's method

This is a key technique coming to Dharma-RAG from Anthropic's September 2024 blog post.

```
WITHOUT Contextual Retrieval:

Chunk: "He then instructed them to practice four foundations..."

Problem: unclear who "he" is, who "them" are, which "four foundations"?

═══════════════════════════════════════════════════════════════════

WITH Contextual Retrieval:

Context (generated by Claude Haiku):
"This passage is from MN 10 Satipaṭṭhāna Sutta of the Pāli Canon, 
where the Buddha addresses monks in Kammassadhamma about the four 
foundations of mindfulness as a direct path to liberation."

Chunk (original):
"He then instructed them to practice four foundations..."

Combined text for embedding and BM25:
"[Context]\n\n[Chunk]"

Result: now embedding "understands" context. Query 
"what is satipaṭṭhāna?" reliably finds this chunk.
```

**Economics:**

- Claude Haiku 4.5: $1 per 1M input tokens, $5 per 1M output tokens
- **Prompt caching** (90% savings on repeat documents)
- On 56,000 chunks: about **$20–50 one-time**

**Measured effect** (from Anthropic publications):

- **−49%** retrieval errors with contextual embeddings + contextual BM25
- **−67%** errors when adding reranker on top

For Dharma-RAG this is a *mandatory* technique, not "nice-to-have".

### Embeddings — BGE-M3

Model `BAAI/bge-m3` (MIT license) — the project's primary choice. **Unique property:** in one forward pass generates three representations of a chunk:

```
One chunk (e.g., child-chunk of 150 words)
                   ↓
         ┌─────────────────────┐
         │    BGE-M3 model     │
         │  (568M parameters)  │
         └─────────────────────┘
           ↓           ↓           ↓
       ┌───────┐  ┌──────────┐  ┌─────────────┐
       │ Dense │  │  Sparse  │  │   ColBERT   │
       │ 1024  │  │ lexical  │  │ multi-vec   │
       │ dim   │  │(IDF-like)│  │(late inter- │
       │       │  │          │  │ action)     │
       └───────┘  └──────────┘  └─────────────┘
```

**Characteristics:**

- 1024-dimensional dense vector
- 8192 tokens of context (important for parent chunks and late chunking)
- 100+ languages
- MIT license (compatible with project)

### MITRA-E — specialized model for Buddhist texts

Document `ARCHITECTURE_REVIEW.pdf` mentions as the most important finding:

> **MITRA** (arXiv 2601.06400, January 2026) — specialized framework for Buddhist NLP, containing 1.74M parallel sentence pairs between Sanskrit, Chinese and Tibetan, plus Gemma 2 MITRA-E — domain-specific embedding model outperforming BGE-M3, BM25, FastText and LaBSE on Buddhist benchmarks. Open license.

---

## Part VII. RAG Pipeline: How a Query Flows

This is the central section of the document. Let's break down the query path from user to answer step by step.

### Full pipeline schema

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        QUERY PIPELINE                                    │
│                                                                          │
│  User: "what is jhāna?"                                                  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 1. Semantic cache check                                            │  │
│  │    - Embed query                                                   │  │
│  │    - Search in separate Qdrant collection "cache"                  │  │
│  │    - If found cos > 0.92 → return cached answer                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓  (cache miss)                                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 2. Language detection                                              │  │
│  │    - EN / RU / other                                               │  │
│  │    - determines answer language                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 3. Query expansion                                                 │  │
│  │    a) Pāli glossary lookup: "jhāna" → add "jhana",                 │  │
│  │       "dhyana" (Sanskrit), "meditation absorption" (English)       │  │
│  │    b) (Optional) HyDE: Claude generates hypothetical               │  │
│  │       paragraph-answer for conceptual queries                      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 4. LLM Router                                                      │  │
│  │    Classifier (Claude Haiku, ~100 tokens):                         │  │
│  │      - factoid → Haiku 4.5                                         │  │
│  │      - synthesis → Sonnet 4.6                                      │  │
│  │      - deep philosophical → Opus 4.6                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 5. Hybrid retrieval (top-100)                                      │  │
│  │                                                                    │  │
│  │    ┌──────────┐     ┌──────────┐     ┌──────────┐                  │  │
│  │    │  Dense   │     │  Sparse  │     │   BM25   │                  │  │
│  │    │  (BGE-M3)│     │  (BGE-M3)│     │ (custom  │                  │  │
│  │    │          │     │          │     │   Pāli)  │                  │  │
│  │    └─────┬────┘     └────┬─────┘     └─────┬────┘                  │  │
│  │          │               │                  │                       │  │
│  │          └───────────────┼──────────────────┘                       │  │
│  │                          ↓                                          │  │
│  │                   RRF Fusion (k=60)                                 │  │
│  │                   weights [1.0, 0.8, 0.6]                           │  │
│  │                          ↓                                          │  │
│  │                     Top-100 chunks                                  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 6. Reranker (BGE-reranker-v2-m3)                                   │  │
│  │    Cross-encoder evaluates each (query, chunk) pair                │  │
│  │    Top-100 → Top-10                                                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 7. MMR diversification                                             │  │
│  │    Penalty for identical pericope_id                               │  │
│  │    Protection from "10 copies of one jhana passage"                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 8. Parent context builder                                          │  │
│  │    For each top-10 child → find its parent chunk (600 words)       │  │
│  │    Form context for LLM                                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 9. Generation (Claude)                                             │  │
│  │    System prompt: role, citation rules,                            │  │
│  │                   refusal patterns, deference language             │  │
│  │    User prompt: query + 10 parent chunks (with UIDs)               │  │
│  │    → Streaming tokens                                              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 10. Citation extraction & verification                             │  │
│  │     Regex parses <cite source="MN10" loc="12.3-5"/>                │  │
│  │     Verifies: UID present in retrieved_context?                    │  │
│  │     If not — flag as hallucination                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 11. Stream response (SSE)                                          │  │
│  │     Events:                                                        │  │
│  │       retrieval_started                                            │  │
│  │       retrieval_done { chunks: [...] }                             │  │
│  │       generation_token { text }                                    │  │
│  │       citation { source, loc, quoted }                             │  │
│  │       done { metrics }                                             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 12. Cache writeback                                                │  │
│  │     Save (query_embedding, response, chunk_ids)                    │  │
│  │     to Qdrant cache with TTL 30 days                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│              ↓                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ 13. Langfuse trace                                                 │  │
│  │     Entire chain of steps recorded for debugging and metrics       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1. Semantic cache

**What:** a separate collection in Qdrant storing (question → answer) pairs.

**Why:** dharma queries are highly cacheable. *"How to cope with restlessness?"* ≈ *"What to do with the hindrance of restlessness?"* ≈ *"Restlessness in meditation"* — this is the same question in three formulations. Regular key-value cache (Redis) doesn't catch this, semantic does.

**Effect:** 40–60% cache hit rate on real queries → sharp reduction in LLM cost.

### 2. Language detection

**What:** determining query language (library `langdetect` or `lingua`).

**Why:** answer must be in the same language. Query *"What is jhāna?"* → answer in Russian, but Pāli terms preserved in original (*jhāna*, not transliterated in text).

### 3. Query expansion

**Pāli glossary (200+ terms):** `data/glossary/pali.yaml`:

```yaml
- term: jhāna
  variants: [jhana, jhaana]
  sanskrit: dhyana
  english: [meditative absorption, meditation state]
  russian: [джхана, поглощение]
  category: samatha
  sutta_refs: [AN 9.36, MN 39, DN 2]
```

**HyDE (Hypothetical Document Embeddings)** — technique for conceptual queries. Idea: LLM generates hypothetical paragraph-answer, and its embedding is used for search. Result is usually better than embedding a short query.

**Measured:** 85% vs 78.7% baseline accuracy for one additional LLM call.

### 4. LLM Router

**Claude cost (April 2026):**

```
                  Input $/1M    Output $/1M   Cache hit
Haiku 4.5          $1.00         $5.00        $0.10
Sonnet 4.6         $3.00         $15.00       $0.30
Opus 4.6           $5.00         $25.00       $0.50
```

**Routing:**

- *Factoid* ("When did Buddha live?") → Haiku
- *Synthesis* ("Compare Theravāda and Mahāyāna on *anattā*") → Sonnet
- *Deep philosophical* ("How does *paṭicca-samuppāda* explain suffering?") → Opus

**Expectation:** routing 70/20/10 Haiku/Sonnet/Opus gives ~$0.014/req vs $0.046 for all-Sonnet.

### 5. Hybrid retrieval

Top-100 candidates at fusion output. RRF with k=60 and weights [1.0, 0.8, 0.6] for dense/sparse/BM25.

### 6. Reranker

**BGE-reranker-v2-m3** (MIT, 568M parameters): takes top-100, outputs relevance for each (query, chunk) pair, filters to top-10. Latency: on CPU 300–600 ms, on GPU 50–80 ms.

**Reranker comparison:**

| Reranker | Params | Quality (Hit@1) | License |
|----------|--------|-----------------|---------|
| `BGE-reranker-v2-m3` | 568M | ~78% | MIT ✓ |
| `Cohere rerank-3.5` | closed | +3–5 pp | API-only |
| `Jina-reranker-v2` | 278M | +15× speed | CC-BY-NC ✗ |
| `Qwen3-Reranker-0.6B` | 600M | +2 pp to BGE | Apache 2.0 |
| `ms-marco-MiniLM-L-6-v2` | 22M | ~62% | outdated |

### 7. MMR diversification

**Maximum Marginal Relevance** — algorithm balancing relevance and diversity. For Dharma: formulas (*pericope*) repeat in hundreds of suttas verbatim. Without MMR, top-10 might be 10 copies of the same *jhāna* formula from different suttas.

### 8. Parent context builder

For each child chunk from top-10, its parent chunk (600 words) is found. LLM gets 10 parent chunks — richer context.

### 9. Generation (Claude)

**System prompt:**

```
You are an assistant for Buddhist teachings. Your task:

1. Answer ONLY based on provided source excerpts.
2. Support every statement with a citation in format <cite source="MN10" loc="12.3-5"/>.
3. If excerpts don't contain answer — say "I don't know" and don't invent.
4. Don't mix traditions (Theravāda/Mahāyāna/Vajrayāna) without explicit indication.
5. Use deference language: "Sources suggest...", "According to MN 10...",
   not "The Buddha says..." in first person.
6. Preserve Pāli terms in original: jhāna, not "absorption".
```

### 10. Citation extraction & verification

Post-processing: regex parses `<cite source="..." loc="..."/>`, verifies UID presence in retrieved_context, flags mismatches as hallucination.

**Anthropic Citations API** (since January 2025) gives this natively: `cited_text` contains exact character spans from source, not billed as output.

### 11. Streaming response (SSE)

Frontend renders answer as it arrives:

```
SSE events:
  retrieval_started
  retrieval_done     { chunks: [{uid, text_preview, score}, ...] }
  generation_token   { text: "Jh" }
  generation_token   { text: "āna" }
  ...
  citation           { source: "MN10", loc: "12.3-5", quoted: "..." }
  done               { total_tokens, cost, latency_ms }
```

---

## Part VIII. Technology Choices: Deep Rationale

This is the longest part because every architectural decision in Dharma-RAG is justified in the documents by comparative analysis.

### 1. Why BGE-M3 as embedding model

**Comparison (from `ARCHITECTURE_REVIEW.pdf`):**

| Model | Params | Dim | Ctx | License | MMTEB | Verdict for Dharma |
|-------|--------|-----|-----|---------|-------|---------------------|
| **BAAI/bge-m3** | 568M | 1024 | 8192 | **MIT ✓** | ~59 | current choice; dense+sparse+ColBERT in one pass |
| multilingual-e5-large-instruct | 560M | 1024 | 512 | MIT | ~63 | higher quality, but 512 ctx kills long-doc |
| jina-embeddings-v3 | 570M | 32–1024 | 8192 | **CC-BY-NC ✗** | ~54 | license incompatible with MIT |
| Cohere embed-multilingual-v3 | proprietary | 1024 | 512 | API-only | n/a | closed, paid |
| OpenAI text-embedding-3-large | proprietary | 3072 | 8191 | API-only | ~64.6 | closed, not updated since Jan 2024 |
| **Qwen3-Embedding-8B** | 8B | 4096 | 32k | Apache 2.0 | **70.58** | best quality, but 10× slower |
| **Qwen3-Embedding-4B** | 4B | 2560 | 32k | Apache 2.0 | ~69.5 | sweet spot — Phase 2 candidate |
| Qwen3-Embedding-0.6B | 600M | 1024 | 32k | Apache 2.0 | ~64.3 | replaces BGE-M3 dense, but no sparse |
| Gemini Embedding 2 | proprietary | 3072 | — | API-only | 67.71 | retrieval leader, paid |

**Why specifically BGE-M3:**

1. **Three representations in one forward pass** — only model with this feature
2. **MIT license** — perfectly compatible with project's MIT license
3. **8192 tokens context** — allows applying **late chunking**
4. **100+ languages** — supports Russian, Spanish, others
5. **Native support in Qdrant** — `SparseVectorParams(modifier=Modifier.IDF)` and `FusionQuery(RRF)` work directly with BGE-M3 output

**Weak points (honestly acknowledged):**

- Yields to Qwen3-Embedding-4B by 5–10 pp MMTEB
- Pali tokenizer suboptimal (XLM-RoBERTa cuts *saṃsāra* into strange subtokens)

**Phase 2 plan:** A/B with Qwen3-Embedding-4B. If it gives +5–7 pp NDCG@10 on golden eval set — migrate.

### 2. Why Qdrant

**Comparison:**

| Engine | Hybrid native | Sparse BGE-M3 | Ops overhead | License | Verdict |
|--------|---------------|---------------|--------------|---------|---------|
| **Qdrant 1.16+** | ✅ Universal Query API + RRF/DBSF | ✅ IDF modifier from 1.10 | Low (single Rust binary) | Apache 2.0 | **best fit** |
| Weaviate 1.27+ | ✅ BM25 + vector | ⚠ weaker | Medium | BSD-3 | schema-heavy, overkill |
| Milvus 2.5 | ✅ | ✅ | High (etcd, Pulsar, MinIO) | Apache 2.0 | overkill below 10M+ |
| pgvector 0.8 + ParadeDB | ✅ via SQL RRF | via pg_search | Low | PostgreSQL / **AGPL v3** | AGPL for pg_search — legal concern |
| Vespa | ✅ industrial | ✅ | Very high (JVM, YQL) | Apache 2.0 | overhead disproportionate |
| LanceDB 0.15+ | ✅ FTS + vector | ✅ | Zero (embedded) | Apache 2.0 | ideal for 56k, but not multi-instance |

**Key reasons for Qdrant:**

1. **Native BGE-M3 sparse support** — `modifier=Modifier.IDF` from version 1.10
2. **FusionQuery(RRF/DBSF)** — right in engine
3. **Apache 2.0** — purely MIT-compatible
4. **Single Rust binary** — low ops overhead
5. **ACORN** (from 1.16+) — metadata filtering **inside** HNSW traversal
6. **Scalar quantization + mmap** — 1M × 1024-dim vectors in ~1.5–2 GB RAM

### 3. Why Claude (with caveats)

**Arguments for Claude:**

- **Citations API** (GA since January 2025): char-level spans, `cited_text` not billed — 15–25% savings
- **1M tokens context in Sonnet 4.6**
- **Prompt caching** (90% savings on repeat documents)

**Criticism:**

> "Claude-at-generation-center contradicts '100% free to user' promise and MIT ethos. Even with best routing, Claude is 3–4× more expensive than open stack."

**Economic comparison:**

| Scenario | $/day | $/month |
|----------|-------|---------|
| All Sonnet 4.6 no cache | $19.5 | ~$585 |
| All Sonnet 4.6 + prompt cache (80% hit) | $10.86 | ~$326 |
| All Haiku 4.5 no cache | $6.5 | ~$195 |
| **Routing 70/20/10 + cache** | $5.20 | ~$156 |
| Llama 3.3 70B via DeepInfra | $1.58 | **~$47** |
| Qwen3-32B self-host on Hetzner GEX44 | amortization | ~€184 fixed |

**Recommendation:**

1. Abstract LLM through **LiteLLM** or OpenRouter
2. **Default free-to-user:** Llama 3.3 70B via DeepInfra
3. **Premium opt-in:** Claude Sonnet 4.6 + Citations API via **BYOK**

### 4. Why BGE-reranker-v2-m3

Already covered in Part VII. MIT license, multilingual, 8192 ctx, drop-in replacement for old `ms-marco-MiniLM-L-6-v2` with improvement ~+15–20 pp.

### 5. Why FastAPI

RAG bottleneck is LLM inference (1–5 sec), not serialization. So Litestar's 2× advantage via msgspec **irrelevant**. FastAPI provides:

- 10K+ req/s
- Native SSE/WebSocket
- Shared event loop with aiogram and Qdrant client
- 80K+ GitHub stars
- First-class integration with all AI libraries

### 6. Why HTMX for Phase 1, SvelteKit for Phase 2+

**HTMX + Jinja2 for MVP (14 KB, streaming SSE chat without JS build).**

**HTMX advantages:**
- Zero JS build
- Server rendering — SEO-friendly
- Streaming via built-in SSE extension
- Minimum cognitive load for solo developer

**When to switch to SvelteKit:** when complex client logic needed (filter panel for suttas, diff between translations, concept graph visualization).

**SvelteKit 2 + Svelte 5 runes:** compiles to vanilla JS → bundles 30–50% smaller than Next.js. **+ Capacitor** → 95% code reuse for mobile.

### 7. Why aiogram 3.x for Telegram

- `python-telegram-bot` — retrofitted async in v20, complex due to history
- **`aiogram 3.x`** — async-native from start, built-in FSM for meditation guide flows, strong Russian-speaking community

### 8. Why Hetzner

| Provider | Pros | Cons |
|----------|------|------|
| **Hetzner** ⭐ | Cheap, EU (Helsinki), reliable | Outdated UI |
| Servers.com | Flexible configs | More expensive |
| Linode (Akamai) | Good data centers | More expensive |
| Vultr | Many locations | Weaker RAM |
| AWS/GCP/Azure | Scale | Expensive for solo |

**Hetzner CX32 — €9/mo:** 4 vCPU, 8 GB RAM, 80 GB NVMe, 20 TB traffic. Ideal starter server.

### 9. Why Langfuse (with Phoenix discussion)

**Langfuse:**
- MIT license
- Self-hosted via Docker Compose
- On 1M traces/mo: **$0** vs ~$2,500 for LangSmith

**Phoenix (Arize) as alternative:**
- ELv2 license
- Low complexity (single Docker + Postgres)
- ~2 GB RAM vs Langfuse v3 ~16 GB
- Pre-built RAG evals

**Recommendation from `DHARMA_RAG_TECHNICAL_AUDIT`:** start with Phoenix for MVP, migrate to Langfuse if prompt versioning needed.

### 10. Knowledge graph: Postgres + pgvector

From `GRAPH_VS_EMBEDDING_RERESEARCH_2026.md`:

**Why not Neo4j:** separate service, separate technology.

**Why not Microsoft GraphRAG:** cost $50–500+ on 56k chunks, in Han et al. 2025 benchmarks **loses to vanilla RAG by −13.4%** accuracy on HotpotQA.

**Why Postgres + pgvector:**

```sql
-- Concepts (graph, stable fact)
CREATE TABLE concepts (
    id VARCHAR(100) PRIMARY KEY,
    label VARCHAR(200),
    pali VARCHAR(200),
    english VARCHAR(500),
    tradition VARCHAR(50)
);

-- Relations
CREATE TABLE concept_relations (
    from_concept VARCHAR REFERENCES concepts(id),
    to_concept VARCHAR REFERENCES concepts(id),
    relation_type VARCHAR,
    source_sutta VARCHAR,
    PRIMARY KEY (from_concept, to_concept, relation_type)
);

-- Chunks with vectors (pgvector)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    text TEXT,
    embedding vector(1024),
    tradition VARCHAR,
    teacher VARCHAR
);
```

**Main principle:**

> **Knowledge graph is a CONSTANT of the project. Embedding model is a VARIABLE.**

The graph *"jhāna → leads_to → nibbāna"* is a FACT, doesn't change when embedding model is replaced.

**Plan:**
- **Phase 1:** Qdrant as-is (vectors only)
- **Phase 2 (month 3):** add graph to Postgres (200–500 concepts manually + YAML)
- **Phase 3 (month 6+):** evaluate migration to "everything in Postgres"

### 11. Whisper via Groq Batch for transcription

**Option comparison (35k hours Dharmaseed):**

| Approach | Cost | Time | WER |
|----------|------|------|-----|
| **Groq Batch turbo** | **~$700** | Hours | ~11% |
| Groq Batch large-v3 | ~$1,943 | Hours | ~10.3% |
| SaladCloud (100 GPU) | ~$200–440 | 1–2 days | ~7.9% |
| Vast.ai 4×RTX 4090 | ~$400–600 | 2–3 days | ~7.9% |
| AssemblyAI Universal-2 | ~$5,250 | Days | ~8.4% |
| OpenAI Whisper API | ~$12,600 | Days | ~7.9% |
| Local GTX 1080 Ti | ~$200 electricity | **200–400 days** | ~7.9% |

**Verdict:** Groq Batch turbo — best fit. Managed, fast, cheap.

---

## Part IX. Audio Transcription

Separate pipeline, launched in Phase 6 (days 64–90).

### Full transcription pipeline

```
Dharmaseed audio (~46,000 lectures, ~35,000 hours)
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 1. Silero VAD pre-processing                             │
│    Remove silence >2 seconds                             │
│    Prevent Whisper hallucinations                        │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 2. Normalization                                         │
│    16 kHz mono                                           │
│    Loudnorm -16 LUFS                                     │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 3. Groq Batch API: Whisper large-v3-turbo                │
│    initial_prompt = 200 Pāli terms:                      │
│    "This is a Buddhist dharma talk discussing jhāna,     │
│     dukkha, satipaṭṭhāna, vedanā, pīti, nimitta,         │
│     samādhi, vipassanā, ānāpānasati, mettā,              │
│     paṭicca samuppāda, anicca, anattā, nibbāna..."       │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 4. WhisperX forced alignment                             │
│    Word-level timestamps                                 │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 5. pyannote diarization (only for Q&A ~20% of corpus)    │
│    Determining "Teacher" vs "Student"                    │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 6. LLM Pali correction (GPT-4o-mini or Claude Haiku)     │
│    Standardizing spellings:                              │
│    "sati patana" → "satipaṭṭhāna"                        │
└──────────────────────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────┐
│ 7. Paragraph segmentation                                │
│ 8. Hallucination detection                               │
│ 9. Output: JSON/VTT with metadata                        │
└──────────────────────────────────────────────────────────┘
```

### Four-layer Pāli correction

**Layer 1: Whisper initial_prompt** — free, immediate. Just pass Whisper a list of 200 Pāli terms before audio.

**Layer 2: LLM post-processing** — GPT-4o-mini or Claude Haiku with Buddhist glossary standardizes spellings. `~$0.003/1K tokens`.

**Layer 3: LoRA finetune Whisper** (optional):

> 458 Rob Burbea lectures already transcribed by Hermes Amāra Foundation with correct spellings. Ideal dataset. LoRA (r=32, q_proj/v_proj) on A100, 1–5 hours, ~$50, −30–50% Pāli term errors.

**Layer 4: Silero VAD preprocessing** — mandatory. Calm-Whisper (arXiv 2505.12969) reduces non-speech hallucinations by 80%.

### Why Groq Batch

**Groq** — startup with specialized **LPU** (Language Processing Unit) chips. Result: 100× faster than regular GPU and cheap.

**Groq Whisper-large-v3-turbo:**
- Speed: 216× real-time (hour of audio in ~17 seconds)
- Cost: $0.04/hr audio
- On 35k hours: **$1,400**

**Project's final estimate:** ~$700–2,000 for 4–6 weeks with full post-processing.

---

## Part X. Voice Pipeline

The most ambitious part of the project, Phase 8–9 (months 5–9).

### Pipeline vs Native Speech-to-Speech

```
1. Native Speech-to-Speech (OpenAI Realtime, Gemini Live)
   Mic → LLM (S2S) → Speaker
   ✓ Low latency (500 ms)
   ✗ NO RAG CONTROL
   ✗ Cannot inject precise citations

2. Hybrid S2S with function calling
   Partially solves RAG, but limits voice quality

3. Pipeline (STT → Text RAG → TTS) ← WINS
   Mic → STT → Text → RAG → LLM → Text → TTS → Speaker
   ✓ Full citation control between STT and LLM
   ✓ Custom calm voice
   ✓ SSML phoneme hints for Pāli terms
   ✗ Higher latency (600–800 ms)
```

**Verdict:**

> Anthropic has no voice API as of April 2026 — pipeline is the only path for Claude + voice RAG.

### Latency budget: <800ms realistic

```
┌────────────────────────────────────────────────────────────┐
│                Voice Pipeline Latency Budget               │
│                                                            │
│  Component              Target   Best    Provider          │
│  ─────────────────────────────────────────────────────────│
│  Capture + network      50ms     20ms    WebRTC LiveKit    │
│  STT                    200ms    150ms   Deepgram Nova-3   │
│  End-of-turn detection  300ms    200ms   LiveKit turn-det  │
│  RAG retrieval+rerank   100ms    50ms    Co-located Qdrant │
│  LLM first token        300ms    150ms   Claude 3.5 Haiku  │
│  TTS first byte         200ms    40ms    Cartesia Sonic /  │
│                                          ElevenLabs Flash  │
│  ─────────────────────────────────────────────────────────│
│  TOTAL                  <800ms   ~450ms                    │
└────────────────────────────────────────────────────────────┘
```

**Trick from `ARCHITECTURE_REVIEW`:**

> Play ambient sound (singing bowl, nature) ~100ms during gap — latency becomes psychologically invisible.

### Voice economics

```
┌─────────────────────────────────────────────────────────────────┐
│             Voice Economics per Minute                          │
│                                                                 │
│  Configuration                        $/min    100×10min/day    │
│  ─────────────────────────────────────────────────────────────│
│  Budget (Deepgram+Haiku+Kokoro self)  $0.009   $27/mo           │
│  Balanced (Deepgram+Sonnet+11labs)    $0.046   $138/mo          │
│  Premium (Deepgram+Sonnet+11labs v3)  $0.098   $294/mo          │
│  OpenAI Realtime                      $0.30    $900/mo          │
└─────────────────────────────────────────────────────────────────┘
```

**Kokoro-82M** — open-source TTS (~160 MB, ELO 1,059, #9 TTS Arena). Self-hosted — cost lever. At 10,000 concurrent × 10 min = ~$27,000/mo vs $900,000/mo for OpenAI Realtime.

### Frameworks

- **Pipecat** (Daily.co, BSD-2): Python-first, transport-agnostic. MVP in hours.
- **LiveKit Agents** (Apache 2.0): WebRTC-native, excellent turn-detection, interruption handling.

**Plan:** Pipecat for MVP (Phase 8), LiveKit for production (Phase 9).

### Meditation specifics

**Unique requirements:**

1. **Push-to-talk during active meditation** — prevents accidental voice activation
2. **VAD with elevated threshold** — only intentional speech triggers system
3. **SSML pauses** `<break time="5s"/>` — natural silence
4. **Web Audio API mixer** — TTS + ambient (bells, bowls) via `AudioContext`
5. **Session state tracking** — meditation phase, elapsed time, reported state
6. **Pāli pronunciation dictionary → SSML:**

```xml
<phoneme alphabet="ipa" ph="dʒʰɑːnə">jhāna</phoneme>
<phoneme alphabet="ipa" ph="pə.t̪it̪͡ɕt͡ɕə səmupˈpaː.d̪ə">paṭicca samuppāda</phoneme>
```

### On-device voice

**Default architecture:**

```
User ─── [local STT Sherpa-ONNX] ───► transcript
                                           │
                                           ▼
                                 [HTTPS] ───► server
                                    RAG pipeline
                                           │
                                 [text response] ───► device
                                           │
                                 [local TTS Kokoro]
                                           │
                                        audio
```

**Advantages:**
- Minus 200 ms latency
- 0 cost per minute
- Offline on retreat
- Audio **never leaves device**

---

## Part XI. Privacy, Security, Ethics

### Privacy principles (PRIVACY.md)

1. **Collect minimum data** — only what's necessary for operation
2. **Zero retention by default** — data not stored longer than needed
3. **Transparency** — open code, you see everything
4. **User control** — right to delete always works
5. **Voice especially protected** — meditation is a state of vulnerability

### Retention periods

```
┌──────────────────────────────────────────────────────┐
│  Data type                   Retention    Where      │
│ ────────────────────────────────────────────────────│
│  Cached query text           30 days      Qdrant     │
│  IP address (hash)           24 hours     Redis      │
│  Langfuse traces             90 days      Postgres   │
│  Application logs            30 days      VPS FS     │
│  Voice audio                 0            (not kept) │
│  Voice transcripts in DB     0            (not kept) │
└──────────────────────────────────────────────────────┘
```

### GDPR compliance

**Article 15 (Right to access):** Email `privacy@dharma-rag.org`, response time 30 days, JSON format.

**Article 17 (Right to deletion):**
- Telegram bot: command `/forget` deletes all traces with your user_id
- Web: form at `/privacy/delete`

**Article 20 (Portability):** Export via `/privacy/export`.

### Voice privacy — DPIA

Voice is **biometric data** per GDPR. **DPIA** (Data Protection Impact Assessment) required before public launch of voice features.

**Key measures:**

1. **On-device by default** via Sherpa-ONNX — audio doesn't leave device
2. **Cloud fallback** — only with explicit consent, zero-retention mode at provider, transcript deleted immediately
3. **Vulnerability context:**
   - Push-to-talk by default (not always-on)
   - Clear recording indication (icon + audio signal)
   - Warning before first voice session

### Guardrails — prohibitions

**Mandatory refusal on:**

- Suicide/self-harm queries → hardcoded response with crisis lines + licensed therapist recommendation
- Medical interpretation of meditation side-effects (*dark night*, *dukkha ñāṇa*, panic during retreat) → don't answer based on suttas, redirect to **Cheetah House / Brown University Britton Lab resources**
- Specific trauma advice → refusal + redirect

### Doctrinal safety — key risk

From `ARCHITECTURE_REVIEW.pdf`:

> **Most dangerous risk is doctrinal.** A RAG system confidently distorting Buddhist teachings — mixing Theravāda and Mahāyāna on *anattā*, or incorrectly describing jhāna factors — can cause real harm to practitioners. Every answer must cite specific sources (sutta name, paragraph, lecture timestamp). System prompt must explicitly instruct Claude to say "I don't know" instead of fabrication. Faithfulness metric is not optional — it's the single most important quality gate of the entire system.

---

## Part XII. Quality Evaluation

### Golden eval test set

**Current status (`EVALUATION.md`):**

- **150+ queries** in `tests/eval/test_queries.yaml`
- Coverage:
  - 30% semantic (*"What is the nature of suffering?"*)
  - 25% lexical (*"Define satipaṭṭhāna"*, *"What does MN 10 say?"*)
  - 20% hybrid (*"What does Thanissaro Bhikkhu say about jhāna?"*)
  - 15% multilingual (Russian, Spanish)
  - 10% doctrinal (Theravāda/Mahāyāna differences)

**Query format:**

```yaml
- id: q001
  query: "What is jhāna?"
  language: en
  type: semantic
  difficulty: basic
  expected_sources:
    - sutta: AN 9.36
      relevance: high
    - sutta: MN 39
      relevance: high
  expected_topics:
    - jhana
    - samatha
    - samadhi
  expected_terms:
    - jhāna
    - samādhi
  golden_answer: |
    Jhāna refers to states of deep meditative absorption developed
    through samatha (concentration) practice...
  contraindicated:  # must NOT appear in answer
    - "Hindu"
    - "yoga"
    - "Krishna"
```

**Goal by v1.0:** 500 queries.

### Key metrics

**Retrieval:**

- `ref_hit@k` — fraction of queries where at least one `expected_sources` in top-k
  - Phase 1 goal: >40%
  - Phase 2: >70%
  - v1.0: >85%
- `topic_hit@k` — match between `retrieved_topics` and `expected_topics`
- `MRR` (Mean Reciprocal Rank) — position of first relevant
- `recall@k` — fraction of relevant in top-k

**Generation (Ragas):**

- `faithfulness` — all claims supported by context
  - Phase 1: >0.80
  - v1.0: >0.92
  - **Critical metric for doctrinal safety!**
- `answer_relevancy` — does answer address question
- `context_precision` — fraction of useful retrieved chunks
- `context_recall` — coverage of golden_answer

**Custom metrics:**

- **`doctrinal_accuracy`** ⭐ — most important for project:

```
RUBRIC (1-5 scale):
5 = Perfectly accurate. Citations match. Tradition properly attributed.
4 = Mostly accurate. Minor imprecision.
3 = Partially accurate. Some doctrinal points correct, others vague.
2 = Significantly inaccurate. Conflates traditions.
1 = Severely inaccurate. False attribution, syncretism.
```

- `citation_validity` — all `[source: SN 56.11]` actually exist (>95%)
- `pali_term_accuracy` — Pāli terms correct (>90%)

### CI integration

`.github/workflows/eval.yml` runs eval on every PR to `dev`. Regression >5pp on any metric — PR blocked.

### Human evaluation

- Sample 30 random queries before each release
- 2–3 Buddhist practitioners evaluate independently
- Disagreements discussed
- Averaged rating → benchmark for LLM-as-judge

---

## Part XIII. Deployment and Infrastructure

### Full production architecture

```
                    ┌──────────────────┐
   Internet ────►   │    Cloudflare    │  (DNS, DDoS, CDN)
                    └────────┬─────────┘
                             │ HTTPS
                    ┌────────▼─────────┐
                    │   Caddy 2.x      │  (reverse proxy, auto-SSL)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   FastAPI app    │  (port 8000)
                    │   uvicorn        │
                    └────┬─────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
       ┌──────▼──────┐      ┌──────▼──────┐
       │   Qdrant    │      │  Langfuse   │
       │   :6333     │      │   :3000     │
       └─────────────┘      └─────────────┘
```

### Hetzner platform

| Phase | Server | Characteristics | Price/mo |
|-------|--------|-----------------|----------|
| Phase 1 | CX32 | 4 vCPU, 8 GB RAM, 80 GB NVMe | €9 |
| Phase 2 | CCX33 | 8 dedicated vCPU, 32 GB RAM | €60 |
| Phase 3 (GPU) | GEX44 | RTX 4000 SFF Ada, 20 GB VRAM | €184 |

### Initial Setup (Day 50)

**Basic protection:**

```bash
# Create dharma user, disable root SSH
# UFW firewall: only 22, 80, 443
# Fail2ban, unattended-upgrades
```

**Docker + Caddy:** installed via `get.docker.com` and APT.

### Caddyfile

```caddyfile
dharma-rag.org, www.dharma-rag.org {
    encode gzip zstd

    handle /api/* {
        reverse_proxy localhost:8000
    }

    handle /api/query/stream {
        reverse_proxy localhost:8000 {
            transport http {
                read_timeout 5m
            }
        }
    }

    log {
        output file /var/log/caddy/dharma-rag.log
    }
}
```

### CI/CD — GitHub Actions

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    steps:
      - Login to GHCR
      - Build and push Docker image
      - Deploy to Hetzner via SSH
```

### Backup strategy

**What's backed up:**

1. **Qdrant collections** — critical
2. **Langfuse Postgres** — desirable
3. **Pāli glossary and configs** — in git, OK
4. **Transcripts** — on separate storage (Hetzner Storage Box €4/mo/1TB)

**Daily backup script (3 AM):**

```bash
#!/bin/bash
DATE=$(date +%Y%m%d)

# Qdrant snapshot
docker exec dharma-qdrant curl -X POST http://localhost:6333/snapshots

# Postgres dump
docker exec dharma-langfuse-db pg_dump -U langfuse langfuse | \
    gzip > /mnt/backup/langfuse_$DATE.sql.gz

# Sync to Storage Box
rclone sync /mnt/backup storagebox:dharma-rag-backups/

# Clean up locally (keep 7 days)
find /mnt/backup -mtime +7 -delete
```

### Monitoring

- Caddy checks upstream automatically
- App: `/api/health` returns `{"status": "ok", "version": "0.4.0"}`
- UptimeRobot — free external monitoring every 5 min
- Prometheus + Grafana (Phase 4)
- Telegram alerts: error_rate >1%, latency p95 >5s, diskspace <10%

### Disaster recovery

1. **VPS down:** restore from backup to new VPS, ~2 hours
2. **Qdrant corrupted:** restore from snapshot, ~30 min
3. **Langfuse lost:** not critical
4. **Key leak:** change `ANTHROPIC_API_KEY`, deploy, ~10 min

### Scaling

**Signs:** CPU > 80%, RAM > 90%, Latency p95 > 3s.

**Steps:**
1. Vertical scale: CX32 → CCX33 (€9 → €60), one click
2. Read replicas for Qdrant
3. App workers: `uvicorn --workers 4 → 8`
4. At >5000 DAU — separate Qdrant server, Redis for cache, Load balancer

---

## Part XIV. Roadmap and Current Status

Entire project divided into 10+ phases, detailed in `DAY_BY_DAY_PLAN.pdf`.

### Phase overview

```
┌────────────────────────────────────────────────────────────────┐
│  Phase             Duration         Goal                       │
│ ──────────────────────────────────────────────────────────────│
│  0. Setup          Days 1-3         Environment + repository   │
│  1. Foundation     Days 4-14        Eval framework + Qdrant    │
│                                     + basic retrieval          │
│  2. Quality        Days 15-28       Hybrid + Contextual +      │
│                                     reranking                  │
│  3. Generation     Days 29-42       Claude + RAG pipeline      │
│                                     + CLI                      │
│  4. Web MVP        Days 43-56       FastAPI + HTMX +           │
│                                     first deploy               │
│  5. Telegram bot   Days 57-63       aiogram bot                │
│  6. Transcription  Days 64-90       Dharmaseed transcription   │
│  7. Mobile         Months 4-5       SvelteKit + Capacitor      │
│  8. Voice MVP      Months 5-6       Pipecat + Deepgram +       │
│                                     ElevenLabs                 │
│  9. Voice Prod     Months 6-9       LiveKit + on-device        │
│                                     + meditation features      │
│  10. Advanced      Months 9-12      LightRAG + curriculum      │
│                                     + scale                    │
└────────────────────────────────────────────────────────────────┘
```

### Phase 1: Foundation (key milestones)

- **Day 4:** Migration of 56,684 chunks.
- **Day 5–6:** Golden eval test set (100 queries) + Ragas setup.
- **Day 7:** Qdrant collection, BGE-M3 installed.
- **Day 8:** Baseline dense-only retrieval → **2% ref_hit@5** (failure, confirming problem).
- **Day 9–10:** BGE-M3 sparse → hybrid retrieval: lexical queries from 0% to **>30%**.
- **Day 11:** BM25 as third retriever → **>50%** ref_hit@5 on lexical.
- **Day 12–13:** BGE-reranker-v2-m3 → **topic_hit@5 +15 pp**.
- **Day 14:** `docs/RAG_PIPELINE.md` documentation, first PR to `main`.

### Phase 2: Quality (days 15–28)

- **Day 15–16:** MITRA-E evaluation.
- **Day 17–19:** Contextual Retrieval for all 56,684 chunks. $20–50. Expected: **−49% errors**.
- **Day 20–21:** 200+ Pāli terms glossary + query expansion.
- **Day 22–24:** Semantic cache. Goal: 40–60% hit rate.
- **Day 25–26:** Parent-child chunking refinement.
- **Day 27–28:** Final Phase 2 eval. Goals: **ref_hit@5 >70%, topic_hit@5 >85%, faithfulness >0.85**.

### Phase 3-10 (brief)

- **Phase 3** (29-42): Claude, streaming, citations, CLI, v0.3.0.
- **Phase 4** (43-56): FastAPI + HTMX + deployment.
- **Phase 5** (57-63): Telegram bot.
- **Phase 6** (64-90): Dharmaseed transcription.
- **Phase 7-10**: mobile, voice, advanced.

### Cost model

**One-time costs:**

```
┌──────────────────────────────────────────────────────────┐
│  Item                                         Cost       │
│ ────────────────────────────────────────────────────────│
│  Transcription 35K hours (Groq Batch turbo)   $700-2000  │
│  Pāli LLM correction (GPT-4o-mini)            $200-500   │
│  Speaker diarization 7K hours Q&A             $100-150   │
│  LoRA finetune (A100 × 5h)                     $50       │
│  Contextual Retrieval preprocessing           $20-50     │
│  Embedding generation 1M chunks               $10-60     │
│ ────────────────────────────────────────────────────────│
│  TOTAL one-time                               $1,080-2,810│
└──────────────────────────────────────────────────────────┘
```

**Monthly costs:**

```
┌──────────────────────────────────────────────────────────┐
│  Component           Phase 1     Phase 2     Phase 3     │
│ ────────────────────────────────────────────────────────│
│  Hetzner server      €9          €60         €60-120    │
│  Claude API          $50-100     $150-300    $200-400   │
│  Voice (Deepgram+TTS) $0          $30-60      $50-200    │
│  Embedding API       $5-10       $10-20      $10-20     │
│  Domain/DNS/CDN      $2          $22         $22        │
│  Modal GPU on-demand $0          $10-30      $20-50     │
│ ────────────────────────────────────────────────────────│
│  TOTAL/mo            $70-125     $290-500    $370-820   │
└──────────────────────────────────────────────────────────┘
```

### Risk analysis

```
┌──────────────────────────────────────────────────────────────────┐
│ Risk                       Severity   Probab.   Mitigation        │
│ ─────────────────────────────────────────────────────────────────│
│ CC-BY-NC-ND Dharmaseed      Critical   Medium    Seek permission;│
│ blocks publication                                fair-use       │
│                                                                   │
│ Pāli terms consistently     High       High      4-layer         │
│ mistranscribed                                    pipeline; LoRA │
│                                                                   │
│ Claude API cost explodes    High       Medium    Semantic cache  │
│ with voice                                        (40-60% hit);  │
│                                                   fallback Haiku │
│                                                                   │
│ Voice latency >800ms in     Medium     Medium    Ambient audio;  │
│ prod                                              on-device bypass│
│                                                                   │
│ Solo developer burnout      High       High      Phase ruthlessly│
│                                                                   │
│ Qdrant OOM on 8GB VPS       Medium     Low       Scalar quant +  │
│                                                   mmap → ~2GB    │
│                                                                   │
│ Doctrinal inaccuracy        Critical   Medium    Faithfulness    │
│                                                   >0.85; citations│
│                                                   mandatory      │
│                                                                   │
│ Voice privacy leak          Critical   Low       On-device by    │
│                                                   default; DPIA  │
└──────────────────────────────────────────────────────────────────┘
```

### Success criteria by phase

- **Phase 1 MVP (day 56):** public URL, Telegram bot, works on 90% of queries
- **Phase 1.5 (day 90):** full Dharmaseed corpus transcribed, retrieval >70% ref_hit@5
- **Phase 2 (month 5):** mobile app in Google Play (alpha)
- **Phase 3 voice (month 9):** voice chat <800 ms latency, $0.05/min cost
- **v1.0 (month 12):** 1000 active users, 50 contributors, 10K monthly queries

---

## Part XV. Critical Comments and Open Questions

From `DHARMA_RAG_TECHNICAL_AUDIT.pdf` — independent critical analysis.

### 1. BYOK pattern vs Claude-only

**Problem:** MIT project promising "100% free-to-user" centrally uses paid Claude API. Logical contradiction — someone always pays.

**Recommendation:**

1. Abstract LLM through **LiteLLM/OpenRouter** from day one
2. Default free-to-user backend: **Llama 3.3 70B** via DeepInfra ($0.35/M, ~$47/mo)
3. Premium opt-in: Claude Sonnet 4.6 + Citations API, user enters own API key (**BYOK**)

### 2. Golden eval set must be on Day 5

**Problem:** without metrics, every change is guessing.

**Recommendation:**

- Ragas TestsetGenerator + cross-model check + 30% human verification = $5 and a couple evenings
- Taxonomy: 40% citation, 30% thematic, 10% comparative, 10% lineage, 10% ethical
- **Fail CI if faithfulness < 0.75**

### 3. Contextual Retrieval — mandatory, not optional

**Arguments:**

- −49% retrieval errors (published Anthropic benchmark)
- $20–50 one-time on 56k chunks
- For Buddhist corpus, effect expected **even stronger**

### 4. CC-BY-NC-ND problem for Dharmaseed

Legal question requiring resolution:

- Fair-use analysis (transformative use in RAG answer + snippet + attribution)
- Per-teacher opt-in (teacher letters)
- Worst case — internal use without transcript publication

### 5. Chunking problem 2% ref_hit@5

Failure not only of model but of chunking. 150-word children may cut:

- **Boilerplate** (*"Evaṃ me sutaṃ..."* repeats in thousands of suttas → pollutes dense search)
- **Pericopes** (satipaṭṭhāna formula, jhāna formula repeat hundreds of times)
- **Anaphoric connectivity** (he said... the Blessed One answered...)

**Solutions:**

- Structural chunking by `<section>` from SuttaCentral JSON
- Parent-document retrieval with child=384 tokens, parent=1024–2048 tokens
- Contextual Retrieval prefixes
- Late chunking (Jina, 2024)
- Pericope-aware dedup + MMR diversification

### 6. Langfuse v3 too heavy

Requires Postgres + ClickHouse + Redis + S3 + 2 containers, minimum 16 GB RAM.

**Recommendation:** start with **Phoenix** (single Docker + Postgres, ~2 GB RAM), migrate to Langfuse if prompt versioning needed.

### 7. Dispersed pipeline expensive mistakes

- **Jina v3, XTTS v2, F5-TTS** have non-commercial licenses — incompatible with MIT
- **pg_search (ParadeDB)** under AGPL v3 — cognitive dissonance with MIT ethos
- **Microsoft GraphRAG** often worse than vanilla RAG on fact-query (−13.4% accuracy)
- **No cloud STT** has native Pāli model — only via `initial_prompt`
- **No TTS "out of the box"** pronounces diacritics correctly — need Pāli-G2P preprocessor

---

## Part XVI. Wellbeing and AI Ethics in Meditation

### Meditation as vulnerable state

From `PRIVACY.md`:

> Meditation is a state of mental vulnerability. Additional measures:
> - Push-to-talk by default (not always-on)
> - Clear recording indication (icon + audio signal)
> - "Pause recording" button always available
> - Warning before first voice session

### Uncanny valley risk in voice guide

From `ARCHITECTURE_REVIEW.pdf`:

> **Audio companion and uncanny valley.** AI-generated guide sounding slightly wrong can disrupt meditation more than absence of guide. Consider pre-generation and human-review of meditation scripts for guided sessions instead of real-time.

Uncanny valley — phenomenon where very human-like but not quite thing (voice, animation, robot) evokes anxiety. For meditation this is especially harmful.

### Not a replacement for a live teacher

Guardrails in UI:

- **Mandatory disclaimers** everywhere: *"Not a substitute for direct contact with a teacher; RAG may err on subtle doctrinal points"*
- **Deference language:** *"Sources suggest…"*, *"The Pali Canon speaks of… (MN 10)"*, not *"The Buddha says…"* in first person
- **Hardcoded disclaimer in footer** on every page
- **"Ask a human teacher" button** with ready query+context summary → forum/email

### Dark night, dukkha ñāṇa — when to redirect to therapist

From `DHARMA_RAG_TECHNICAL_AUDIT`:

> **For meditation side-effect questions (dark night, dukkha nāṇa, panic during retreat) — don't answer based on suttas**, but redirect to **Cheetah House / Brown University Britton Lab resources**.

These are specific organizations engaged in scientific study and assistance with difficult meditative experiences. Supported by Professor Willoughby Britton at Brown University.

### Anti-misuse guardrails in UI

Input-classifier (cheap LLM or regex) detects:

- **Suicide/self-harm triggers** → hardcoded response with crisis lines (Samaritans, Crisis Text Line)
- **Medical interpretation of meditation side-effects** → redirect
- **Specific advice on traumatic trigger** → refuse + redirect

### Public audit log

Anonymized refused-queries published monthly → transparency to community.

---

## Part XVII. Summary and Conclusion

### Project essence in one block

**Dharma-RAG** is an open-source system for meaningful answer-seeking over Buddhist teachings. It accepts a natural-language question, finds relevant passages from the Pāli Canon, contemporary teachers' works, and academic sources, and forms a coherent answer with mandatory references to primary sources. The project is built with pragmatic minimalism by a solo developer: MIT license, open-source stack (BGE-M3 + Qdrant + FastAPI + Claude), deployment on a €9 Hetzner server, phased roadmap to mobile app and voice assistant. Central values — citation verifiability, doctrinal accuracy, user privacy (especially in voice features), and ethical caution in working with spiritual practices.

### Key architectural strengths

1. **Hybrid retrieval (dense + sparse + BM25) via RRF** — solves OOV terms problem in Pāli
2. **Contextual Retrieval (Anthropic)** — mandatory technique giving −49% errors for $20–50
3. **BGE-M3 as only model with three representations** — inference economy, MIT license
4. **Parent-child chunking** — precise search with rich LLM context
5. **LLM routing Haiku/Sonnet/Opus** — 3–4× economy vs all-Sonnet
6. **Claude Citation API** — built-in citation verification
7. **Langfuse observability from day one** — visibility into every query
8. **Consent Ledger** — legal artifact in git
9. **Pipeline for voice** (not S2S) — preserves RAG control between STT and LLM
10. **On-device voice by default** — audio doesn't leave device
11. **Doctrinal accuracy as central metric** — not "faithfulness", but specific to Buddhism
12. **Phase-based roadmap** — pragmatic path from €9 MVP to full platform

### Key risks and uncertainties

1. **Legal uncertainty of CC-BY-NC-ND Dharmaseed** — may block publication of 46,000 transcripts
2. **Claude-centrism contradicts "free-to-user"** — BYOK pattern needed
3. **Pāli terms** — problem at all levels: tokenizer, STT, TTS
4. **Chunking needs serious rework** — 2% ref_hit@5 baseline showed fixed-size approach failure
5. **Doctrinal inaccuracy** — main ethical risk
6. **Solo developer burnout** — most underestimated risk in ambitious solo projects
7. **Voice uncanny valley** — may disrupt meditations
8. **Transcription scale (35k hours)** — technically solvable, operationally complex

### Practical significance

**For Buddhist community:**

- First systematic attempt to make dharma corpus accessible through modern AI while preserving doctrinal accuracy
- Conservative approach to ethics — not a teacher replacement, but a study tool
- Respect for licenses and intellectual property via Consent Ledger

**For open-source community:**

- Exemplary case of how to build RAG system as solo developer
- Pragmatic stack without over-engineering (no Kubernetes, no LangChain)
- Honest self-criticism in `DHARMA_RAG_TECHNICAL_AUDIT`

**For AI/ML industry:**

- Case study of applying modern 2025–2026 techniques: Contextual Retrieval, Citations API, hybrid search with RRF, MITRA-E for domain-specific embeddings
- Realistic cost model ($70–820/mo by phase)
- Target metrics (faithfulness >0.85, doctrinal_accuracy >4/5)

**For ML engineer or researcher:**

This is a complete technological map showing how each architectural decision is made in a modern RAG project:

- Not "choose Qdrant because popular", but **compare 9 vector DBs by 6 criteria**
- Not "use BGE-M3", but **analyze three-mode approach and compare with 9 alternatives**
- Not "LLM writes answer", but **route Haiku/Sonnet/Opus with measured economy**
- Not "there will be voice-chat", but **calculate latency budget across 6 components to 800 ms**

This is what a project could look like if every decision was thought through and justified with compromises in mind. In the community, such "fully documented" projects are very few, and Dharma-RAG is one of the outstanding examples.

---

*End of document. English version. Size: ~80 pages.*

*Author: prepared based on open documentation of the toneruseman/Dharma-RAG repository. All quotes from project documents are in quotation marks with source indication. Research license: CC-BY-SA 4.0 (same as project documentation).*
