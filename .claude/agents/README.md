# Project subagents for Dharma-RAG

Three project-scoped Claude Code subagents live here. They are
version-controlled so every developer's Claude Code session sees the
same specialists. User-level agents belong in `~/.claude/agents/` and
are NOT committed.

## Available agents

| Name | Model | Tools | Use for |
|---|---|---|---|
| [`dharma-code-reviewer`](dharma-code-reviewer.md) | sonnet | Read, Grep, Glob, Bash | Pre-commit review of a diff against FRBR invariants, Pali correctness, SQLAlchemy hygiene, license rules, and test discipline. |
| [`buddhist-scholar-proxy`](buddhist-scholar-proxy.md) | opus | Read, Grep, Glob, WebSearch, WebFetch | Sanity-check LLM-generated answers for doctrinal soundness while blocker [#8](https://github.com/toneruseman/Dharma-RAG/issues/8) is unresolved. Proxy, not a replacement. |
| [`eval-analyst`](eval-analyst.md) | sonnet | Read, Grep, Glob, Bash | Post-eval root-cause analysis: why did `ref_hit@5` drop, which query category regressed, what to verify next. Active from rag-day-14 onwards. |

## When each one fires

### `dharma-code-reviewer` — before every non-trivial commit

Invocation examples:
- *"Review the current diff for FRBR / Pali / type issues"*
- *"Check this migration for upgrade/downgrade symmetry"*
- *"Is chunk.text_ascii_fold being populated correctly on all new rows?"*

Output: structured **🔴 Must Fix / 🟡 Should Fix / 🟢 Nice to Have**
report with file:line citations. Main agent applies fixes.

### `buddhist-scholar-proxy` — after generation, before showing user

Active once `rag-day-15` (contextual retrieval + first real LLM
generation) is merged. Until then, nothing to review.

Invocation examples:
- *"Review this generated answer about jhāna for doctrinal accuracy"*
- *"Does this MN-10 summary conflate Theravāda and Mahāyāna framings?"*
- *"Is the Pāli transliteration in this paragraph correct?"*

Output: **🔴 Inaccurate / 🟡 Imprecise / 🟢 Context note** findings
with sutta/commentary citations.

### `eval-analyst` — after every Ragas run

Active once `rag-day-14` (first Ragas baseline) lands.

Invocation examples:
- *"Analyse the latest run in tests/eval/results/"*
- *"Compare v1 vs v2 Contextual Retrieval results and tell me which categories improved"*
- *"Is the ref_hit@5 drop between 2026-05-01 and 2026-05-07 real signal or noise?"*

Output: root-cause analysis (what changed / which category / hypothesis
/ how to verify / recommended next step).

## How to invoke

From a Claude Code chat in this repo:

```text
use the dharma-code-reviewer agent to review the current diff
```

Or programmatically via the `Task` / `Agent` tool:

```text
Agent(
  description="Pre-commit review of day-7 chunker",
  subagent_type="dharma-code-reviewer",
  prompt="Review the diff on feat/rag-day-07-chunker against FRBR and Pali invariants. Short report."
)
```

## Design principles

1. **Narrow tool scope.** Each agent gets only the tools it needs.
   `dharma-code-reviewer` can read + grep + run git commands; it
   cannot edit files. Reviewer writes reports, main agent applies.

2. **Opus only where judgement matters.** `buddhist-scholar-proxy`
   uses opus because doctrinal subtlety needs capability. Code review
   and eval analysis are fine on sonnet (cheaper, faster).

3. **Honest framing.** `buddhist-scholar-proxy` is explicit about
   being a proxy, not a replacement for blocker [#8](https://github.com/toneruseman/Dharma-RAG/issues/8).
   `eval-analyst` is explicit about synthetic-golden caveats.

4. **Return structured reports, don't edit.** All three return text
   findings; the main agent orchestrates fixes. This keeps the main
   context window in control of what actually lands in git.

5. **Project-scoped, not user-scoped.** Committed to git so every
   contributor's session uses the same specialists. Personal
   agents (e.g. preferred shell tweaks) go in `~/.claude/agents/`
   and stay private.

## Adding a new agent

1. Create `.claude/agents/{name}.md` with YAML frontmatter:
   ```yaml
   ---
   name: ...
   description: when to invoke (critical — this is the trigger text)
   tools: Read, Grep, Bash   # narrow, principle of least privilege
   model: sonnet | opus | haiku
   ---
   ```
2. Body is the system prompt: what the agent does, how it reports,
   what it should NOT do, context shortcuts.
3. Commit. Every Claude Code session in this repo picks it up
   automatically.

## See also

- Decision to add subagents: discussed [in the dev session on rag-day-06](https://github.com/toneruseman/Dharma-RAG/commits/dev).
- Claude Code subagents docs: <https://docs.claude.com/en/docs/claude-code/sub-agents>
