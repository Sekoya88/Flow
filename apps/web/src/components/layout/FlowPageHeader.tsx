import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type FlowPageHeaderProps = {
  title: string;
  description?: string;
  /** Shown to the left of the title (e.g. icon). */
  leading?: ReactNode;
  /** Inline with title (e.g. status badge). */
  titleSuffix?: ReactNode;
  /** Top row above title (e.g. small badges). */
  eyebrow?: ReactNode;
  actions?: ReactNode;
  /** Row under description: links, chips. */
  meta?: ReactNode;
  className?: string;
};

/**
 * Shared page chrome aligned with motion-frame / shell direction: clear hierarchy, border trail, readable body size.
 */
export function FlowPageHeader({
  title,
  description,
  leading,
  titleSuffix,
  eyebrow,
  actions,
  meta,
  className,
}: FlowPageHeaderProps) {
  return (
    <header className={cn("space-y-4 border-b border-flow-800 pb-6", className)}>
      {eyebrow ? <div className="flex flex-wrap items-center gap-2">{eyebrow}</div> : null}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            {leading ? <span className="shrink-0 text-flow-violet">{leading}</span> : null}
            <h1 className="font-heading text-3xl font-semibold tracking-tight text-balance">{title}</h1>
            {titleSuffix}
          </div>
          {description ? (
            <p className="max-w-2xl text-pretty text-[15px] leading-relaxed text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {meta ? <div className="flex flex-wrap items-center gap-2">{meta}</div> : null}
    </header>
  );
}
