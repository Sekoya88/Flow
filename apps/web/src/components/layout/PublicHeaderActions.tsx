"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LayoutDashboard } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { getToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Header actions that reflect auth state: account shortcut when signed in. */
export function PublicHeaderActions() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  useEffect(() => {
    setAuthed(Boolean(getToken()));
  }, []);

  // Avoid a flash of the wrong CTA before the token check resolves.
  if (authed === null) return <div className="h-8" />;

  if (authed) {
    return (
      <>
        <Link href="/dashboard" className={cn(buttonVariants({ variant: "default", size: "sm" }), "gap-1.5")}>
          <LayoutDashboard className="h-3.5 w-3.5" />
          My workspace
        </Link>
      </>
    );
  }

  return (
    <>
      <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
        Sign in
      </Link>
      <Link href="/register" className={cn(buttonVariants({ variant: "default", size: "sm" }))}>
        Register
      </Link>
    </>
  );
}
