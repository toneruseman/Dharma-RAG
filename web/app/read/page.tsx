import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const SUGGESTED_WORKS = [
  {
    uid: "mn10",
    title: "Satipaṭṭhāna Sutta",
    description: "The Establishings of Mindfulness — the canonical short discourse on the four foundations.",
  },
  {
    uid: "sn56.11",
    title: "Dhammacakkappavattana Sutta",
    description: "Rolling Forth the Wheel of Dhamma — the Buddha's first sermon on the four noble truths.",
  },
  {
    uid: "dn22",
    title: "Mahāsatipaṭṭhāna Sutta",
    description: "The Longer Discourse on Mindfulness Meditation — extended exposition of MN 10.",
  },
] as const;

export default function ReadIndexPage() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-3">
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Reading Room
        </p>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          Read the canon directly.
        </h1>
        <p className="max-w-2xl text-base text-muted-foreground">
          Texts are the heart of this project. Open a sutta to read it in its full
          structure — citations from the search and chat surfaces link straight
          back here so you can verify the source.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SUGGESTED_WORKS.map((work) => (
          <Link
            key={work.uid}
            href={`/read/${work.uid}`}
            className="group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Card className="h-full transition-colors group-hover:border-foreground/30">
              <CardHeader>
                <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
                  {work.uid}
                </p>
                <CardTitle className="dharma-text text-xl italic">{work.title}</CardTitle>
                <CardDescription className="text-sm leading-relaxed">
                  {work.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm font-medium text-foreground/80 group-hover:text-foreground">
                Read →
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>

      <p className="rounded-md border border-dashed border-border bg-muted/30 p-4 text-xs text-muted-foreground">
        In stub mode the corpus exposes the three works above. Real-mode deployments
        ingest thousands more from SuttaCentral and partner sources.
      </p>
    </main>
  );
}
