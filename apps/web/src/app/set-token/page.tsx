"use client";
import { useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function Inner() {
  const router = useRouter();
  const params = useSearchParams();
  useEffect(() => {
    const t = params.get("t");
    if (t) localStorage.setItem("flow_token", t);
    router.replace("/dashboard");
  }, [router, params]);
  return null;
}

export default function SetToken() {
  return <Suspense><Inner /></Suspense>;
}
