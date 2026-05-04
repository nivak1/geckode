import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary/10 text-primary ring-1 ring-inset ring-primary/30",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        outline: "text-foreground",
        muted:
          "border-transparent bg-muted text-muted-foreground",
        success:
          "border-transparent bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30",
        warning:
          "border-transparent bg-amber-500/10 text-amber-300 ring-1 ring-inset ring-amber-500/30",
        destructive:
          "border-transparent bg-destructive/10 text-destructive-foreground ring-1 ring-inset ring-destructive/40",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
