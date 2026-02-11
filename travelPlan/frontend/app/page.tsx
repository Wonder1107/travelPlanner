"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { createTrip } from "@/lib/api";

type DurationRange = "1-3" | "4-7" | "8-14" | "15+";
type BudgetChoice = "low" | "mid" | "high";

const DURATION_OPTIONS: DurationRange[] = ["1-3", "4-7", "8-14", "15+"];
const INITIAL_INTERESTS = ["Museums", "Local Food"];

function mapDurationToDays(duration: DurationRange): number {
  if (duration === "1-3") return 2;
  return 3;
}

function mapInterestToPreference(label: string): string {
  const normalized = label.trim().toLowerCase();
  if (normalized.includes("food")) return "food";
  if (normalized.includes("museum")) return "museum";
  if (normalized.includes("night")) return "nightwalk";
  return normalized.replace(/\s+/g, "_");
}

export default function HomePage() {
  const router = useRouter();
  const [destination, setDestination] = useState("Shanghai, China");
  const [duration, setDuration] = useState<DurationRange>("1-3");
  const [budget, setBudget] = useState<BudgetChoice>("mid");
  const [interests, setInterests] = useState<string[]>(INITIAL_INTERESTS);
  const [interestDraft, setInterestDraft] = useState("");
  const [avoidText, setAvoidText] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preferenceTags = useMemo(
    () => interests.map((item) => mapInterestToPreference(item)),
    [interests],
  );

  const avoidTags = useMemo(
    () =>
      avoidText
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean),
    [avoidText],
  );

  async function onGenerate() {
    setLoading(true);
    setError(null);
    try {
      const result = await createTrip({
        city: destination.trim() || "Shanghai",
        days: mapDurationToDays(duration),
        budget_level: budget,
        preferences: preferenceTags.length > 0 ? preferenceTags : ["museum", "coffee", "nightwalk"],
        avoid: avoidTags,
        pace: "balanced",
        travel_note: notes,
      });
      router.push(`/trip/${result.trip_id}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to generate itinerary.");
    } finally {
      setLoading(false);
    }
  }

  function addInterest() {
    const value = interestDraft.trim();
    if (!value) return;
    if (interests.some((item) => item.toLowerCase() === value.toLowerCase())) {
      setInterestDraft("");
      return;
    }
    setInterests((prev) => [...prev, value]);
    setInterestDraft("");
  }

  return (
    <>
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white/80 px-4 py-4 backdrop-blur-md dark:border-slate-800 dark:bg-background-dark/80">
        <button className="flex size-10 items-center justify-center rounded-full transition-colors hover:bg-slate-100 dark:hover:bg-slate-800">
          <span className="material-symbols-outlined">arrow_back_ios_new</span>
        </button>
        <h1 className="text-lg font-bold tracking-tight">Plan Your Journey</h1>
        <button className="flex size-10 items-center justify-center rounded-full transition-colors hover:bg-slate-100 dark:hover:bg-slate-800">
          <span className="material-symbols-outlined text-primary">auto_awesome</span>
        </button>
      </div>

      <div className="h-1 w-full bg-slate-100 dark:bg-slate-800">
        <div className="h-full w-1/3 rounded-r-full bg-primary transition-all duration-500" />
      </div>

      <main className="flex-1 overflow-y-auto px-5 pb-32">
        <div className="pb-6 pt-8">
          <h2 className="text-3xl font-bold leading-tight">Tell us about your trip</h2>
          <p className="mt-2 text-slate-500 dark:text-slate-400">
            Our AI agent will craft a personalized itinerary based on your preferences.
          </p>
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Destination
            </label>
            <div className="group relative">
              <input
                className="h-14 w-full rounded-xl border-slate-200 bg-slate-50 pl-12 pr-4 text-base outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 dark:border-slate-800 dark:bg-slate-900/50"
                placeholder="e.g. Kyoto, Japan"
                type="text"
                value={destination}
                onChange={(event) => setDestination(event.target.value)}
              />
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary">
                map
              </span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Duration (Days)
            </label>
            <div className="flex h-12 items-center justify-center rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
              {DURATION_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setDuration(option)}
                  className={`h-full grow rounded-lg px-2 text-sm font-medium transition-all ${
                    duration === option
                      ? "bg-white text-primary shadow-sm dark:bg-slate-700"
                      : "text-slate-500"
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Budget Level
            </label>
            <div className="grid grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setBudget("low")}
                className={`flex h-14 flex-col items-center justify-center rounded-xl border-2 transition-colors ${
                  budget === "low"
                    ? "border-primary bg-primary/5 dark:bg-primary/10"
                    : "border-slate-200 hover:border-primary/50 dark:border-slate-800"
                }`}
              >
                <span className={`text-lg font-bold ${budget === "low" ? "text-primary" : ""}`}>$</span>
                <span className={`text-[10px] ${budget === "low" ? "text-primary/70" : "text-slate-400"}`}>
                  Budget
                </span>
              </button>
              <button
                type="button"
                onClick={() => setBudget("mid")}
                className={`flex h-14 flex-col items-center justify-center rounded-xl border-2 transition-colors ${
                  budget === "mid"
                    ? "border-primary bg-primary/5 dark:bg-primary/10"
                    : "border-slate-200 hover:border-primary/50 dark:border-slate-800"
                }`}
              >
                <span className={`text-lg font-bold ${budget === "mid" ? "text-primary" : ""}`}>$$</span>
                <span className={`text-[10px] ${budget === "mid" ? "text-primary/70" : "text-slate-400"}`}>
                  Balanced
                </span>
              </button>
              <button
                type="button"
                onClick={() => setBudget("high")}
                className={`flex h-14 flex-col items-center justify-center rounded-xl border-2 transition-colors ${
                  budget === "high"
                    ? "border-primary bg-primary/5 dark:bg-primary/10"
                    : "border-slate-200 hover:border-primary/50 dark:border-slate-800"
                }`}
              >
                <span className={`text-lg font-bold ${budget === "high" ? "text-primary" : ""}`}>$$$</span>
                <span className={`text-[10px] ${budget === "high" ? "text-primary/70" : "text-slate-400"}`}>
                  Luxury
                </span>
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Travel Preferences
            </label>
            <div className="flex flex-wrap gap-2">
              {interests.map((interest) => (
                <button
                  key={interest}
                  type="button"
                  onClick={() => setInterests((prev) => prev.filter((value) => value !== interest))}
                  className="flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary"
                >
                  {interest}
                  <span className="material-symbols-outlined text-xs">close</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input
                className="h-10 flex-1 rounded-xl border-slate-200 bg-slate-50 px-3 text-sm outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 dark:border-slate-800 dark:bg-slate-900/50"
                placeholder="Add interest"
                value={interestDraft}
                onChange={(event) => setInterestDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addInterest();
                  }
                }}
              />
              <button
                type="button"
                onClick={addInterest}
                className="flex h-10 items-center gap-1 rounded-full bg-slate-100 px-3 text-sm font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                <span className="material-symbols-outlined text-sm">add</span>
                Add
              </button>
            </div>
          </div>

          <div className="space-y-3 pt-2">
            <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Things to avoid
            </label>
            <input
              className="h-12 w-full border-b-2 border-slate-100 bg-transparent px-1 text-base outline-none transition-all focus:border-primary dark:border-slate-800"
              placeholder="e.g. Crowds, Steep hills, Long walks"
              value={avoidText}
              onChange={(event) => setAvoidText(event.target.value)}
              type="text"
            />
          </div>

          <div className="space-y-3 pt-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Context &amp; Notes (AI Feed)
              </label>
              <span className="rounded bg-green-100 px-2 py-0.5 text-[10px] font-bold uppercase text-green-600 dark:bg-green-900/30 dark:text-green-400">
                RAG Enabled
              </span>
            </div>
            <div className="relative">
              <textarea
                className="min-h-[140px] w-full resize-none rounded-xl border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed outline-none transition-all focus:border-primary focus:ring-2 focus:ring-primary/20 dark:border-slate-800 dark:bg-slate-900/50"
                placeholder="Paste travel notes, TikTok links, or Pinterest board URLs. Our agent will analyze them to match your vibe..."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              <div className="absolute bottom-3 right-3 flex gap-2">
                <button
                  type="button"
                  className="flex size-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-800"
                >
                  <span className="material-symbols-outlined text-xl">link</span>
                </button>
                <button
                  type="button"
                  className="flex size-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-800"
                >
                  <span className="material-symbols-outlined text-xl">image</span>
                </button>
              </div>
            </div>
          </div>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>
      </main>

      <div className="fixed bottom-0 left-1/2 w-full max-w-[480px] -translate-x-1/2 bg-gradient-to-t from-white via-white/95 to-transparent p-6 dark:from-background-dark dark:via-background-dark/95 dark:to-transparent">
        <div className="mb-3 text-center">
          <p className="flex items-center justify-center gap-1 text-[10px] text-slate-400 dark:text-slate-500">
            <span className="material-symbols-outlined text-[12px]">info</span>
            AI is tailoring your unique itinerary based on 3 sources
          </p>
        </div>
        <button
          onClick={onGenerate}
          disabled={loading}
          className="flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-primary text-lg font-bold text-white shadow-lg shadow-primary/25 transition-all active:scale-[0.98] disabled:opacity-70"
        >
          <span>{loading ? "Generating..." : "Generate Itinerary"}</span>
          <span className="material-symbols-outlined">auto_awesome</span>
        </button>
        <div className="h-2" />
      </div>
    </>
  );
}
