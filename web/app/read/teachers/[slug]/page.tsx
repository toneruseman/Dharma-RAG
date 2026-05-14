"use client";

import { useCallback, useEffect, useState } from "react";

import { TalkCard } from "@/components/reader/TalkCard";
import { Button } from "@/components/ui/button";
import { type WorkCard, getTeachers, getWorks } from "@/lib/api-client";

const PAGE_SIZE = 50;

type Props = {
  params: Promise<{ slug: string }>;
};

export default function TeacherPage({ params }: Props) {
  const [slug, setSlug] = useState<string | null>(null);
  const [teacherName, setTeacherName] = useState<string>("");
  const [talks, setTalks] = useState<WorkCard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // Resolve the slug from the async params (Next.js 15 pattern)
  useEffect(() => {
    params.then(({ slug: s }) => setSlug(s));
  }, [params]);

  // Initial load: fetch teacher name + first page of talks
  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    Promise.all([
      getTeachers(),
      getWorks({ source_type: "dharmaseed_talk", teacher_slug: slug, limit: PAGE_SIZE, offset: 0 }),
    ])
      .then(([teachers, result]) => {
        const teacher = teachers.find((t) => t.slug === slug);
        setTeacherName(teacher?.name ?? slug);
        setTalks(result.items);
        setTotal(result.total);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  const handleLoadMore = useCallback(() => {
    if (!slug || loadingMore) return;
    setLoadingMore(true);
    getWorks({
      source_type: "dharmaseed_talk",
      teacher_slug: slug,
      limit: PAGE_SIZE,
      offset: talks.length,
    })
      .then((result) => {
        setTalks((prev) => [...prev, ...result.items]);
        setTotal(result.total);
      })
      .finally(() => setLoadingMore(false));
  }, [slug, talks.length, loadingMore]);

  const hasMore = talks.length < total;

  if (loading) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10 px-4 py-12 sm:px-6 sm:py-16">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-10 px-4 py-12 sm:px-6 sm:py-16">
      <header className="flex flex-col gap-3">
        <nav className="text-xs text-muted-foreground">
          <a href="/read" className="hover:underline">
            Reading Room
          </a>
          {" / "}
          <span>Dharma Talks</span>
          {" / "}
          <span className="text-foreground">{teacherName}</span>
        </nav>
        <h1 className="font-heading text-3xl font-semibold tracking-tight sm:text-4xl">
          {teacherName}
        </h1>
        <p className="text-sm text-muted-foreground">
          {total} talk{total === 1 ? "" : "s"} · sorted by date
        </p>
      </header>

      {talks.length === 0 ? (
        <p className="text-sm text-muted-foreground">No talks found.</p>
      ) : (
        <section className="flex flex-col gap-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {talks.map((talk) => (
              <TalkCard key={talk.canonical_id} talk={talk} />
            ))}
          </div>
          {hasMore ? (
            <div className="flex justify-center pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? "Loading…" : `Load more (${total - talks.length} remaining)`}
              </Button>
            </div>
          ) : (
            <p className="text-center text-xs text-muted-foreground">
              All {total} talks loaded.
            </p>
          )}
        </section>
      )}
    </main>
  );
}
