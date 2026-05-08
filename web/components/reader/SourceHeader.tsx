import type { SourceDocument } from "@/lib/api-client";

const TRADITION_LABELS: Record<string, string> = {
  theravada: "Theravāda",
  mahayana: "Mahāyāna",
  vajrayana: "Vajrayāna",
  zen: "Zen",
  chan: "Chan",
  pragmatic_dharma: "Pragmatic Dharma",
  secular: "Secular",
};

export function SourceHeader({ document }: { document: SourceDocument }) {
  const tradition = TRADITION_LABELS[document.tradition_code] ?? document.tradition_code;
  const provenance = [
    document.translation.author,
    document.translation.publication_year,
    document.translation.license,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <header className="flex flex-col gap-2 border-b border-border/60 pb-6">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
        {document.canonical_id} · {tradition}
      </p>
      <h1 className="font-heading text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
        {document.title}
      </h1>
      {document.title_pali ? (
        <p className="dharma-text text-lg italic text-muted-foreground">
          {document.title_pali}
        </p>
      ) : null}
      {provenance ? (
        <p className="text-sm text-muted-foreground">{provenance}</p>
      ) : null}
    </header>
  );
}
