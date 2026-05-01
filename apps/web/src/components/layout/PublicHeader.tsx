import Link from "next/link";
import { FlowLogo } from "@/components/brand/FlowLogo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PublicHeaderProps = {
  /** Auth pages: adjust links in the header rail. */
  auth?: "login" | "register";
};

export function PublicHeader({ auth }: PublicHeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-[90rem] items-center gap-3 px-5 py-3.5 sm:px-8">
        <FlowLogo href="/" variant="header" subtitle="Runs · memory · tools" />
        <div className="flex flex-1 justify-end gap-2">
          {auth === "login" ? (
            <>
              <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
                Home
              </Link>
              <Link href="/register" className={cn(buttonVariants({ variant: "default", size: "sm" }))}>
                Register
              </Link>
            </>
          ) : auth === "register" ? (
            <>
              <Link href="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
                Home
              </Link>
              <Link href="/login" className={cn(buttonVariants({ variant: "default", size: "sm" }))}>
                Sign in
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}>
                Sign in
              </Link>
              <Link href="/register" className={cn(buttonVariants({ variant: "default", size: "sm" }))}>
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
