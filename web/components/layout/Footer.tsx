import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-border/60 bg-background">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-6 text-sm text-muted-foreground sm:px-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-2xl text-xs leading-relaxed">
          Dharma-RAG — open retrieval over Buddhist contemplative texts. Generated answers
          cite sources but are not a substitute for a qualified teacher. If you are in crisis,
          please contact a local hotline or emergency services.
        </p>
        <nav className="flex items-center gap-3 text-xs">
          <Link href="/sources" className="hover:text-foreground transition-colors">
            Sources
          </Link>
          <Link href="/audit" className="hover:text-foreground transition-colors">
            Audit
          </Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">
            Privacy
          </Link>
          <a
            href="https://github.com/toneruseman/Dharma-RAG"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            GitHub
          </a>
        </nav>
      </div>
    </footer>
  );
}
