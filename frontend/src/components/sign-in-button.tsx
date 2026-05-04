"use client";

import { signIn } from "next-auth/react";
import { Github } from "lucide-react";
import { Button, type ButtonProps } from "@/components/ui/button";

type Props = ButtonProps & {
  callbackUrl?: string;
  label?: string;
};

export function SignInButton({
  callbackUrl = "/dashboard",
  label = "Continue with GitHub",
  size = "lg",
  ...rest
}: Props) {
  return (
    <Button
      onClick={() => signIn("github", { callbackUrl })}
      size={size}
      {...rest}
    >
      <Github />
      {label}
    </Button>
  );
}
