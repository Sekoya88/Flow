import { forwardRef } from "react";
import Link from "next/link";

const LEMNISCATE_PATH = "M 8 32 C 8 12, 28 12, 32 32 C 36 52, 56 52, 56 32 C 56 12, 36 12, 32 32 C 28 52, 8 52, 8 32 Z";

export function FlowMark({ size, className }: { size: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className ?? "shrink-0 text-foreground opacity-90 transition-opacity group-hover:opacity-100"}
      aria-hidden
    >
      <path
        d={LEMNISCATE_PATH}
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        pathLength="100"
      />
    </svg>
  );
}

export const FlowMarkAnimated = forwardRef<SVGSVGElement, { className?: string; size?: number | string }>(
  function FlowMarkAnimated({ className, size = 64 }, ref) {
    return (
      <svg
        ref={ref}
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        aria-hidden="true"
      >
          <path
          d={LEMNISCATE_PATH}
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          pathLength="100"
          strokeDasharray="100 0"
          style={{ animation: "flow-reveal 1.6s ease-in-out forwards" }}
        />
        <path
          d={LEMNISCATE_PATH}
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          pathLength="100"
          strokeOpacity="0.4"
          strokeDasharray="8 92"
          style={{ animation: "flow-drift 6s linear 1.6s infinite" }}
        />
      </svg>
    );
  }
);

type FlowLogoProps = {
  href?: string;
  size?: "sm" | "md";
  variant?: "inline" | "header";
  subtitle?: string;
};

export function FlowLogo({
  href = "/",
  size = "md",
  variant = "inline",
  subtitle = "Agent platform · workspace",
}: FlowLogoProps) {
  const dim = size === "sm" ? 28 : 36;

  if (variant === "header") {
    return (
      <Link href={href} className="group flex min-w-0 items-center gap-3 text-foreground">
        <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-md border border-border bg-card shadow-sm ring-1 ring-white/5">
          <div className="flex h-full w-full items-center justify-center">
            <FlowMark size={22} className="shrink-0 text-foreground opacity-95" />
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold leading-none tracking-tight">Flow</p>
          <p className="mt-1 truncate text-[10.5px] text-muted-foreground">{subtitle}</p>
        </div>
      </Link>
    );
  }

  const text = size === "sm" ? "text-base" : "text-lg";
  return (
    <Link href={href} className="group flex items-center gap-2.5 font-semibold tracking-tight text-foreground">
      <FlowMark size={dim} />
      <span className={text}>Flow</span>
    </Link>
  );
}
