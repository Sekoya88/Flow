"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { HomeLanding } from "@/components/marketing/HomeLanding";
import { getToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace("/dashboard");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground text-sm">
        Loading…
      </div>
    );
  }

  return <HomeLanding />;
}
