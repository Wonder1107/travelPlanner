"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { createTrip } from "@/lib/api";

const DEFAULT_PREFS = ["museum", "coffee", "nightwalk"];

export function OnboardingPanel() {
  const router = useRouter();
  const [city, setCity] = useState("Shanghai");
  const [days, setDays] = useState(2);
  const [budgetLevel, setBudgetLevel] = useState<"low" | "mid" | "high">("mid");
  const [pace, setPace] = useState<"slow" | "balanced" | "fast">("slow");
  const [preferencesText, setPreferencesText] = useState(DEFAULT_PREFS.join(","));
  const [avoidText, setAvoidText] = useState("kids");
  const [travelNote, setTravelNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preferences = useMemo(
    () =>
      preferencesText
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [preferencesText],
  );

  const avoid = useMemo(
    () =>
      avoidText
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [avoidText],
  );

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await createTrip({
        city,
        days,
        budget_level: budgetLevel,
        preferences,
        avoid,
        pace,
        travel_note: travelNote,
      });
      router.push(`/trip/${result.trip_id}`);
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Failed to create trip. Please retry.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-5xl rounded-3xl bg-surface p-6 shadow-card md:p-10">
      <p className="font-serif text-2xl text-ink md:text-3xl">
        Dynamic Smart Itinerary Engine
      </p>
      <p className="mt-2 max-w-2xl text-sm text-slate-600">
        Plan once, adapt all the way. This MVP focuses on city weekend trips and
        real-time replanning with RAG + Agent workflows.
      </p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">
          Prompt Engineering
        </span>
        <span className="rounded-full bg-cyan-50 px-3 py-1 text-cyan-700">RAG Retrieval</span>
        <span className="rounded-full bg-orange-50 px-3 py-1 text-orange-700">Agent Replan</span>
      </div>

      <form className="mt-7 grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
        <label className="flex flex-col gap-2 text-sm">
          City
          <input
            className="rounded-xl border border-slate-200 px-3 py-2"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-2 text-sm">
          Days (1-3)
          <input
            className="rounded-xl border border-slate-200 px-3 py-2"
            type="number"
            min={1}
            max={3}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-2 text-sm">
          Budget
          <select
            className="rounded-xl border border-slate-200 px-3 py-2"
            value={budgetLevel}
            onChange={(e) => setBudgetLevel(e.target.value as "low" | "mid" | "high")}
          >
            <option value="low">low</option>
            <option value="mid">mid</option>
            <option value="high">high</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          Pace
          <select
            className="rounded-xl border border-slate-200 px-3 py-2"
            value={pace}
            onChange={(e) => setPace(e.target.value as "slow" | "balanced" | "fast")}
          >
            <option value="slow">slow</option>
            <option value="balanced">balanced</option>
            <option value="fast">fast</option>
          </select>
        </label>

        <label className="md:col-span-2 flex flex-col gap-2 text-sm">
          Preferences (comma separated)
          <input
            className="rounded-xl border border-slate-200 px-3 py-2"
            value={preferencesText}
            onChange={(e) => setPreferencesText(e.target.value)}
          />
        </label>

        <label className="md:col-span-2 flex flex-col gap-2 text-sm">
          Avoid tags (comma separated)
          <input
            className="rounded-xl border border-slate-200 px-3 py-2"
            value={avoidText}
            onChange={(e) => setAvoidText(e.target.value)}
          />
        </label>

        <label className="md:col-span-2 flex flex-col gap-2 text-sm">
          Notes / Xiaohongshu snippets / image URLs
          <textarea
            className="min-h-24 rounded-xl border border-slate-200 px-3 py-2"
            placeholder="Paste your travel notes, links, mood words..."
            value={travelNote}
            onChange={(e) => setTravelNote(e.target.value)}
          />
        </label>

        <div className="md:col-span-2 flex items-center gap-4">
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {loading ? "Generating..." : "Generate 2-3 Day Trip"}
          </button>
          <span className="text-xs text-slate-500">
            Output includes one dynamic replan-ready timeline.
          </span>
        </div>
      </form>
      {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
    </section>
  );
}
