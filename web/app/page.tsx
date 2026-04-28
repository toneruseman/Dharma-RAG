import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const SURFACES = [
  {
    href: "/read",
    title: "Reading Room",
    description:
      "Open original texts in their structure — chapters, verses, parallel translations, hover-glossary for Pāli terms.",
    badge: "primary surface",
  },
  {
    href: "/search",
    title: "Search",
    description:
      "Hybrid retrieval (dense + sparse + reranker) across the corpus. Filters by tradition, language, translator.",
    badge: "search-first",
  },
  {
    href: "/chat",
    title: "Q&A",
    description:
      "Ask questions, receive answers with inline citations. Each citation links back to the exact passage in the Reading Room.",
    badge: "with citations",
  },
] as const;

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-12 px-4 py-16 sm:px-6 sm:py-24">
      <section className="flex flex-col gap-4">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          dharma-rag — open-source · BYOK
        </p>
        <h1 className="font-heading text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          Retrieval and answers grounded in Buddhist contemplative texts.
        </h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Pāli Canon, contemporary teachings, Dharmaseed transcripts — searchable, cited,
          and shown alongside the original. Built for practitioners, researchers, and
          anyone who wants verifiable sources rather than synthesized opinions.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SURFACES.map((surface) => (
          <Link
            key={surface.href}
            href={surface.href}
            className="group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Card className="h-full transition-colors group-hover:border-foreground/30">
              <CardHeader>
                <p className="text-xs uppercase tracking-wider text-muted-foreground">
                  {surface.badge}
                </p>
                <CardTitle className="font-heading text-2xl">{surface.title}</CardTitle>
                <CardDescription className="text-sm leading-relaxed">
                  {surface.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm font-medium text-foreground/80 group-hover:text-foreground">
                Open →
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>

      <section className="rounded-lg border border-dashed border-border bg-muted/30 p-6 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">A note on use.</p>
        <p className="mt-2 max-w-3xl leading-relaxed">
          This tool returns excerpts and paraphrases from translated and licensed sources.
          It does not provide spiritual instruction, medical advice, or crisis support.
          For personal practice questions, please consult a qualified human teacher.
        </p>
      </section>
    </main>
  );
}
