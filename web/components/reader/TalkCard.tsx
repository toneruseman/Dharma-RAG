import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkCard } from "@/lib/api-client";

type Props = {
  talk: WorkCard;
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  // "YYYY-MM-DD" → "1 Jan 2005"
  const d = new Date(iso + "T00:00:00Z");
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function TalkCard({ talk }: Props) {
  return (
    <Link
      href={`/read/${encodeURIComponent(talk.canonical_id)}`}
      className="group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-colors group-hover:border-foreground/30">
        <CardHeader>
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {formatDate(talk.talk_date)}
          </p>
          <CardTitle className="dharma-text text-base font-medium leading-snug">
            {talk.title}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm font-medium text-foreground/80 group-hover:text-foreground">
          Read →
        </CardContent>
      </Card>
    </Link>
  );
}
