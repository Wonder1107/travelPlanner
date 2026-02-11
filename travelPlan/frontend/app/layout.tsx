import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import "./globals.css";

const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "AI Travel Agent MVP",
  description: "Dynamic itinerary from onboarding to live replanning",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html className="light" lang="en">
      <body className={`${display.variable} font-display bg-background-light text-slate-900 dark:bg-background-dark dark:text-slate-100`}>
        <div className="relative mx-auto flex min-h-screen w-full max-w-[480px] flex-col overflow-x-hidden border-x border-slate-200 bg-white dark:border-slate-800 dark:bg-background-dark">
          {children}
        </div>
      </body>
    </html>
  );
}
