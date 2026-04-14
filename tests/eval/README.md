# Evaluation Test Set

This directory holds the golden evaluation dataset for Dharma RAG retrieval
and generation quality.

## Files (to be created in Days 5-6)

| File | Description |
|------|-------------|
| `test_queries.yaml` | Questions with expected sources and topics |
| `golden_answers.yaml` | Reference answers for faithfulness scoring |
| `results/` | JSON outputs from evaluation runs |

## Adding new questions

Follow the schema in `test_queries.yaml`. Each question needs:

- `id` — unique identifier (q001, q002, ...)
- `query` — the question text
- `language` — `en` or `ru`
- `type` — `semantic`, `lexical`, `hybrid`, or `cross_lingual`
- `expected_sources` — list of suttas / teachers that should appear
- `topics` — keyword tags
- `difficulty` — `basic`, `intermediate`, or `advanced`
- `golden_answer` — reference answer text
