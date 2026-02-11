import { Suspense } from "react";

import { ConsoleClient } from "@/components/console-client";

export default function ConsolePage() {
  return (
    <Suspense fallback={<main className="rounded-2xl bg-white p-5 shadow-card">Loading console...</main>}>
      <ConsoleClient />
    </Suspense>
  );
}
