# Dharma-RAG: A Project Walkthrough for the Technically Literate Non-Specialist

*A deep dive for people who aren't in AI/ML*

Why this exists, how it works under the hood, and why these specific choices were made

An analytical report based on the project's internal documents

April 2026

## Table of Contents

- [Chapter 1. What is this actually about](#chapter-1-what-is-this-actually-about)
  - [Dharma-RAG in plain language](#dharma-rag-in-plain-language)
  - [Why this is not a simple task](#why-this-is-not-a-simple-task)
  - [Who this is for](#who-this-is-for)
  - [The core principle that shapes everything](#the-core-principle-that-shapes-everything)
- [Chapter 2. How the system works — the big picture](#chapter-2-how-the-system-works-the-big-picture)
- [Chapter 3. The corpus: where the texts come from](#chapter-3-the-corpus-where-the-texts-come-from)
- [Chapter 4. The brain of search: embeddings](#chapter-4-the-brain-of-search-embeddings)
  - [What is an embedding model and why is it the heart of the system](#what-is-an-embedding-model-and-why-is-it-the-heart-of-the-system)
  - [Fork 1: closed paid model or open free one](#fork-1-closed-paid-model-or-open-free-one)
  - [Fork 2: large model or small one](#fork-2-large-model-or-small-one)
  - [Fork 3: BGE-M3 — why this is a unique choice](#fork-3-bge-m3-why-this-is-a-unique-choice)
  - [The "quantization zoo" problem](#the-quantization-zoo-problem)
  - [The solution: "named vectors" in Qdrant](#the-solution-named-vectors-in-qdrant)
- [Chapter 5. Qdrant: where "semantic coordinates" live](#chapter-5-qdrant-where-semantic-coordinates-live)
  - [What is a vector database](#what-is-a-vector-database)
- [Chapter 6. Knowledge graph: where vectors lose](#chapter-6-knowledge-graph-where-vectors-lose)
  - [What is a knowledge graph](#what-is-a-knowledge-graph)
- [Chapter 7. Chunking: how to slice texts correctly](#chapter-7-chunking-how-to-slice-texts-correctly)
- [Chapter 8. The language model: how AI composes the answer](#chapter-8-the-language-model-how-ai-composes-the-answer)
- [Chapter 9. Reranking: the second filtering stage](#chapter-9-reranking-the-second-filtering-stage)
- [Chapter 10. Evaluating quality: metrics, golden set, CI](#chapter-10-evaluating-quality-metrics-golden-set-ci)
- [Chapter 11. UX: how it feels to the user](#chapter-11-ux-how-it-feels-to-the-user)
- [Chapter 12. Fine-tuning: adapting models to Buddhist data](#chapter-12-fine-tuning-adapting-models-to-buddhist-data)
- [Chapter 13. Observability: watching the live system](#chapter-13-observability-watching-the-live-system)
- [Chapter 14. Where it all lives: infrastructure and budget](#chapter-14-where-it-all-lives-infrastructure-and-budget)
- [Chapter 15. The first 14 days: detailed launch plan](#chapter-15-the-first-14-days-detailed-launch-plan)
- [Chapter 16. What makes Dharma-RAG special](#chapter-16-what-makes-dharma-rag-special)

---

## Chapter 1. What is this actually about

### Dharma-RAG in plain language

Imagine you have a vast library of Buddhist books: ancient Pali suttas, Tibetan texts, Chinese translations, modern lectures by Western meditation teachers, scholarly articles on altered states of consciousness. In English and Russian. Hundreds of thousands of pages. And you want to ask this library a simple question — for example, "What did the Buddha say about the first jhāna?" — and receive, not a list of 50 books to read, but a specific, meaningful answer backed by exact quotations indicating precisely where each claim comes from.

That's Dharma-RAG. The project builds an assistant that reads an enormous Buddhist corpus and answers users' questions with honest references to primary sources — so that every claim can be verified.

> **What the name means**
>
> Dharma — the Buddha's teaching, the spiritual tradition whose texts we're collecting.
>
> RAG (Retrieval-Augmented Generation) — "generation augmented by retrieval from a database." A technical term for the approach: the system first searches for relevant chunks of text in the library, then a language model (AI) composes an answer from them.
>
> So Dharma-RAG is "a Buddhist AI assistant with citations to primary sources."

### Why this is not a simple task

At first glance the task looks easy: take ChatGPT, feed it the books, ask questions. In practice that doesn't work, and here's why:

- **Language models lie.** ChatGPT and similar models are notorious for "hallucinating" — inventing facts that don't exist. For everyday questions this is annoying. For Buddhist texts it's catastrophic: if the AI puts words in the Buddha's mouth that he never said, or confuses Theravāda doctrine with Mahāyāna, it causes real harm to practicing humans.

- **The corpus is huge and heterogeneous.** 56,000 text fragments in the starting version, close to a million planned. It's several languages (Pali, Sanskrit, Tibetan, Chinese, English, Russian), different traditions (Theravāda, Mahāyāna, Vajrayāna, Zen), different eras (from oral tradition of the 5th century BCE to lectures from the 2020s).

- **Citation accuracy is critical.** In academic and religious contexts, citing a source is not a formality — it's the foundation of trust. An answer like "it's somewhere in the Saṃyutta Nikāya" is useless. You need: "SN 22.59, paragraph 3, translation by Bhikkhu Bodhi."

- **Two languages at once.** A question asked in Russian must find answers in English and Pali sources — and vice versa. This is called "cross-lingual retrieval" and requires special techniques.

- **Specialized terminology.** Words like śūnyatā, paṭicca-samuppāda, satipaṭṭhāna don't translate automatically. They live in their own coordinates of meaning, and ordinary search engines stumble on them.

### Who this is for

Per the design documents, the project has five very different types of users:

- **Reading Room — the reader/practitioner.** Wants to read a sutta with parallel translation, see explanations of unfamiliar terms on hover, bookmark passages.

- **Research Workbench — scholar/translator.** Looks for parallel passages across canons (Pali, Chinese, Tibetan), compares editions, exports citations in academic formats (BibTeX/RIS).

- **Dharma Q&A — the curious layperson.** Asks questions in a chat, gets answers with citations, can expand any citation to see the source.

- **Study Companion — the learner.** Flashcards for terms and mantras, study plans, progress tracking, personal notes. Works offline for retreats.

- **API / MCP — developers.** Can plug Dharma-RAG into their own applications or other AI tools.

*The documentation explicitly warns: trying to build all five surfaces at once is a dead end. Better to do one or two excellently than five mediocrely.*

### The core principle that shapes everything

> **Three rules that run through the entire project**
>
> 1. The texts are sacred. The system is built around primary sources, not around a chatbot. Reading and navigating texts comes first; the AI answer is an optional layer, not the main product.
>
> 2. Every claim is verifiable. Without a citation to a concrete place in a concrete text, no answer is released to the user. Ever.
>
> 3. AI does not replace a teacher. The interface and the system's behavior bake in respect for the living tradition: "check with your teacher," "this is not a substitute for practice," "if you're in crisis, see a professional."

## Chapter 2. How the system works — the big picture

### Three floors of the system

It helps to imagine Dharma-RAG as a building with three floors. Each has its own job; together they deliver one answer.

**Ground floor — the corpus and its preprocessing.** Here Buddhist texts live in their "raw" form: sutta files from SuttaCentral, PDFs from 84000 (Tibetan canon in English), lecture transcripts, academic articles. Before the system can search over them, each text goes through a preparation pipeline: cleaning, splitting into small pieces (chunks), attaching metadata (what tradition, what school, what language, who the translator is, what the license is), creating stable identifiers for each passage so you can cite it. This is a one-time but labor-intensive operation.

**Middle floor — the search engine.** This is the most technically sophisticated part. Each text chunk is converted into a set of numbers — a "semantic coordinate" (1024 numbers for every chunk). These coordinates are stored in a special database, Qdrant. When the user asks a question, it too is converted into semantic coordinates, and the database finds 20–30 chunks whose coordinates are nearest to the question. Then those 20–30 are rescored by a second model (the "reranker"), and the top 5–10 most relevant remain.

**Top floor — the answer generator.** The top 5–10 chunks are passed to a large language model (Claude, or an open model like Qwen3 or Llama) along with the user's question. The model reads the chunks and composes a coherent answer, weaving in references to sources. Output: a structured answer with clickable citations, a confidence indicator, and a warning if the question touches sensitive topics.

### The flow of a single query

When the user types "What is the role of right speech in the Noble Eightfold Path?":

1. The question goes to the system. It is analyzed: what language, what type (factoid, multi-hop comparison, lineage question), is clarification needed.

2. The question is converted into a vector ("semantic coordinates").

3. Qdrant finds the top 20 closest text chunks — some from Pali translations, some from commentaries, some from Western teachers' lectures.

4. A reranker re-evaluates these 20 chunks by a more sophisticated criterion and keeps the 5 best ones.

5. These 5 chunks plus the original question are passed to Claude or a local LLM.

6. The LLM composes the answer, embedding citations in a standardized format.

7. The response is streamed to the user in real time, sentence by sentence, with clickable source markers.

### Why this path

A reasonable question: why go through all these steps? Why not just ask ChatGPT to answer directly?

The answer is trust. ChatGPT cannot *prove* that its claim comes from a real source. It generates text that sounds plausible, but there's no reliable way to check whether it's true. In Buddhist content, where a single garbled doctrinal point can mislead someone for years, this is unacceptable.

The RAG architecture changes the rules: the AI only gets to work with specific text fragments that actually exist and have verifiable sources. Its job is reduced to summarizing and synthesizing, not remembering. This dramatically reduces hallucinations: according to Anthropic's research, just adding "contextual retrieval" (described later) cuts retrieval errors by 49%, and combining with reranking yields a 67% improvement.

## Chapter 3. The corpus: where the texts come from

### The scale of the corpus

At start: **56,684 chunks**. That's roughly the Pali Canon plus major modern translations. Target: **close to a million chunks** — after adding Tibetan canon, Chinese Mahāyāna, Dharmaseed lecture transcriptions (~46,000 hours of audio), academic articles.

For context: an average novel is ~400–500 chunks. Dharma-RAG starts at ~100 novels worth and grows toward ~2,000 novels.

### Where the texts come from

The project research identified five foundational open-source pillars on which the corpus rests:

**SuttaCentral — the main source of the Pali Canon.**

- License: CC0 (full public domain) — the most permissive possible.
- Content: the complete Pali Tipiṭaka (all three "baskets" of the canon) in Latinized Pali plus parallel English translations by Bhikkhu Sujato.
- Format: Bilara-data — a git-versioned JSON where each sutta is split into numbered segments (for example, `mn10:1.1` — Majjhima Nikāya sutta 10, section 1, segment 1). These are stable identifiers that don't break across version updates.
- For the Dharma-RAG team this is a dream source: free, clean, machine-readable, with built-in stable citation IDs.

**84000 — Tibetan canon in English translation.**

- License: CC BY-NC-ND 3.0 (free for non-commercial use with attribution, no modifications).
- Content: over 400 texts of the Kangyur have been translated as of late 2025 (about 46% of the canon; target — two-thirds in the next few years). Available as HTML, PDF, EPUB.
- Unique feature: every text has a stable ID like `toh291` (Tohoku catalog number), making citations reproducible.
- Subtlety: the "NoDerivatives" clause formally prohibits modifications. Slicing text into chunks might legally count as "modification," but the community consensus is that non-commercial research use like RAG is acceptable.

**Access to Insight + dhammatalks.org — Theravāda translations.**

- License: "free distribution" with attribution.
- Content: about 1,000 suttas translated by Thanissaro Bhikkhu, Bhikkhu Bodhi, Nyanaponika, and others, plus thousands of Thanissaro's Dhamma talks and essays.

**BDK America — Chinese Mahāyāna in English.**

- License: CC BY-NC-SA 3.0.
- Content: ~30 free PDF volumes of the BDK English Tripiṭaka, including the Lotus Sutra, the Platform Sutra, Dōgen's Shōbōgenzō, Shinran's works.

**Lotsawa House — Tibetan commentarial texts.**

- License: CC BY-NC 4.0.
- Content: over 2,000 short texts — prayers, sādhanas, commentarial verses from all four Tibetan schools.

### Three tiers of legal cleanliness (licensing tiers)

For a project that must remain legal forever and not create problems for users, the research proposes a three-tier scheme:

**Tier 1 — fully open (CC0, CC BY, public domain).** SuttaCentral, Access to Insight, dhammatalks.org, Leigh Brasington's jhāna materials, Daniel Ingram's MCTB2. These texts can be chunked, indexed, and served verbatim with attribution.

**Tier 2 — open, non-commercial (CC BY-NC, CC BY-NC-ND, CC BY-NC-SA).** 84000, Lotsawa House, BDK, AudioDharma, Hermes Amāra (Rob Burbea's jhāna transcripts). Safe for non-commercial RAG with attribution.

**Tier 3 — copyrighted, fair-use retrieval only.** Books from Wisdom Publications (Bhikkhu Bodhi's famous Nikāya translations, Anālayo's scholarly books), Shambhala (Brasington's "Right Concentration," Tanahashi's Dōgen), Sounds True. These texts can only be stored as metadata and short excerpts; full text is never served — the user is directed to purchase the original.

> **Why this is important**
>
> The temptation is to pour everything in and hope no one notices. This is the path to lawsuits and reputational destruction of the project. The licensing-tier scheme makes "no one gets hurt" a default: every text chunk stores its license flag, the system automatically decides how much text can be shown.
>
> This is also a moral stance: the project respects the work of translators and publishers. Bhikkhu Bodhi spent decades translating the Nikāyas — forcing his translations into the pool of "free resources" without permission would be disrespectful.

### The Russian corpus: more modest, but workable

The research acknowledges that the Russian side is thinner than the English. Yet it exists:

- **theravada.ru** — complete Russian translations of the four main Nikāyas (Dīgha, Majjhima, Saṃyutta, Aṅguttara) plus a sizable portion of the Khuddaka by SV (Sergey Tyulin). This is the only complete modern Russian Nikāya translation and is indispensable.

- **dhamma.ru** — Russian translations of many Ajahn Chah, Thanissaro, Nyanaponika texts.

- **probud.narod.ru** — classic Russian translations of Mahāyāna sutras.

- **dharma.org.ru** — Tibetan and Vajrayāna material.

- **Berzin Archives Russian section** — from Alexander Berzin.

The pragmatic conclusion: the system should use **cross-lingual retrieval** as the default — the user asks in Russian, the system searches both Russian and English corpora, and either shows English passages with clear language labels or uses on-the-fly translation for secondary paraphrase.

### Restricted texts (Vajrayāna)

Some Vajrayāna texts — specific tantric practices, guru-lineage instructions — are traditionally transmitted only through direct teacher-to-student relationships. Publishing them to a broad public audience creates problems for the practice tradition.

The project's solution is a simple `restricted: true` flag in a text's metadata. If the flag is true:

- such texts are never sent to external APIs (Claude, OpenAI) so they never leak to a third-party cloud;
- they don't appear in the common public retrieval pool, but can be used only in a local (self-hosted) instance of the system;
- users see an explicit warning: "this is a restricted text; consult a qualified teacher."

This is an example of how a technical solution (a simple boolean flag in the database) enforces respect for the tradition.

## Chapter 4. The brain of search: embeddings

### What is an embedding model and why is it the heart of the system

We mentioned that each text chunk is converted into "semantic coordinates" — a set of ~1000 numbers. The neural network that does this conversion is called an **embedding model**. The whole system's quality depends on it: does the system understand that "release from suffering" and "nibbāna" are about the same thing, while "emptiness" in Buddhism and "empty fridge" are completely different?

An embedding model is, more or less, a geometric map of meanings. Close points on this map are texts with related meanings. Distant points are unrelated texts. When the user asks a question, that question is placed onto the same map, and the system finds the nearest neighbors.

There's a real arms race in these models during 2025–2026. The project's research compares more than 15 variants. For the non-specialist, three key forks matter most.

### Fork 1: closed paid model or open free one

**Closed models** are OpenAI's text-embedding-3, Voyage-3, Cohere Embed v4, Gemini Embedding. Their quality is good and consistent, but each call costs money (pennies, but over millions of queries it becomes serious), and you depend on the vendor's server, their pricing, their uptime.

**Open models** are BGE-M3, Qwen3-Embedding, FRIDA (Russian), Snowflake Arctic, Jina. You download them once and run them on your own machine. No per-call fees, no dependence on someone else's cloud. But you need your own server with a GPU or a powerful CPU.

> **The project's choice: a hybrid strategy**
>
> Phase 1 (quick start): closed Voyage-3-large as the primary option (best quality/price ratio), Cohere Embed v4 for very long suttas (supports 128K-token context).
>
> Phase 2 (local): BGE-M3 as the main retriever, plus Qwen3-Embedding-4B for "second opinion," plus Russian FRIDA as a Russian-language booster.
>
> The logic: pay for quality while infrastructure is being built. When it's ready, migrate to in-house models and become fully independent.

### Fork 2: large model or small one

The obvious answer seems: larger is better. The research uncovered an interesting counter-intuitive fact. Qwen3-Embedding in the 0.6B version (600M parameters) weighs only 639 MB in compressed form and beats most 7-billion-parameter models on the standard MTEB benchmark. That means in 2025–2026, small specialized models have become competitive with gigantic ones.

The gap between small and large is about 6 points on the standard quality scale. For many tasks this gap is critical; for many it isn't. At scale (millions of documents), the small model works 13× faster than the large one. That's the difference between "indexing in an hour" and "indexing over a day."

### Fork 3: BGE-M3 — why this is a unique choice

The most interesting technical decision of the project is choosing BGE-M3 as the main model. It's almost the only model in the world that produces three different text representations in a single forward pass:

- **Dense vector** — the 1024 coordinate numbers. Good at catching general meaning and context.

- **Sparse vector** — something between "semantic coordinates" and "old-school keyword search." Good at catching rare and specific terms like Pali words.

- **ColBERT (multivector)** — a separate vector for each token of text. Used at the final stage for especially fine-grained relevance scoring.

It's like having three search engines in one box. Plus an MIT license (free for any use, including commercial), 100+ languages, long-context support (8,192 tokens is about 6,000 words at a time).

### The "quantization zoo" problem

Here the project runs into a non-obvious subtlety. The same embedding model exists in different "precisions":

| **Variant** | **Size** | **Quality** | **Use case** |
|---|---|---|---|
| FP32 | 2.4 GB | 100% | Reference, maximum precision |
| FP16/BF16 | 1.2 GB | 99.9% | Half precision, nearly indistinguishable |
| INT8 | 0.6 GB | ~99% | 8-bit, small quality loss |
| Q4_K_M (GGUF) | 0.4 GB | ~94% | Strong memory savings |
| Q2_K (GGUF) | 0.25 GB | ~80% | For very weak hardware |

The problem: once you choose one variant and run 900,000 chunks of text through it, you're locked to that variant forever. You can't index in Q4 and query in Q8 — they're different coordinate systems, as if one cartographer drew in meters and another in feet.

Every model or precision change = re-indexing the entire database. For 900,000 chunks that's several hours of server work and non-trivial money.

### The solution: "named vectors" in Qdrant

The research noticed that Qdrant (the database where vectors are stored) can hold several different vectors for the same record. This is called **named vectors**. Technically that means one record contains:

- **dense_v1** — the current primary vector (e.g. BGE-M3);
- **dense_v2** — a slot for a future model whenever the team wants to try something new;
- **sparse** — a sparse vector for word-level retrieval;
- **colbert** — a multivector for final reranking.

This solves the "one Qdrant = one model" problem: you can calmly add a second vector from a different model to the database, run an A/B test (which is better?), and only then flip primary retrieval. All without downtime, on a live database.

> **Practical value**
>
> Without named vectors, changing the embedding model is a multi-hour "migration" with service outage. With named vectors it's a smooth gradual migration: both models run in parallel first, the team compares results, confirms the new one is genuinely better, and only then turns the old one off. This is how Notion and other large companies manage their search evolution.

## Chapter 5. Qdrant: where "semantic coordinates" live

### What is a vector database

An ordinary database (Postgres, MySQL) stores tables: ID, name, date, price. Finding a record by exact value is simple: "everyone named Ivan." Finding similar numbers is simple too: "everyone with price between 100 and 200."

But what if you need to find "all text fragments whose meaning is close to this question"? A conventional DB has no idea how. You'd have to pull all records into memory, compute the distance from each, and sort. On 900,000 records that's unacceptable — tens of seconds per query.

**A vector database is a specialized database** that solves exactly this problem. Its main trick is an index called **HNSW (Hierarchical Navigable Small World)**. Roughly, it's a network of shortcuts between points: instead of checking all 900,000 neighbors, the system jumps from landmark to landmark and finds the answer in 2–5 milliseconds.

For Dharma-RAG, this speed matters because under the hood a single user question might fire 3–5 similarity searches (main question + reformulations + multi-query expansion) and the user expects an answer in a second, not a minute.

### Why Qdrant and not alternatives

The research compares 12 vector databases. Here's a simplified version of the comparison for a 56,000–500,000 chunk corpus:

| DB | Native hybrid search | Native BGE-M3 sparse | Operational overhead | License | Fit for Dharma-RAG |
|---|---|---|---|---|---|
| **Qdrant** | ✅ Universal Query API | ✅ IDF modifier | Low (single Rust binary) | Apache 2.0 | **Best fit** |
| Weaviate | ✅ BM25 + vector | ⚠ weaker | Medium | BSD-3 | Schema-heavy, overkill |
| Milvus | ✅ | ✅ | High (etcd, Pulsar, MinIO) | Apache 2.0 | Overkill at this scale |
| pgvector | Manual via SQL | ❌ | Low (if Postgres already present) | PostgreSQL | Viable alternative |
| Chroma | ⚠ | ❌ | Zero | Apache 2.0 | Prototypes only |
| LanceDB | ✅ | ✅ | Zero (embedded) | Apache 2.0 | Single-instance only |

Key reasons for choosing Qdrant:

1. **Native support for BGE-M3's three representations in a single collection.** Other databases require either two separate collections or extra glue code.

2. **Apache 2.0 license** — a clean fit for an MIT project.

3. **Operational simplicity.** Milvus requires a zoo of companion services (etcd, Pulsar, MinIO); Qdrant is a single binary with no external dependencies.

4. **Honest performance.** On 50M vectors pgvector + pgvectorscale delivers 471 QPS vs. Qdrant's 41 QPS on the same Cohere dataset. But at 1M–10M — the realistic Dharma-RAG scale — the two are equal (~5 ms per query on HNSW).

### The memory problem and its solution — in-database quantization

Each text chunk is 1024 numbers × 4 bytes = 4 KB. Multiplied by 900,000 chunks: ~3.5 GB just for vectors. Plus the HNSW index: another 1.5× — that's ~5 GB of RAM per collection. On a budget VPS (8 GB RAM), this doesn't fit.

Qdrant offers three memory-saving compression methods:

**Scalar quantization (INT8)** — each number represented with 8 bits instead of 32. 4× savings, 1–1.5% quality loss. Recommended default.

**Binary quantization (1-bit)** — each number becomes one bit (plus or minus). 32× savings, 5–18% quality loss. Makes sense only for vectors of 1024 dimensions or more with an oversampling trick and rescoring — then final quality drops by only 2–3%.

**Float8** — a new 2025 development. 4× compression, same as INT8, but less than 0.3% quality loss (vs ~1.5% for INT8). Essentially "free" compression.

For Dharma-RAG the recommendation is: in Phase 1 use INT8 scalar quantization (standard), in Phase 2 consider binary quantization with 1.5-bit precision plus ColBERT reranking to recover accuracy. The combination yields ~24× compression with near-zero quality loss.

## Chapter 6. Knowledge graph: where vectors lose

### What is a knowledge graph

A **knowledge graph** is a way to store connections between concepts explicitly, as a network. Imagine a large diagram with nodes (concepts: Buddha, Nāgārjuna, śūnyatā, Diamond Sutra) and edges between them (wrote, taught, criticized, is a translation of).

Vector search answers the question "what is similar to this in meaning?". A knowledge graph answers questions of the type:

- "Who were the students of Tsongkhapa who wrote about śūnyatā?"
- "What are all the commentaries on the Diamond Sutra written before the 10th century?"
- "What is the teacher-lineage from the Buddha to Thanissaro Bhikkhu?"

These are called **multi-hop queries** — traversing multiple links. A vector system can't solve them natively, because "Tsongkhapa's students" is not a semantic relation but a factual one.

### When the graph wins

The research is honest about when a graph genuinely outperforms vectors. The most vivid comparison: on an AIMultiple benchmark (3,904 documents), on aggregation queries Graph RAG scored 73.5% accuracy vs. Vector RAG's 18.5%. On cross-document reasoning — 4× better (33% vs 8%). On queries involving 5+ entities, vector RAG accuracy degrades toward 0%, while a graph stays stable even at 10+ entities.

Typical graph-favoring queries for a Buddhist context:

- Teacher-student lineages (Mahākassapa → Ānanda → Sāṇavāsī...).
- Cross-canonical parallels (DN22 ↔ MA98 ↔ Toh291 — the same sutta in Pali, Chinese, and Tibetan canons).
- Concept networks (paṭicca-samuppāda has 12 links, each linked to specific suttas).
- Historical causal chains (which school gave rise to which, who criticized whom).

### When the graph loses

And here the project has a nuanced position. On **factoid queries** ("what did the Buddha say about anatta in SN?") pure vector RAG is faster, cheaper, and often more accurate. The GraphRAG-Bench benchmark showed GraphRAG losing 13.4% to plain RAG on Natural Questions and 16.6% on time-sensitive queries.

The root cause: building a graph from text via an LLM is expensive and noisy. Microsoft GraphRAG indexing costs $3,000–15,000 for 900,000 chunks using GPT-4o, even the cheaper variant with GPT-4o-mini — around $5,000. Each update requires partial re-indexing.

### Evolution of graph approaches: from expensive to cheap

The field evolved quickly in 2024–2025:

| Approach | Indexing cost | Quality | Fit for Dharma-RAG |
|---|---|---|---|
| Microsoft GraphRAG | Very high | Good on global queries | Too expensive |
| LightRAG (HKU, 2025) | 1/100 of GraphRAG | 70–90% of GraphRAG's quality | ✅ Main candidate |
| LazyGraphRAG (MS, 2025) | 0.1% of GraphRAG | Matches on exploratory | ✅ Alternative |
| HippoRAG 2 (ICML 2025) | Low-medium | SOTA on multi-hop | ✅ Production option |
| Rule-based + Apache AGE | Near zero | Very good on structured domain | ✅ Recommended |

### The project's key insight

> **The graph is a constant of the project. The embedding model is a variable.**
>
> Embedding vectors depend on model version, on quantization, on random initialization. Change the model — you throw everything away and re-embed from scratch.
>
> Graph knowledge ("DN22 is parallel to MA98", "Mahākassapa is the teacher of Ānanda", "paṭicca-samuppāda has 12 links") is permanent. It doesn't depend on any model. Once you curate this data — it's yours forever.
>
> Therefore: invest time in the graph. But do it gradually.

### The solution for Dharma-RAG: optional layer, not core

The research proposes a three-phase approach:

**Phase 1 (months 1–3).** No explicit graph. All "graph-like" queries handled by plain SQL tables in PostgreSQL — `parallels` (cross-canonical parallels), `concepts` (terms in multiple languages), `chunk_concepts` (which chunk mentions which concept), `lineages` (teacher-student chains via the `ltree` extension for hierarchies).

SQL queries on these tables cover ~80% of "graph questions" at speeds of 1–5 ms per hop. No LLM noise, deterministic.

**Phase 2 (months 3–6).** If ≥3-hop queries become a noticeable share of traffic, add **LightRAG** or **HippoRAG 2** as a projection over the same SQL tables. LLM extracts some additional connections from free-text commentaries (where rules don't work).

**Phase 3 (months 6+).** If needed, add full **Apache AGE** — an extension for PostgreSQL that turns regular tables into a full graph queryable with Cypher language. This allows complex queries without losing ACID transactions.

### Apache AGE: the graph inside Postgres

Why exactly Apache AGE and not Neo4j (the industry standard)?

1. **Stays within Postgres.** You don't spin up a second database, there's no eventual consistency between vectors and graph — everything in one transaction.

2. **Apache 2.0 license.** Neo4j Community Edition is under AGPL v3 plus Commons Clause — it's dangerous for a commercial or widely-distributed project. Neo4j sued PureThink in 2024 over license violations and won $597K in fines. This is a real, not hypothetical, risk.

3. **Microsoft's architectural approval.** In April 2026 Microsoft documented the Apache AGE + pgvector + pg_diskann combo as a reference architecture for GraphRAG in Azure PostgreSQL.

4. **Cypher support on ~90%** of the Neo4j dialect.

### Why Kuzu is "dead"

An important piece of context: the research highlights that in October 2025 Apple acquired Kùzu Inc., archived the main repo, and left the project without an official future. Three community forks (RyuGraph, LadybugDB, Vela) exist, but they're all in alpha. For Dharma-RAG the practical consequence is: if earlier iterations used Kuzu, it has to be migrated to Apache AGE or Neo4j.

> **Lesson from this story**
>
> Choosing infrastructure based on "what's trending" is dangerous. Kuzu looked like a brilliant choice in 2024 — embedded, fast, Cypher-compatible. A year later the company was bought, the project frozen. Apache AGE looks more boring (an extension to a 30-year-old Postgres), but it's backed by the strongest possible technological guarantee: the Postgres ecosystem doesn't die.

## Chapter 7. Chunking: how to slice texts correctly

### Why you can't just cut text into fixed-size pieces

A naïve approach: take a 100,000-word sutta, chop it into 512-token pieces. Problem solved. On Western text this gives acceptable results. On Buddhist text it's a disaster, and here's why:

**Problem 1: stock formulas (pericopes).** In the Pali Canon, every sutta begins with the same formula: "Evaṃ me sutaṃ. Ekaṃ samayaṃ Bhagavā..." ("Thus have I heard. On one occasion the Blessed One..."). Hundreds of identical opening fragments. Without deduplication, the vector retriever ranks random suttas at the top purely because they share this formula.

**Problem 2: verses (gāthā).** Much of the canon is poetry with specific metric patterns. Cutting a gāthā in half destroys its meaning. The chunker must respect verse boundaries.

**Problem 3: anaphoric density.** A large portion of suttas is dialogue, where the speaker is introduced at the start and referred to as "he" for the next few paragraphs. A fixed-size chunker tears replies from their speakers.

**Problem 4: nested structure.** A sutta has sections, paragraphs, individual teachings. A cut in the middle of a teaching produces a stub that lacks context.

### A three-level strategy

The research recommends three complementary layers of chunking:

**Level 1: structural chunking.** Splitting by natural boundaries: sutta → section → paragraph → verse. Each chunk gets metadata: `{sutta_uid, nikaya, speaker, audience, pericope_id}`. Where possible, use SuttaCentral's ready-made JSON format which already contains this markup.

**Level 2: contextual retrieval (Anthropic).** For each small chunk, a cheap LLM (Claude Haiku 4.5) generates a 50–100-token prefix describing where this chunk came from. Example:

```
Original chunk:
"Then, monks, a monk takes the fourth jhāna..."

After contextual retrieval:
"[This passage is from MN 10 Satipaṭṭhāna Sutta, where the Buddha
instructs monks on the four foundations of mindfulness, specifically
in the section on mindfulness of mental states]

Then, monks, a monk takes the fourth jhāna..."
```

Anthropic's published numbers: −35% retrieval errors with contextual embeddings, −49% when contextual BM25 is added, −67% with a reranker. The one-time cost for 56,000 Dharma-RAG chunks ≈ $30 on Claude Haiku with prompt caching. Cheap for such a big gain.

**Level 3: hierarchical (parent-child) retrieval.** Index small children (~384 tokens) for precise matching, but when passing context to the LLM hand it the larger "parent" (full sutta or a semantic section of 1024–2048 tokens). Large quality boost at near-zero cost.

### Stable identifiers as the foundation

A critical architectural decision: every chunk receives a **stable ID** that doesn't change when the corpus is re-processed. Examples:

- `mn10:12.3` — Majjhima Nikāya, sutta 10, section 12, segment 3 (SuttaCentral format).
- `toh4094:f.362.b` — Tohoku catalog number 4094, folio 362 verso.
- `dn22:kayanupassana:breath_meditation:step_3` — a hierarchical path.

> **Why stable IDs are important**
>
> Without them the system is fragile. If you re-chunk the corpus (change chunking parameters), all citations break: "MN 10, passage 42" refers to a different place now. All bookmarks, all user quotes, all links in generated answers — go invalid.
>
> With stable IDs the chunking parameters can change freely. The ID sticks to a semantic unit ("section 12.3 of Satipaṭṭhāna Sutta"), not to a byte offset in a file.

## Chapter 8. The language model: how AI composes the answer

### What an LLM is and what options exist

A **large language model (LLM)** is what actually forms the final answer. It receives the question plus 5–10 text fragments found by the retrieval step and writes coherent text that cites the sources.

The market in 2026 splits into two camps:

**Closed commercial LLMs** — Claude (Anthropic), GPT (OpenAI), Gemini (Google). Highest quality, but paid per call, cloud only.

**Open models** — Qwen3, Llama 3.3, DeepSeek V3.2, Kimi K2.5. You download them once, run them locally. Quality approaches the closed models in 2025–2026.

### Comparison of options

| Model | Input $/1M | Output $/1M | Context | License | Strengths |
|---|---|---|---|---|---|
| Claude Opus 4.6 | $5 | $25 | 1M | closed | Best citations, Citations API |
| Claude Sonnet 4.6 | $3 | $15 | 1M | closed | Best default for generation |
| Claude Haiku 4.5 | $1 | $5 | 200K | closed | Cheap, good with prompt caching |
| GPT-5 | $2.50 | $20 | 1M+ | closed | Strong reasoning |
| Qwen3-235B-A22B | $0 (self-host) | $0 | 128K | Apache 2.0 | Best open for local deploy |
| Qwen 2.5 72B | $0 (self-host) | $0 | 128K | Apache 2.0 | Dense, simpler to serve |
| Llama 3.3 70B | $0.35/M (DeepInfra) | same | 128K | Llama license | Cheap via API |
| DeepSeek V3.2 | $0.55 | $2.19 | 128K | MIT | MoE, near-top quality |

### The project's strategy

Two phases, two approaches:

**Phase 1 (cloud): Claude Sonnet 4.5 as primary, Claude Haiku 4.5 for cheap operations.**

Why Claude:

1. **Native Citations API** — a unique feature of Anthropic. The model returns citations as structured data: which piece of input text was used for which sentence of the answer, with character-level precision. Critical for Dharma-RAG, where citation accuracy is the foundation of trust.

2. **Prompt caching** — if a long prompt is reused (and in RAG it almost always is — the system prompt and tool descriptions repeat), 90% cost savings on the cached part. For contextual retrieval indexing with Haiku this is a lifesaver.

3. **Large context (1M tokens for Sonnet 4.6 / Opus).** A very long sutta or a whole chapter of commentary fits without forced chunking.

4. **Low hallucination rate** in 2026 — by various tests, one of the best values on RAG benchmarks.

**Phase 2 (local): Qwen3-235B-A22B as primary, Qwen 2.5 72B as backup.**

Why local:

1. **Zero per-call cost.** After $15–40K in hardware, inference is electricity alone.

2. **No data leakage.** Vajrayāna restricted texts never leave the local server.

3. **Independence.** No vendor lockout risk, no price hikes.

4. **Quality.** Qwen3-235B at Q4 quantization via KTransformers delivers ~85–90% of Claude Sonnet 4.6 quality on most RAG tasks.

### Routing queries between models

Not every query needs the most expensive model. Three approaches to routing:

1. **Cheap-first classifier.** A small model (Haiku or a free classifier) categorizes the query — factoid, synthesis, interpretive — then decides which model to use. Low cost, but adds 100–200 ms latency.

2. **Confidence-based escalation.** Haiku answers first. If its self-evaluation says confidence < 0.7, or "groundedness check" shows less than 70% of the answer is grounded in retrieved chunks, re-run with Sonnet. Saves ~50% of cost vs "always Sonnet" with < 2% quality loss.

3. **Type-based routing.** Direct rules: "citations → Haiku, comparisons → Sonnet, meditation philosophy → Opus."

The project recommendation: approach #2 (confidence escalation) + groundedness check via cosine similarity between the generated answer and retrieved chunks.

### Local inference: 2×48 GB VRAM + 256 GB RAM

The target local configuration described in the documents: a workstation with two GPUs of 48 GB VRAM each (e.g., two RTX 4090 48GB or an RTX A6000 Ada) and 256 GB of system RAM.

What fits into this:

- **Qwen 2.5 72B / Qwen3-72B** — fits entirely in VRAM via tensor parallelism (TP=2, i.e. the model is split across both GPUs). Primary dense model for Phase 2.

- **Qwen3-235B-A22B MoE** — through a special engine (KTransformers), only 22B active parameters live on the GPU, while the rest (the "experts") sit in 256 GB of RAM. Works with acceptable latency for interactive applications.

- **DeepSeek V3.2 (685B / 37B MoE)** — at Q4 quantization via KTransformers it fits, though the 256 GB of RAM is tight; partial SSD offload may be required.

- **Embedding + reranker stack:** BGE-M3 (2.3 GB) + Qwen3-Reranker-4B (~9 GB) + FRIDA (~2 GB) = ~15 GB, can live on GPU 0 permanently, while GPU 1 is fully dedicated to the LLM.

### KTransformers: the magic box for gigantic models

The project's key technological trick is **KTransformers** (from Tsinghua). It's a special inference engine for **Mixture-of-Experts (MoE)** models.

An MoE model is a smart neural network where, for each specific token, only a small subset of its "experts" (sub-networks) are activated. E.g., in Qwen3-235B: total 235B parameters, but only 22B active per token. In DeepSeek V3.2: 685B / 37B active.

The standard inference approach requires all 235 or 685 billion parameters to be on the GPU — hundreds of gigabytes of VRAM. KTransformers moves experts into RAM and only pulls the active ones onto the GPU as needed. Result:

- DeepSeek V3 at Q4: ~14 GB VRAM + ~382 GB RAM (compared to ~340 GB VRAM in naïve approach).
- 3–28× faster than llama.cpp on MoE.

This makes Phase 2 realistic: a single workstation can run models on par with frontier cloud APIs.

## Chapter 9. Reranking: the second filtering stage

### What reranking is

The embedding model finds the "top 20–30 most similar" chunks. But "similar" isn't the same as "actually answers the question." Sometimes a passage with a high similarity score is in fact off-topic — just shares words with the question.

A **reranker** is the second filtering stage. It's a separate model that takes each question–chunk candidate pair and gives a more accurate relevance score (on a 0–1 scale). After reranking, only the top 5–10 best candidates remain, which are sent to the LLM.

### Why this is needed even when the first stage is good

Technically, the first stage uses a **bi-encoder** — the question and each chunk are embedded *independently*, then compared. Fast (tens of ms) but less accurate — the model doesn't "see" them together.

The reranker uses a **cross-encoder** — the question and the chunk are jointly fed to the model, which looks at both simultaneously and gives a paired relevance score. Slower (tens to hundreds of ms *per pair*) but 5–10% more accurate on average.

An analogy: the embedding is like a quick visual scan of book titles on a shelf. Reranking is like pulling the 20 most promising books off the shelf and flipping through the first pages of each.

### The project's two-tier approach

**Phase 1: BGE-reranker-v2-m3.**

- Size: 568 M parameters.
- License: MIT.
- Multilingual (100+ languages).
- Latency: 50–80 ms on GPU, 300–600 ms on CPU per pair.
- Quality: solid baseline on BEIR benchmark.

**Phase 2: Qwen3-Reranker-4B.**

- Size: 4B parameters.
- License: Apache 2.0.
- Top open reranker on MTEB-R (69.76).
- Quality: +2–3 points above BGE-v2-m3 in most tests.
- Cost: needs more VRAM, slower.

### Why not Cohere Rerank (closed, paid)?

It's the best-quality option on Russian language (+3–5 points over BGE baseline on multilingual BEIR). But:

1. Cost: ~$0.001 per rerank. For 1000 queries/day × 30 pairs = $30/month — not critical, but over a year compounds.

2. Vendor dependency — not in the project's spirit.

3. BGE-v2-m3 is "good enough" for the MVP; Qwen3-Reranker-4B is already competitive in Phase 2.

## Chapter 10. Evaluating quality: metrics, golden set, CI

### Why you can't just ask "does it work or not"

The system has many moving parts: embedding model, chunking, reranker, LLM, prompt. Each change can improve some queries and degrade others. Without a formal measurement process every change is guessing.

The documentation even specifically flags this: "A golden eval set must appear on Day 5 of development, not at the end. Without it, all optimization of chunking/rerankers/prompts is blind guesswork."

### The golden dataset: 500–800 question–answer pairs

A **golden dataset** is a reference set of "correct" pairs: a user question + the correct answer + the exact references to passages supporting the answer. Constructed once, used thereafter as the measuring instrument of the system.

For Dharma-RAG the recommended size is **500–800 pairs**. That sounds small, but it's statistically justified: with 500 pairs you can reliably detect improvements of ~4 percentage points (the Minimum Detectable Effect in a paired bootstrap). Less — too noisy. More — diminishing returns.

Distribution across query types:

- Citation/factoid — 15% ("Where in SN does the Buddha speak about anatta?")
- Definition — 15% ("What is śūnyatā?")
- Cross-canonical comparison — 15% ("How are MN 10 and MA 98 related?")
- Multi-hop — 12% ("Who were Nāgārjuna's students who wrote about Yogācāra?")
- Comparative — 10% (e.g. "Svātantrika vs Prāsaṅgika on śūnyatā")
- Meditation practice — 10% ("Instructions for samatha")
- Doctrinal-interpretive — 13% ("What is paṭicca-samuppāda?")
- Adversarial — 10% ("Did the Buddha talk about iPhones?")

### Statistical justification of size

Why exactly 500 pairs? The research gives a detailed calculation. For paired Recall@5 testing at baseline 0.65, two-sided significance α=0.05, power 0.80:

- n=500 → MDE ≈ 3.8 p.p. — matches the CI Warning threshold of 5 p.p.
- n=800 → MDE ≈ 3 p.p. for subgroup analysis across 8 query types.

That is, 500–800 is not arbitrary; it precisely matches the regression thresholds of the CI/CD pipeline.

### Three-tier metrics

**Layer 1: Retrieval quality** — did the system find the right chunks?

- Recall@10 ≥ 0.85
- NDCG@10 ≥ 0.70
- MRR@10 ≥ 0.75

**Layer 2: Generation quality** — was the answer well written?

- Faithfulness ≥ 0.90 (Does the answer match the retrieved texts?)
- Answer Relevancy ≥ 0.85 (Does it actually answer the question?)
- Context Precision/Recall (RAGAS)

**Layer 3: Citation quality** — is the attribution correct?

- Citation Recall ≥ 0.90 (Did all the used passages end up in citations?)
- Citation Precision ≥ 0.85 (Do all cited passages actually exist?)
- Citation F1 ≥ 0.87 (ALCE benchmark)

### Cross-family LLM judge

A critical detail: **a Claude-generated answer is evaluated by Gemini 2.5 Pro or GPT-5, never Claude by Claude**. Reason: **self-enhancement bias** — a model rates its own outputs higher. Cross-family evaluation eliminates this bias.

Another technique — **Jury of LLMs (PoLL)**: three cheaper judges (Haiku + Gemini Flash + GPT-4.1-mini), majority vote — statistically better than a single expensive Opus judge on cost/quality.

### Human evaluation: Buddhologists in the loop

For the top layer of quality — **doctrinal correctness** — automation isn't enough. A machine can verify that Bhikkhu Bodhi's quote is quoted accurately, but it cannot judge whether the interpretation of paṭicca-samuppāda is orthodox.

The research proposes:

1 PhD-level Buddhologist (core reviewer, 50% of items, €40–55/hour) + 2 experienced practitioners (5+ years of study, €18–25/hour).

Total annotation volume for v1.0: ~1,200 annotations at 2 annotators with 20% double-annotation, ~120 person-hours, €3,600 — fits into the $4,625/year budget with optimization.

**Inter-Annotator Agreement (IAA) targets:** Krippendorff α ≥ 0.7 is called "reliable," ≥ 0.8 "highly reliable." If α is below 0.7, that's a signal that the rubric is poorly defined or annotators are underqualified — you don't publish the golden set.

### CI gates: automated quality checkpoints

Every change to the code passes through two stages of automatic evaluation:

**Quick eval** (on every PR, <5 min): 30 random queries, cheap retrieval metrics + one faithfulness sanity check on Claude Haiku.

**Full eval** (on merge to main, <1 hour): all 500 queries, all metrics, cross-family LLM judge, latency, cost. 20 parallel workers.

**PR-blocking rules:**

- Ref_hit@5 and Recall@5 — a drop of > 5 p.p. blocks the PR, > 2 p.p. requires review.
- Faithfulness — > 3 p.p. blocks, > 1 p.p. requires review.
- Doctrinal correctness — ANY regression blocks.
- Latency p95 > 3 s absolute or > 20% relative.
- Cost/query > 25% above absolute.

**Significance test:** paired BCa bootstrap + Wilcoxon. A PR is blocked only if CI does not cross 0 AND |Δ| > threshold — protection against noise.

## Chapter 11. UX: how it feels to the user

### Five surfaces of the application

The documents explicitly note that trying to make every user happy with a single screen is a dead end. The project identifies **five distinct product surfaces**:

1. **Reading Room** — for practitioners. Parallel text display (original ↔ translation), hover-glossary, footnotes, bookmarks, reading progress.

2. **Research Workbench** — for scholars. A parallel-passages graph (like BuddhaNexus), a table of matches, an alignment viewer, BibTeX/RIS export.

3. **Dharma Q&A** (chat) — for curious laypeople. Chat with inline citations à la Perplexity, pull-quotes, "explain in simpler terms."

4. **Study Companion** — for students. SRS flashcards (terms, mantras), study plans, progress, annotations. Offline (retreats), PWA, Yjs/Automerge sync.

5. **API / MCP server** — for developers/integrations. REST + MCP endpoint for other AI tools.

### The main principle: search-first, not chat-first

The research flags a classic mistake of Buddhist RAG projects: putting chat at the center. ChatGPT has taught users that "conversation is primary."

For a Buddhist domain that doesn't work, and here's why:

- Practitioners want to read the suttas themselves, not the AI's paraphrase.
- Scholars need direct access to the texts for quoting.
- The AI can err on subtle doctrinal points; the user should have an easy path "into" the primary source.

The **Dharmamitra-style pattern** (an actual Buddhist AI project, Goa University): search is primary, AI is an optional helper. The user first gets a list of passages from the canon; under each passage there's an "Explain this passage" button that triggers an AI summary on demand. Not the reverse.

### Key UX patterns

The project research systematizes patterns worth imitating from Perplexity, NotebookLM, Elicit, 84000, SuttaCentral:

**Numbered inline [n]** — a classic Perplexity style. Minimal visual noise, maximum usefulness.

**Hover-card with chunk preview** — when the cursor stops on `[3]`, a popover shows the quoted fragment + sutta + chapter + translator. The user sees context without leaving the page.

**Click → jump-to-source** — clicking a citation opens the full sutta in a side pane with the chunk highlighted.

**Pull-quote beside the answer** — an exact quote from the source next to the paraphrase. A religious-text anti-hallucination shield: the user can directly compare "what the AI said" vs "what the text actually says."

**Source transparency list** — Glean's pattern. At the bottom of the answer, "Used N sources, did not use M." The user sees why the system rejected certain passages.

**Query reformulation chips** — "refine by canon," "exclude commentaries," "include Tibetan parallels." Quick refinement without retyping.

**Bilingual sync-scroll (84000 style)** — original (Pali/Tibetan) on the left, translation on the right. Scrolling is synchronized by segment ID, not by pixel position (otherwise different-length texts desync).

### The frontend stack

For the web interface the project's recommendation is:

- **Next.js 15 App Router** — React framework with SSR and static-first delivery. Essential because SEO matters (SuttaCentral users will find Dharma-RAG through Google).
- **assistant-ui** — a library of AI-chat primitives in the Radix style.
- **shadcn AI blocks** — pre-built components: `AIInlineCitation`, `AISources`, `AIReasoning`, `AIBranch`.
- **Vercel AI SDK v6** — handles SSE streaming with typed events.
- **next-intl** — internationalization with full support for the Russian locale.
- **Floating UI** — pop-ups and hover cards for terminology.
- **@tanstack/react-virtual** — virtual scroll for long documents.
- **Tailwind CSS + shadcn/ui** — standard styling toolkit.

For Tibetan and Devanagari scripts additional work is needed: Noto Serif Tibetan / Noto Serif Devanagari fonts via @font-face with unicode-range subsetting (full Noto Sans CJK is ~20 MB, too heavy). Tibetan script has known rendering bugs in Safari; live testing on macOS + iOS is needed.

### Voice mode

A separate track is voice interaction (for meditation, retreats, when you can't type). The project recommends:

**Pipecat (BSD-2)** — framework for orchestrating a voice pipeline: STT → RAG → LLM → TTS (cascading architecture). Each component is replaceable.

**Why not OpenAI Realtime or Gemini Live?** These are speech-to-speech models that bypass the retrieval step. But skipping retrieval means no citations. Unacceptable.

**STT (Speech to Text): Whisper large-v3-turbo** + an initial_prompt glossary of Pali terms (jhāna, anattā, samādhi, paṭicca-samuppāda). Whisper saw a lot of Buddhist texts in pretraining and handles Romanized Pali well.

**TTS (Text to Speech) is a hard problem.** No out-of-the-box TTS pronounces paṭiccasamuppāda correctly. The solution: a rule-based G2P (grapheme-to-phoneme) preprocessor for Pali + Piper (MIT) or ElevenLabs with an uploaded pronunciation dictionary.

## Chapter 12. Fine-tuning: adapting models to Buddhist data

### Why fine-tuning is needed

Generic models (BGE-M3, Claude, Qwen3) were trained on web text. They know that "compassion" is a positive emotion, but they don't know that in Theravāda context "karuṇā" is one of the four brahmavihāras with a specific set of meditation techniques.

**Fine-tuning** is additional training of an already-trained model on domain data. The result: the model "gets the domain" — learns terminology, learns connections, learns to answer in the expected style.

### The project's priority hierarchy

A strong decision of the documentation: fine-tuning matters in a strict order.

**Tier 1 (mandatory): embedding model fine-tuning.** BGE-M3 is dominant here — learns domain hard negatives (cases where the default model confuses "Theravāda anattā" with "Hindu ātman"). Expected gain: +5–15 percentage points on Hit@5. Cost: ~€0.50 of electricity for a single LoRA run.

**Tier 2 (highly desirable): reranker fine-tuning.** Qwen3-Reranker-4B or BGE-reranker-v2-m3, fine-tuning on 3K–10K pairs of synthetic Buddhist QA. Expected gain: +3–8 percentage points on MRR. Cost: €1 of electricity.

**Tier 3 (optional): LLM fine-tuning.** Qwen2.5-72B via QLoRA. Expected gain: +0–3 percentage points on faithfulness. Cost: €5–10 of electricity, plus a lot of setup time. Rarely justifies itself.

**Tier 0 (forbidden): pretraining from scratch.** Training a 7B model on 2T tokens would cost $15–30K in compute and deliver marginal gain over a simple LoRA SFT. Never do it.

### Fine-tuning methods

**LoRA (Low-Rank Adaptation)** — a technique that adds small trainable "adapters" to the model's frozen weights. Training is 1000× faster than full fine-tuning, memory is 10× lower. Standard parameters: r=8–16 for style, r=32 for domain, r=64 for reasoning.

**QLoRA** — LoRA + 4-bit NF4 quantization of the base model. Allows fine-tuning Qwen2.5-72B on 2×48 GB GPUs (otherwise it needs >200 GB of VRAM).

**DoRA** — LoRA variant decomposing the weight update into magnitude + direction. +1 p.p. over LoRA at the cost of ~20% slower training.

**RAFT (Berkeley, 2024)** — a training method specifically for RAG. Each training example is a 4-tuple: (question, oracle document, 3 distractors, CoT answer with verbatim citation). The model learns to distinguish a real source from a plausible fake. Paper: +35% on HotpotQA, +76% on HuggingFace docs QA. The key detail: the optimal fraction of examples with oracle is P=80%. 100% oracle destroys robustness to poor retrieval.

### Fine-tuning is the last step, not the first

> **A strong anti-rule**
>
> The 2025–2026 AI community has a fad of "agentic fine-tuning everywhere." Many teams start a project with LLM fine-tuning, thinking this is the core of the work.
>
> The research explicitly pushes against this. For RAG systems, retrieval quality dominates. Fine-tuning the embedding/reranker yields 10× more effect per €1 of electricity than fine-tuning the LLM.
>
> The correct sequence: first build the baseline on off-the-shelf models → assemble the golden set → measure the weakest component → fine-tune exactly that component.

## Chapter 13. Observability: watching the live system

### What observability is

Once the system goes into production, a new class of questions arises: how often do users get satisfactory answers, when does latency spike, which query types fail most, how is model quality drifting over time. **Observability** is the tooling layer that answers these questions in real time.

### Langfuse and Phoenix — two options

**Langfuse v3** — a mature platform for LLM observability. Apache 2.0 license, self-hostable, prompt versioning, a playground, pre-built evaluators. But heavy to run: requires Postgres + ClickHouse + Redis + S3 + 2 containers. Minimum 16 GB RAM for production.

**Phoenix (Arize)** — a simpler alternative. Single Docker container + Postgres, minimum 2 GB RAM, integrated RAG evaluations out of the box (hallucination, groundedness, context relevance). ELv2 license, slightly more restrictive than Apache 2.0.

The project recommendation: start with Phoenix (days 1–5 MVP) due to simplicity, migrate to Langfuse if prompt versioning becomes critical.

### What gets logged

On every query the system records:

- `trace_id`, `session_id`, `query_text`, `detected_query_type`.
- top-k passages with scores, retriever_version, latency.
- The full prompt and response, token counts, citations.
- LLM judge scores (faithfulness, citation accuracy).
- User feedback (thumbs up/down).
- Cost per call, cache hits, safety flags.

Weekly drift-detection: is the popularity of queried passages changing (KL-divergence > 0.2), is answer length changing (>2σ), is the percentage of uncited answers rising.

Alerts: error_rate > 1% per hour → PagerDuty; latency_p95 > 3 s over 15 min; faithfulness drop > 3 p.p. over 24h rolling; cost/query +30% week-over-week.

### Preventing personal-data leaks

For a project that promises "zero user data collection," this is critical. Specific patterns:

- **Server-side PII masking** — a callback that replaces emails, phones, and other personally identifiable information with `<EMAIL>`, `<PHONE>` before logging.
- **Session-only mode** — queries stored in Redis with TTL=session_end; no persistent user-query DB.
- **No-persistence flag** — a header `X-No-Log: 1` skips all tracing.
- **Ephemeral session IDs** — random per browser tab, no cookies, not linkable to a user.
- **Presidio** (from Microsoft) for additional NER-based PII detection.
- **Full self-hosting** — Langfuse, Qdrant, vLLM locally; no third-party telemetry.

## Chapter 14. Where it all lives: infrastructure and budget

### What the server needs

Minimum Phase 1 configuration:

- CPU: 4–8 cores (Hetzner CCX33 or similar).
- RAM: 32 GB (for embeddings + reranker + Qdrant).
- Disk: 200 GB SSD.
- Network: standard.

Phase 2 local configuration:

- Workstation with 2×48 GB VRAM (RTX 4090 48GB modded or RTX A6000 Ada).
- 256 GB DDR5 ECC RAM.
- 2 TB NVMe SSD (ideally PCIe 5.0).
- Server PSU 1500W+.
- AMD EPYC Milan / Threadripper / Intel Xeon.

### Hosting choices

The project research compares several options:

| Platform | GPU | Long-running | For Dharma-RAG |
|---|---|---|---|
| Vercel | ❌ | 800 s max | ⭐ Frontend only |
| Railway | ❌ | ✅ | ⭐ Backend + DBs |
| Fly.io | Limited | ✅ | Alternative to Railway |
| Hetzner | ✅ | ✅ | ⭐ Self-host, cheap |
| Modal | ✅ serverless GPU | ✅ | ⭐ Embedding reindex, FT |
| OCI Always Free | ❌ | ✅ | ⭐ MVP/staging |
| Kubernetes | ✅ | ✅ | Overkill below 10k MAU |

**Recommended setup:** Vercel (web UI) + Hetzner CX32→CCX33 (backend + Qdrant + Postgres) + Modal (batch reindex GPU). LLM via API in Phase 1. In Phase 2 — full local workstation.

Interesting option: **OCI Always Free** gives 4 Ampere ARM cores + 24 GB RAM + 200 GB disk free forever. Enough for Phase 1 MVP at 1–2 RPS. For a free open-source project this is real value.

### Budget for 12 months

The project's explicit budget ceiling is **$4,625 for 12 months**. Distribution:

- **LLM API** (Claude for generation, Gemini for judge, PPI) — $1,500.
- **Annotation** (2 annotators + 20% double-annotation, 500 QA) — €3,600 ≈ $3,900, optimized to $2,200.
- **Hosting** (Hetzner CX32→CCX33, Langfuse Hobby, Argilla self-host) — $1,200.
- **Tools and hardware buffer** — $225.

> **The main insight on the budget**
>
> The main investment is not compute but **data quality and Buddhological validation**. 500 golden QA pairs with Krippendorff α ≥ 0.7 and a full doctrinal rubric are worth more than any specific model or vector DB.
>
> Compute is commodity (GPUs drop in price every year, models get cheaper every month). An evaluated expert golden set — is an infrastructural asset on which the project develops for the next 5 years.

### Why local deploy is possible on "not that powerful" hardware

Two years ago, 2×48 GB VRAM was "barely enough for a 70B model." In 2026, thanks to:

1. **KTransformers and expert offloading** — makes 235B MoE real;
2. **BQ 1.5-bit and float8** — reduces memory by 4–24×;
3. **vLLM / SGLang / TensorRT-LLM** — boosts throughput to commercial-serving levels;
4. **Matryoshka embedding** — allows variable embedding precision;

— the same workstation delivers ~85–90% of cloud-frontier quality at $0 per query. For a Dharma-RAG with an assumed load of 10–100 queries/day, a local Phase 2 gives 10× cost efficiency.

## Chapter 15. The first 14 days: detailed launch plan

### Philosophy of the 14-day sprint

The project docs contain an explicit **day-by-day plan for the first 14 days** (April 14–27, 2026). The core idea:

> **Don't try to build everything at once.**
>
> A classic failure mode: the team spends 3 months "preparing the infrastructure" and then discovers that retrieval quality is unacceptable. Changes cost too much.
>
> The right approach: MVP of the full pipeline in 2 weeks, even with a minimal corpus (10K chunks instead of 900K) and mediocre components. Then measure, find the weakest link, improve it. Iterate.

### Main milestones by day

**Day 1.** Infrastructure baseline: Docker Compose with Qdrant, Redis, Phoenix, FastAPI. All services healthy. ≤5 min from fresh clone to working local stack.

**Day 2.** Ingest + schema + first 10K chunks in Qdrant. SuttaCentral Bilara format, structural chunking (by section), BGE-M3 embeddings. Hybrid retrieval on smoke queries.

**Day 3.** Full Contextual Retrieval pipeline + all 56K chunks indexed. Claude Haiku 4.5 generates context for each chunk. BM25 with ICU normalization for Pali diacritics.

**Day 4.** Baseline hybrid retrieval endpoint (`POST /retrieve`). Qdrant Query API with RRF fusion. Rate-limiting, async client, Prometheus metrics.

**Day 5 (critical).** Golden eval set + first Ragas run. 150 Q generated via Ragas TestsetGenerator, cross-model check on Haiku, 30 questions manually labeled. The numbers become baseline for all subsequent decisions.

**Day 6.** Reranking (BGE-reranker-v2-m3) + MMR diversification + multi-query expansion (3 reformulations with Pali/Sanskrit). Comparing with Day 5 baseline.

**Day 7.** LLM abstraction via LiteLLM (Claude, GPT, Llama — swap with an env-var). Grounded generation with XML citations. Routing: default Llama 3.3 70B, escalate to Claude Sonnet on long/hard queries.

**Day 8.** SSE streaming (`/ask/stream`). Structured citation payload for the frontend. Graceful cancel on disconnect.

**Day 9.** Phoenix/Langfuse observability + PII masking + HHEM-2.1-Open for automatic hallucination detection. Grafana dashboards.

**Day 10.** Minimal HTMX UI: landing + chat area + SSE rendering + confidence indicator. One HTML file, works everywhere.

**Day 11.** Guardrails: crisis detection, attribution verifier, deference-check ("The Buddha says" → "According to MN 10"), hard-refusals on harmful queries.

**Day 12.** Retrieval experiments: Qwen3-Reranker vs BGE, hierarchical retrieval, late chunking, HyPE. Decisions backed by the golden set.

**Day 13.** Prompt hardening + load test (50 concurrent users for 10 min) + cost model. Known performance ceilings.

**Day 14.** Docs + demo screencast + v0.1.0 release. Public tag, GHCR image, CONTRIBUTING.md.

## Chapter 16. What makes Dharma-RAG special

### Summary of the main theses

After going through the entire document, the essence of the project's philosophy can be stated in a few points:

**1. Citation-first architecture.** Not "AI answers," but "AI finds and summarizes what humans wrote." Every sentence in the answer has a traceable source.

**2. Texts, not chat.** Reader-first UX, not chatbot-first. The user first gets access to primary sources; AI is optional help.

**3. Hybrid retrieval.** Not "one embedding is enough." Three retrieval channels in parallel (dense + sparse + BM25), fused via RRF, a reranker on top.

**4. Knowledge graph is optional.** Not "GraphRAG everywhere." 80% of queries are handled by vectors + flat tables. The graph is added only where it actually beats SQL on multi-hop.

**5. Fine-tuning embedding, not LLM.** Not "fine-tune everything." Embedding and reranker fine-tuning yields 10× better gain per €1 than LLM fine-tuning.

**6. Cross-family LLM judge.** Claude is not evaluated by Claude. Gemini or GPT-5 evaluates Anthropic outputs; this eliminates self-enhancement bias.

**7. Human-in-the-loop buddhologists.** Doctrinal correctness is not automatable. A PhD Buddhologist + practitioners annotate the golden set.

**8. Qdrant named vectors as a migration key.** Changing the embedding model isn't a "rewrite from scratch," but a smooth parallel migration.

**9. Apache AGE as the strategic endpoint.** Not Neo4j (license risk), not Kuzu (dead). Apache AGE inside Postgres = everything in one transaction.

**10. Local deploy is possible on $15K of hardware.** 2×48 GB VRAM + 256 GB RAM + KTransformers = 85–90% of Claude Sonnet quality for electricity.

### What distinguishes Dharma-RAG from an ordinary ChatGPT clone

| Parameter | ChatGPT clone | Dharma-RAG |
|---|---|---|
| Data source | Model weights | Primary-source corpus |
| Citations | None | Mandatory, verifiable |
| Languages | 1–2 | 6 (Pali, Sanskrit, Tibetan, Chinese, EN, RU) |
| Domain knowledge | Weak | Buddhist specialization |
| Hallucinations | Common | <3% (doctrinal guardrails) |
| Cost structure | Per-call forever | One-time compute + electricity |
| Who controls data | Vendor | Project owner |
| Update lifecycle | Wait for next vendor model | On-demand reindex |
| Trust | "It sounds plausible" | "Checkable every sentence" |

### Three main takeaways for a non-technical reader

**First.** Dharma-RAG is not another ChatGPT. It is a **question-answering system over a specific library**, where every AI answer is tied to specific pages of specific books. It is closer in spirit to a scholarly search engine with AI assistance than to a chatbot.

**Second.** The project is deliberately **conservative in its architectural choices.** Every technology is chosen after comparison with 5–10 alternatives with explicit arguments why exactly this one. This is unusual for the 2026 AI field, where "take the latest trendy thing" is the norm.

**Third.** The project's main asset is **not code but data.** 500 golden questions with Buddhologist-validated answers are more valuable than any specific model or database. Models are replaceable every 6 months; a golden evaluation dataset is a 5-year asset.

---

*Report prepared based on the Dharma-RAG project's internal research documents: ARCHITECTURE_RAG_RESEARCH, DHARMA_RAG_TECHNICAL_AUDIT, EMBEDDING_ARCHITECTURE_DECISIONS, GRAPH_VS_EMBEDDING_RESEARCH, BUDDHIST_TEXT_CORPORA_RESEARCH, ARCHITECTURE_APPLICATION_UX_ANALYSIS, KNOWLEDGE_GRAPHS_VS_VECTOR_SEARCH, Dharma_RAG_RESEARCH.*

*April 2026.*
