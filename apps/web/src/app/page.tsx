"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { HomeLanding } from "@/components/marketing/HomeLanding";
import { getToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const routerRef = useRef(router);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    routerRef.current = router;
  }, [router]);

  useEffect(() => {
    setReady(true);
  }, []);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-muted-foreground text-sm">
        Loading…
      </div>
    );
  }

  return <HomeLanding />;
}
