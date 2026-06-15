"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, LayoutDashboard } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Token-aware hero CTA: returning users jump straight into the workspace. */
export function EnterAppCta() {
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    setAuthed(Boolean(getToken()));
  }, []);

  if (authed) {
    return (
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Link href="/dashboard" className={cn(buttonVariants({ size: "lg" }), "gap-2")}>
          <LayoutDashboard className="h-4 w-4" />
          Enter workspace
        </Link>
        <Link href="/run" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
          New run
        </Link>
      </div>
    );
  }

  return (
    <div className="mt-8 flex flex-wrap items-center gap-3">
      <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "gap-2")}>
        Start building
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
      <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>
        Sign in
      </Link>
    </div>
  );
}
