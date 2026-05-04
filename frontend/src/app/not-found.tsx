import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="container flex min-h-screen flex-col items-center justify-center gap-4 text-center">
      <p className="text-sm uppercase tracking-wide text-muted-foreground">
        404
      </p>
      <h1 className="text-3xl font-semibold tracking-tight">
        That page doesn&apos;t exist
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        The repo might not be connected, or the URL might be off. Head back to
        your dashboard to see your connected repositories.
      </p>
      <Button asChild>
        <Link href="/dashboard">Go to dashboard</Link>
      </Button>
    </div>
  );
}
