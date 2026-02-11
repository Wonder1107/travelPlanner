"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  getTrip,
  getTripVersions,
  rollbackTripVersion,
  sendDecisionFeedback,
  sendTripEvent,
  Itinerary,
  ItineraryItem,
  ItineraryVersion,
  ReplanDecision,
  ReplanMeta,
} from "@/lib/api";

type TimelineRow = ItineraryItem & { day: number; date: string };

export default function TripPage() {
  const params = useParams<{ id: string }>();
  const tripId = params.id ?? "";
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [latestDecision, setLatestDecision] = useState<ReplanDecision | null>(null);
  const [latestMeta, setLatestMeta] = useState<ReplanMeta | null>(null);
  const [latestDecisionId, setLatestDecisionId] = useState<string | null>(null);
  const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);
  const [versions, setVersions] = useState<ItineraryVersion[]>([]);
  const [currentVersion, setCurrentVersion] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const rows = useMemo<TimelineRow[]>(() => {
    if (!itinerary) return [];
    return itinerary.days.flatMap((day) =>
      day.items.map((item) => ({
        ...item,
        day: day.day,
        date: day.date,
      })),
    );
  }, [itinerary]);

  const currentIndex = rows.length > 1 ? 1 : 0;
  const completedItem = rows.length > 1 ? rows[0] : null;
  const currentItem = rows[currentIndex];
  const upcomingItems = rows.slice(currentIndex + 1);
  const progress = rows.length === 0 ? 0 : Math.round(((currentIndex + 1) / rows.length) * 100);
  const poiNameById = useMemo(() => {
    const index = new Map<string, string>();
    for (const row of rows) {
      index.set(String(row.poi_id), row.name);
    }
    return index;
  }, [rows]);

  async function loadTrip() {
    if (!tripId) return;
    try {
      const tripResponse = await getTrip(tripId);
      setItinerary(tripResponse.itinerary);
      setLatestDecision(null);
      setLatestMeta(null);
      setLatestDecisionId(null);
      setError(null);
      const versionResponse = await getTripVersions(tripId);
      setVersions(versionResponse.versions);
      setCurrentVersion(versionResponse.current_version);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load trip");
    }
  }

  useEffect(() => {
    void loadTrip();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tripId]);

  async function trigger(eventType: "weather" | "crowd" | "user_status", payload: Record<string, unknown>) {
    // 统一事件入口：按钮触发后由后端完成 monitor + replanner 并返回解释结果。
    if (!tripId) return;
    setLoading(true);
    try {
      const response = await sendTripEvent(tripId, {
        event_type: eventType,
        payload,
        source: "manual",
        occurred_at: new Date().toISOString(),
      });
      setItinerary(response.updated_itinerary);
      setAlerts(response.alerts);
      setLatestDecision(response.decision ?? null);
      setLatestMeta(response.meta ?? null);
      setLatestDecisionId(response.agent_log_id);
      setFeedbackNotice(null);
      const versionResponse = await getTripVersions(tripId);
      setVersions(versionResponse.versions);
      setCurrentVersion(versionResponse.current_version);
    } catch (triggerError) {
      setError(triggerError instanceof Error ? triggerError.message : "Failed to trigger event");
    } finally {
      setLoading(false);
    }
  }

  async function submitFeedback(accepted: boolean) {
    if (!tripId || !latestDecisionId) return;
    setLoading(true);
    try {
      const response = await sendDecisionFeedback(tripId, latestDecisionId, {
        accepted,
        reason: accepted ? "User accepted and applied the recommendation." : "User kept original plan.",
      });
      setFeedbackNotice(response.accepted ? "Feedback sent: accepted." : "Feedback sent: kept original plan.");
    } catch (feedbackError) {
      setError(feedbackError instanceof Error ? feedbackError.message : "Failed to send feedback");
    } finally {
      setLoading(false);
    }
  }

  async function rollbackVersion(versionId: number) {
    if (!tripId) return;
    setLoading(true);
    try {
      const response = await rollbackTripVersion(tripId, versionId);
      setItinerary(response.itinerary);
      setAlerts([`Rolled back to version ${response.restored_version}. Active version is now ${response.active_version}.`]);
      setLatestDecision(null);
      setLatestMeta(null);
      setLatestDecisionId(null);
      setFeedbackNotice(null);
      const versionResponse = await getTripVersions(tripId);
      setVersions(versionResponse.versions);
      setCurrentVersion(versionResponse.current_version);
    } catch (rollbackError) {
      setError(rollbackError instanceof Error ? rollbackError.message : "Failed to rollback version");
    } finally {
      setLoading(false);
    }
  }

  if (error) {
    return (
      <main className="p-6">
        <p className="text-red-600">{error}</p>
      </main>
    );
  }

  if (!itinerary) {
    return (
      <main className="p-6">
        <p className="text-slate-700">Loading itinerary...</p>
      </main>
    );
  }

  return (
    <>
      <header className="glass-morphism sticky top-0 z-30 border-b border-gray-200 bg-background-light/80 px-4 pb-2 pt-6 dark:border-gray-800 dark:bg-background-dark/80">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-xs font-bold uppercase tracking-wider text-primary">
              Day 1 of {itinerary.days.length}
            </span>
            <h1 className="text-xl font-bold dark:text-white">{itinerary.city} Adventure</h1>
          </div>
          <div className="flex gap-2">
            <button className="rounded-full bg-gray-100 p-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              <span className="material-symbols-outlined text-xl">map</span>
            </button>
            <Link
              href={`/console?tripId=${tripId}`}
              className="rounded-full bg-gray-100 p-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
            >
              <span className="material-symbols-outlined text-xl">more_horiz</span>
            </Link>
          </div>
        </div>

        <div className="flex flex-col gap-2 pb-4">
          <div className="flex items-end justify-between">
            <div className="flex items-center gap-1.5">
              <span className="flex h-2 w-2 animate-pulse rounded-full bg-green-500" />
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Agent Status: <span className="text-green-600 dark:text-green-400">On Track</span>
              </p>
            </div>
            <p className="text-xs font-semibold text-gray-500">{progress}% of today completed</p>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
            <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto px-4 py-6">
        {completedItem ? (
          <div className="mb-8 grid grid-cols-[32px_1fr] gap-4">
            <div className="flex flex-col items-center">
              <div className="z-10 flex size-8 items-center justify-center rounded-full bg-gray-200 text-gray-400 dark:bg-gray-800">
                <span className="material-symbols-outlined text-base">check</span>
              </div>
              <div className="my-2 w-0.5 flex-1 bg-gray-200 dark:bg-gray-800" />
            </div>
            <div className="pb-2 opacity-50">
              <p className="text-xs font-bold uppercase text-gray-500">{completedItem.start_time}</p>
              <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300">{completedItem.name}</h3>
              <p className="text-sm text-gray-500">
                Finished early • {completedItem.duration_minutes ?? 60}m spent
              </p>
            </div>
          </div>
        ) : null}

        {currentItem ? (
          <div className="mb-8 grid grid-cols-[32px_1fr] gap-4">
            <div className="flex flex-col items-center">
              <div className="z-10 flex size-8 items-center justify-center rounded-full bg-primary text-white ring-4 ring-primary/20">
                <span className="material-symbols-outlined text-base">camera_enhance</span>
              </div>
              <div className="timeline-line my-2 flex-1" />
            </div>
            <div className="relative rounded-xl border border-primary/30 bg-white p-4 shadow-sm dark:bg-gray-900">
              <div className="absolute -top-3 right-4 rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                Now
              </div>
              <p className="mb-2 text-xs font-bold uppercase text-primary">
                {currentItem.start_time} - {currentItem.end_time}
              </p>
              <h3 className="mb-3 text-lg font-bold text-[#0d141b] dark:text-white">{currentItem.name}</h3>
              <div className="flex flex-wrap gap-2">
                <div className="flex items-center gap-1 rounded bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                  <span className="material-symbols-outlined text-xs">wb_sunny</span>
                  <span>{currentItem.indoor ? "Indoor" : "Outdoor"}</span>
                </div>
                <div className="flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-[11px] font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">
                  <span className="material-symbols-outlined text-xs">groups</span>
                  <span>Crowd {currentItem.crowd_index.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-1 rounded bg-red-50 px-2 py-1 text-[11px] font-medium text-red-700 dark:bg-red-900/30 dark:text-red-300">
                  <span className="material-symbols-outlined text-xs">schedule</span>
                  <span>{currentItem.queue_minutes}m wait</span>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        {upcomingItems.slice(0, 2).map((item, index) => (
          <div key={`${item.slot_id}-${item.day}`} className={`grid grid-cols-[32px_1fr] gap-4 ${index === 1 ? "mb-16" : "mb-8"}`}>
            <div className="flex flex-col items-center">
              <div className="z-10 flex size-8 items-center justify-center rounded-full border-2 border-gray-200 bg-white text-gray-400 dark:border-gray-700 dark:bg-gray-800">
                <span className="material-symbols-outlined text-base">
                  {index === 0 ? "restaurant" : "park"}
                </span>
              </div>
              {index === 0 ? <div className="timeline-line my-2 flex-1" /> : null}
            </div>
            <div className="rounded-xl border border-gray-100 bg-white/50 p-4 dark:border-gray-800 dark:bg-gray-900/50">
              <p className="mb-1 text-xs font-bold uppercase text-gray-400">{item.start_time}</p>
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">{item.name}</h3>
              {index === 0 ? (
                <div className="mt-2 flex items-center gap-3 text-gray-500 dark:text-gray-400">
                  <div className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">cloud</span>
                    <span className="text-xs">Rain in 1h</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">confirmation_number</span>
                    <span className="text-xs">Booking ready</span>
                  </div>
                </div>
              ) : (
                <p className="mt-1 text-xs italic text-gray-500">
                  Agent Suggestion: May want to swap for an indoor stop if raining.
                </p>
              )}
            </div>
          </div>
        ))}

        {alerts.length > 0 ? (
          <section className="mb-8 rounded-lg border border-red-100 bg-red-50 p-3 dark:border-red-900/30 dark:bg-red-900/10">
            <p className="text-xs font-bold uppercase text-red-600 dark:text-red-400">Replanner Alert</p>
            <ul className="mt-2 space-y-1 text-xs text-red-700 dark:text-red-300">
              {alerts.map((alert) => (
                <li key={alert}>{alert}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {latestDecision ? (
          <section className="mb-8 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Decision Evidence</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                  latestMeta?.decision_source === "llm"
                    ? "bg-primary/10 text-primary"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                }`}
              >
                {/* 与后端 ReplanMeta.decision_source 对齐：展示 LLM / Fallback 来源。 */}
                {latestMeta?.decision_source === "llm" ? "LLM" : "Fallback"}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Why changed</p>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">{latestDecision.primary_reason}</p>

            <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-950">
              <p className="font-semibold text-slate-600 dark:text-slate-300">Updated action</p>
              <p className="mt-1 text-slate-700 dark:text-slate-200">{latestDecision.user_message}</p>
              <p className="mt-1 text-slate-500 dark:text-slate-400">
                Selected:{" "}
                <span className="font-semibold text-slate-700 dark:text-slate-200">
                  {latestDecision.selected_poi_id
                    ? poiNameById.get(latestDecision.selected_poi_id) ?? latestDecision.selected_poi_id
                    : "No replacement selected"}
                </span>
              </p>
            </div>

            {latestDecision.alternatives.length > 0 ? (
              <p className="mt-3 text-xs text-slate-600 dark:text-slate-300">
                Alternatives: {latestDecision.alternatives.join(" / ")}
              </p>
            ) : null}

            {latestDecision.tradeoffs.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-600 dark:text-slate-300">
                {latestDecision.tradeoffs.map((tradeoff) => (
                  <li key={tradeoff}>{tradeoff}</li>
                ))}
              </ul>
            ) : null}

            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
              {/* 直接映射 decision/meta 字段，提升重规划可解释性。 */}
              <span>confidence {(latestDecision.confidence * 100).toFixed(0)}%</span>
              {latestMeta?.latency_ms ? <span>latency {latestMeta.latency_ms}ms</span> : null}
              {latestMeta?.fallback_used ? <span>fallback used</span> : null}
              {latestMeta?.critic_passed !== undefined ? (
                <span>{latestMeta.critic_passed ? "critic passed" : "critic flagged"}</span>
              ) : null}
              {latestMeta?.itinerary_version ? <span>version v{latestMeta.itinerary_version}</span> : null}
              {latestMeta?.prompt_variant ? <span>prompt {latestMeta.prompt_variant}</span> : null}
              {latestMeta?.error ? <span>error: {latestMeta.error}</span> : null}
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                disabled={loading || !latestDecisionId}
                onClick={() => void submitFeedback(true)}
                className="rounded-full bg-green-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-70"
              >
                Accept Suggestion
              </button>
              <button
                disabled={loading || !latestDecisionId}
                onClick={() => void submitFeedback(false)}
                className="rounded-full bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-70 dark:bg-slate-700 dark:text-slate-200"
              >
                Keep Original Plan
              </button>
              {feedbackNotice ? <span className="text-xs text-slate-500">{feedbackNotice}</span> : null}
            </div>
          </section>
        ) : null}

        {versions.length > 0 ? (
          <section className="mb-8 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Version History</p>
              <span className="text-[11px] text-slate-500">Current v{currentVersion}</span>
            </div>
            <div className="space-y-2">
              {versions
                .slice()
                .reverse()
                .slice(0, 5)
                .map((version) => (
                  <div
                    key={`${version.version_id}-${version.created_at}`}
                    className="flex items-center justify-between rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-800"
                  >
                    <div>
                      <p className="font-semibold text-slate-700 dark:text-slate-200">v{version.version_id}</p>
                      <p className="text-slate-500 dark:text-slate-400">{version.diff_summary}</p>
                    </div>
                    {version.version_id !== currentVersion ? (
                      <button
                        disabled={loading}
                        onClick={() => void rollbackVersion(version.version_id)}
                        className="rounded-full bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-700 disabled:opacity-70 dark:bg-amber-900/30 dark:text-amber-300"
                      >
                        Rollback
                      </button>
                    ) : (
                      <span className="text-[11px] text-emerald-600 dark:text-emerald-400">Active</span>
                    )}
                  </div>
                ))}
            </div>
          </section>
        ) : null}
      </main>

      <div className="fixed bottom-28 right-4 z-40">
        <Link
          href={`/console?tripId=${tripId}`}
          className="flex size-14 items-center justify-center rounded-full bg-primary text-white shadow-lg transition-transform hover:scale-105 active:scale-95"
        >
          <span className="material-symbols-outlined text-3xl">smart_toy</span>
        </Link>
      </div>

      <footer className="glass-morphism sticky bottom-0 z-50 border-t border-gray-100 bg-white/80 px-4 pb-8 pt-4 dark:border-gray-800 dark:bg-gray-950/80">
        <div className="mb-3 flex items-center justify-between px-1">
          <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
            Quick AI Re-planning
          </span>
          <span className="flex items-center gap-1 text-[10px] font-bold text-primary">
            AGENT ACTIVE <span className="size-1 animate-pulse rounded-full bg-primary" />
          </span>
        </div>
        <div className="no-scrollbar flex gap-3 overflow-x-auto pb-2">
          <button
            disabled={loading}
            onClick={() => trigger("user_status", { status: "tired", duration_minutes: 140 })}
            className="flex h-11 shrink-0 items-center justify-center gap-x-2 rounded-xl bg-gray-100 pl-3 pr-4 transition-colors active:bg-gray-200 disabled:opacity-70 dark:bg-gray-800"
          >
            <div className="text-primary">
              <span className="material-symbols-outlined text-xl">bedtime</span>
            </div>
            <p className="whitespace-nowrap text-sm font-semibold text-[#0d141b] dark:text-white">I am tired</p>
          </button>
          <button
            disabled={loading}
            onClick={() => trigger("user_status", { status: "hungry", duration_minutes: 130 })}
            className="flex h-11 shrink-0 items-center justify-center gap-x-2 rounded-xl bg-gray-100 pl-3 pr-4 transition-colors active:bg-gray-200 disabled:opacity-70 dark:bg-gray-800"
          >
            <div className="text-primary">
              <span className="material-symbols-outlined text-xl">restaurant</span>
            </div>
            <p className="whitespace-nowrap text-sm font-semibold text-[#0d141b] dark:text-white">I am hungry</p>
          </button>
          <button
            disabled={loading}
            onClick={() => trigger("weather", { condition: "rain" })}
            className="flex h-11 shrink-0 items-center justify-center gap-x-2 rounded-xl border border-blue-200 bg-blue-50 pl-3 pr-4 dark:border-blue-700/50 dark:bg-blue-900/30"
          >
            <div className="text-primary">
              <span className="material-symbols-outlined text-xl">cloud</span>
            </div>
            <p className="whitespace-nowrap text-sm font-semibold text-[#0d141b] dark:text-white">It&apos;s raining</p>
          </button>
          <button
            disabled={loading}
            onClick={() => trigger("crowd", { crowd_index: 0.93, queue_minutes: 120 })}
            className="flex h-11 shrink-0 items-center justify-center gap-x-2 rounded-xl bg-gray-100 pl-3 pr-4 transition-colors active:bg-gray-200 disabled:opacity-70 dark:bg-gray-800"
          >
            <div className="text-primary">
              <span className="material-symbols-outlined text-xl">fast_forward</span>
            </div>
            <p className="whitespace-nowrap text-sm font-semibold text-[#0d141b] dark:text-white">Skip next</p>
          </button>
        </div>
        <div className="mt-4 flex justify-center">
          <div className="h-1.5 w-32 rounded-full bg-gray-300 dark:bg-gray-700" />
        </div>
      </footer>
    </>
  );
}
