import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TeacherCard as TeacherCardType } from "@/lib/api-client";

type Props = {
  teacher: TeacherCardType;
};

export function TeacherCard({ teacher }: Props) {
  return (
    <Link
      href={`/read/teachers/${encodeURIComponent(teacher.slug)}`}
      className="group rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-colors group-hover:border-foreground/30">
        <CardHeader>
          <p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {teacher.tradition_code ?? "dharma"}
          </p>
          <CardTitle className="dharma-text text-xl">{teacher.name}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {teacher.talk_count} talk{teacher.talk_count === 1 ? "" : "s"}
          </span>
          <span className="font-medium text-foreground/80 group-hover:text-foreground">
            Browse →
          </span>
        </CardContent>
      </Card>
    </Link>
  );
}
