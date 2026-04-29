import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SourceBody } from "@/components/reader/SourceBody";
import { SourceHeader } from "@/components/reader/SourceHeader";
import { getSource } from "@/lib/api-client";

type PageProps = {
  params: Promise<{ uid: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { uid } = await params;
  const document = await getSource(uid).catch(() => null);
  if (!document) {
    return { title: `${uid} — Dharma-RAG` };
  }
  const titleParts = [document.title, document.title_pali].filter(Boolean);
  return {
    title: `${titleParts.join(" · ")} — Dharma-RAG`,
    description:
      document.translation.title ??
      `${document.canonical_id} translated by ${document.translation.author ?? "unknown"}.`,
  };
}

export default async function ReadPage({ params }: PageProps) {
  const { uid } = await params;
  const document = await getSource(uid);

  if (!document) {
    notFound();
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-12 sm:px-6 sm:py-16">
      <nav className="text-sm">
        <Link
          href="/read"
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          ← Reading Room
        </Link>
      </nav>
      <SourceHeader document={document} />
      <SourceBody paragraphs={document.paragraphs} />
    </main>
  );
}
