"use client";

import { useEffect } from "react";
import { useStore } from "./store";
import { getToken } from "./auth";

export function useAuthSync() {
  const setToken = useStore((s) => s.setToken);
  useEffect(() => {
    const token = getToken();
    setToken(token);
  }, [setToken]);
}
