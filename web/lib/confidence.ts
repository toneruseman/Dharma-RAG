/**
 * Heuristic confidence scoring for an LLM answer.
 *
 * No NLP — purely structural signals: how many distinct sources the
 * model cited and whether citations are spread across the answer
 * (vs front-loaded only). Calibrated for our `/api/answer` output:
 * stub fixture cites 3 works in 2-3 places; real DeepSeek V4 Flash
 * usually cites 3-5 works distributed through the body.
 *
 * Sane defaults — thresholds will tune as we collect feedback.
 */

import type { Source } from "@/lib/api-client";
import { parseAnswerCitations } from "@/lib/citations";

export type ConfidenceTier =
  | "well-grounded"
  | "synthesized"
  | "limited"
  | "interpretive"
  | "no-sources";

export type ConfidenceVerdict = {
  tier: ConfidenceTier;
  label: string;
  reason: string;
  uniqueCitations: number;
  totalCitations: number;
};

export function computeConfidence(
  answer: string,
  sources: readonly Source[],
): ConfidenceVerdict {
  const trimmed = answer.trim();

  if (sources.length === 0 || trimmed.length === 0) {
    return {
      tier: "no-sources",
      label: "no sources",
      reason: "Retrieval returned no relevant passages — the model declined to answer.",
      uniqueCitations: 0,
      totalCitations: 0,
    };
  }

  const knownIds = new Set(sources.map((s) => s.work_canonical_id));
  const segments = parseAnswerCitations(answer, knownIds);

  const citationSegments = segments.filter(
    (s): s is { type: "citation"; ids: string[] } => s.type === "citation",
  );
  const totalCitations = citationSegments.length;
  const uniqueIds = new Set(citationSegments.flatMap((s) => s.ids));
  const uniqueCitations = uniqueIds.size;

  // Distribution: where in the answer the last citation appears.
  // Front-loaded (everything cited only in the intro) => weaker signal.
  let runningOffset = 0;
  let lastCitationOffset = 0;
  for (const segment of segments) {
    const length =
      segment.type === "text" ? segment.text.length : segment.ids.join(", ").length + 2;
    runningOffset += length;
    if (segment.type === "citation") {
      lastCitationOffset = runningOffset;
    }
  }
  const distribution = trimmed.length === 0 ? 0 : lastCitationOffset / trimmed.length;
  const wellDistributed = distribution >= 0.6;

  if (uniqueCitations >= 3 && wellDistributed) {
    return {
      tier: "well-grounded",
      label: "well-grounded",
      reason: `${uniqueCitations} sources cited and references are spread through the answer.`,
      uniqueCitations,
      totalCitations,
    };
  }

  if (uniqueCitations >= 2) {
    return {
      tier: "synthesized",
      label: "synthesized",
      reason: `${uniqueCitations} sources cited — combine and verify against the originals.`,
      uniqueCitations,
      totalCitations,
    };
  }

  if (uniqueCitations === 1) {
    return {
      tier: "limited",
      label: "limited grounding",
      reason: "Only one source cited — the answer rests on a narrow base.",
      uniqueCitations,
      totalCitations,
    };
  }

  return {
    tier: "interpretive",
    label: "interpretive — verify with a teacher",
    reason:
      "No citations found in the answer body. The model may be paraphrasing " +
      "or speaking outside the retrieved sources.",
    uniqueCitations,
    totalCitations,
  };
}
