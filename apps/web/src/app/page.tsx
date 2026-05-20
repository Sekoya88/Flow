"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { HomeLanding } from "@/components/marketing/HomeLanding";
import { getToken } from "@/lib/auth";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  return <HomeLanding />;
}
