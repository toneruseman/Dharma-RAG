# Dharma-RAG: A Comprehensive Project Study

**Unified Research Document for the Non-Specialist**

*An in-depth description of the architecture, technologies, and design decisions of an open-source RAG system for Buddhist teachings*

---

**Version:** April 2026
**Based on:** repository `toneruseman/Dharma-RAG` and two internal research documents
**Intended reader:** technically literate reader without prior AI/ML experience
**Length:** ~11,000 words, approximately 45 pages when rendered
**License:** CC-BY-SA 4.0

---

## How to Read This Document

This document is layered. The first three parts form the **foundation**: introduction to the project and basic concepts. Without them, later technical sections will be opaque. If you already know what embeddings and RAG are, you can skip Part II, but return to it if something is unclear.

Parts IV–XIII are the **technical core**. Each architectural decision is dissected: what was chosen, what alternatives existed, why this particular choice was made, what the trade-offs were. You can read sequentially or selectively.

Parts XIV–XIX cover **operational and ethical matters**: infrastructure, budget, privacy, wellbeing, critique, comparison with competitors, conclusion.

At the end: a **glossary** of ~60 terms and **appendices**.

---

## Table of Contents

1. [Part I. Introduction](#part-i-introduction)
2. [Part II. Core Concepts for Understanding the Project](#part-ii-core-concepts-for-understanding-the-project)
3. [Part III. Essence and Values of the Dharma-RAG Project](#part-iii-essence-and-values-of-the-dharma-rag-project)
4. [Part IV. Overall Architecture — the Path of a Single Question](#part-iv-overall-architecture--the-path-of-a-single-question)
5. [Part V. Data Layer: Corpus, Sources, Licenses, FRBR](#part-v-data-layer-corpus-sources-licenses-frbr)
6. [Part VI. Chunking — How to Properly Slice Texts](#part-vi-chunking--how-to-properly-slice-texts)
7. [Part VII. Embeddings — the Heart of Semantic Search](#part-vii-embeddings--the-heart-of-semantic-search)
8. [Part VIII. Vector Database — Where "Meaning Coordinates" Live](#part-viii-vector-database--where-meaning-coordinates-live)
9. [Part IX. Hybrid Search and RRF — Why One Search Method Is Not Enough](#part-ix-hybrid-search-and-rrf--why-one-search-method-is-not-enough)
10. [Part X. Knowledge Graph — Where Vectors Fall Short](#part-x-knowledge-graph--where-vectors-fall-short)
11. [Part XI. Reranking — the Second Filtering Stage](#part-xi-reranking--the-second-filtering-stage)
12. [Part XII. LLM — Generating the Answer](#part-xii-llm--generating-the-answer)
13. [Part XIII. Fine-Tuning — Adapting the Models](#part-xiii-fine-tuning--adapting-the-models)
14. [Part XIV. Voice Pipeline and Audio Transcription](#part-xiv-voice-pipeline-and-audio-transcription)
15. [Part XV. Quality Evaluation — Golden Set, Metrics, CI](#part-xv-quality-evaluation--golden-set-metrics-ci)
16. [Part XVI. Observability — Watching the Live System](#part-xvi-observability--watching-the-live-system)
17. [Part XVII. Infrastructure and Budget — Where It All Lives](#part-xvii-infrastructure-and-budget--where-it-all-lives)
18. [Part XVIII. Privacy, Security, Ethics](#part-xviii-privacy-security-ethics)
19. [Part XIX. Wellbeing and AI Ethics in Meditation](#part-xix-wellbeing-and-ai-ethics-in-meditation)
20. [Part XX. Comparison with Competitors](#part-xx-comparison-with-competitors)
21. [Part XXI. Roadmap — Development Phases](#part-xxi-roadmap--development-phases)
22. [Part XXII. Critical Remarks and Open Questions](#part-xxii-critical-remarks-and-open-questions)
23. [Part XXIII. RAG Trends in 2026](#part-xxiii-rag-trends-in-2026)
24. [Part XXIV. Summary and Conclusion](#part-xxiv-summary-and-conclusion)
25. [Appendix A. Glossary of Terms](#appendix-a-glossary-of-terms)
26. [Appendix B. Key Numbers of the Project](#appendix-b-key-numbers-of-the-project)
27. [Appendix C. Recommended Reading](#appendix-c-recommended-reading)

---

## Part I. Introduction

### 1.1. What Dharma-RAG Is — in One Paragraph

**Dharma-RAG** is an open-source research system for questions and answers on Buddhist teachings. A user poses a question in natural language — Russian, English, or any other — and the system finds relevant passages from the Pali Canon, lectures by modern meditation teachers, and academic works, after which an AI assembles a coherent answer **with mandatory citations to primary sources**. The project is being built by a single developer on principles of pragmatic minimalism: first a working prototype on a basic server for €9/month, then gradual expansion to a mobile app, voice assistant, and knowledge graph. The code is distributed under the MIT license; the documents, under CC-BY-SA 4.0.

### 1.2. A Simple Analogy for Understanding

Imagine you have a vast library of Buddhist books: ancient Pali suttas, Tibetan texts, Chinese translations, modern lectures by Western meditation teachers, scientific articles about states of consciousness. In English and Russian. Hundreds of thousands of pages. And you want to ask this library a simple question — for example: *"What did the Buddha say about the first jhāna?"* — and receive not a reference to 50 books, but a concrete, meaningful answer backed by exact quotes with an indication of where each comes from.

That is Dharma-RAG. The project creates an assistant that reads a massive Buddhist corpus and answers user questions with honest references to primary sources — so that every assertion can be verified.

> **Decoding the name**
>
> **Dharma** — the teachings of the Buddha, the spiritual tradition whose texts the project collects.
>
> **RAG** (Retrieval-Augmented Generation) — a technical term describing the approach: the system first searches relevant text fragments in a library, then a language model (AI) composes an answer from them.
>
> So Dharma-RAG is a "Buddhist AI assistant with citations to primary sources."

### 1.3. Who This Document Is For

This document is written for an **IT professional without prior AI experience**. The reader is assumed to know:

- what an API and HTTP requests are;
- what SQL databases are;
- how a client-server application is structured;
- the basics of Docker and command-line tools.

The reader is **not** expected to know in advance:

- what large language models (LLMs) are;
- what embeddings, vector databases, or RAG are;
- what chunking, reranking, or hybrid search mean;
- the specifics of Buddhist texts or the Pali language.

All these concepts are explained in Part II before we move on to the project's concrete implementation.

### 1.4. Why the Project Exists — Problem, Solution, Essence

**Problem #1: The volume of Buddhist texts exceeds human capacity.**

The Pali Canon is roughly 20,000 pages of canonical texts composed over centuries. Add commentaries (*aṭṭhakathā*), academic translations into various languages, thousands of lectures by modern teachers (Ajahn Chah, Thanissaro Bhikkhu, Mahasi Sayadaw, Pa-Auk Sayadaw, Rob Burbea), and video recordings of retreats. The Dharmaseed archive alone contains about 46,000 lectures totaling approximately 35,000 hours — roughly four years of continuous listening without sleep.

No human can read and listen to all of this in one lifetime. Even specialist Buddhologists spend decades mastering one canon (Pali, Tibetan, or Chinese) — and there are three large canons plus several smaller ones.

**Problem #2: Standard ChatGPT or Claude will not do.**

If you ask ChatGPT *"what is jhāna?"*, it will produce a rough answer from its training data, but:

- it **cannot reliably cite a specific sutta** (and if it does, it often cites a nonexistent one);
- it may **confuse traditions** — Theravada, Mahayana, Vajrayana — which diverge on certain doctrinal questions;
- sometimes it simply **hallucinates** — fabricating quotations that do not exist in the original texts.

For a practicing Buddhist, researcher, or teacher, this is unacceptable. In academic and religious settings, citing a source is not a formality but the foundation of trust. An answer saying *"somewhere in the Saṃyutta Nikāya it says this"* is useless. What's needed is: *"SN 22.59, paragraph 3, Bhikkhu Bodhi's translation."*

**Problem #3: Linguistic barriers.**

The original texts are written in Pali and Sanskrit with diacritical marks: *ṃ, ñ, ṭ, ḍ, ā, ī, ū*. Online, the same term can appear as *satipaṭṭhāna*, *satipatthana*, *sati-patthana*, *сатипаттхана* — and standard search engines do not connect them. Moreover, many texts exist only as unindexed PDFs or audio recordings.

A question posed in Russian should find answers in English and Pali sources — and vice versa. This is called **cross-lingual search** and requires specialized technologies absent from ordinary search engines like Google.

**Dharma-RAG's solution** is to build a system that:

1. indexes the entire accessible corpus of Buddhist texts;
2. finds relevant passages for any question, even with variations in Pali term spelling and even if the question is asked in a different language;
3. uses AI to compose coherent answers;
4. **mandatorily cites specific sources** so that every answer can be verified.

### 1.5. Why "Dharma" — the Buddhist Connection

The word *dharma* (Pali: *dhamma*) has several interrelated meanings in the Buddhist tradition:

1. **The Buddha's teaching** — the sum of what the Buddha transmitted to his disciples over 45 years of teaching.
2. **The nature of things** — how reality is structured (*anicca* — impermanence, *dukkha* — unsatisfactoriness, *anattā* — non-self).
3. **A phenomenon** — an element of experience (thought, sensation, perception).

The project's name emphasizes that this is not merely a technical exercise but an attempt to make the corpus of Buddhist teachings more accessible for study and practice.

The project's documentation explicitly prescribes a code of conduct rooted in Buddhist ethics (*sīla*):

- **Mettā** (loving-kindness) — treating every participant warmly;
- **Satya** (truthfulness) — honesty in discussion, acknowledgment of errors;
- **Khanti** (patience) — especially with newcomers and in disagreements;
- **Anattā** (non-ego) — criticize ideas, not people.

The project closes its `CONTRIBUTING.md` with the phrase: *"Sabbe sattā sukhitā hontu — May all beings be happy."*

### 1.6. Five User Types

By design, the project has five very different user types — and deliberately does not attempt to serve all five perfectly. The task is first to do one or two scenarios excellently.

| # | User | What they do |
|---|------|--------------|
| 1 | **Reading Room — reader/practitioner** | Reads a sutta with parallel translation, sees term explanations on hover, makes bookmarks |
| 2 | **Research Workbench — scholar/translator** | Searches parallel passages across canons (Pali, Chinese, Tibetan), compares editions, exports citations in academic format |
| 3 | **Dharma Q&A — the curious** | Asks questions in a chat, receives answers with citations, can expand any quote to see the source |
| 4 | **Study Companion — learner** | Flashcards for terms and mantras, study plans, progress, notes. Works offline on retreats |
| 5 | **API / MCP — developers** | Integrate Dharma-RAG into their own applications or into other AI tools |

The documentation is candid: trying to build all five surfaces simultaneously is a dead end. Better to do one or two of them superbly than five mediocrely.

### 1.7. Three Rules That Run Through the Whole Project

> **The master principle that governs everything**
>
> **1. Texts are sacred.** The system is built around primary sources, not around chat. Reading and navigation of texts come first; AI answers are an optional layer, not the main product.
>
> **2. Every claim is verifiable.** Without a reference to a specific passage in a specific text, no answer is released to the user. Ever.
>
> **3. AI does not replace a teacher.** Respect for the living tradition is embedded in the UI and system behavior: "consult your teacher," "this is not a substitute for practice," "if you are in crisis, seek a qualified professional."

These three rules explain nearly every architectural decision we will examine later.

---

## Part II. Core Concepts for Understanding the Project

If you have never worked with modern AI systems, this part is required reading. Without understanding these seven concepts, everything that follows will look like a cluster of mysterious acronyms. I will explain each concept in simple terms, with examples and analogies.

### 2.1. What an LLM (Large Language Model) Is

An **LLM** is a large language model — a program trained to predict the next word in a text based on a vast amount of data. Examples you have probably heard of: ChatGPT (OpenAI), Claude (Anthropic), Gemini (Google), Llama (Meta), Qwen (China's Alibaba), DeepSeek (China's High-Flyer).

**How an LLM works (simplified):**

```
Input text:          "The capital of France is "
                              ↓
                    ┌─────────────────┐
                    │  Neural network │
                    │  with billions  │
                    │  of parameters  │
                    └─────────────────┘
                              ↓
Word probabilities:   "Paris"    (95%)
                      "Lyon"     (2%)
                      "Marseille" (1%)
                      ...
                              ↓
Output:                     "Paris"
```

An LLM is trained on text collected from the Internet, books, and code. By the end of training, the model "knows" — meaning, can continue text with high accuracy — an enormous volume of facts, styles, and languages.

**A key point often misunderstood:** an LLM **does not store facts explicitly** like a database. It stores *statistical patterns* between words. So when you ask it about a fact, it actually "reconstructs" the fact from patterns, and sometimes it reconstructs incorrectly.

This is similar to a human trying to recall a poem learned in school 20 years ago. Most of the words come to mind — but some will be replaced with "semantically similar ones" because the exact word has been forgotten. An LLM does the same with every fact in the world.

**The size of an LLM** is measured in *parameters* — the numbers the model is made of. Modern models come in sizes:

- **Small:** 1–8 billion parameters (Llama 3.1 8B, Qwen 2.5 7B). Fit on a single consumer GPU.
- **Medium:** 30–80 billion (Llama 3.3 70B). Require 2–4 powerful GPUs.
- **Large:** 200–700 billion (DeepSeek V3, Qwen3-235B, Llama 4). Require server racks.
- **Cloud flagships:** Claude Opus, GPT-4o/GPT-5, Gemini 2.5 Pro. Sizes are not disclosed but are presumed to be 1+ trillion parameters.

### 2.2. The Problem of LLM Hallucinations

A **hallucination** is when an LLM produces a plausible but factually incorrect answer. The model confidently says: *"The Buddha spoke this phrase in MN 10, paragraph 7"* — but in reality, MN 10 contains no such phrase.

**Why hallucinations are inevitable in pure LLMs:**

1. **Data compression.** Billions of pages of text are compressed into hundreds of billions of parameters. Details are inevitably lost. It's as if you asked a human to memorize the content of 100,000 books — they could give you the general sense, but details would inevitably be "filled in."

2. **No verification.** The model cannot "check" its own answer — it generates what most plausibly fits the patterns. It has no internal "is this true?" mechanism.

3. **Obsolescence.** A model is trained on data up to a certain cutoff date and does not know of later events. Claude Opus 4.7 is trained on data up to early 2026 and does not know what happened afterward.

4. **Poor coverage of rare topics.** Buddhist texts in Pali are a rare topic. The model has seen less of them than of the English Wikipedia. For rare topics the hallucination rate is higher.

**For ordinary chat**, hallucinations are an annoying but non-critical flaw. **For Buddhist teachings**, this can be spiritually dangerous: a false quote attributed to the Buddha can mislead a practitioner. In academic settings this is considered a serious professional transgression, and rightly so.

### 2.3. What RAG (Retrieval-Augmented Generation) Is

**RAG** stands for "Retrieval-Augmented Generation." The idea is simple:

```
Classic LLM:
Question → LLM → Answer (possibly with hallucinations)

RAG:
Question → Search in database → Retrieved documents
                              ↓
             Question + Documents → LLM → Answer (with citations)
```

**Example of RAG answering "What is satipaṭṭhāna?":**

1. The system takes the question.
2. Searches the Buddhist text database for passages containing information about satipaṭṭhāna.
3. Finds, for example:
   - MN 10 "Satipaṭṭhāna Sutta" (full text)
   - Bhikkhu Bodhi's commentary
   - A lecture by Thanissaro Bhikkhu on the subject
4. Takes **only these texts** and passes them to the LLM together with the question and an instruction: *"Answer the user's question using only these texts. If there is insufficient information, say so."*
5. The LLM composes an answer: *"Satipaṭṭhāna is the practice of the four foundations of mindfulness described by the Buddha in MN 10. According to this sutta, the four foundations are body, feelings, mind, and mental objects [quote 1]. Bhikkhu Bodhi explains that... [quote 2]."*

**Why this is radically better than pure LLM:**

- The answer is **grounded in real texts**, not in the model's vague memories.
- Every claim **can be checked** by clicking a reference.
- The model is **trained to say "I don't know"** if no relevant texts are found.
- **Currency** — the database can be updated without retraining the whole LLM.
- **Privacy** — you can add your corporate documents to the database without pouring them into a public model.

RAG is the foundational technology underlying almost every corporate AI product in 2024–2026: from legal assistants to medical expert systems.

### 2.4. What Embeddings Are

For a computer to search texts by meaning rather than by literal word match, there must be a way to **represent meaning as numbers** that the computer can compare.

This is done with **embeddings**.

> **The map analogy**
>
> Imagine a city map where every location has coordinates: latitude and longitude. Two numbers tell you whether two points are near each other.
>
> An **embedding** does the same thing, but for meanings of text. Each piece of text is turned into a set of ~300–4000 numbers — its "meaning coordinates" in a multidimensional space. Texts close in meaning have close coordinates, even if the words differ.
>
> For example: *"The Buddha taught impermanence"* and *"anicca is a fundamental characteristic of existence"* will end up close in this space, even though they share almost no words.

**Technical unpacking:**

An embedding is a vector of numbers. For the phrase *"The Buddha taught impermanence"* it might look like this:

```
[0.23, -0.15, 0.87, 0.04, -0.32, ..., 0.61]   ← 1024 numbers total
```

And for *"anicca is a fundamental characteristic of existence"*:

```
[0.19, -0.11, 0.91, 0.06, -0.28, ..., 0.58]   ← a very similar vector
```

The computer measures **cosine distance** between such vectors — a number between -1 and 1. Closer to 1 means the texts are more similar in meaning.

**This work is done by a special neural network** — an "embedding model." Dharma-RAG uses **BGE-M3** (compared with alternatives — we go deep in Part VII).

**Why this works:**

Embedding models are trained on billions of text pairs: "similar in meaning" and "not similar." During training, the model learns to place similar texts close together in a multidimensional space and dissimilar ones far apart. This is called **contrastive learning** — learning through contrasts.

### 2.5. What a Vector Database Is

So we have a Buddhist corpus broken into 56,000 small pieces (chunks). Each piece is turned into an embedding — a 1024-number vector. Now the user asks a question — it is also turned into a vector. Task: **quickly find among the 56,000 vectors the 20–30 closest to the question vector**.

This is a specialized task called **nearest neighbor search**. An ordinary database (PostgreSQL, MySQL) cannot do it efficiently. A **vector database** is required.

Vector DBs use specialized indexing algorithms — most often **HNSW** (Hierarchical Navigable Small World). HNSW builds a multilevel data structure resembling a friends-of-friends graph in a social network: on each level every vector "knows" a few nearest ones, and the search walks this graph, rapidly converging on the target.

Popular vector databases in 2026:

- **Qdrant** (chosen by Dharma-RAG) — Rust, Apache 2.0, high performance.
- **pgvector** — a PostgreSQL extension that lets you store vectors in a regular SQL DB.
- **Weaviate** — heavier, with built-in modules.
- **Milvus** — popular in China, for large volumes.
- **Chroma** — simple, for prototyping.
- **Pinecone** — a cloud managed service.
- **FAISS** — a library from Meta, not a full DB but a tool.

We cover this in depth in Part VIII.

### 2.6. What Chunking Is

The Buddhist corpus cannot be put entirely into a single vector DB cell. Even one sutta is a text of 5–500 pages. A vector for too large a piece loses distinctiveness: everything blurs into "general meaning" and search becomes useless.

**Chunking** (from *chunk* — "piece") is the splitting of long texts into small fragments before indexing. A typical chunk size is 200–800 tokens (roughly 150–600 English words).

**The problem with naive chunking:**

The simplest approach — slice the text every 500 words — breaks meaning:

- A dialogue can be split mid-flow: a monk's question in one chunk, the Buddha's answer in another.
- A five-line verse formula is cut in half.
- Context (who is speaking, about what) is left in the previous chunk.

Therefore, Dharma-RAG uses a layered chunking strategy:

- **Structural chunking** — cutting on natural boundaries (paragraphs, verses, chapters).
- **Contextual Retrieval** (an Anthropic technique, September 2024) — prepending context to each chunk via LLM.
- **Parent-child chunking** — indexing small chunks but feeding the LLM a larger "parent" context.

Detailed in Part VI.

### 2.7. What Reranking Is

After vector search we have 20–30 "candidates" — chunks similar to the question. But among them there may be:

- Very word-similar chunks that do not actually answer the question.
- Truly relevant ones, but not in first place.
- Chunks close in general topic but not in the specific point of the question.

A **reranker** is a second, more precise neural network that looks at a pair *"question + chunk"* and scores its relevance on a 0–1 scale. From the 20–30 candidates the reranker selects the 5–8 best for passing to the LLM.

**Why a separate stage is needed:**

Embeddings are fast but imprecise on details: they compress text into a fixed number of coordinates. Rerankers are slower (one pass per pair) but **see the full text** of both elements and detect fine distinctions.

This is a two-stage strategy common to most modern search systems:

1. **Fast, approximate search** (vector + BM25 + sparse) — from a million documents to 30 candidates in milliseconds.
2. **Slow, precise filtering** (reranker) — from 30 candidates to the 5–8 best in seconds.

Popular rerankers in 2026:

- **BGE-reranker v2-m3** — open-source, MIT;
- **Cohere Rerank 3** — paid cloud;
- **Jina Reranker v2** — open-source with restrictions;
- **Voyage Rerank-2** — cloud.

Detailed in Part XI.

### 2.8. Hybrid Search — Why One Method Is Not Enough

Pure vector search excellently finds texts by overall meaning but fails in several cases:

- **Rare proper names:** if a user asks about "Pemasiri Thera," vector search may miss an exact mention of that name.
- **Numeric identifiers:** sutta numbers (MN 10, SN 22.59), dates, pages — vectors do not preserve them exactly.
- **Pali diacritics:** *paṭicca-samuppāda* vs *paticca-samuppada* vs *pratītya-samutpāda*.

So professional RAG systems use **hybrid search** — several methods simultaneously:

1. **Dense vector search** — by embedding, captures meaning.
2. **Sparse vector search** — neural but focused on rare words (e.g. SPLADE or BGE-M3 sparse mode).
3. **BM25** — the classic 1980s algorithm based on exact word matches weighted by rarity in the corpus. The same algorithm used in Elasticsearch.

Results from the three channels are merged via **RRF** (Reciprocal Rank Fusion) — a simple formula that accounts for each document's position in each list.

Hybrid search gives +10–30% accuracy over any single method. For Pali with its diacritics this is a mandatory solution; otherwise the system is "blind" to a fraction of queries.

### 2.9. Concepts Recap

Before moving on, let's fix these:

| Concept | What it does | Analogy |
|---------|-----------|---------|
| **LLM** | Predicts the next word | A smart but forgetful erudite |
| **Hallucination** | LLM fabricates a fact | When the erudite "misremembers" |
| **RAG** | Gives the LLM access to a text base | The erudite reads a reference first, then answers |
| **Embedding** | Turns text into a meaning vector | Map coordinates |
| **Vector DB** | Stores and searches vectors | A specialized library catalog |
| **Chunking** | Slices texts into pieces | Breaking a book into paragraphs |
| **Reranker** | Precision filtering of candidates | A second-round job interview |
| **Hybrid search** | Multiple search methods at once | Google + library catalog + asking a librarian |

Now we are ready to approach the project itself.

---

## Part III. Essence and Values of the Dharma-RAG Project

### 3.1. Five Principles the Project Stands On

Dharma-RAG is not "just another Buddhist chatbot." It is a carefully designed system where each technical decision is made deliberately, accounting for the specifics of Buddhist texts: their multilingualism, structural richness, licensing complexity, and doctrinal sensitivity.

The five pillars of the project:

1. **Texts are sacred.** Reading-room first, not chat-bot. Suttas are primary, AI is an optional helper.
2. **Every claim is verifiable.** Strict citations with char-level spans, automatic verification, hardcoded refusal when evidence is insufficient.
3. **Openness and independence.** MIT license, BYOK pattern (Bring Your Own Key), self-hostable on free Oracle Cloud, portable to a local server with two 48GB GPUs.
4. **Measurement discipline.** Golden eval set with Krippendorff α ≥ 0.7, CI blocking on regressions, cross-family LLM judges to eliminate bias.
5. **Respect for the tradition.** Deference language in the UI, anti-abuse guardrails for crisis situations, a restricted flag for Vajrayana content, a constant disclaimer "this is not a substitute for a teacher."

### 3.2. Value Self-Definition: What the Project Does NOT Do

Equally important is understanding what the project deliberately is **not**:

- **Not a teacher substitute.** Dharma-RAG is a study and reference tool, not a spiritual mentor.
- **Not a meditation coach.** The system does not give direct practice instructions, especially for advanced techniques.
- **Not a doctrinal judge.** When traditions disagree, the system presents both viewpoints with sources.
- **Not a general AI.** Answers outside the Buddhist context are issued with an explicit warning or declined.
- **Not a commercial product.** Open-source, MIT, "free-to-user" (by intent); BYOK rather than subscription sales.
- **Not an attempt to "digitize enlightenment."** A conscious acknowledgment that AI is a technical helper, not a replacement for practice.

This value self-definition runs through the entire project and manifests in every UI element: from the phrasing "Sources suggest..." instead of "The Buddha says..." to a "Ask a human teacher" button next to each answer.

### 3.3. The Project's Ethical Code

The repository contains `CODE_OF_CONDUCT.md`, `PRIVACY.md`, `CONTRIBUTING.md` files that explicitly formulate a Buddhist-oriented ethical code:

- **Mettā** (loving-kindness) — respectful communication with any participant regardless of their knowledge level.
- **Satya** (truthfulness) — openness about errors, a public audit log of system refusals.
- **Khanti** (patience) — especially with newcomers who ask "stupid" questions.
- **Anattā** (non-ego) — criticize ideas, not people; contributors' personal ambitions do not drive the design.

These are not decorative — the principles shape concrete architectural decisions: from a gentle tone of voice in LLM prompts to a mechanism for publishing a monthly report of anonymized system refusals.

---

## Part IV. Overall Architecture — the Path of a Single Question

Before diving into the details of each component, let us trace the full path of one question — from the press of "Enter" to the returned answer. This "big picture" provides a frame onto which all technical details will later be layered.

### 4.1. The Question's Journey End-to-End — Visually

```
Step 0. DATA PREPARATION (once, in advance)
═══════════════════════════════════════════════════
  Buddhist corpus (56k–900k chunks)
      ↓ (structural chunking + Contextual Retrieval)
  Chunks with context
      ↓ (embedding via BGE-M3: dense + sparse + ColBERT)
  Vectors + sparse representations
      ↓ (indexing in Qdrant + BM25 in Postgres)
  Indexed database

╔═══════════════════════════════════════════════════╗
║               REAL-TIME (single request)           ║
╚═══════════════════════════════════════════════════╝

Step 1. User query
─────────────────────────
  "What does satipaṭṭhāna mean?"
      ↓

Step 2. Preprocessing
─────────────────────────
  - Language detection (en)
  - Diacritic normalization (satipaṭṭhāna = satipatthana = сатипаттхана)
  - Embed the question (BGE-M3 → 1024-dim vector)
  - Extract key terms for BM25
      ↓

Step 3. Hybrid Retrieval (parallel, 3 channels)
─────────────────────────
  ┌─ Dense vector search (Qdrant HNSW) ──→ 30 candidates ─┐
  ├─ Sparse vector (BGE-M3 sparse)    ──→ 30 candidates ─┤
  └─ BM25 (Postgres FTS)              ──→ 30 candidates ─┘
                                                          ↓
                                                     RRF merge
                                                          ↓
                                                    20 candidates
      ↓

Step 4. Reranking (precision filtering)
─────────────────────────
  20 candidates → BGE-reranker v2-m3 → top 5–8
      ↓

Step 5. Parent-expansion
─────────────────────────
  Child chunks are replaced by their parents (more context)
      ↓

Step 6. LLM generation (Claude / Llama / other)
─────────────────────────
  Prompt: "Here is the question. Here are passages. Answer ONLY from them, with citations."
  Claude Citations API automatically attaches citations to char spans
      ↓

Step 7. Verification
─────────────────────────
  - Do all citations exist in the context?
  - Faithfulness ≥ 0.7?
  - No triggers for the kill-switch (crisis queries)?
      ↓

Step 8. Delivery to user (Streaming SSE)
─────────────────────────
  Answer is streamed token-by-token + clickable citations + disclaimer

Step 9. Logging (in parallel)
─────────────────────────
  Langfuse/Phoenix: tokens, latency, faithfulness, user feedback
```

**The entire path takes 2–5 seconds.** The user sees the answer "typing" itself out gradually, word by word (streaming) — as both Claude and ChatGPT do.

### 4.2. System Layers

Architecturally, Dharma-RAG is divided into five layers:

| Layer | What it does | Technologies |
|-------|-----------|-----------|
| **Frontend** | Web/mobile interface | Next.js 14, React, TypeScript |
| **API gateway** | HTTP API, auth, BYOK | FastAPI (Python) |
| **Retrieval** | Hybrid search + reranking | Qdrant, Postgres (pgvector, BM25) |
| **Generation** | LLM answer with citations | Claude API (primary), BYOK for others |
| **Observability** | Quality monitoring | Langfuse/Phoenix, Postgres |

Each layer lives in its own Docker container. For the MVP, all containers run on a single Hetzner VPS (€9/month). As load grows, layers can be distributed across servers or moved to the cloud.

### 4.3. Key Components and Their Roles

**Qdrant** — the vector database. Stores 56k–900k vectors with metadata. HNSW indexing for nearest-neighbor search in milliseconds. Supports named vectors (multiple vectors per record — the key to migrating between embedding models).

**PostgreSQL** — the relational database. Stores:

- Chunk metadata (which sutta, which translator, which tradition, which license).
- A full-text BM25 index for lexical search.
- User session logs.
- Consent Ledger — a legal artifact with information about source licenses.
- The knowledge graph via Apache AGE (in Phase 2).

**FastAPI** — the Python framework for the API. Accepts HTTP requests, orchestrates retrieval and generation.

**Claude** — the primary LLM (by default Sonnet; Haiku for simple requests, Opus for complex ones). Supports the Citations API — built-in citation-to-span binding.

**BGE-M3** — the embedding model (Part VII covers it in detail).

**BGE-reranker v2-m3** — a second neural network for precise filtering.

**Langfuse/Phoenix** — observability. Logs every request: tokens, latency, what context was passed, what answer was produced, how the user rated it.

### 4.4. Why the Architecture Looks Like This

More fashionable or powerful components could have been chosen. Why exactly this?

**First, optimization for "solo developer + minimal budget":**

- No Kubernetes (over-engineering for one server).
- No LangChain/LlamaIndex (too many abstractions; FastAPI + direct code is easier to debug).
- No microservice architecture (five layers in one Docker Compose — enough).

**Second, choosing "reversible" solutions:**

- Qdrant named vectors let you change the embedding model without reindexing the whole corpus.
- The BYOK pattern for LLMs lets the user choose between Claude, OpenAI, Llama, DeepSeek.
- A Postgres-based graph (Apache AGE) can be rolled out gradually without breaking the existing Qdrant.

**Third, a pragmatic open-source stack:**

- BGE-M3: MIT license. Free to use.
- Qdrant: Apache 2.0. Self-hostable.
- PostgreSQL: the PostgreSQL license (permits nearly everything).
- Apache AGE: Apache 2.0.

**Fourth, reproducibility:**

Every component can be deployed locally with identical results. This is critical for scientific reproducibility and so that any researcher can run the system on their own machine.

### 4.5. What Happens in Parallel and What Sequentially

A single request is a combination of parallel and sequential execution:

**In parallel (in Step 3, Hybrid Retrieval):**

- Dense, sparse, BM25 search simultaneously.
- Context for the LLM is loaded from the cache concurrently with reranking.

**Sequentially:**

- Embed question → search → rerank → LLM → verify → deliver.

This gives an optimal distribution: the first milliseconds are spent on parallel search operations, followed by the sequential stages of reranking and generation.

Now let us examine each component in detail.

---

## Part V. Data Layer: Corpus, Sources, Licenses, FRBR

### 5.1. Why Corpus Composition Is a Discipline of Its Own

Any RAG system is only as good as its sources. In IT this has long been expressed in the proverb **"garbage in — garbage out."** For Dharma-RAG this is especially important: you can't simply download random Buddhist sites — you must carefully select texts that are legally reusable and of real quality.

Questions that must be answered **before** a single line of code is written:

1. Which texts are freely available?
2. Under which licenses? Can they be indexed, excerpted, used for training?
3. What is the quality of translations? Are there alternative translations for comparison?
4. Which languages to support? Which scripts (Pali, Sanskrit, Tibetan, Chinese)?
5. How to handle diacritics and spelling variants?

### 5.2. Five Pillars of the Corpus

Research for the project shows that most of the needed corpus can be assembled from five principal sources:

| Source | What it provides | License | Notes |
|--------|---------|----------|-------------|
| **SuttaCentral** | The Pali Canon (suttas), Bhikkhu Sujato's translations | CC0 (fully free) | The only complete modern English translation of the Canon under the most permissive license. **The project's foundation.** |
| **84000** | The Tibetan Canon (Kangyur, Tengyur) | CC BY-NC-ND | About 46% of the Kangyur is already translated; two-thirds planned over the coming years. HTML, PDF, EPUB + public API |
| **Access to Insight + dhammatalks.org** | Theravada translations and lectures | Free distribution / CC BY-NC | ~1000 suttas, texts by Thanissaro Bhikkhu, Bhikkhu Bodhi, Nyanaponika |
| **BDK America** | The Chinese Tripiṭaka in English translation | CC BY-NC-SA | ~30+ volumes already free; 139 planned. Critical source for Mahayana and Chan texts |
| **Lotsawa House** | Tibetan commentaries, practice texts | CC BY-NC | 2000+ translated short texts across all four schools |

### 5.3. A Special Layer: Jhānas

The project's developer is especially interested in *jhānas* — deep states of concentration in Buddhist meditation. Research found a rare combination: high-quality, serious, freely licensed material exists here:

- **Leigh Brasington** (leighb.com) — dozens of free essays on jhānas in sutta style.
- **Rob Burbea** — ~460 lecture recordings, including the final "Practicing the Jhānas" series (2019–2020); audio and transcripts are free.
- **Daniel Ingram, *Mastering the Core Teachings of the Buddha* (MCTB2)** — the complete book is openly available.
- **Bhikkhu Anālayo** — academic articles on jhānas; free PDFs from the University of Hamburg.
- **Varieties of Contemplative Experience** — the Brown University research project on difficult experiences in meditation. All papers openly available. **Critically important** for a system that may receive questions from someone in a meditative crisis.

### 5.4. Conservative and Difficult Sources

The project deliberately excludes some materials:

- **Dharmaseed.org** — 46,000 lectures, ~35,000 hours. License: CC-BY-NC-ND. This permits non-commercial use without derivative works. The problem: RAG by definition creates a "derivative" (transcript + semantic search + answer built from it). Legally gray.
- **Lion's Roar / Tricycle** — commercial licenses, subscription access only. Can't be indexed wholesale.
- **Books by modern teachers printed through publishers** — Thich Nhat Hanh, Pema Chödrön, etc. Only with publisher permission.

**The project's strategic decision:** start with CC0 (SuttaCentral) and expand only where the license clearly permits. Each new source goes through a legal check and into the **Consent Ledger** — a table in the Git repository recording the license, date of acquisition, link to the original, and any conditions of use.

### 5.5. Consent Ledger as a Legal Artifact

This is a non-standard decision rarely seen even in serious AI projects:

```
consent_ledger.yaml
────────────────────
- source: SuttaCentral.net
  license: CC0
  obtained: 2025-01-15
  url: https://suttacentral.net/api/ ...
  conditions: none
  consent_contact: hello@suttacentral.net
  retrieval_date: 2026-04-10

- source: accesstoinsight.org
  license: Free distribution (author-specific)
  obtained: 2025-02-03
  url: https://www.accesstoinsight.org/
  conditions:
    - "Per-author review required"
    - "No commercial redistribution"
  consent_contact: (noted per document)
  retrieval_date: 2026-04-10
```

This file:

- Serves as legal evidence that the corpus was assembled in compliance with licenses.
- Can be audited externally (public in Git).
- Is updated with each ingest of new documents.
- Shields the project from claims by authors/rights holders.

Many open-source RAG projects simply ignore this topic. Dharma-RAG deliberately makes it a central artifact.

### 5.6. Why FRBR Is Indispensable

When the corpus contains 50 different translations of the same Satipaṭṭhāna Sutta, an architectural question arises: **how should they be stored?**

The naive approach — "one record = one document" — would lead to:

- 50 records labeled "Satipaṭṭhāna Sutta" in the database;
- Searches returning 20 nearly identical results;
- Inability to answer questions like "show me all translations of MN 10."

**The correct approach is to use the library model FRBR** (Functional Requirements for Bibliographic Records). This model distinguishes three levels:

| Level | What it is | Example |
|---------|---------|--------|
| **Work** | The abstract work as idea | "Satipaṭṭhāna Sutta" (MN 10) — one for all |
| **Expression** | A specific expression — translation/edition | Bhikkhu Bodhi's 1995 translation vs Sujato's 2018 vs Nyanaponika's 1962 |
| **Instance** | Physical realization — a file | HTML on SuttaCentral revision 2024-10 vs PDF on Access to Insight vs TXT in a Legacy archive |

One Work has dozens of Expressions and hundreds of Instances. Without this separation you get chaos: *"do we have MN 10 in Bodhi's translation, or Sujato's, or Access to Insight, or SuttaCentral?"*

### 5.7. Database Schema: 11 PostgreSQL Tables

The project documentation describes a well-considered PostgreSQL schema. The core is the three FRBR levels plus Buddhism-specific tables:

```
┌──────────────────┐
│  work            │  ← abstract work (MN 10, DN 22, Toh 95)
└────────┬─────────┘
         │ 1:N
┌────────▼─────────┐
│  expression      │  ← translation/edition
└────────┬─────────┘
         │ 1:N
┌────────▼─────────┐
│  instance        │  ← specific file
└────────┬─────────┘
         │ 1:N
┌────────▼─────────┐
│  chunk           │  ← search fragment (~384 tokens)
└──────────────────┘

Reference tables:
- tradition_t: theravada, mahayana, vajrayana, zen, chan, pragmatic_dharma...
- language_t: pli, san, bo, zh-Hant, zh-Hans, en, ru + European
- author_t: translators, teachers
- relation_t: 14 types of relations between Works
- lineage: transmission lineages of teachings
- canonical_id_t: numbering systems (MN/DN/SN/AN, Tohoku, Taisho)
- consent_ledger: licenses
```

### 5.8. 14 Relation Types (relation_t)

Between Works there are many types of relations:

- `is_a` — "Anapanasati-sutta IS-A breathing-meditation instruction";
- `part_of` — "MN 10 IS-PART-OF Majjhima Nikaya";
- `causes` — "right-effort CAUSES samadhi";
- `opposed_to` — "kāmacchanda OPPOSED-TO pīti";
- `synonym_of` — "dukkha SYNONYM-OF suffering";
- `translates_as` — "nibbāna TRANSLATES-AS nirvana";
- `derived_from` — "Visuddhimagga DERIVED-FROM Vimuttimagga";
- `elaborates` — "Patthana ELABORATES Dhammasangani";
- `refines` — "Pa-Auk method REFINES Visuddhimagga method";
- `prerequisite_of` — "sīla PREREQUISITE-OF samādhi";
- `contradicts` — traditions sometimes diverge; mark it explicitly;
- `cited_in` — secondary reference;
- `taught_by` — teacher–text;
- `practiced_in` — school–teacher.

This is an explicit structure that can be built **deterministically** via regex on canonical sources, without LLM involvement. The graph produced is clean and verifiable.

### 5.9. Transmission Lineages: ltree + Closure Table

Transmission lineages in Buddhism are hierarchical: "Buddha → Ananda → ... → Ajahn Mun → Ajahn Chah → Ajahn Sumedho." For such queries, Postgres offers two techniques used together:

- **ltree** — a Postgres extension for hierarchical paths. Format: `buddha.ananda.moggallana.X.Y.Z`. "All descendants of Y" becomes one query.
- **Closure table** — an explicit table with precomputed ancestor–descendant pairs. One row per pair. Fast queries on deep hierarchies.

Both are classic SQL techniques and **require no graph DB at all**. Counter-intuitively, for hierarchies and a knowledge graph, Postgres copes excellently.

---

## Part VI. Chunking — How to Properly Slice Texts

### 6.1. Why You Can't Just Cut Every 500 Words

When a sutta or book is loaded into a RAG system, it must be split into pieces ("chunks"), each of which becomes a vector. **The naive approach** is to cut the text on a fixed character count (for example, 1000 characters with 200-character overlap). This is exactly what the default settings of LangChain, LlamaIndex, and similar libraries do.

For Buddhist texts this approach is **catastrophically bad**. The project's research identifies three specific problems:

**Problem 1: Boilerplate — verbatim repeated formulas.**

*"Evaṃ me sutaṃ. Ekaṃ samayaṃ Bhagavā…"* ("Thus have I heard. Once the Blessed One…") repeats in thousands of suttas. Without deduplication, vector search ranks random suttas to the top merely because they contain this formula.

**Problem 2: Pericopes — standard passages.**

The satipaṭṭhāna formula, the jhāna formula, the bojjhaṅga formula appear hundreds of times. Cutting such a passage in the middle destroys its meaning entirely.

**Problem 3: Anaphoric density.**

Suttas are often dialogues where the subject is introduced in the preamble, then the rest is "he said," "he replied." A fixed divider severs the replies from their speakers.

### 6.2. How the Problems Manifested: the Baseline Disaster

The project's `DHARMA_RAG_TECHNICAL_AUDIT` records: the initial baseline with fixed-size chunking achieved **ref_hit@5 = 2%**. This means for 98% of queries **none of the relevant chunks appeared in the top five results**. A failure.

This is the concrete motivation for the layered chunking strategy that was adopted.

### 6.3. A Three-Layer Chunking Strategy

The project's documentation proposes a layered approach where each layer addresses its own problem.

**Layer 1: Structural chunking**

Splitting occurs not on characters but on natural structure: heading → chapter → paragraph → verse. Never cut a pāda (verse line) in the middle. Gāthās (verses) and mantras are atomic units that go into vectors whole.

Metadata attached to each chunk:

- `canonical_id` — DN 22, Toh 44-45;
- `verse_range` — from which line to which;
- `folio` — for Tibetan texts: `[F.362.b]`;
- `speaker` — Buddha, Ananda, Sāriputta;
- `audience` — monks, laypeople, King Pasenadi;
- `pericope_id` — if this is a standard formula, the id of the common formula (for later deduplication);
- `tradition` — Theravada/Mahayana/Vajrayana;
- `language` — pli/san/en/ru/zh.

**Layer 2: Contextual Retrieval — Anthropic's Secret Weapon**

In September 2024, Anthropic published a technique that raises retrieval accuracy by 35–67%. The idea is simple: before turning each chunk into a vector, ask a **cheap LLM** (Claude Haiku) to write a **50–100-token explanatory prefix**:

> *"This passage is from MN 10 Satipaṭṭhāna Sutta, where the Buddha instructs the monks on the four foundations of mindfulness. Specifically — the section on contemplation of the body…"*

This context is **prepended to the chunk itself** before embedding and before BM25 indexing.

> **Why this works — a concrete example**
>
> Original chunk: *"Furthermore, monks, a monk contemplates the body as body."*
>
> On its own it is context-poor: unclear who is speaking, where, about what.
>
> With context: *"MN 10, section on contemplation of the body: Furthermore, monks, a monk contemplates the body as body."*
>
> Now a search for *"contemplation of the body practices by the Buddha"* will reliably find this chunk.
>
> Cost for 56,000 chunks: **~$30 one-off** (Haiku 4.5 with prompt caching). For a Buddhist corpus where the cost of hallucination is high, this is not a "nice-to-have" but mandatory.

Official numbers from Anthropic (confirmed in several independent sources):

| Approach | Retrieval failure rate | Improvement |
|--------|------------------------|-----------|
| Traditional RAG | 5.7% | — (baseline) |
| + Contextual Embeddings | 3.7% | **−35%** |
| + Contextual BM25 | 2.9% | **−49%** |
| + Reranking | 1.9% | **−67%** |

**Layer 3: Hierarchical retrieval (parent-child)**

Index small child chunks (~384 tokens) for precise matching. When delivering to the LLM context, substitute the **parent** — a full sutta or semantic section (1024–2048 tokens).

This yields a large quality gain at almost no extra cost: **the search pinpoints the exact location, but the LLM receives rich context for a meaningful answer**.

Schema:

```
Indexed child chunk: "Furthermore, monks, a monk contemplates the body as body"
   ↓ (found by search)
   ↓ (at context assembly for the LLM)
Parent: full "Contemplation of the Body" section of MN 10 (1024 tokens)
   ↓ (passed to the LLM)
LLM answer: "In MN 10, the contemplation-of-the-body section, the Buddha describes... [quote]"
```

### 6.4. HyPE — Hypothetical Questions Instead of the Chunk Embedding

A more recent technique (2024–2025): instead of embedding the original chunk, **generate questions** that the chunk answers, and embed those.

Example:

- **Original chunk:** *"Satipaṭṭhāna is the practice of the four foundations of mindfulness."*
- **Generated questions:**
  - *"What is satipaṭṭhāna?"*
  - *"Which are the four foundations of mindfulness?"*
  - *"What is the mindfulness practice called in Theravada?"*
  - *"Where does the term satipaṭṭhāna come from?"*

Embed each of these questions separately, link them to the source chunk. On search for "what is satipaṭṭhāna?" you get a direct hit, because the match is between **the user question and a generated question**, not between a question and a description.

HyPE adds another +10–20% precision but costs more (3–5 questions per chunk to generate via LLM).

### 6.5. Late Chunking (Jina, 2024)

An even more recent technique: first embed the **whole document**, then cut the embedding into chunks. This preserves document-wide context. Used in Jina Embeddings v3.

### 6.6. Pericope-Aware Deduplication

For Buddhist texts it is critical to detect standard formulas and not flood the search with them:

1. Collect a list of known formulas (satipaṭṭhāna, jhānas, bojjhaṅga, 37 bodhipakkhiya dhamma).
2. Check each chunk: does it wholly contain such a formula?
3. If yes — **one** copy of the formula goes into the database (with a list of all places it appears), not 200 copies.
4. At search time the user gets a single hit noting "this formula appears in MN 10, DN 22, AN 10.61, ..."

### 6.7. MMR Result Diversification

Another technique: when returning 20 candidates — avoid near-duplicates. **Maximum Marginal Relevance** (MMR) is an algorithm that rewards relevance but penalizes similarity to already chosen results.

For the Buddhist corpus this is particularly important: when a user searches for "breath meditation," they don't need 10 nearly identical quotes about *ānāpānasati* — better 3 quotes from different suttas + 2 from commentaries + 2 from modern teachers.

### 6.8. Summary: What Dharma-RAG Does

| Technique | Applied | Reason |
|---------|-------------|---------|
| **Fixed-size chunking** | ❌ No | Catastrophic on Buddhist text (2% ref_hit@5 baseline) |
| **Structural chunking** | ✅ Yes (Layer 1) | Respects natural sutta structure |
| **Contextual Retrieval** | ✅ Yes (Layer 2) | −49% retrieval failure for $30 one-off |
| **Parent-child** | ✅ Yes (Layer 3) | Precise search + rich LLM context |
| **HyPE** | ⚠️ Under consideration | +10–20% more, but costlier |
| **Late chunking** | ⚠️ Only if using Jina | Tied to a specific embedding model |
| **Pericope dedup** | ✅ Yes | Without it, 200 copies of one formula clog the search |
| **MMR diversification** | ✅ Yes | Diverse sources in the output |

---

## Part VII. Embeddings — the Heart of Semantic Search

### 7.1. Why the Embedding Model Is the Most Important Architectural Decision

If one thing in a RAG system determines search quality more than anything else, it is the **embedding model**. It determines whether the system can find the *Satipaṭṭhāna Sutta* when queried *"the practice of mindfulness taught by the Buddha,"* or not.

The embedding model is a **one-way door**. If you have indexed the entire corpus with model X, switching to model Y requires **reindexing the entire corpus**. For 56,000 chunks, that is several hours and $30–100. For 900,000 chunks, it is a full day and $500–2000.

So this choice is a long-term decision that must be made deliberately.

### 7.2. Fork 1: Closed Paid Model or Open Free One

**Closed cloud models** (OpenAI text-embedding-3, Voyage AI, Cohere embed-v4, Gemini Embedding 2):

Pros:
- Excellent quality in English (MTEB 65–70).
- No infrastructure setup — just an API call.
- Automatic updates.

Cons:
- Paid: $0.018–0.18 per million tokens.
- Provider dependency (vendor lock-in).
- Data leaves your servers — a problem for confidential documents.
- For 900k chunks, indexing costs $50–500 + lifetime payments per query.
- If the API changes the model's behavior or deprecates it, you must reindex.

**Open self-hosted models** (BGE-M3, Qwen3-Embedding, GigaEmbeddings, Nomic, Jina):

Pros:
- Free (only your server costs).
- Data does not leave your server.
- Full control: you can fine-tune, freeze the version, reproduce.
- MIT or Apache 2.0 licenses — use as you wish.

Cons:
- Requires a GPU for indexing (BGE-M3 needs at least 8 GB VRAM).
- You maintain it.
- In English, may slightly lag paid models (but the gap is closing fast).

**Dharma-RAG's decision:** open self-hosted. Reasons:

1. **Cost.** For 900k chunks × 1000 queries/month, self-hosted is 10–100× cheaper.
2. **Privacy.** Meditation is a sensitive domain, and the corpus is the fruit of manual curation.
3. **Reproducibility.** Anyone can spin up the system on their own machine.
4. **MIT compatibility.** Corpus under CC, code under MIT — an OSS model logically completes the stack.

### 7.3. Fork 2: Big Model or Small

Within open source, the choice ranges from 100 million to 8 billion parameters.

| Class | Parameters | VRAM (FP16) | MTEB quality | Examples |
|-------|-----------|-------------|---------------|---------|
| **Tiny** | < 100M | < 1 GB | 55–58 | all-MiniLM-L6-v2 |
| **Small** | 100–400M | 1–2 GB | 58–63 | E5-small, BGE-small |
| **Medium** | 400M–1B | 2–4 GB | 62–66 | **BGE-M3 (568M)**, Nomic, Jina v3 |
| **Large** | 1–4B | 4–10 GB | 66–69 | EmbeddingGemma, Qwen3-4B |
| **XL** | 7–8B | 15–30 GB | 69–71 | Qwen3-8B, NV-Embed-v2, e5-mistral-7b |

**The classic trade-off:** more parameters = better quality, but more expensive to index and store.

**For 900k chunks:**
- Tiny: 1-hour indexing on an RTX 3060.
- Medium: 4–6 hours.
- XL: 12–24 hours + more VRAM.

In server RAM:
- Medium: 2 GB RAM.
- XL: 15+ GB RAM.

### 7.4. Fork 3: Why BGE-M3 Is a Unique Choice

**BGE-M3** from BAAI (Beijing Academy of Artificial Intelligence) is a 568M-parameter model, MIT license. Its uniqueness: it outputs **three different representations simultaneously**:

1. **Dense embedding** — a standard 1024-number vector for semantic search.
2. **Sparse representation** — a sparse vector (SPLADE-style) for lexical search, reflecting rare words.
3. **Multi-vector (ColBERT-style)** — several vectors per token for high-precision late-interaction reranking.

In one model. This eliminates the need to run three models and saves inference time.

**BGE-M3 specifications:**

- **Size:** 568M parameters;
- **Context:** up to 8192 tokens (about 30 pages);
- **Languages:** 100+, including Russian, Pali (via romanization), Sanskrit, Tibetan, Chinese;
- **MTEB:** ~63 (Medium tier);
- **License:** MIT (permits everything, including commercial use);
- **VRAM (FP16):** 2–3 GB;
- **CPU inference:** works, ~50 ms per query.

### 7.5. Comparing BGE-M3 with Alternatives

| Model | Parameters | License | MTEB | ruMTEB | Multi-mode | Pros | Cons |
|--------|-----------|----------|------|--------|-----------|-------|--------|
| **BGE-M3** | 568M | MIT | 63.0 | ~61 | **Yes (3-in-1)** | OSS, multilingual, hybrid in one model | Middling MTEB |
| **Qwen3-Embedding-8B** | 8B | Apache 2.0 | 70.58 | 70.6 | No | SOTA multilingual, instruction-aware, MRL | Large, slow |
| **Qwen3-Embedding-4B** | 4B | Apache 2.0 | 69.5 | 69.5 | No | Good quality, MRL | Heavier than BGE-M3 |
| **Qwen3-Embedding-0.6B** | 600M | Apache 2.0 | 64.3 | ~62 | No | Compact, instruction-aware | No sparse/ColBERT |
| **GigaEmbeddings** (Sber) | 3B | MIT | — | **69.1** | No | SOTA for Russian, understands nuances | 3B size, no multimodal |
| **Gemini Embedding 2** | ? (API) | Paid | 68+ | ~66 | No | Native 5 modalities | Closed, not self-hosted |
| **OpenAI text-embedding-3-large** | ? (API) | Paid | 64.6 | ~60 | No | Reliable, simple | Closed, paid |
| **Cohere embed-v4** | ? (API) | Paid | 65.2 | — | No | 128K context, multilingual | Closed |
| **Voyage AI voyage-3-large** | ? (API) | Paid | 67.2 | — | No | Retrieval leader | Closed |
| **Jina Embeddings v3** | 570M | Non-commercial | 62 | — | No | Task-specific LoRA | Incompatible with MIT |
| **Nomic v1.5** | 137M | Apache 2.0 | 62 | — | No | Fully open (training data too) | Strong only in English |
| **EmbeddingGemma-300M** | 300M | Apache 2.0 | 62+ | — | No | On-device, 200MB RAM | For mobile/edge |
| **MITRA-E** (domain-specific) | — | — | — | — | — | Buddhological fine-tune (hypothetical) | In development |

### 7.6. Why BGE-M3 Rather Than Qwen3

Technically, Qwen3-8B beats BGE-M3 on MTEB (70.58 vs 63.0). Why did Dharma-RAG pick BGE-M3?

1. **Three modes in one model.** BGE-M3 outputs dense + sparse + ColBERT in one inference. Qwen3 yields only dense. For hybrid search with BGE-M3 you don't need separate BM25/SPLADE models — saving RAM and CPU.

2. **Compactness.** 568M vs 8B — a 14× difference. BGE-M3 fits on a €9 Hetzner VPS (8 GB RAM); Qwen3-8B does not.

3. **Maturity.** BGE-M3 released January 2024, tested in thousands of production scenarios. Qwen3 — June 2025, still young.

4. **MIT vs Apache.** Both permit commercial use, but MIT is shorter and clearer, reducing legal ambiguity for contributors.

5. **Cross-lingual.** BGE-M3 handles cross-lingual search excellently (a Russian question → finds answers in English texts). Critical for Dharma-RAG.

**However:** if the project outgrows the €9 server and migrates to beefier hardware, switching to Qwen3-4B or Qwen3-8B is considered in Phase 2 via the named-vectors mechanism.

### 7.7. Russian-Language Specifics: GigaEmbeddings as a Serious Alternative

For Russian-speaking users, ruMTEB (the Russian benchmark) matters:

- **GigaEmbeddings** (Sber AI, October 2025, MIT) — 69.1 ruMTEB. **SOTA for Russian.** 3B parameters, captures Russian cultural and linguistic nuance, runs on a home GPU.
- **Qwen3-Embedding-8B** — 70.6 ruMTEB, but 8B parameters and less "native" Russian specialization.
- **BGE-M3** — ~61 ruMTEB, good multilingual but not SOTA for Russian.
- **multilingual-e5-large** — ~65.5 ruMTEB, outdated.

For Dharma-RAG there is a potential improvement: **use GigaEmbeddings for Russian queries** and BGE-M3 for other languages. This is realized via Qdrant named vectors: one collection, multiple embeddings, selected at query time.

### 7.8. The "Quantization Zoo" Problem

**Quantization** compresses a model by representing its weights with fewer bits:

| Quantization | Memory | Quality | Speed |
|-------------|--------|----------|----------|
| **FP32** (32-bit float) | 100% | 100% | Baseline |
| **FP16** (half-precision) | 50% | ~100% | 1.5× faster |
| **BF16** (brain float 16) | 50% | ~100% | ~FP16 |
| **INT8** (8-bit integer) | 25% | −1.5% | 2–3× faster |
| **FP8** (8-bit float) | 25% | **−0.3%** | 2–3× faster |
| **INT4** (4-bit integer) | 12.5% | −3% to −10% | 3–4× faster |
| **Binary** (1 bit) | 3% | −15% to −30% | 10× faster |

The problem: if your corpus is indexed with FP32, but your search query is embedded with INT8 — results are worse than if both sides used the same quantization.

### 7.9. Float8 vs INT8 — a Fresh 2025 Finding

Work by Huerga-Pérez et al. (HAIS 2025) shows that **float8 achieves 4× compression at <0.3% quality loss**, while INT8 loses about 1.5%.

This challenges the industrial default (many vector DBs default to INT8).

For Dharma-RAG this means:
- **900k index at FP32:** ~7 GB.
- **At FP8:** ~1.75 GB (practically no quality loss).
- **Savings:** 4× in memory, almost no quality penalty.

### 7.10. Solution: Qdrant "Named Vectors"

**Qdrant named vectors** is a mechanism allowing **several different vectors per record**. Each vector has a name and its own config (size, metric, quantization).

```json
{
  "id": "chunk_12345",
  "vectors": {
    "bge_m3_dense":   [0.12, -0.45, ...],  // BGE-M3 dense (1024-dim FP16)
    "bge_m3_sparse":  {"indices": [...], "values": [...]},  // BGE-M3 sparse
    "bge_m3_colbert": [[...], [...], ...],  // ColBERT multi-vector
    "qwen3_8b":       [0.23, 0.11, ...],   // Future migration
    "giga_ru":        [0.04, -0.22, ...]   // For Russian
  },
  "payload": { "text": "...", "source": "MN10", ... }
}
```

**Advantages:**

1. **Reversible migration.** Want to try Qwen3? Index the corpus in parallel, keep both vectors, A/B test on real queries. If better — remove the old one.

2. **Model ensembles.** Different queries can use different embeddings. Russian → GigaEmbeddings. English → BGE-M3. Multilingual → Qwen3.

3. **No reindexing.** You do not delete or rebuild HNSW for the old model — both work in parallel.

**This is the main reversibility technique** in Dharma-RAG. Without it, choosing an embedding model would be a one-way door; with it, a fully reversible decision.

### 7.11. Concrete Footprint for 900k Chunks

```
Storage budget for 900k chunks:

BGE-M3 dense (1024-dim):
  FP32: 900k × 1024 × 4 bytes = 3.5 GB
  FP16: 1.75 GB
  FP8:  0.9 GB

BGE-M3 sparse (SPLADE):
  Variable length, ~100 bytes per chunk: 90 MB

BGE-M3 ColBERT (multi-vector):
  ~384 tokens × 128 dim = 49k bytes per chunk
  CRITICALLY large; typically used only at reranking time

Qwen3-8B dense (4096-dim):
  FP16: 7 GB
  FP8:  3.5 GB

Total for Dharma-RAG (BGE-M3 + optional Qwen3):
  Minimum: 2 GB (BGE-M3 dense FP16 + sparse)
  With ColBERT: 45 GB — use only at rerank stage, don't persist
  With Qwen3: +3.5 GB (if FP8)
```

### 7.12. MITRA-E — a Specialized Model for Buddhism

Mentioned in the project documentation as a long-term goal: **MITRA-E** is a Buddhist-domain-specialized fine-tune of BGE-M3 on the Pali corpus.

The idea: if a general-purpose BGE-M3 delivers 61% on ruMTEB, a fine-tune on Buddhist data could add +10–15% specifically on Buddhist queries. The work is being done by the Dharmamitra project.

If MITRA-E is released under an open license with decent quality, Dharma-RAG will add it as a third named vector alongside BGE-M3 and optional Qwen3.

---

## Part VIII. Vector Database — Where "Meaning Coordinates" Live

### 8.1. What a Vector DB Is and Why You Need One

So we have 56,000 – 900,000 chunks. Each chunk has been turned into a 1024-number vector by BGE-M3. Those vectors must be:

1. **Stored** — preferably compactly.
2. **Quickly searched** — find the 20 nearest to a query vector in milliseconds.
3. **Filtered** — by metadata (language, tradition, author, date).
4. **Updated** — when new texts are added.
5. **Combined across searches** — dense + sparse simultaneously.

An ordinary relational DB (MySQL, PostgreSQL) cannot do this efficiently. A linear scan of 900k vectors = seconds, unacceptable for an interactive UI.

A specialized class of databases is needed — **vector databases**. They use **approximate nearest neighbor** (ANN) algorithms, most often **HNSW** (Hierarchical Navigable Small World), delivering answers in milliseconds at the cost of a small recall loss (95–99% recall, not 100%).

### 8.2. HNSW in Plain Terms

**HNSW** works like a multilevel map of connections, similar to a friend-of-friend social network:

```
Level 3 (sparse):    A ──── D
                     │       │
Level 2 (middle):    A ─ B ─ D
                     │   │   │
Level 1 (dense):     A-B-C-D-E-F-G

Search from point G to point A:
- Start at the top level: big jumps between distant points.
- Descend: refine.
- On the bottom level: fine-grained search.
```

- On the **top level** each point "knows" only a few others, far apart.
- On the **lower levels** — each point knows its closest neighbors.
- The search goes top-down: rough-precise-precise-finer.

This yields **O(log N) instead of O(N)** search, working for millions of vectors in milliseconds.

### 8.3. Vector DB Comparison 2026

| DB | Language | License | Performance | Named vectors | Hybrid search | Notes |
|------|------|----------|--------------------|--------------:|---------------|-------------|
| **Qdrant** | Rust | Apache 2.0 | High | ✅ Yes (full) | ✅ Yes | HNSW, quantization, filter JOIN, GPU indexing |
| **pgvector** | PostgreSQL ext | PostgreSQL | Medium | ⚠️ Via JSONB | ⚠️ Via extensions | Lives in Postgres, convenient for SQL |
| **Milvus** | Go | Apache 2.0 | Very high | ✅ Yes | ✅ Yes | Scales to billions of vectors |
| **Weaviate** | Go | BSD | Medium | ⚠️ Limited | ✅ Yes (built-in) | Modules for ML models, GraphQL |
| **Chroma** | Python | Apache 2.0 | Low | ❌ No | ❌ No | Simplest prototyping |
| **Pinecone** | ? (closed) | Paid | Very high | ⚠️ Via namespaces | ✅ Yes | Managed SaaS, no self-hosted |
| **Elasticsearch + ANN** | Java | Elastic (since 2024) | Medium | ⚠️ Via aliases | ✅ Yes (built-in) | If ES infra already exists |
| **Vespa** | Java | Apache 2.0 | Very high | ✅ Yes | ✅ Yes | Powerful, but complex |
| **FAISS** | C++ | MIT | Highest | ❌ No (library) | ❌ No | Not a DB, just an index |

### 8.4. Detailed Comparison by Criteria

**1. Performance:**

Milvus and Qdrant lead on speed. Qdrant (Rust) uses native HNSW, efficient SIMD ops, supports GPU for indexing. Milvus (Go) is also fast, chiefly via horizontal scaling.

pgvector is slower than pure vector DBs, but on volumes up to 10M vectors the gap is acceptable (tens of milliseconds).

**2. Named vectors:**

This is the critical distinction. **Qdrant** is the only OSS vector DB with full named-vectors support (several vectors from different models/sizes in one record). Milvus supports it, more simply. pgvector needs JSONB hacks.

**3. License:**

Qdrant, Milvus, Chroma — Apache 2.0 (free). pgvector — PostgreSQL license (also free). Pinecone — closed/paid. Elasticsearch since 2024 — Elastic License (restrictive).

**4. Hybrid search:**

Critical for Dharma-RAG. Out-of-the-box support:
- Qdrant: built-in (dense + sparse + fusion),
- Weaviate: built-in,
- Milvus: built-in (since 2024),
- pgvector: combine with Postgres FTS manually.

**5. Storage footprint:**

Quantization (INT8/FP8/binary) is supported by all modern ones. Qdrant leads on efficiency: ready INT8 quantization with <2% quality loss, binary quantization for extreme memory savings.

**6. Filtering + search:**

Often you need "find vector-similar, but only with metadata X=Y." This is **filterable ANN**. Qdrant and Milvus do it efficiently (filter embedded in HNSW), pgvector — via SQL WHERE (can be slow on large volumes).

### 8.5. Why Qdrant Is the Right Choice for Dharma-RAG

1. **Named vectors** — critical for reversible migration between models.
2. **Apache 2.0** — compatible with the project's MIT.
3. **Rust** — high performance, low RAM usage.
4. **Docker deployment** — simple install in one command.
5. **Hybrid search out of the box** — important for Pali.
6. **INT8/FP8 quantization** — memory savings.
7. **Production-ready** — used in thousands of projects.
8. **REST + gRPC API** — easy FastAPI integration.

### 8.6. When pgvector Might Be Better

For Phase 1 with <1M chunks, you could weigh pgvector against Qdrant:

**pgvector pros:**
- One DB (Postgres) instead of two (Qdrant + Postgres) — simpler backup, monitoring, admin.
- Transactionality: vector and metadata update atomically.
- Familiar SQL: write normal JOINs with metadata.
- Apache AGE (knowledge graph) lives in the same Postgres.

**pgvector cons:**
- Less flexible named vectors (via JSONB).
- Hybrid search needs manual work (pgvector + ts_vector).
- Performance issues possible at >10M volumes.
- A/B testing different models is harder.

**Project recommendation:**

- **Phase 1 (MVP):** Qdrant for vectors + Postgres for metadata. Two containers, but higher flexibility.
- **Phase 2 (Growth):** consider migrating everything into Postgres (pgvector + Apache AGE) for unification.

This is a **reversible** decision — Qdrant → pgvector migration can go either way.

### 8.7. HNSW Parameters

Two key HNSW settings:

- **M (max connections per node)** — how many neighbors each vector has on the bottom level. Higher = better quality, more memory. Typically 16–64.
- **ef_construction** — how many candidates to consider while building the index. Higher = better index, slower indexing. Typically 100–500.
- **ef_search** — the same at search time. Higher = better quality, slower search. Typically 50–200.

Dharma-RAG uses M=32, ef_construction=200, ef_search=100 — a good balance for corpora <1M.

### 8.8. Example Docker Compose for Qdrant

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"  # REST API
      - "6334:6334"  # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__MAX_REQUEST_SIZE_MB: 32
    restart: unless-stopped

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: dharma
      POSTGRES_USER: dharma
      POSTGRES_PASSWORD: secret
    volumes:
      - pg_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  qdrant_data:
  pg_data:
```

On a €9 Hetzner VPS (4 CPU, 8 GB RAM) this configuration handles 500k–1M chunks comfortably.

---

## Part IX. Hybrid Search and RRF — Why One Search Method Is Not Enough

### 9.1. The Problem of Pure Vector Search

Vector search excellently finds texts by **meaning** but fails in several cases:

**1. Rare proper names.**

Query: *"Pemasiri Thera."* A little-known Theravada teacher. In BGE-M3's training data he is scarce; the vector may not align exactly with the chunks where he is mentioned.

**2. Numeric identifiers.**

Query: *"MN 10."* Vectors encode short codes poorly. They "smear" numbers across a semantic space, losing precision.

**3. Pali diacritics.**

*paṭicca-samuppāda* vs *paticca-samuppada* vs *pratītya-samutpāda*. Different spellings should match, but vectors handle them differently.

**4. Technical terms with rare words.**

Query: *"Anapanasati 16 steps."* The word "steps" dilutes meaning, and *Anapanasati* is a rare token. Results may be irrelevant.

### 9.2. Solution: Three Parallel Search Channels

Professional RAG systems use **hybrid search**:

```
            Query "MN 10 Satipaṭṭhāna"
                         │
           ┌─────────────┼─────────────┐
           │             │             │
    Dense vector    Sparse vector     BM25
    (BGE-M3 dense) (BGE-M3 sparse) (Postgres FTS)
           │             │             │
        Top-30        Top-30        Top-30
        candidates    candidates    candidates
           │             │             │
           └─────────────┼─────────────┘
                         │
                       RRF
                     (fusion)
                         │
                 Top-20 merged
                         │
                    Reranker
                         │
                  Top-5 for LLM
```

**1. Dense vector (BGE-M3 dense):**

Semantic search. Catches: *"mindfulness practice"* → *"satipaṭṭhāna."*

**2. Sparse vector (BGE-M3 sparse):**

A neural analog of BM25. Accounts for rare words, rare tokens. Catches: *"Pemasiri Thera"* → exact mention location.

**3. BM25 (Postgres FTS or Elasticsearch):**

The classic 1980s algorithm. Formula:

```
score(q, d) = Σᵢ IDF(qᵢ) × (tf(qᵢ, d) × (k₁ + 1)) / (tf(qᵢ, d) + k₁ × (1 − b + b × |d|/avg_dl))
```

Roughly: a word is more valuable the rarer it is in the corpus. A document is more valuable the more times the query word appears in it. Adjusted for document length.

Catches: *"MN 10"* → documents with the exact code.

### 9.3. Contextual BM25 — an Upgrade via the Anthropic Approach

Recall: Contextual Retrieval (Part VI) adds context before embedding. But the same prefix is prepended **before BM25 indexing** too.

This is **Contextual BM25**. The effect: if the word *"MN 10"* appears as a prefix of each chunk via context, then a search for *"MN 10"* finds them all via BM25.

### 9.4. RRF — Reciprocal Rank Fusion

Three channels each returned their own top 30. How do we merge them?

You cannot simply sum scores, because scores from different channels are incomparable: dense gives cosine similarity (0–1), BM25 gives an unbounded number (could be 50 or 500).

**Reciprocal Rank Fusion** is a simple formula:

```
RRF_score(d) = Σ (1 / (k + rank_i(d)))
               where k is usually 60, and rank_i is the document's position in list i
```

A document that is 1st in dense and 5th in BM25 gets: `1/(60+1) + 1/(60+5) = 0.0164 + 0.0154 = 0.0318`.

A document that is 1st in dense but absent from BM25: `1/(60+1) = 0.0164`.

A document that is 1st in all three channels gets the maximum.

### 9.5. Why RRF and Not Other Methods

Alternatives:

- **Sum of normalized scores** — requires normalization that is hard to tune.
- **Weighted Reciprocal Rank** — assigns weights to channels, but calibrating them is hard.
- **Learned-to-Rank** — requires training data, which for a Buddhist corpus must be collected from scratch.

**RRF** is parameter-free (only `k=60`), robust to poorly-calibrated scores, works out of the box. That is why it became the standard in 2024–2026.

### 9.6. Approximate Effect of Hybrid Search

Benchmarks show that hybrid search through RRF yields:

- **+10–20% recall@5** vs pure dense.
- **+30–50% precision** vs pure BM25.
- **Robustness** to outliers — if one channel fails, others compensate.

For the Buddhist corpus, robustness to diacritics and rare proper names is especially important, and hybrid solves this.

---

## Part X. Knowledge Graph — Where Vectors Fall Short

### 10.1. What a Knowledge Graph Is

A **knowledge graph** (KG) is a network of nodes (entities) and named relations between them.

Example:

```
[Buddha] ─ taught_by ─→ [Ananda]
   │
   ├─ developed ───→ [Satipatthana]
   │                     │
   │                     ├─ subtype_of ─→ [Sati]
   │                     │
   │                     └─ leads_to ───→ [Nirvana]
   │
   └─ described ───→ [Dependent Origination]
                         │
                         └─ synonym_of ──→ [Paticca-samuppada]
```

Each node is a concept (name, term, idea). Each relation is a typed relation (15 types in Dharma-RAG, see Part V).

### 10.2. Why a Graph Is Needed Beyond Vectors

There are classes of questions that vector search handles poorly:

**1. Multi-hop reasoning — "jumps" across several steps.**

Query: *"Which student of Ajahn Chah teaches in England?"*

Vector search:
- Finds chunks about Ajahn Chah.
- Finds chunks about "England" (thousands).
- Cannot tie "student(s) → their students → location."

Graph:
- `Ajahn Chah --taught--> Ajahn Sumedho --lives_in--> UK`
- One JOIN, precise answer.

**2. Explicit relationships.**

Query: *"What is satipaṭṭhāna?"*

- Vector search: finds chunks that mention it.
- Graph: `satipaṭṭhāna --subtype_of--> sati, --leads_to--> nibbāna, --described_in--> MN 10, --has_four_parts--> kāya/vedanā/citta/dhamma`.

Explicit, structured information. No need to read 500 words to grasp the relations.

**3. Aggregation queries.**

*"Show me all texts whose teacher is Dīpaṃkara"* — for a graph this is a single op, for vector search it is iteration over the whole corpus.

### 10.3. Microscopy: GraphRAG and Its Variants

In 2024–2025 enthusiasm grew around **GraphRAG** (Microsoft, 2024). The key idea: extract a graph from the corpus via LLM, then use the graph for retrieval.

**Variants:**

- **Microsoft GraphRAG** — clusters the graph, generates community summaries, answers from them.
- **LightRAG** (2024) — lighter weight, without dual-level retrieval.
- **LazyGraphRAG** (2024) — builds the graph on-the-fly, not precomputed — 100× cheaper.
- **HippoRAG 2** — uses PageRank over the graph for retrieval.

The common idea: **graph + vector is better than either alone**.

### 10.4. GraphRAG-Bench ICLR 2026 — a Problem

In 2026, at ICLR, a paper titled **GraphRAG-Bench** presented an independent evaluation of GraphRAG approaches. Results were unexpected:

- On **Natural Questions** (simple fact questions) GraphRAG **underperforms** vanilla RAG by **−13.4% accuracy**.
- On **time-sensitive** queries GraphRAG is worse by **−16.6%**.
- Retrieval latency is on average **2.3× slower**.

**Conclusion:** enthusiasm around GraphRAG was overblown. Graphs add value but **do not replace** vector search; they **complement** it.

### 10.5. Why for Dharma-RAG the Graph Is a Layer, Not the Foundation

Key observations:

**1. 80% of user queries are 1–2 hop.**

*"Find parallels to MN 10,"* *"what is jhāna,"* *"Thanissaro's texts on mindfulness"* — all 1–2 hop queries. For these:

- SQL JOIN or recursive CTE (standard SQL): **1–5 ms** for one hop, **5–30 ms** for two.
- Cypher (Apache AGE): **adds 10–30 ms overhead.**
- Neo4j: **50–100 ms** due to network overhead.

So **SQL is faster** for simple queries.

**2. The Buddhist corpus is already structured.**

Canonical citations (DN 22, MN 10, SN 56.11), parallels (SuttaCentral `parallels.json`), teacher lineages — all can be parsed with **deterministic regex**, no LLM required. LLM-extracted graphs add noise in areas with clear structure.

**3. LLM fabrication when building the graph.**

Microsoft GraphRAG uses LLMs to extract entities and relations. On Buddhist texts this is risky: the LLM can "hallucinate" connections that do not exist.

### 10.6. Kùzu Is Dead — an Important Signal

In October 2025, Apple acquired Kùzu Inc. — a startup building an embedded graph database that many AI projects had bet on. The **kuzudb/kuzu repo was archived** on 10 October 2025. The company's website is offline.

Forks (**RyuGraph**, **LadybugDB**, **Vela-Engineering/kuzu**) are in early stages, with no production cases.

**For Dharma-RAG:** do not use Kùzu, pick more stable alternatives.

### 10.7. Apache AGE — the Right Choice

**Apache AGE** is a PostgreSQL extension that lets one Postgres cluster host:

- Relational tables (metadata, logs, consent ledger);
- Vectors (via pgvector);
- Graph (via AGE's Cypher syntax).

Microsoft documented a working pattern in April 2026: AGE and pgvector living in one database, one transaction, with full ACID guarantees.

**Apache AGE advantages:**

1. **Apache 2.0 license** — perfectly compatible with an MIT project.
2. **One Postgres for everything** — one backup, one monitor, one admin tool.
3. **Gradual migration:**
   - Phase 1-2: Qdrant + Postgres metadata;
   - Phase 2: AGE graph added as a projection layer;
   - Phase 3 (optional): full migration of vectors into pgvector.

### 10.8. What Graph to Build in Dharma-RAG

The project's documentation describes **200–500 manually curated concepts** as the core. Not an auto-extracted 31k-node graph that can be noisy, but a small, precise, expert-verified graph:

**Nodes (around 500):**
- Core terms (sati, samādhi, paññā, nibbāna, anicca, dukkha, anattā);
- Principal suttas (MN 10, DN 22, SN 56.11);
- Classical teachers (Buddhaghosa, Nāgārjuna, Śāntideva);
- Modern teachers (Ajahn Chah, Bhikkhu Bodhi, Thich Nhat Hanh);
- Schools and traditions.

**Edges (around 2000–5000):**
- `is_a`, `part_of`, `causes`, `opposed_to`, `synonym_of`, `translates_as`, `derived_from`, `elaborates`, `refines`, `prerequisite_of`, `contradicts`, `cited_in`, `taught_by`, `practiced_in`.

Most relations are either manually verified by Buddhologists or deterministically extracted from the SuttaCentral API.

### 10.9. Principle: Embedding = Variable, Graph = Constant

> **A foundational observation**
>
> **A knowledge graph** is a CONSTANT of the project. The fact *"jhāna → leads_to → nibbāna"* does not change with the next embedding model release.
>
> **An embedding** is a VARIABLE. The vector `[0.23, -0.15, 0.87, ...]` depends on the model, its version, and quantization.
>
> So **investing time in manual graph curation** (200–500 concepts) is long-term value. **Embeddings can be swapped** monthly; recomputing vectors costs pennies.

This is the central architectural observation: something must remain stable over the long term; otherwise the system cannot survive model-generation turnover.

### 10.10. When the Graph Adds Value

The graph is genuinely useful for:

1. **Multi-hop queries** — the 20% of hard questions.
2. **Cross-tradition comparisons** — "how do Theravada vs Mahayana define śūnyatā?"
3. **Building learning paths** — "where to start studying dependent origination?"
4. **Explainability** — when the LLM produced an answer, the graph helps show *why these sources*.
5. **Comparative analysis** — "which suttas are parallel to MN 10?"

For these scenarios the graph is used **after** vector search, to enrich the context before the LLM.

---

## Part XI. Reranking — the Second Filtering Stage

### 11.1. Why a Second Stage Is Needed

After hybrid search and RRF we have **20 candidates**. They are ranked by combined score. But by no means all of them are equally useful for answering the specific question:

- Some contain the right keyword but do not answer the question.
- Some are topic-relevant but shallow.
- Some are from parallel suttas with near-identical phrasing — duplicates.

What's needed is a **smarter**, but **slower** filter — a **reranker**.

### 11.2. Bi-encoder vs Cross-encoder — a Fundamental Distinction

**Bi-encoder (embedding model):**

```
Question → Vec_q (1024 numbers)
Chunk    → Vec_c (1024 numbers)
Similarity: cos(Vec_q, Vec_c)
```

Question and chunk are embedded **independently**. All Vec_c values can be precomputed and indexed. Fast (milliseconds across 100k candidates) but less precise.

**Cross-encoder (reranker):**

```
Question + Chunk → [Q: ..., C: ...] → Neural network → Score (0-1)
```

Question and chunk are fed **together** into a single neural network. The model sees their token-level interaction. Much more precise, but cannot be precomputed: each pair requires a forward pass.

Therefore a reranker is applied **only to a small number of candidates** (20–30) already selected by the bi-encoder.

### 11.3. Popular Rerankers in 2026

| Model | Parameters | License | Performance | Notes |
|--------|-----------|----------|--------------------|------------|
| **BGE-reranker-v2-m3** | 568M | MIT | High | Multilingual, 100+ languages |
| **BGE-reranker-v2-gemma2-lightweight** | ~9B | Apache 2.0 | Very high | Heavy, token compression |
| **Cohere Rerank 3** | ? (API) | Paid | High | $0.02 per 1000 reranks, benchmark leader |
| **Jina Reranker v2** | 278M | Non-commercial | High | Multilingual, fast |
| **Voyage Rerank-2** | ? (API) | Paid | Very high | MS MARCO leader |
| **Qwen3-Reranker-4B/8B** | 4B/8B | Apache 2.0 | SOTA | Based on Qwen3, instruction-aware |
| **ms-marco-MiniLM-L-12-v2** | 22M | MIT | Medium | Fast, light, aging |

### 11.4. Why BGE-reranker-v2-m3 for Dharma-RAG

**Reasons:**

1. **Same producer as the embedding (BAAI).** Stack consistency, expected compatibility with the BGE-M3 dense vector.
2. **MIT license** — compatible with the project's MIT.
3. **Multilingual** — 100+ languages including Russian, Pali (romanized), Sanskrit.
4. **Compact** — 568M, fits on a €9 server.
5. **Fast inference** — ~50 ms per (q, c) pair on CPU, ~10 ms on GPU.

**Rerank cost:** 20 pairs × 10 ms = 200 ms per query on GPU, 1 s on CPU. Acceptable for interactive UI.

### 11.5. The Effect of Reranking

Per Anthropic's Contextual Retrieval paper:

| Pipeline | Failure rate |
|----------|--------------|
| Contextual Embeddings + Contextual BM25 | 2.9% |
| **+ Reranking** | **1.9%** |

Reranking delivers an **additional −34% in residual error**. For a Buddhist corpus with high cost of hallucination, this is a meaningful win.

### 11.6. Alternatives: Cohere Rerank vs BGE-reranker

| Aspect | BGE-reranker (self-hosted) | Cohere Rerank (API) |
|--------|----------------------------|----------------------|
| Price | Free | $0.02 per 1000 reranks |
| Latency | ~10-50 ms + network | ~200 ms (API call) |
| Privacy | Data stays on server | Goes to Cohere cloud |
| Setup | Requires GPU or strong CPU | Zero setup |
| License | MIT | Closed |

For 1000 requests/day, Cohere costs $0.60/day = $18/month. Acceptable for an MVP. But for the open-source self-hosted approach, BGE-reranker is the right choice for Dharma-RAG.

### 11.7. Reranking Hyperparameters

- **top_k_after_retrieval** = 20 (how many candidates come from hybrid search)
- **top_k_after_rerank** = 5–8 (how many go to the LLM)
- **reranker_threshold** = 0.3 (if best score is below — answer "I don't know")

The threshold matters: if the reranker sees no good candidates, it is better to **refuse to answer** than to serve irrelevant information.

---

## Part XII. LLM — Generating the Answer

### 12.1. The LLM's Task in the RAG Pipeline

After hybrid search + rerank we have 5–8 top chunks. Now the LLM's job is to:

1. Read the user's question.
2. Read the passed chunks.
3. Produce a coherent, correct natural-language answer.
4. **Mandatorily add citations** — not "somewhere in a sutta," but "MN 10, paragraph 3."
5. **Refuse to answer** if the chunks are insufficient.

### 12.2. The System Prompt

A simplified structure of Dharma-RAG's system prompt:

```
You are a Buddhist scholar assistant. Your job is to answer
questions about Buddhist teachings based ONLY on the provided
passages.

RULES:
1. Use ONLY the provided context. Do not use your own knowledge.
2. Every claim must cite a specific source (e.g., [MN 10, §3]).
3. If the context does not contain enough information to answer,
   say: "The provided sources don't contain sufficient information
   to answer this question."
4. Distinguish between traditions (Theravada, Mahayana, Vajrayana)
   when they differ.
5. Use deference language: "Sources suggest...", "The Pali Canon
   speaks of...", NOT "The Buddha says..." in first person.
6. For questions about meditation side effects or dark night
   experiences, recommend consulting a qualified teacher.

CONTEXT:
{retrieved_passages}

QUESTION: {user_query}
```

### 12.3. Claude Citations API — Built-In Verification

In 2024 Anthropic released the **Citations API** — functionality that lets Claude attach each claim to a specific passage in the context **automatically, at the char-level span granularity**.

How it works:

```python
response = anthropic.messages.create(
    model="claude-sonnet-4-6",
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {"type": "text", "data": "MN 10 text..."},
                "title": "MN 10 Satipatthana Sutta",
                "citations": {"enabled": True}
            },
            {"type": "text", "text": "What are the four foundations?"}
        ]
    }]
)

# response.content will contain blocks like:
# - text: "The four foundations are body, feelings, mind, and dhammas"
# - citations: [{"document": "MN 10", "start_char": 234, "end_char": 389, "cited_text": "..."}]
```

**Advantages:**

1. **Automatic attribution** — no need to instruct the model in the prompt to "cite the source"; it is enforced at the system level.
2. **Char-level precision** — the citation points to exact start and end offsets in the document.
3. **Verification** — whether a citation actually exists in the context can be checked automatically.
4. **Lower hallucinations** — the model "realizes" that every claim needs grounding.

### 12.4. LLM Routing — Haiku / Sonnet / Opus

Anthropic offers three classes of models of different size and cost. As of April 2026:

| Model | Size | Price (input/output per 1M tokens) | Used for |
|--------|--------|-----------------------------------|----------|
| **Haiku 4.5** | Small | $1 / $5 | Fast, simple tasks |
| **Sonnet 4.6** | Medium | $3 / $15 | The main everyday mode |
| **Opus 4.7** | Large | $5 / $25 | Hard tasks, extended reasoning |

Dharma-RAG uses **routing** — sending requests to different models depending on complexity:

**Haiku** — for:
- Contextual Retrieval (generating context prefixes for chunks);
- Classifying the query intent;
- Simple Q&A;
- Paraphrasing.

**Sonnet** — for:
- The main Q&A mode;
- Cross-tradition comparisons;
- Generating answers with citations.

**Opus** — for:
- Doctrinally complex questions;
- Multi-hop reasoning;
- Controversial or sensitive topics.

### 12.5. Routing Economics

Example for Dharma-RAG at 1000 requests/day:

```
60% Haiku   × 2400 tokens input + 350 output  = $7.47/day
35% Sonnet  × 2400 input + 350 output         = $13.07/day
5% Opus     × 2400 input + 350 output         = $2.08/day
─────────────────────────────────────────────
Total: ~$22.6/day ≈ $680/month

If everything went through Sonnet: $37.4/day ≈ $1120/month
Savings: ~40%

If everything via Opus: $62.3/day ≈ $1870/month
Savings: ~64%
```

For an MVP at 100 requests/day — $70/month. Acceptable at the outset.

### 12.6. Prompt Caching — Another Saving

The Claude API has **prompt caching** — caching repeating parts of the prompt:

- **Write cost:** 1.25× (5-minute cache) or 2× (1-hour) the base input.
- **Read cost:** 0.1× the base input. **A 90% savings on cache hits.**

For Dharma-RAG this is critical: the system prompt, instructions, and part of the context repeat in every request. Caching them yields:

```
Without cache: 2400 tokens × $3/M = $0.0072 per request
With cache:    2400 tokens × $0.30/M × 90% + 0.3× × 10% = ~$0.002 per request
Savings: 72%
```

### 12.7. BYOK — Bring Your Own Key

An architectural decision for open-source: **the user pays for the LLM**, providing their own API key.

**How it works:**

```
User:
  1. Signs up for Dharma-RAG (free).
  2. Goes to claude.com/pricing or openai.com/api.
  3. Obtains their own API key.
  4. Enters it into Dharma-RAG settings.
  5. All queries go with their key → they pay.

Dharma-RAG server:
  - Proxies requests to the LLM.
  - Does not store keys (passes them through in the Authorization header).
  - Only pays for embeddings (self-hosted, i.e., 0).
  - Only pays for Contextual Retrieval at ingest (one-off $30).
```

**Advantages:**

- The project remains free in itself.
- The user controls their costs.
- The user can pick any compatible API (Claude, OpenAI, DeepSeek, local Llama via LM Studio).

**Drawbacks:**

- Requires technical literacy of the user.
- Not suited to a mass consumer market.
- Requires a key-management UI.

For a research project this is the right trade-off.

### 12.8. Open-Source Alternatives to Claude

For users wanting a fully self-hosted deploy (no cloud APIs), several open-source LLMs are available:

| Model | Parameters | License | VRAM (FP16) | Quality | Notes |
|--------|-----------|----------|-------------|----------|-------------|
| **Llama 3.3 70B** | 70B | Meta Custom | 140 GB | High | Reliable, proven |
| **Llama 4 Scout** | 109B MoE (17B active) | Meta Custom | 40 GB | Very high | MoE efficiency |
| **DeepSeek V3.2** | 671B MoE (37B active) | MIT | 140 GB | SOTA | Excellent reasoning |
| **Qwen3-235B-A22B** | 235B MoE (22B active) | Apache 2.0 | 48 GB (INT4) | Very high | MoE, reasonable RAM |
| **Mistral Large 2** | 123B | Mistral Research | 250 GB | High | EU-based |
| **Kimi K2.5** | ? MoE | MIT | Varies | High | Chinese |
| **Gemma 3 27B** | 27B | Apache 2.0 | 54 GB | Good | Google's open model |

### 12.9. KTransformers — Running Large MoEs on Modest Hardware

**KTransformers** is an open-source engine for running large MoE models through smart expert offloading.

**How it works:**

- In an MoE model, only a few experts are active at once (e.g. 8 of 256).
- Inactive experts don't need to be in VRAM — they can wait in RAM.
- When an expert is needed, it is quickly paged into VRAM from RAM.

**Result:** Qwen3-235B-A22B (235 billion parameters, 22 billion active) runs on:

- **96 GB VRAM** (2× RTX 5090 or 2× A6000 48GB);
- **256 GB RAM** (holding inactive experts);
- Throughput ~5–10 tokens/s.

This makes frontier models accessible to workstation-class hardware costing ~€15,000–20,000. That is 5–10× cheaper than server solutions for the same models.

### 12.10. Phase 2 Dharma-RAG: Local LLM

On the project's second stage, migration is envisaged:

- **Phase 1:** Claude via API (BYOK).
- **Phase 2:** local Llama 3.3 70B or Qwen3-235B via KTransformers on a 2× RTX 5090 box.
- **Phase 3:** optionally — fine-tune on Buddhist data (RAFT).

This delivers:
- Full independence from cloud APIs.
- Zero operational LLM costs.
- "Data never leaves the building" privacy level.

---

## Part XIII. Fine-Tuning — Adapting the Models

### 13.1. What Fine-Tuning Is

**Fine-tuning** is continuing to train an already pre-trained model on your specific dataset. Goal: adapt the model to a specific domain, improve it on exactly your tasks.

An analogy: a general doctor vs. a specialist. The first knows general medicine (a "pre-trained model"). The second has a deeper specialization in, say, cardiology — they know the heart in depth even if they are weaker in general medicine (a "fine-tuned model").

For Dharma-RAG, fine-tuning is potentially useful for:

1. **Embedding model** — to better capture the semantics of Buddhist terms.
2. **Reranker** — to better judge relevance in a Buddhist context.
3. **LLM** — theoretically, to answer more doctrinally precisely (but risky).

### 13.2. LoRA — Efficient Fine-Tuning

Ordinary fine-tuning requires changing **all parameters of the model** — expensive:

- For a 7B model: ~28 GB GPU for training (FP16).
- For a 70B model: ~280 GB (i.e. 4× A100).

**LoRA** (Low-Rank Adaptation, 2021) is a technique that modifies only a **small low-rank residual** on top of the original weights:

```
Original weights W (frozen) + ΔW (low-rank, trainable)

ΔW = A × B, where:
  - A has size d×r
  - B has size r×d
  - r << d (usually r = 8–64, while d = 1000+)
```

**LoRA advantages:**

- Trains 0.1–1% of parameters.
- 10× less VRAM for training.
- The result is detachable — the original model is unchanged.
- Several LoRA adapters can be held simultaneously for different tasks.

**QLoRA** (Quantized LoRA, 2023) — the same but with the base model in 4-bit. Lets you fine-tune 70B models on a single 48GB GPU.

### 13.3. RAFT — Retrieval-Augmented Fine-Tuning

**RAFT** (2024) is a technique specific to RAG systems. The idea: train the LLM **to answer only from the provided context, ignoring its internal knowledge**.

Process:

1. Build a dataset of (question, relevant context, **distractor** context, correct answer).
2. Train the model to:
   - Use relevant context for answering.
   - Ignore distractors.
   - Cite the context explicitly.
   - Refuse when context is insufficient.

Outcome: the LLM starts to behave like an *"obedient student"* — even if its own knowledge suggests a different answer, it sticks to the provided documents.

### 13.4. What Dharma-RAG Fine-Tunes (and Does Not)

**Fine-tune:**

- **Embedding model (BGE-M3)** — on Buddhist (question, relevant-chunk) pairs. Potential +10–15% on internal Buddhist queries.
- **Reranker (BGE-reranker)** — similarly.

**Do NOT fine-tune:**

- **LLM (Claude/Llama)** — left as-is. Reasons:
  1. Fine-tuning Claude is unavailable via API.
  2. Fine-tuning Llama 70B demands serious resources.
  3. **Most importantly:** the Citations API + good context + a good prompt deliver 95% of the effect without doctrinal fabrication risk.

### 13.5. Fine-Tuning Dataset for the Embedding Model

Training needs pairs (question, relevant-chunk). Where to get them?

**Sources:**

1. **SuttaCentral parallels.json** — between parallel passages there is an automatic "this is one and the same teaching fragment" link.
2. **Questions from the community** — dhammawheel.com, sutta-central discuss, reddit /r/Buddhism have thousands of questions with linked answers.
3. **Academic works** — citations in textbooks and articles with explicit source indication.
4. **Golden QA set** — 500–800 hand-checked (question, ideal answer, sources) triples (see Part XV).
5. **Synthetic via LLM** — ask Claude to generate questions for each chunk.

This produces a dataset of ~10–50k pairs. For LoRA fine-tuning this is more than enough.

### 13.6. Domain Specialization Delivers Real Gains

From 2024–2026 research:
- Fine-tuning a **generic embedding** on domain-specific data adds **+10–30%** on in-domain queries.
- Fine-tuning a **reranker** similarly.

Example: BGE on SEC filings (finance) delivers quality on par with paid Cohere embed-v4.

For the Buddhist corpus the potential is analogous — universal BGE-M3 at 61% ruMTEB could reach 70%+ on Buddhist-specific queries after fine-tuning.

---

## Part XIV. Voice Pipeline and Audio Transcription

### 14.1. Two Scales — Transcription and Voice Chat

In Dharma-RAG there are two audio topics:

1. **Batch transcription of the corpus** — turn 35,000 hours of Dharmaseed lectures into indexable text. This is a **one-off** task.
2. **Real-time voice chat** — a voice assistant for users. Spoken query → spoken answer. This is an **ongoing** task.

These demand different technologies.

### 14.2. Transcribing 35,000 Hours: Scale and Licenses

**Problem 1: Legal gray area.**

Dharmaseed lectures are CC-BY-NC-ND. This does **not permit** derivative works, and a transcript is a derivative.

**Solutions:**

- Obtain explicit permission from each teacher.
- Do not store transcripts as "lecture text" but only as a search index (vectors and keywords) from which the original cannot be reconstructed.
- Alternative: include only lectures for which the teacher has given explicit permission. Start with a smaller subcorpus.

**Problem 2: Technical scale.**

35,000 hours × 60 minutes/hour = 2.1M minutes.

On Whisper Large v3 (OpenAI):
- Cloud API: $0.006/min × 2.1M = **$12,600** + waiting time.
- Self-hosted on A100: ~1× realtime → 35,000 hours = **4 years on one GPU**.
- Self-hosted on A100 (batch): 8–16× realtime → **4–8 months**.
- Cluster 8× A100: **2–3 weeks**.

### 14.3. STT (Speech-to-Text) Options

| Model | Producer | Self-hosted | Quality | Price | Pali? |
|--------|---------------|-------------|---------|------|-------|
| **Whisper Large v3** | OpenAI | Yes (MIT) | High | $0.006/min cloud | Poor, via `initial_prompt` |
| **Whisper Large v3 Turbo** | OpenAI | Yes | A bit lower | ~3× faster | Poor |
| **Parakeet** | NVIDIA | Yes | High | Free | Poor |
| **Canary-1B** | NVIDIA | Yes | High | Free | Poor |
| **Deepgram Nova-2** | Deepgram | No | Very high | $0.004/min | Poor |
| **Azure Speech** | Microsoft | No | High | $1/hour | Poor |
| **Google Chirp** | Google | No | High | $0.024/min | Poor |
| **ElevenLabs** | ElevenLabs | No | Good | Variable | Poor |
| **Voxtral** | Mistral | Yes | ? | Free | Unknown |

**The problem:** no STT is trained on Pali. You must use the `initial_prompt` hack:

```python
whisper.transcribe(
    audio_file,
    initial_prompt="Pali terms: satipaṭṭhāna, jhāna, nibbāna, dukkha, anattā, saṅgha..."
)
```

This helps but is not perfect. The model sometimes transcribes *satipaṭṭhāna* as *satipatana* or *sati-pat-thana*.

**Post-processing:** a normalization dictionary (all variants → canonical). An extra layer.

### 14.4. Whisper and Its Quantizations

**Whisper Large v3** is the de facto standard in 2025–2026. 1.55B parameters.

Quantized versions for edge:

- **Whisper Large v3 Turbo** — a distilled version, 3× faster, slightly worse quality.
- **Whisper Medium** — 764M, a compromise, works on CPU.
- **Whisper.cpp** — a C++ implementation with INT8/INT4 quantization for phones.
- **Faster-Whisper** — a CTranslate2 implementation, 4× faster than the Python version.

For batch transcription of 35k hours Faster-Whisper Large v3 on 2–4× A100 is recommended.

### 14.5. Voice Pipeline: Not Speech-to-Speech but a Pipeline

The newest models like GPT-4o Voice and Gemini Live do **Speech-to-Speech** (S2S) — voice in, voice out, no intermediate text. Impressive, but for a RAG system it is a **dead end**:

- You cannot insert retrieval between speech-in and speech-out.
- Citations cannot be verified.
- It is opaque for observability.

**Dharma-RAG's solution — a pipeline:**

```
🎤 User voice
    ↓ [STT, on-device or cloud]
Query text
    ↓ [FastAPI]
RAG pipeline (embedding → retrieval → rerank → LLM)
    ↓
Answer text
    ↓ [TTS, on the server]
🔊 Answer voice
```

This approach is slower than S2S by a few hundred milliseconds, but:
- It permits RAG in the middle.
- All text is logged (observability).
- Citations are verifiable.
- The user sees the text and hears the voice.

### 14.6. Latency Budget

Target latency for voice chat: **<1.5 seconds** from the end of the user's speech to the start of answer playback. Budget:

| Stage | Target | Method |
|------|------|-------|
| STT (Whisper) | 100–300 ms | Streaming Whisper, partial results |
| Query embedding | 20–50 ms | BGE-M3 CPU or GPU |
| Hybrid retrieval | 20–50 ms | Qdrant HNSW |
| Rerank | 50–150 ms | BGE-reranker on 20 candidates |
| LLM first token | 300–700 ms | Streaming, cached prompts |
| TTS first chunk | 100–200 ms | Streaming TTS |
| **Total to first audio** | **~600–1450 ms** | ~target budget |

### 14.7. TTS (Text-to-Speech)

| Model | Self-hosted | Quality | Price | Pali diacritic? |
|--------|-------------|----------|------|-----------------|
| **ElevenLabs** | No | SOTA | Expensive | Poor |
| **OpenAI TTS** | No | High | $15/1M chars | Poor |
| **Azure Neural** | No | High | Medium | Poor |
| **Coqui TTS** | Yes | Medium | Free | Poor |
| **XTTS v2** | Yes | High | Free | Poor, **non-commercial license!** |
| **F5-TTS** | Yes | Very high | Free | **non-commercial license** |
| **Parler-TTS** | Yes | Good | Apache 2.0 | Needs G2P |
| **StyleTTS 2** | Yes | High | MIT | Needs G2P |

**The problem:** no TTS "out of the box" pronounces Pali diacritics correctly (*ṃ, ñ, ṭ, ḍ, ā, ī*). Letters are read as Latin characters, yielding garbled speech.

**Solution:** a **Pali G2P preprocessor** — a module that transliterates Pali words into a phonetic representation:

```
satipaṭṭhāna → SAH-tee-PAH-tah-NAH  (IPA: [sɐtɪpɐʈʈʰaːnɐ])
```

A separate task requiring a Pali phonetic dictionary and a fine-tuned TTS.

### 14.8. On-Device Voice by Default

An important architectural decision: **voice is processed locally on the user's device**, not on the server.

**Advantages:**

- **Privacy.** Voice does not go to the cloud — critical for meditative context.
- **Latency.** No network round-trip.
- **Offline operation.** Usable on a retreat without internet.
- **Cost savings for the user.** No STT/TTS cloud charges.

**Limitations:**

- Requires a sufficiently powerful device (modern iPhone/Android, Mac).
- Whisper Large v3 on mobile is ~500 MB, works but slower.
- CPU/battery usage.

For older devices a fallback to cloud STT/TTS remains, with a privacy warning to the user.

### 14.9. Push-to-Talk vs Always-On

From the project's `PRIVACY.md`:

> **Meditation is a state of mental vulnerability. Additional measures:**
> - Push-to-talk by default (not always-on);
> - Clear recording indicator (icon + audible cue);
> - A "Pause recording" button is always accessible;
> - A warning before the first voice session.

This is a conscious trade-off between UX and privacy. Always-on is more convenient but creates the risk of accidentally recording private conversations.

---

## Part XV. Quality Evaluation — Golden Set, Metrics, CI

### 15.1. Why Without Evaluation There Is No Way

In AI/ML there is an iron principle: **what is not measured, cannot be improved**. For a RAG system this is critical, because there are dozens of knobs (chunking, embedding, reranking, prompt), and changing one can improve some things and worsen others.

Without systematic evaluation you move blindly and will not notice regressions until users complain.

### 15.2. Golden QA Set — 500–800 Questions

A **golden dataset** is a hand-verified set of canonical (question, correct-answer, sources) triples. Dharma-RAG plans 500–800 such triples.

**How the golden set is assembled:**

1. **Collect questions** — from the community (sutta-central discuss, reddit, dhammawheel), from Buddhologists, from typical user queries.
2. **Expert verification** — 2–3 independent Buddhologists verify each question and expected answer.
3. **Mark sources** — which specific suttas/passages should appear in the answer.
4. **Inter-annotator agreement** — reviewers must agree — otherwise the data is unreliable.

### 15.3. Krippendorff α — a Reviewer Agreement Metric

**Krippendorff α** is a statistical measure of agreement across annotators:

- **α < 0.67** — unreliable, requires reworking.
- **0.67 ≤ α < 0.8** — acceptable, usable.
- **α ≥ 0.8** — highly reliable.

Dharma-RAG's goal: **α ≥ 0.7** on the golden set. Without this metric **you cannot trust the human annotation**.

### 15.4. Key RAG Metrics

**1. Retrieval metrics:**

- **recall@k** — fraction of relevant documents in the top-k.
- **precision@k** — fraction of documents in top-k that are actually relevant.
- **MRR** (Mean Reciprocal Rank) — average of 1/rank of the first relevant.
- **nDCG** (Normalized Discounted Cumulative Gain) — considers ordering of relevants.
- **ref_hit@k** — specific: at least one of the expected sources in top-k.

**2. Generation metrics:**

- **Faithfulness** — how well the answer is supported by sources. The primary anti-hallucination measure.
- **Answer relevance** — does the answer address the question.
- **Context precision** — fraction of the provided context actually used.
- **Answer correctness** — does the answer agree with the reference answer.

**3. Dharma-specific metrics:**

- **Doctrinal accuracy** — are traditions (Theravada/Mahayana) not confused.
- **Citation accuracy** — do citations actually exist.
- **Deference appropriateness** — is "Sources suggest..." used instead of "The Buddha says..."

### 15.5. How to Measure Faithfulness — LLM-as-Judge

**Faithfulness** is measured like this:

1. Break the answer into atomic claims (individual assertions).
2. For each claim, ask an **LLM judge**: *"Does the provided context support this claim? Yes / No / Partial."*
3. `faithfulness = (Yes + 0.5 × Partial) / Total`.

**Cross-family LLM judges:** use an LLM **from a different family** than the answer generator. If the answer was produced by Claude, faithfulness is judged by GPT-4 and Gemini. This removes the model's bias toward itself.

Dharma-RAG's goal: **faithfulness ≥ 0.85**.

### 15.6. Continuous Integration — CI Gates

A **CI gate** is an automatic check that **blocks merges to main** on regressions:

```yaml
# .github/workflows/rag-eval.yml
- name: Run RAG evaluation
  run: |
    python evaluate.py --golden-set eval/golden_800.json

- name: Check thresholds
  run: |
    python check_thresholds.py \
      --min-faithfulness 0.85 \
      --min-ref_hit-5 0.70 \
      --min-doctrinal-accuracy 4.0
    # exit 1 if any threshold failed → CI fails → PR blocked
```

Example: a developer changes the chunking strategy, thinking they improved it. CI runs 800 golden questions and sees:
- ref_hit@5 dropped from 72% to 68% → **CI blocks the merge**.

This is the main mechanism preventing regressions. Without CI gates "improvements" can silently degrade the system.

### 15.7. Current Evaluation State in Dharma-RAG

From `DHARMA_RAG_TECHNICAL_AUDIT`:

- **Baseline (fixed chunking):** ref_hit@5 = **2%** — catastrophe.
- **After structural chunking:** expected ~40%.
- **After Contextual Retrieval:** expected ~55–65%.
- **After reranking:** expected ~70–80%.
- **Phase 1 MVP target:** ref_hit@5 ≥ 70%, faithfulness ≥ 0.85.

### 15.8. The Project's Main Bet — Data Quality, Not Model

> **Observation**
>
> 500 golden QA are more valuable than any model.
>
> The project's main bet is not on compute, but on data quality and Buddhological validation. 500 golden QA with Krippendorff α ≥ 0.7 builds infrastructure on which sustainable development is possible for five years forward. Hardware and models change every year — a quality eval set outlives them all.

This is long-term wisdom. Models update, benchmarks date — but a carefully assembled golden set remains useful for decades.

---

## Part XVI. Observability — Watching the Live System

### 16.1. Why Observability Is Needed

After launching into production, questions arise:

- How many requests per day?
- What is the average latency? What are p95, p99?
- What does each request cost?
- What percentage of users rate the answer positively?
- Where are the bottlenecks — retrieval or LLM?
- How does faithfulness change after updates?

Without observability you are **blind**. The system can gradually degrade without your noticing until mass complaints arrive.

### 16.2. What Tracing Means for LLM Applications

Ordinary backend apps have logs (text) and metrics (numbers). For LLM apps a third thing is added — **traces**: a complete picture of one request with every intermediate step.

A single Dharma-RAG trace looks roughly like this:

```
Trace: req_abc123
├── [50 ms]  Query preprocessing (language detection, normalization)
├── [20 ms]  Embedding generation (BGE-M3)
├── [45 ms]  Retrieval
│   ├── [20 ms] Dense search (Qdrant)
│   ├── [15 ms] Sparse search (Qdrant)
│   ├── [30 ms] BM25 search (Postgres)
│   └── [5 ms]  RRF fusion
├── [120 ms] Reranking (BGE-reranker on 20 candidates)
├── [1200 ms] LLM generation (Claude Sonnet)
│   ├── prompt tokens: 2400
│   ├── output tokens: 380
│   ├── cached tokens: 2000 (saved $0.005)
│   └── cost: $0.0082
├── [40 ms]  Citation verification
└── [5 ms]   Response formatting

Total: 1480 ms
```

### 16.3. Langfuse — Observability Platform

**Langfuse** is an open-source platform for LLM observability. Key capabilities:

- Request tracing with a span hierarchy.
- Logging prompts, contexts, answers.
- Collecting user feedback (thumbs up/down).
- Prompt versioning and A/B testing.
- Cost, latency, quality analytics.
- OpenTelemetry integration.

### 16.4. Langfuse v3 — Infrastructure Requirements

Ironically, Langfuse v3 is itself **heavy**. Requires:

- PostgreSQL;
- ClickHouse (for time-series metrics);
- Redis;
- S3-compatible storage (MinIO);
- 2 containers (worker + web);
- **Minimum 16 GB RAM.**

Too much for a €9 Hetzner server (8 GB). So in Phase 1 a lighter alternative — **Phoenix** — is used.

### 16.5. Phoenix (Arize) — Lighter at the Start

**Phoenix** is open-source observability from Arize AI:

- Single Docker container + Postgres.
- ~2 GB RAM.
- Good trace visualizations.
- OpenTelemetry integration.
- Less feature-rich than Langfuse (no prompt versioning), but enough.

**Recommendation:** start with Phoenix, migrate to Langfuse in Phase 2 (when resources appear and prompt versioning is needed).

### 16.6. What Is Specifically Logged

For each request, kept:

1. **Input:** question, language, user (if auth).
2. **Retrieval:** which chunks found, their scores.
3. **Reranking:** which selected, their rerank scores.
4. **LLM input:** the full prompt, token count.
5. **LLM output:** the answer, citations, token count.
6. **Verification:** faithfulness score, citation check.
7. **User feedback:** 👍 / 👎, comments.
8. **Latency breakdown:** per stage.
9. **Cost:** full breakdown.

A gold mine for optimization and debugging.

### 16.7. Alerts

Automatic notifications:

- **p95 latency > 5 sec** → alert.
- **Faithfulness < 0.75** over a rolling window → alert.
- **Error rate > 5%** → alert.
- **Cost burn rate** exceeds budget → alert.
- **Retrieval failure rate** (reranker returns all scores <0.3) → alert.

### 16.8. Public Audit Log

From the project's documentation:

> Anonymized refused queries are published **monthly** as an audit log → transparency for the community.

A unique decision: once a month, publish a list of questions the system **refused** to answer (without personal data), with reasons: "highly sensitive topic," "insufficient sources," "doctrinal conflict"…

This builds trust in the system and allows the community to audit its behavior.

---

## Part XVII. Infrastructure and Budget — Where It All Lives

### 17.1. Deployment Phases

Dharma-RAG envisages three deployment phases with growing infrastructure demands:

| Phase | Server | Budget/month | Capabilities |
|------|--------|--------------|-------------|
| **Phase 0 (MVP)** | Hetzner CX22 (4 CPU, 8 GB RAM) | €9 + $20–70 LLM | Text Q&A, 56k chunks |
| **Phase 1 (Beta)** | Hetzner CX42 or Oracle Always Free | €40 + $200 LLM | + Mobile app, 200k chunks |
| **Phase 2 (Production)** | Local 2× GPU 48GB | ~€80 electricity + $0 (local LLM) | + Voice, 900k chunks, local LLM |
| **Phase 3 (Scale)** | Kubernetes cluster | €500–2000 | + Fine-tuned models, 5M+ chunks |

### 17.2. Phase 0 — €9 Hetzner

**Hetzner Cloud CX22** (April 2026):
- 4 × Intel vCPU;
- 8 GB RAM;
- 80 GB NVMe;
- 20 TB traffic;
- **€9/month.**

Docker Compose on it runs:

```yaml
services:
  qdrant:           # 1 GB RAM
  postgres:         # 512 MB
  fastapi:          # 512 MB
  bge-m3-embed:     # 2 GB (CPU inference)
  bge-reranker:     # 2 GB (CPU inference)
  phoenix:          # 1.5 GB
  nginx:            # 100 MB
  frontend-nextjs:  # 500 MB
  ─────────────────
  Total:           ~8 GB (at the edge)
```

For 56k chunks this works. For 200k+ an upgrade is required.

### 17.3. Oracle Always Free — an Alternative

Oracle Cloud offers an **Always Free tier**:
- 4 × Arm Ampere vCPU;
- 24 GB RAM;
- 200 GB storage;
- **Forever free.**

A possible alternative to the €9 Hetzner for those who accept Oracle's restrictions (traffic limits, bandwidth throttling).

### 17.4. Phase 2 — Local Server with GPU

Migrating to a local LLM requires a server with serious GPU power.

**Configuration for Qwen3-235B via KTransformers:**

| Component | Specification | Price (EU, April 2026) |
|-----------|--------------|------------------------|
| CPU | AMD EPYC 9334 (32 core Zen 4) | €2800 |
| RAM | 256 GB DDR5 ECC | €1500 |
| GPU | 2× RTX 5090 (32 GB VRAM) | €6000 |
| Storage | 4× 2 TB NVMe RAID | €1000 |
| PSU + case + cooling | — | €1500 |
| **Total** | — | **~€12,800** |

Alternative: 2× Nvidia RTX 6000 Ada (48 GB each) instead of 5090 — pricier, but more VRAM.

**Electricity:**
- Total draw: ~800 W under load, ~200 W idle.
- In the Netherlands ~€0.35/kWh (2026).
- Monthly usage: ~300 kWh ≈ **€105/month** (including idle time).

**Breakeven vs cloud Claude:**
- Cloud: $200–500/month for 1000 requests/day.
- Local: €105 + amortized €12,800 / 36 months = **~€460/month**.
- Crossover point: ~2000 requests/day, after which local is cheaper.

### 17.5. Frontier Open-Source LLMs on Local Hardware (April 2026)

What can be run on 96 GB VRAM + 256 GB RAM:

| Model | Quantization | Tokens/sec | Quality |
|--------|-------------|------------|----------|
| **Llama 3.3 70B** | INT4 | 20–30 | Good |
| **Llama 4 Scout 109B** | INT4 | 15–25 | Very good |
| **DeepSeek V3.2 (671B MoE)** | INT4 + offload | 5–10 | SOTA |
| **Qwen3-235B-A22B** | INT4 + KTransformers | 8–15 | Very good |
| **Kimi K2.5** | — | — | Unknown |
| **Mixtral 8x22B** | INT4 | 25–40 | Good |

For Dharma-RAG optimal: **Qwen3-235B** or **DeepSeek V3.2** — they lead reasoning benchmarks, handle Russian, and are MIT/Apache 2.0.

### 17.6. Phase 0 Budget in Detail

For an initial MVP (100 requests/day):

```
Infrastructure:
  Hetzner CX22:           €9/month

LLM (via BYOK or proxy):
  Claude Sonnet 4.6 (50% of requests):  $5/month
  Claude Haiku 4.5 (45% of requests):   $2/month
  Claude Opus 4.7 (5% of requests):     $2/month
  Total LLM:                            ~$9/month ≈ €8

Ingest (one-off):
  Contextual Retrieval for 56k chunks (Haiku + caching): $30

Domain name:              €10/year ≈ €1/month

Operational total: ~€18/month + one-off €30
```

Realistic for a solo enthusiast.

### 17.7. Phase 1 Budget (1000 requests/day)

```
Infrastructure:
  Hetzner CX42 (16 GB RAM): €25/month

LLM:
  Haiku/Sonnet/Opus routing: $680/month ≈ €620

CDN:
  Cloudflare free tier: €0

Observability:
  Self-hosted Langfuse: €0 (on the server)

Monitoring + backups:
  Hetzner storage 200 GB: €9/month

Total: ~€660/month
```

Still cheap for enterprise-class service.

### 17.8. Architecture Is Not Just Code

An important observation: architecture is not only code and technology. It also includes:

- **Processes.** How does the developer manage the golden set? How is feedback collected?
- **Documentation.** Without documentation a solo project will be incomprehensible even to its author in two years.
- **Contributor code of conduct.** Open-source projects live on contributions — clear rules are needed.
- **Legal framing.** Consent Ledger, licenses, GDPR.
- **Community.** Forum? Discord? Email? How to respond to users?

All of this is part of "architecture" in the broad sense.

---

## Part XVIII. Privacy, Security, Ethics

### 18.1. Privacy Principles

From the project's `PRIVACY.md`:

1. **Minimum collection.** Collect only what is strictly necessary.
2. **Local storage.** User data lives on the device, not on the server.
3. **Transparency.** Every decision is publicly explained.
4. **User control.** Ability to delete all data at any time.
5. **No tracking.** No analytics cookies, pixels, or third-party trackers.

### 18.2. What Is Actually Stored on the Server

**Stored:**

- The corpus of Buddhist texts (open source, CC0/CC-BY);
- Vector indices;
- Anonymized request logs (for observability);
- The public audit log (monthly published refused queries).

**Not stored:**

- Users' personal data (email, name) — only if they create an account themselves;
- Content of private requests (only aggregate metrics);
- IP addresses (nginx keeps them only 24 hours for anti-DDoS, then rotates them);
- Voice recordings (voice is processed on-device).

### 18.3. GDPR Compliance

The project is European (developer in the Netherlands), so GDPR is mandatory:

- **Right of access.** The user can receive all their data.
- **Right to erasure.** A "delete account" command removes all related data within 30 days.
- **Portability.** Export in JSON.
- **Consent.** Explicit consent for each processing purpose.
- **DPO.** Data Protection Officer — in a solo project, the developer themselves, with a public email.

### 18.4. Abuse Protection — Anti-Misuse Guardrails

Guardrails against misuse are built into the UI:

An **input classifier** (cheap LLM or regex) detects:

1. **Suicide/self-harm triggers** → hardcoded response with crisis lines:
   - Samaritans (UK): 116 123
   - Crisis Text Line: Text HOME to 741741 (US)
   - National helpline in Russia and others.

2. **Medical interpretation of meditation side effects** → redirect to specialists (no medical advice).

3. **Specific advice on traumatic triggers** → refuse + redirect to a live teacher.

### 18.5. Medication / Substance Queries

If a user asks about the use of psychedelics in meditation (a topic of heated debate in the community), the system:

1. Provides facts from academic sources.
2. **Does not recommend** specific substances.
3. Redirects to Cheetah House / MAPS for serious discussion.

### 18.6. Vajrayana Guardrails

In Vajrayana there are teachings that **must not** be publicly disclosed without initiation (*samaya*). For example, secret tantric practices.

Dharma-RAG marks such texts with `restricted: true` in the database and:

- Does not include them in public answers.
- May show them only to verified disciples (though this mechanism is not yet implemented).
- Explicitly states: *"This topic requires initiation from a qualified teacher."*

This is respect for tradition in action.

### 18.7. Security Basics

Standard web-application security practices:

- HTTPS only, HSTS, CSP headers.
- Rate limiting (100 req/min per IP, 1000/day per user).
- API key rotation.
- Secrets in environment variables, not in code.
- Regular dependency updates (Dependabot).
- Backups every 6 hours with off-site replication.
- Penetration testing quarterly (via OWASP ZAP).

### 18.8. No Personalization

A conscious decision: the system **does not personalize** answers based on a user profile.

- No interests, preferences, or history kept.
- Every request is stateless.
- No "recommendation engine."

This reduces risks (less data — fewer leaks) but diminishes the "personal assistant" UX. A trade-off in favor of privacy.

---

## Part XIX. Wellbeing and AI Ethics in Meditation

### 19.1. Meditation as a Vulnerable State

Meditation is not neutral activity like solving a crossword. Deep meditative practice can:

- **Evoke strong emotional experiences** — joy, fear, grief, ecstasy, terror;
- **Dissolve the familiar sense of "self"** (anattā-experience), which can be destabilizing;
- **Trigger flashbacks of traumatic experience** (trauma-sensitive meditation is its own discipline);
- **Launch dukkha ñāṇa** — the "stages of knowing suffering" described in the Visuddhimagga and researched in modern science.

Which means an AI assistant for meditation works in a **high-risk area**. Poor advice can have serious psychological consequences.

### 19.2. Dark Night of the Soul and dukkha ñāṇa

Buddhist literature (especially Theravada) describes the stages a practitioner passes through on the path to awakening. Some are extremely difficult:

- **Bhaya ñāṇa** (knowledge of fear);
- **Ādīnava ñāṇa** (knowledge of danger);
- **Nibbidā ñāṇa** (knowledge of disenchantment);
- **Muñcitukamyatā ñāṇa** (knowledge of desire for deliverance);
- **Saṅkhārupekkhā ñāṇa** (knowledge of equanimity toward formations).

For Western practitioners this is often described as the **"dark night of the soul"** — a period of existential crisis, depression, anxiety, dissociation that can last weeks, months, or years.

**Scientific research** (Britton Lab, Brown University) shows that **10–25% of serious meditators** face difficult experiences requiring professional help.

### 19.3. Cheetah House / Brown University Britton Lab

The **Cheetah House** project (founded by Willoughby Britton and Jared Lindahl) is:

- A research initiative at Brown University;
- Clinical support for people with meditation-related difficulties;
- A peer support community;
- Free resources.

**Varieties of Contemplative Experience** — their key study, documenting 59 types of difficult experiences in meditation. All publications open-access.

For Dharma-RAG this is a critical resource for redirect. If the system detects triggers of *dark night*, *dukkha ñāṇa*, *meditation crisis*, *dissociation*, *panic during meditation* in a query, it:

1. **Does not give specific practice advice.**
2. Provides information about dukkha ñāṇa as a descriptive concept (not therapeutic).
3. **Strongly recommends** Cheetah House or a qualified teacher.
4. Provides contacts:
   - Cheetah House: cheetahhouse.org
   - Brown Britton Lab: britton.lab.brown.edu
   - Specialists working on meditation-related issues.

### 19.4. Uncanny Valley Voice

The voice pipeline includes caution around the **uncanny valley** — the feeling that "something is off" about the voice.

If the system sounds **too alive and empathic** when discussing a spiritual topic, that produces:

- A false sense of interpersonal connection with AI;
- Possible user dependency on the system;
- Risk that the user receives the answer as "learning from a teacher."

An architectural decision: voice output is **deliberately neutral**, without emotional coloring. The speech is clear and informative, but not "warm." A UX trade-off: some users find it dull, but risks are minimized.

### 19.5. Deference Language — the Language of Respect

A key stylistic decision in the LLM prompt:

**Do not say:**
- *"The Buddha says that sati is the foundation of enlightenment"*
- *"You should meditate on the breath"*
- *"You must practice..."*

**Say:**
- *"Sources from the Pali Canon suggest that sati is described as a foundation of enlightenment"*
- *"The suttas describe a practice of breath meditation"*
- *"The texts propose a practice of..."*

The difference is in distance and in the user's freedom to interpret. The first phrasing places the AI in a position of authority; the second places it as an impartial intermediary between the user and the texts.

### 19.6. Disclaimer Footer

Every system answer has a persistent footer:

```
─────────────────────────────────────────────
This information is drawn from open Buddhist
texts. It is not a substitute for a living
teacher or therapist.

If you are experiencing difficulties in practice,
consider reaching out to:
  • A qualified teacher in your tradition
  • Cheetah House (cheetahhouse.org) — for
    meditation-related difficulties
  • Your therapist

[Ask a Human Teacher →] — button with contacts
─────────────────────────────────────────────
```

The "Ask a Human Teacher" button is a direct link to a list of qualified teachers with contacts (with the teachers' consent).

### 19.7. No Advice on Specific Practices

A deliberate limitation: the system **does not give instructions** on:

- Advanced techniques (vipallāsa, jhāna, sakkāyadiṭṭhi contemplation);
- Energetic practices of Vajrayana;
- Advanced khandha concentration;
- Tantric preliminaries.

For these topics the system **only describes** theory and redirects to living teachers.

Reason: such practices require individual tuning and supervision that AI cannot provide.

### 19.8. Kill-Switch for Crisis Situations

A **hardcoded bypass** is built into the LLM prompt: if obvious triggers of suicidal ideation or acute psychological crisis are detected, the system **does not search the base and does not generate a RAG answer**; instead it returns a pre-written message:

```
Your question touches on serious mental-health
topics. I am not a qualified specialist and
cannot provide the help you may need right now.

Please reach out immediately:

🇷🇺 RU:  8-800-2000-122 (free, 24/7)
🇺🇸 US:  988 (Suicide and Crisis Lifeline)
🇬🇧 UK:  116 123 (Samaritans)
🇳🇱 NL:  113 (Zelfmoordpreventie)

If you are in immediate danger — call emergency
services (112 in EU, 911 in US).

You are not alone. Help is available 24/7.
```

No sutta quotations, no AI answer. Only backup contacts and an explicit acknowledgment of the limits of its capacity.

---

## Part XX. Comparison with Competitors

### 20.1. The Overall Landscape of Buddhist Digital Resources

Dharma-RAG does not exist in a vacuum. There are several similar projects, each with its strengths and limits.

| Project | Origin | Focus | License | Approach |
|--------|--------|-------|----------|--------|
| **SuttaCentral** | Australia/Asia | Pali Canon + parallels | CC0 | Reading room, API |
| **84000** | Tibet/USA | Tibetan Canon (Kangyur, Tengyur) | CC BY-NC-ND | Translations, API |
| **DharmaSutra.org** | USA | LLM chat with Buddhist knowledge | Closed | Chatbot |
| **Dharmamitra / MITRA** | Germany/India | Scientific NLP for Buddhologists | Mixed | Research tools |
| **FoJin** | China/USA | The Chinese Tripiṭaka | — | Reading/search |
| **Lotsawa House** | USA | Tibetan short texts | CC BY-NC | Reading room |
| **Access to Insight** | USA | Theravada literature | Free (author-specific) | Reading room |
| **dhammatalks.org** | USA | Thanissaro Bhikkhu | Free | Lectures + texts |
| **Plum Village App** | Plum Village | Thich Nhat Hanh meditations | Paid | Meditation app |

### 20.2. Detailed Comparison with Key Competitors

**SuttaCentral:**

- **Strengths:** The world's best Pali Canon database, parallels, Bhikkhu Sujato's translations under CC0.
- **Limits:** Read-only, no AI interpretation. Search by exact words, no semantic search.
- **Relationship to Dharma-RAG:** SuttaCentral is a **data source**, not a competitor. Dharma-RAG relies on their API.

**84000:**

- **Strengths:** A monumental translation effort for the Tibetan Canon. Many translations are the only ones in the world.
- **Limits:** CC BY-NC-ND does not permit derivatives.
- **Relationship:** Material is included in Dharma-RAG only with special per-contributor permission.

**DharmaSutra.org:**

- **Strengths:** A working LLM chatbot "ask the Buddha."
- **Limits:** Closed-source, proprietary data, no explicit citations, hallucinations possible.
- **Relationship:** The closest functional competitor. Dharma-RAG differs: open-source, citations-first, multi-traditional.

**Dharmamitra (Hamburg Lab):**

- **Strengths:** Scientific approach, collaboration with Buddhologists. MITRA — a Pali embedding model.
- **Limits:** Oriented to scholars, not the general audience. Complex UIs.
- **Relationship:** Dharma-RAG may use their models (MITRA-E) in future versions.

**Lotsawa House:**

- **Strengths:** 2000+ short Tibetan texts, excellently curated.
- **Limits:** Reading-room only, no search.
- **Relationship:** Potential data source (if approved).

### 20.3. Dharma-RAG's Unique Positions

What makes Dharma-RAG unique in this landscape:

1. **Open-source code + open-source data** — few projects combine both;
2. **Citations-first** — every answer verifiable, unlike DharmaSutra;
3. **Multi-traditional** — Theravada + Mahayana + Vajrayana in one search;
4. **Cross-lingual** — a question in any language finds answers in original sources;
5. **Wellbeing guardrails** — none of the competitors has worked user protection out in such detail;
6. **BYOK + self-hostable** — full independence from providers.

### 20.4. What Dharma-RAG Does NOT Do Better

Honestly: there are areas where competitors are stronger.

- **SuttaCentral** is incomparably better for reading suttas in full (reading room).
- **84000** holds unique Tibetan content available nowhere else.
- **Plum Village App** is better for guided meditation (but doesn't claim this).
- **Commercial chatbots** can be faster and simpler in UX.

Dharma-RAG does not try to replace them — it fills a particular niche: **semantic search + RAG with citations across a multi-traditional Buddhist corpus**.

---

## Part XXI. Roadmap — Development Phases

### 21.1. General Timeline

The project is conceived as a long-term research initiative, not a commercial product. Phases are tied not to rigid dates but to the accomplishment of goals.

### 21.2. Phase 0 — MVP (Q2 2026)

**Goal:** a working demo prototype on a minimal budget.

**Scope:**
- Corpus: SuttaCentral (~20k chunks), Access to Insight (~3k), a small selection from 84000 with permission (~30k).
- Functions: Chat Q&A, basic reading room, citations.
- Technology: Qdrant, Postgres, FastAPI, Claude API (BYOK).
- Eval: 100 golden QA, faithfulness ≥ 0.75, ref_hit@5 ≥ 65%.
- Infrastructure: Hetzner CX22 €9/month.

**Success criteria:**
- 10 beta testers confirm answer quality.
- 50% satisfaction rate in UI feedback.
- No critical hallucinations on 100 test queries.

### 21.3. Phase 1 — Beta (Q4 2026)

**Goal:** public launch, gathering data from real users.

**New:**
- Corpus expanded to 200k chunks.
- Graph knowledge (Apache AGE) for a concept explorer.
- Mobile web app (PWA).
- User accounts (optional).
- Multi-language UI (EN, RU, possibly PL, DE).
- Golden set 500 QA, Krippendorff α ≥ 0.7.
- Langfuse observability.

**Success criteria:**
- 500 active users.
- Publication of the first monthly audit log.
- Faithfulness ≥ 0.85 on public queries.

### 21.4. Phase 2 — Production (2027)

**Goal:** sustainable operation, voice, local stack.

**New:**
- Voice pipeline (on-device STT/TTS + server RAG).
- Pali G2P for correct pronunciation.
- Dharmaseed transcription (with permissions): 5k–10k hours.
- MITRA-E or fine-tuned BGE-M3 for Buddhist studies.
- Local LLM on a 2× RTX 5090 server (optional).
- MCP/agent integration.
- Mobile native apps (iOS/Android).

**Success criteria:**
- 5000 active users.
- Voice queries with <1.5s latency.
- 3 UI languages + cross-lingual search across all.

### 21.5. Phase 3 — Scale (2028+)

**Goal:** long-term sustainability, community growth.

**New:**
- Full Dharmaseed transcription (35k hours).
- Full Tibetan from 84000.
- Chinese Tripiṭaka (BDK).
- Study Companion with progress tracking.
- Research Workbench for Buddhologists.
- Contributor network: teachers, translators, programmers.
- Possibly: a non-profit or foundation for sustainable funding.

### 21.6. What Is Not Planned

Deliberately out of scope:

- **Monetization.** Free-to-user forever.
- **Personalized meditations.** Do not become an "AI teacher."
- **Psychotherapeutic claims.** Do not say "meditation will help you with depression."
- **Social features.** Do not build "Facebook for Buddhists" — too much risk.
- **Content generation.** Do not invent new "suttas" or "teachings."

---

## Part XXII. Critical Remarks and Open Questions

No project is perfect. An honest analysis identifies several serious risks and open questions.

### 22.1. Dharmaseed — Licensing Uncertainty

35,000 hours of lectures is an enormous asset, but the CC-BY-NC-ND license does not permit derivative works. A transcript and a semantic index are likely derivatives.

**Solutions:**
- Contact each teacher individually (slow, costly, but lawful);
- Use only metadata for search (lecture title, teacher, date), without content indexing;
- Public discussion with Dharmaseed.org about a special license for educational use.

Until this is resolved, Dharmaseed is **not** included in the core corpus.

### 22.2. Claude-Centrism vs Free-to-User

There is a tension: the project is positioned as "free-to-user," but the primary LLM is Claude, which costs money via API.

**Mitigations:**
- BYOK — the user pays for their own key. The project is free; the API cost is the user's.
- Fallback on open LLMs (Llama, DeepSeek) via self-hosted or public proxies.
- In Phase 2 — a local LLM as default, Claude as an "nicer quality" option.

This is an honest tension the project lives with.

### 22.3. Pali at All Levels vs Pragmatic Scope

Ideal: full Pali support — as input language, search language, citation language, voice language.

Reality: Pali is a very marginal language in AI. STT, TTS, fine-tuned models are minimal.

**Compromise:**
- Pali diacritics are supported in search.
- Pali text in citations is preserved exactly.
- But a voice pipeline in Pali is not supported in Phase 0-1.

### 22.4. Doctrinal Imprecision

There are disagreements among traditions. Theravada says one thing, Mahayana another, Vajrayana a third. How should the system answer?

**Current solution:** show **both viewpoints** with tradition labels and sources, without imposing a "correct" answer.

**Risk:** this can frustrate users who want "a straight answer." But it is a necessary trade-off.

### 22.5. Solo Developer Burnout

The project is run by one person. This creates risks:

- **Bus factor = 1.** If the developer drops out, the project freezes.
- **Perspective limits.** One person cannot see every nuance of the many-sided Buddhist world.
- **Burnout.** The emotional load of the subject matter (especially wellbeing topics) is significant.

**Mitigations:**
- Early recruitment of collaborators (even in Phase 0).
- External reviewers for the golden QA set (Buddhologists).
- A project with clear boundaries — do not try to do everything at once.
- An explicit continuity plan in case the developer leaves (public docs, clear governance).

### 22.6. Voice Uncanny Valley

Even with "deliberately neutral" TTS the risk remains that users develop emotional dependency on the system. Especially dangerous in meditative contexts.

**Mitigations:**
- Push-to-talk (not always-on).
- Regular reminders that "this is not a substitute for a teacher."
- An optional "rotation break" — offering the user a pause after 30 minutes of use.

But this problem cannot be fully solved by technical means.

### 22.7. Scale of 35k Hours

Even if the licensing question is resolved, transcribing 35k hours is **4–6 months** on a dedicated GPU cluster or $12,600 on the cloud. A serious financial and technical investment for a solo project.

A more realistic plan: start with ~500 hours of the most important lectures and expand.

### 22.8. KG vs Vector — an Imperfect Compromise

The decision to use a knowledge graph as a **constant layer** on top of vector search works but is imperfect:

- Manual curation of 500 concepts — slow.
- As the corpus grows, the graph becomes a bottleneck (must be updated manually).
- LLM-extracted graphs would be faster but noisier.

This is not a "solved problem" — a continuously managed trade-off.

### 22.9. Langfuse v3 Is Heavy for a €9 Server

As noted: Langfuse v3 requires 16+ GB RAM. Phoenix is an acceptable alternative but less functional.

When the project outgrows the €9 server, migrating to Langfuse should be planned.

---

## Part XXIII. RAG Trends in 2026

To place Dharma-RAG in context, a review of the key RAG trends at the start of 2026.

### 23.1. Late Chunking

Developed by the Jina AI team. The idea: first run the whole document through an encoder (up to 8k–32k tokens), then split the **resulting token representations** into chunks. This preserves document-wide context in every chunk.

Effect: +5–15% retrieval on long documents.

Dharma-RAG plans to evaluate this in Phase 1.

### 23.2. Multi-Vector and ColBERT-Style Late Interaction

Instead of one vector per chunk — **N vectors per token**. At search time, maximum match between query tokens and doc tokens is computed (MaxSim).

Pros: more precise matching, especially on rare words.
Cons: 30–50× more memory.

Used as a **reranking layer**, not primary storage.

### 23.3. MoE Embeddings

Jina v4 uses Mixture-of-Experts for embeddings: the model has several "experts" (by topic), and each query selects a subset.

Pros: better quality at the price of one inference.
Cons: harder to train and deploy.

### 23.4. Multimodal Embeddings — Gemini Embedding 2

In March 2026 Google released Gemini Embedding 2, which **natively** accepts text, images, video, audio, and PDF into one 3072-dimensional vector space.

This means: you can search "an image of the Buddha in meditation pose" across a corpus of images, obtaining results vector-close to textual descriptions.

For Dharma-RAG in Phase 3 this may be interesting: index thangkas, handwritten Pali manuscripts, audio lectures in the same space as texts.

### 23.5. Agentic RAG

Instead of a pipeline "query → retrieve → generate" — an **LLM as agent** that iteratively:

1. Poses a sub-question.
2. Requests retrieval.
3. Decides whether to continue.
4. Aggregates results.

Advantage: better on multi-hop queries.
Drawback: much slower, less predictable.

For Dharma-RAG in Phase 2-3 this may be an option for complex academic queries.

### 23.6. Long-Context Retrieval

Models with 1M–10M-token contexts raise the question: **is RAG even necessary?** If you can drop the entire SuttaCentral directly into Claude Opus 4.7's context (1M) — do you need chunking?

Answer: **yes, you do.** Reasons:

- 1M tokens ≈ 3000 pages. A Buddhist corpus of 900k chunks = 100k pages. Does not fit.
- Cost: 1M tokens × $5/M = $5 **per query**. Unacceptable.
- Lost-in-the-middle: LLMs worsen at finding information in the middle of huge contexts.

RAG stays relevant even in 2026.

### 23.7. Local Frontier Models via KTransformers

The ability to run 235B–685B MoE models on **workstation-class hardware** (2× RTX 5090, 256 GB RAM) is a revolution for privacy-first AI.

This makes Dharma-RAG Phase 2 (local LLM) technically realistic.

---

## Part XXIV. Summary and Conclusion

### 24.1. What Dharma-RAG Is — In One Phrase

**An open, verifiable, multi-traditional RAG system for Buddhist teachings, built on the principle of "texts are sacred, every claim is verifiable, AI does not replace a teacher."**

### 24.2. Key Strengths

1. **Architectural clarity.** Every decision is justified with alternatives and trade-offs.
2. **Reversibility.** Qdrant named vectors, BYOK, phase-based roadmap — every choice can be undone.
3. **Doctrinal sensitivity.** Multi-traditional approach, citations-first, wellbeing guardrails.
4. **Open-source integrity.** MIT code + CC-BY-SA data + self-hostable + reproducible.
5. **Financial realism.** €9 MVP, routing economics, phased rollout.
6. **Evaluation discipline.** Golden QA, Krippendorff α, CI gates.

### 24.3. Key Risks

1. **Bus factor = 1.** Solo developer.
2. **Licensing gray zone** — Dharmaseed.
3. **Claude-centrism** — tension with "free."
4. **Dark night / wellbeing** — thin ethical ground.
5. **Corpus scale** — 35k hours of transcription is vast.
6. **Voice uncanny valley** — not fully solvable.

### 24.4. What Makes the Project Significant

Against an industry where AI products are often:
- Closed and commercial;
- Irresponsible toward religious/spiritual traditions;
- Maximizing engagement at the expense of wellbeing;
- Non-transparent in data sourcing and licensing;

Dharma-RAG is a conscious **counter-offer**. An attempt to prove that AI can:
- Be fully open;
- Respect the living tradition;
- Put user wellbeing above engagement;
- Be transparent and auditable.

The project's technical success or failure is secondary. **The approach itself** is a model for other domain-specific AI systems in sensitive areas (medicine, psychotherapy, justice, child education).

### 24.5. Practical Significance for Different Audiences

**For the Buddhist community:**
- A study tool that respects the tradition.
- Voice and search in native languages.
- A bridge between ancient texts and modern questions.

**For AI researchers:**
- An example of considered RAG architecture.
- A case study in multilingual, multi-traditional retrieval.
- A reference implementation for high-quality open-source RAG.

**For other domain projects:**
- A blueprint for "how to make responsible AI in a sensitive area."
- Examples of wellbeing guardrails, consent ledger, audit log.

**For solo developers:**
- Proof that an ambitious project is possible on €9/month.
- A phased-rollout approach with clear criteria.
- A "do one thing well" model, not "boil the ocean."

### 24.6. Closing Words

Dharma-RAG is not "just another chatbot." It is an attempt at **serious care** for what it means to build an AI system in a domain where the cost of a mistake is measured not merely in wasted time but in potential spiritual harm.

In an era where "move fast and break things" has become the tech norm, Dharma-RAG offers the opposite philosophy: **move carefully, build trust, honor tradition**.

Whether the project will be successful depends on dozens of factors, many beyond the developer's control. But **the approach itself** already has value — as a message about what AI **can** and **should** be in sensitive domains.

> *"Sabbe sattā sukhitā hontu."*
> *"May all beings be happy."*
>
> — From the CONTRIBUTING.md of the Dharma-RAG project

---

## Appendix A. Glossary of Terms

**ACID** — properties of database transactions: Atomicity, Consistency, Isolation, Durability.

**ANN** (Approximate Nearest Neighbors) — approximate nearest-neighbor search in vector space.

**anattā** (Pali) — "non-self," one of the three fundamental characteristics of existence in Buddhism.

**anicca** (Pali) — "impermanence," one of the three fundamental characteristics of existence.

**Apache AGE** — a PostgreSQL extension for graph data with Cypher syntax.

**aṭṭhakathā** (Pali) — "commentaries" on canonical texts.

**BGE-M3** — a versatile open-source embedding model from BAAI (MIT, 568M parameters).

**BM25** — a classical text-search algorithm based on word statistics.

**BYOK** (Bring Your Own Key) — a pattern in which the user provides the API key.

**chunking** — splitting long texts into fragments for indexing.

**ColBERT** — a late-interaction embedding architecture producing one vector per token.

**Consent Ledger** — a document recording licenses of all data sources.

**Contextual Retrieval** — Anthropic technique (2024) to improve RAG by adding context before embedding.

**cross-encoder** — a reranker architecture processing (query, doc) pairs jointly.

**CTE** (Common Table Expression) — a table expression in SQL.

**dense vector** — a dense vector (all components populated), an ordinary embedding.

**dhamma** (Pali) / **dharma** (Sanskrit) — the Buddha's teaching; a phenomenon; an element of experience.

**dukkha** (Pali) — "unsatisfactoriness," "suffering," one of the three characteristics of existence.

**dukkha ñāṇa** — stages of the "knowledge of suffering" described in the Visuddhimagga.

**embedding** — a vector representing the meaning of text in a multidimensional space.

**FAISS** — Facebook's library for fast nearest-neighbor search.

**fine-tuning** — further training of a pre-trained model on specific data.

**FRBR** — a library model (Work–Expression–Manifestation–Item) for describing works.

**G2P** (Grapheme-to-Phoneme) — conversion of spelling into pronunciation.

**GDPR** — the European General Data Protection Regulation.

**GraphRAG** — RAG with a knowledge graph (not only vector search).

**hallucination** — an LLM confidently inventing facts.

**HNSW** (Hierarchical Navigable Small World) — an index algorithm for vector search.

**hybrid search** — search combining several methods (dense + sparse + BM25).

**HyPE** (Hypothetical Prompt Embedding) — a technique that embeds generated questions instead of the original chunk.

**INT8, FP8, BF16** — weight quantization types (8-bit integer, 8-bit float, brain float 16).

**jhāna** (Pali) — a state of deep concentration in meditation.

**Kùzu** — an embedded graph DB, acquired by Apple in October 2025 (archived).

**KG** (Knowledge Graph) — a graph of knowledge.

**Krippendorff α** — a measure of reviewer agreement.

**KTransformers** — an engine for running large MoE models via expert offloading.

**Langfuse** — an observability platform for LLM applications.

**late chunking** — a Jina technique where chunks are created after embedding the whole document.

**LLM** (Large Language Model) — a large language model.

**LoRA** (Low-Rank Adaptation) — an efficient fine-tuning technique via low-rank residuals.

**ltree** — a PostgreSQL extension for hierarchical data.

**mettā** (Pali) — "loving-kindness."

**MCP** (Model Context Protocol) — a protocol for integrating LLMs with external tools.

**MMR** (Maximum Marginal Relevance) — a search-result diversification algorithm.

**MoE** (Mixture of Experts) — an architecture in which only part of the parameters is active.

**MRL** (Matryoshka Representation Learning) — nested embedding dimensions (truncatable without strong quality loss).

**MTEB** (Massive Text Embedding Benchmark) — the standard benchmark of embedding models.

**nibbāna** (Pali) / **nirvana** (Sanskrit) — liberation, the goal of the Buddhist path.

**observability** — the ability to observe the system's operation.

**parent-child chunking** — indexing small chunks but showing a larger context.

**pericope** — a standardized recurring formula in texts.

**pgvector** — a PostgreSQL extension for vector search.

**prompt caching** — caching prompt parts for cost savings.

**Qdrant** — an open-source vector DB in Rust (Apache 2.0).

**QLoRA** — LoRA + quantization, even more efficient.

**RAFT** (Retrieval-Augmented Fine-Tuning) — fine-tuning an LLM for better RAG behavior.

**RAG** (Retrieval-Augmented Generation) — generation augmented by search.

**recall@k** — retrieval metric: fraction of relevant documents in the top-k.

**reranker** — a second, more precise neural network that filters candidates after retrieval.

**RRF** (Reciprocal Rank Fusion) — a formula for merging rankings from different sources.

**samādhi** (Pali) — "concentration."

**sati** (Pali) — "mindfulness."

**satipaṭṭhāna** (Pali) — "foundation of mindfulness," the practice of MN 10.

**sīla** (Pali) — "ethical conduct," "ethics."

**sparse vector** — a sparse vector (most components are zero).

**SPLADE** — a neural architecture for sparse retrieval.

**STT** (Speech-to-Text) — speech recognition.

**TTS** (Text-to-Speech) — speech synthesis.

**vector database** — a database optimized for vector search.

**VRAM** — GPU video memory.

**Whisper** — OpenAI's open-source STT model.

---

## Appendix B. Key Numbers of the Project

**Corpus sizes:**
- Phase 0 MVP: ~56,000 chunks (SuttaCentral + Access to Insight + 84000 subset)
- Phase 1 Beta: ~200,000 chunks
- Phase 2 Production: ~500,000 chunks
- Phase 3 Scale: ~900,000 – 1,500,000 chunks (with Dharmaseed and full Tibetan integrated)

**Model specifications:**
- BGE-M3: 568M parameters, 1024 dim, MIT, MTEB 63.0, ruMTEB ~61
- Qwen3-Embedding-8B: 8B parameters, Apache 2.0, MTEB 70.58, ruMTEB 70.6
- GigaEmbeddings: 3B parameters, MIT, ruMTEB 69.1 (SOTA for Russian)
- BGE-reranker-v2-m3: 568M, MIT, multilingual
- Whisper Large v3: 1.55B, MIT

**Contextual Retrieval metrics (Anthropic):**
- Baseline failure rate: 5.7%
- + Contextual Embeddings: 3.7% (−35%)
- + Contextual BM25: 2.9% (−49%)
- + Reranking: 1.9% (−67%)

**Budget:**
- MVP: €9/month (Hetzner CX22)
- Ingest Contextual Retrieval for 56k chunks: ~$30 (one-off)
- LLM at 100 req/day: ~$20/month
- LLM at 1000 req/day with routing: ~$680/month
- Phase 2 local server: ~€12,800 capex, ~€105/month electricity

**Claude API pricing (April 2026):**
- Haiku 4.5: $1 / $5 per 1M input/output tokens
- Sonnet 4.6: $3 / $15
- Opus 4.7: $5 / $25 (released April 16, 2026)
- Prompt caching: up to 90% savings on repeat input

**Target quality metrics:**
- ref_hit@5: ≥ 70% (Phase 1)
- Faithfulness: ≥ 0.85
- Doctrinal accuracy: ≥ 4/5
- Krippendorff α on golden set: ≥ 0.7

**Voice latency budget:**
- Target end-to-end: < 1.5 seconds
- STT: 100–300 ms
- RAG pipeline: 200–400 ms
- LLM first token: 300–700 ms
- TTS first chunk: 100–200 ms

**Hardware requirements:**
- MVP server: 4 vCPU, 8 GB RAM
- Phase 2 local GPU: 2× RTX 5090 (64 GB total VRAM) + 256 GB RAM + 32-core EPYC

---

## Appendix C. Recommended Reading

### Foundational RAG Works

1. **Lewis et al. (2020)** — "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" — the original paper that named RAG.
2. **Anthropic (September 2024)** — "Introducing Contextual Retrieval" — the key technique used in Dharma-RAG.
3. **Microsoft (April 2024)** — "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" — GraphRAG.

### Embeddings

1. **Chen et al. (2024)** — "BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings" — the BGE-M3 paper.
2. **Qwen Team (2025)** — Qwen3-Embedding Technical Report.
3. **Snegirev et al. (2024)** — "The Russian-focused embedders' exploration: ruMTEB benchmark."
4. **Sber AI (2025)** — "GigaEmbeddings: Efficient Russian Language Embedding Model" (arXiv 2510.22369).

### Fine-Tuning

1. **Hu et al. (2021)** — "LoRA: Low-Rank Adaptation of Large Language Models."
2. **Zhang et al. (2024)** — "RAFT: Adapting Language Model to Domain Specific RAG."

### Buddhist Wellbeing

1. **Lindahl, Britton et al.** — "The Varieties of Contemplative Experience" — Cheetah House research.
2. **Britton Lab publications** — britton.lab.brown.edu
3. **Kornfield, J.** — *"A Path with Heart"* — a classic on the sensitive side of practice.

### Open-Source Projects

- SuttaCentral: github.com/suttacentral/sc-data
- 84000: github.com/84000-translation
- Qdrant: github.com/qdrant/qdrant
- BGE: github.com/FlagOpen/FlagEmbedding
- Langfuse: github.com/langfuse/langfuse
- Apache AGE: github.com/apache/age

### Licenses

- CC0 (Creative Commons Zero): creativecommons.org/publicdomain/zero/1.0
- CC BY-SA 4.0: creativecommons.org/licenses/by-sa/4.0
- MIT License: opensource.org/licenses/MIT
- Apache 2.0: apache.org/licenses/LICENSE-2.0

### Dharma-RAG Repository

- **GitHub:** github.com/toneruseman/Dharma-RAG
- **Docs:** (phase-dependent)

---

**End of document.**

*This document does not replace primary sources. For an in-depth study of any topic, consult the original papers, repositories, and Buddhist texts.*

*The document is distributed under CC-BY-SA 4.0. You are free to use, redistribute, and adapt it with attribution and under the same terms.*
