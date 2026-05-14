import Link from "next/link";

import { TeacherCard } from "@/components/reader/TeacherCard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getTeachers } from "@/lib/api-client";

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

export default async function ReadIndexPage() {
  // Errors here (e.g. API down) are allowed to propagate — Next.js
  // will render the nearest error.tsx boundary.
  const teachers = await getTeachers().catch(() => []);

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

      <section className="flex flex-col gap-4">
        <h2 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          Pāli Canon
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
        </div>
      </section>

      {teachers.length > 0 ? (
        <section className="flex flex-col gap-4">
          <h2 className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Dharma Talks
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {teachers.map((teacher) => (
              <TeacherCard key={teacher.slug} teacher={teacher} />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
