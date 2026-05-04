"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="container flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <p className="text-sm uppercase tracking-wide text-muted-foreground">
        Something went wrong
      </p>
      <h1 className="text-3xl font-semibold tracking-tight">
        We hit an unexpected error
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">{error.message}</p>
      <div className="flex gap-2">
        <Button onClick={() => reset()}>Try again</Button>
        <Button variant="ghost" asChild>
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
