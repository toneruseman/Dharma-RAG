/**
 * Parse `[work_id]` and `[work_a, work_b]` citation markers out of an
 * LLM answer body so the renderer can turn them into Reading-Room
 * links.
 *
 * Hallucinated citations (IDs that aren't in the actual retrieved
 * sources) are left as plain text — we don't manufacture a broken
 * link to a non-existent document.
 */

export type AnswerSegment =
  | { type: "text"; text: string }
  | { type: "citation"; ids: string[] };

const CITATION_RE = /\[([^\[\]]+)\]/g;

export function parseAnswerCitations(
  answer: string,
  knownWorkIds: ReadonlySet<string>,
): AnswerSegment[] {
  const segments: AnswerSegment[] = [];
  let lastIndex = 0;

  for (const match of answer.matchAll(CITATION_RE)) {
    const idx = match.index ?? 0;
    const ids = match[1]
      .split(",")
      .map((s) => s.trim())
      .filter((id) => knownWorkIds.has(id));

    if (ids.length === 0) {
      // No matching retrieved source — leave the [xyz] text untouched.
      continue;
    }

    if (idx > lastIndex) {
      segments.push({ type: "text", text: answer.slice(lastIndex, idx) });
    }
    segments.push({ type: "citation", ids });
    lastIndex = idx + match[0].length;
  }

  if (lastIndex < answer.length) {
    segments.push({ type: "text", text: answer.slice(lastIndex) });
  }
  return segments;
}
