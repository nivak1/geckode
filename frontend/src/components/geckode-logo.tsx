import Image from "next/image";
import { cn } from "@/lib/utils";

export function GeckodeLogo({
  className,
  size = 28,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 font-semibold tracking-tight",
        className,
      )}
    >
      <Image
        src="/logo.png"
        alt=""
        width={size}
        height={size}
        className="shrink-0 rounded-md"
        priority
      />
      <span>Geckode</span>
    </span>
  );
}
