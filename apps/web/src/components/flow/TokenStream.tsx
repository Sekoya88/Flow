"use client";

import { useEffect, useRef } from "react";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

interface TokenStreamProps {
  className?: string;
  placeholder?: string;
}

// Zero React renders per token: Zustand subscribe writes directly to DOM via ref.
export function TokenStream({ className, placeholder }: TokenStreamProps) {
  const spanRef = useRef<HTMLSpanElement>(null);
  const isRunning = useStore((s) => s.activeExecutionId !== null);

  useEffect(() => {
    if (spanRef.current) {
      spanRef.current.textContent = useStore.getState().tokens.join("");
    }

    return useStore.subscribe((state) => {
      if (spanRef.current) {
        spanRef.current.textContent = state.tokens.join("");
      }
    });
  }, []);

  return (
    <div
      className={cn(
        "font-mono text-[13px] leading-relaxed text-foreground/90",
        className,
      )}
    >
      <span ref={spanRef} />
      {isRunning && (
        <span
          aria-hidden="true"
          className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[1px] rounded-sm bg-flow-streaming"
          style={{ animation: "cursor-blink 1s step-end infinite" }}
        />
      )}
      {!isRunning && !spanRef.current?.textContent && placeholder ? (
        <span className="text-muted-foreground">{placeholder}</span>
      ) : null}
      <style>{`
        @keyframes cursor-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
