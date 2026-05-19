import Link from "next/link";

export function FlowMark({ size = 24, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={Math.round(size * 0.6)}
      viewBox="0 0 100 60"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className ?? "shrink-0 text-foreground"}
      aria-hidden
    >
      <path d="M50,30 C56.5,10 92,10 92,30 C92,50 56.5,50 50,30 C43.5,50 8,50 8,30 C8,10 43.5,10 50,30Z" fill="currentColor" />
      <path d="M50,30 C55,19 82,19 82,30 C82,41 55,41 50,30 C45,41 18,41 18,30 C18,19 45,19 50,30Z" fill="var(--background)" />
      <path d="M50,30 C52.8,22 70,22 70,30 C70,38 52.8,38 50,30 C47.2,38 30,38 30,30 C30,22 47.2,22 50,30Z" fill="currentColor" />
      <path d="M50,30 C51.4,25.5 60,25.5 60,30 C60,34.5 51.4,34.5 50,30 C48.6,34.5 40,34.5 40,30 C40,25.5 48.6,25.5 50,30Z" fill="var(--background)" />
      <path d="M50,30 C50.6,27.5 54,27.5 54,30 C54,32.5 50.6,32.5 50,30 C49.4,32.5 46,32.5 46,30 C46,27.5 49.4,27.5 50,30Z" fill="currentColor" />
    </svg>
  );
}

type FlowLogoProps = {
  href?: string;
  variant?: "inline" | "header";
};

export function FlowLogo({ href = "/", variant = "inline" }: FlowLogoProps) {
  const content = (
    <span className="flex items-center gap-2 text-foreground">
      <FlowMark size={variant === "header" ? 28 : 36} />
      <span className="font-mono font-bold tracking-tight text-sm">Flow</span>
    </span>
  );

  return href ? (
    <Link href={href} className="flex items-center">
      {content}
    </Link>
  ) : (
    content
  );
}
