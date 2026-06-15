import { HomeLanding } from "@/components/marketing/HomeLanding";

export default function Home() {
  // Always render the landing page — including for authenticated users — so
  // clicking the Flow logo returns here. The landing shows an "Enter workspace"
  // CTA when a session token is present.
  return <HomeLanding />;
}
