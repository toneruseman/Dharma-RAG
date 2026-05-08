/**
 * Build the ordered list of `Source`s actually cited in an answer.
 *
 * Inputs come from `AnswerResponse`:
 *   - `answer`     — full text with `[work_id]` markers
 *   - `sources`    — every source the LLM saw (top_k)
 *   - `citations`  — distinct work_canonical_ids the LLM emitted
 *
 * Output:
 *   - subset of `sources` whose work_id is in `citations`,
 *   - one Source per work_id (highest-score wins for multi-segment hits,
 *     same rule as `<AnswerView>` hover-preview),
 *   - ordered by **first appearance** of the `[work_id]` marker in the
 *     answer text — not by score, not by `citations` array order.
 *
 * Pure: no DOM access, no React, no side effects. Easy to unit-test.
 */

import type { Source } from "@/lib/api-client";

export function citedSourcesInOrder(
  answer: string,
  sources: ReadonlyArray<Source>,
  citations: ReadonlyArray<string>,
): Source[] {
  // First-appearance index of each citation marker in the answer text.
  // We match the literal "[mn10" prefix because the closing `]` may be
  // part of a comma-separated bracket like `[mn10, dn22]`.
  const firstIdx = new Map<string, number>();
  for (const cite of citations) {
    const idx = answer.indexOf(`[${cite}`);
    if (idx >= 0) firstIdx.set(cite, idx);
  }

  // Multiple sources can share a work_canonical_id (different segments
  // matched). We keep the best-scoring one — same convention as the
  // hover-preview tooltip in `<AnswerView>`, so users see the same
  // passage in both places.
  const bestByWorkId = new Map<string, Source>();
  for (const source of sources) {
    const cur = bestByWorkId.get(source.work_canonical_id);
    if (!cur || source.score > cur.score) {
      bestByWorkId.set(source.work_canonical_id, source);
    }
  }

  return citations
    .filter((c) => bestByWorkId.has(c))
    .slice() // copy so .sort() is non-mutating on the input
    .sort((a, b) => (firstIdx.get(a) ?? Infinity) - (firstIdx.get(b) ?? Infinity))
    .map((c) => bestByWorkId.get(c) as Source);
}
