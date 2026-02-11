"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getTripLogs, sendTripEvent, AgentLog } from "@/lib/api";

type DecisionLogSummary = {
  decisionSource?: "llm" | "fallback_rule";
  fallbackUsed?: boolean;
  latencyMs?: number;
  model?: string;
  decisionReason?: string;
  decisionMessage?: string;
};

function readDecisionSummary(log: AgentLog): DecisionLogSummary {
  // 从后端 replan_done 日志里提取结构化决策摘要，供 UI 统计与展示。
  const payload = log.payload;
  if (!payload) return {};
  const decisionSource = payload.decision_source;
  const fallbackUsed = payload.fallback_used;
  const latencyMs = payload.latency_ms;
  const model = payload.model;
  const decision = payload.decision;
  if (decisionSource !== "llm" && decisionSource !== "fallback_rule") {
    return {};
  }
  const decisionObject = typeof decision === "object" && decision !== null ? decision : {};
  const reason =
    typeof (decisionObject as Record<string, unknown>).primary_reason === "string"
      ? ((decisionObject as Record<string, unknown>).primary_reason as string)
      : undefined;
  const message =
    typeof (decisionObject as Record<string, unknown>).user_message === "string"
      ? ((decisionObject as Record<string, unknown>).user_message as string)
      : undefined;
  return {
    decisionSource,
    fallbackUsed: typeof fallbackUsed === "boolean" ? fallbackUsed : undefined,
    latencyMs: typeof latencyMs === "number" ? latencyMs : undefined,
    model: typeof model === "string" ? model : undefined,
    decisionReason: reason,
    decisionMessage: message,
  };
}

export function ConsoleClient() {
  const searchParams = useSearchParams();
  const [tripId, setTripId] = useState(searchParams.get("tripId") ?? "");
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [status, setStatus] = useState("Enter trip id and load logs.");
  const [loading, setLoading] = useState(false);

  const canRun = useMemo(() => tripId.trim().length > 0, [tripId]);
  const ragHits = useMemo(
    // 统计 search_poi_rag 次数，用于观察 RAG 工具调用频次。
    () => logs.filter((log) => String(log.tool_name ?? "").includes("search_poi_rag")).length,
    [logs],
  );
  const decisionSummaries = useMemo(
    () =>
      logs
        .map((log) => ({ log, summary: readDecisionSummary(log) }))
        .filter((item) => item.summary.decisionSource),
    [logs],
  );
  const llmDecisionCount = useMemo(
    () => decisionSummaries.filter((item) => item.summary.decisionSource === "llm").length,
    [decisionSummaries],
  );
  const fallbackCount = useMemo(
    // 统计降级次数：可直观看到系统韧性是否在“吃 fallback”。
    () => decisionSummaries.filter((item) => item.summary.fallbackUsed).length,
    [decisionSummaries],
  );
  const latestDecisionSummary = useMemo(
    () => decisionSummaries[decisionSummaries.length - 1]?.summary,
    [decisionSummaries],
  );
  const replanLogs = useMemo(
    () => logs.filter((log) => String(log.tool_name ?? "") === "replan_done"),
    [logs],
  );
  const avgReplanLatency = useMemo(() => {
    const latencies = replanLogs
      .map((log) => (typeof log.payload?.latency_ms === "number" ? log.payload.latency_ms : null))
      .filter((item): item is number => item !== null);
    if (latencies.length === 0) return 0;
    return Math.round(latencies.reduce((sum, item) => sum + item, 0) / latencies.length);
  }, [replanLogs]);
  const criticPassRate = useMemo(() => {
    if (replanLogs.length === 0) return 0;
    const passed = replanLogs.filter((log) => log.payload?.critic_passed === true).length;
    return Math.round((passed / replanLogs.length) * 100);
  }, [replanLogs]);
  const feedbackLogs = useMemo(
    () => logs.filter((log) => String(log.tool_name ?? "") === "decision_feedback"),
    [logs],
  );
  const acceptanceRate = useMemo(() => {
    if (feedbackLogs.length === 0) return 0;
    const accepted = feedbackLogs.filter((log) => log.payload?.accepted === true).length;
    return Math.round((accepted / feedbackLogs.length) * 100);
  }, [feedbackLogs]);
  const rollbackCount = useMemo(
    () => logs.filter((log) => String(log.tool_name ?? "") === "version_rollback").length,
    [logs],
  );

  async function loadLogs() {
    if (!canRun) return;
    setLoading(true);
    try {
      const response = await getTripLogs(tripId.trim());
      setLogs(response.logs);
      setStatus(`Loaded ${response.logs.length} logs.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load logs.");
    } finally {
      setLoading(false);
    }
  }

  async function simulate(eventType: "weather" | "crowd" | "user_status", payload: Record<string, unknown>) {
    // 与 Trip 页保持一致：通过同一事件接口驱动后端 Monitor/Replanner。
    if (!canRun) return;
    setLoading(true);
    try {
      await sendTripEvent(tripId.trim(), { event_type: eventType, payload });
      await loadLogs();
      setStatus(`Triggered ${eventType} and refreshed logs.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Simulation failed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canRun) {
      void loadLogs();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const traceLogs = logs.slice(-8).reverse();

  return (
    <>
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-background-light/80 backdrop-blur-md dark:border-slate-800 dark:bg-background-dark/80">
        <div className="mx-auto flex max-w-md items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center rounded-lg bg-primary/10 p-2 text-primary">
              <span className="material-symbols-outlined text-2xl">terminal</span>
            </div>
            <div>
              <h1 className="text-lg font-bold leading-none">Agent Console</h1>
              <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-slate-500 dark:text-slate-400">
                v2.4.0 • Live Trace
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setLogs([])} className="p-2 text-slate-500 transition-colors hover:text-red-500">
              <span className="material-symbols-outlined">delete_sweep</span>
            </button>
            <button className="p-2 text-slate-500">
              <span className="material-symbols-outlined">settings</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-md pb-32">
        <div className="grid grid-cols-3 gap-3 p-4">
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">RAG Hits</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{ragHits}</span>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">Fallback</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{fallbackCount}</span>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">Avg Latency</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">
              {avgReplanLatency > 0 ? `${avgReplanLatency}ms` : "--"}
            </span>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">Accept Rate</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{acceptanceRate}%</span>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">Critic Pass</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{criticPassRate}%</span>
          </div>
          <div className="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <span className="text-[10px] font-bold uppercase text-slate-400">Rollbacks</span>
            <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{rollbackCount}</span>
          </div>
        </div>

        {latestDecisionSummary ? (
          <section className="px-4 pb-2">
            <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Decision Snapshot</p>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                    latestDecisionSummary.decisionSource === "llm"
                      ? "bg-primary/10 text-primary"
                      : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                  }`}
                >
                  {latestDecisionSummary.decisionSource === "llm" ? "LLM" : "Fallback"}
                </span>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-300">
                {latestDecisionSummary.decisionReason ?? "No structured reason found."}
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {latestDecisionSummary.decisionMessage ?? "No user message recorded."}
              </p>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                model {latestDecisionSummary.model ?? "n/a"} · llm {llmDecisionCount} · fallback {fallbackCount} · accept{" "}
                {acceptanceRate}%
              </p>
            </div>
          </section>
        ) : null}

        <div className="px-4 pb-2">
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="h-11 flex-1 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-primary dark:border-slate-800 dark:bg-slate-900"
              value={tripId}
              placeholder="Paste trip id"
              onChange={(e) => setTripId(e.target.value)}
            />
            <button
              disabled={!canRun || loading}
              onClick={() => void loadLogs()}
              className="h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-white disabled:opacity-70"
            >
              Load
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">{status}</p>
        </div>

        <section className="mb-6 px-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Planner Logic</h3>
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">GPT-4o</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            <div className="border-b border-slate-100 p-4 dark:border-slate-800">
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-xl text-primary">psychology</span>
                <div>
                  <p className="text-sm font-medium">Objective: Weekend Smart Trip Planning</p>
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                    Constraints: preference alignment, weather sensitivity, and realistic queue handling.
                  </p>
                </div>
              </div>
            </div>
            <div className="space-y-2 bg-slate-50 p-4 font-mono text-[11px] dark:bg-slate-950">
              <div className="flex gap-2">
                <span className="text-slate-400">01</span>
                <span className="text-primary">PLAN:</span>
                <span>Generate timeline from RAG candidate pool</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-400">02</span>
                <span className="text-primary">VERIFY:</span>
                <span>Check event trigger thresholds and constraints</span>
              </div>
              <div className="flex gap-2">
                <span className="text-slate-400">03</span>
                <span className="text-primary">EXEC:</span>
                <span>Update itinerary with replanner decision</span>
              </div>
            </div>
          </div>
        </section>

        <section className="mb-6 px-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Live Agent Trace</h3>
            <div className="flex items-center gap-1">
              <div className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700" />
              <span className="text-[10px] text-slate-400">Updated just now</span>
            </div>
          </div>
          <div className="space-y-3">
            {traceLogs.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                No logs yet. Trigger an event to inspect live trace.
              </div>
            ) : (
              traceLogs.map((log, index) => {
                const isAlert = log.stage === "replanner" && log.message.toLowerCase().includes("replan");
                const summary = readDecisionSummary(log);
                return (
                  <div key={log.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-full ${
                          isAlert ? "bg-red-500/10" : index % 2 === 0 ? "bg-primary/10" : "bg-orange-500/10"
                        }`}
                      >
                        <span
                          className={`material-symbols-outlined text-sm ${
                            isAlert ? "text-red-500" : index % 2 === 0 ? "text-primary" : "text-orange-500"
                          }`}
                        >
                          {isAlert ? "emergency_home" : index % 2 === 0 ? "map" : "database"}
                        </span>
                      </div>
                      {index !== traceLogs.length - 1 ? <div className="my-1 h-full w-px bg-slate-200 dark:bg-slate-800" /> : null}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="mb-1 flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-bold ${isAlert ? "text-red-500" : ""}`}>
                            {log.stage.toUpperCase()}: {log.tool_name ?? "unknown_tool"}
                          </span>
                          {summary.decisionSource ? (
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                                summary.decisionSource === "llm"
                                  ? "bg-primary/10 text-primary"
                                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                              }`}
                            >
                              {summary.decisionSource === "llm" ? "LLM" : "Fallback"}
                            </span>
                          ) : null}
                        </div>
                        <span className="font-mono text-[10px] text-slate-400">{log.created_at.slice(11, 19)}</span>
                      </div>
                      <div
                        className={`rounded-lg border p-3 ${
                          isAlert
                            ? "border-red-100 bg-red-50 dark:border-red-900/30 dark:bg-red-900/10"
                            : "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
                        }`}
                      >
                        <p
                          className={`font-mono text-xs leading-relaxed ${
                            isAlert ? "text-red-700 dark:text-red-400" : "text-slate-600 dark:text-slate-400"
                          }`}
                        >
                          {log.message}
                        </p>
                        {summary.decisionReason ? (
                          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{summary.decisionReason}</p>
                        ) : null}
                        {log.payload ? (
                          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap font-mono text-[11px] text-slate-500 dark:text-slate-400">
                            {JSON.stringify(log.payload, null, 2)}
                          </pre>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </main>

      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white/80 pb-8 pt-4 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-900/80">
        <div className="mx-auto max-w-md px-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="material-symbols-outlined text-sm text-slate-500">science</span>
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Simulate Environment Event
            </span>
          </div>
          <div className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4">
            <button
              disabled={!canRun || loading}
              onClick={() => void simulate("weather", { condition: "rain" })}
              className="flex shrink-0 items-center gap-2 rounded-xl border border-transparent bg-slate-100 px-4 py-2.5 transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary disabled:opacity-70 dark:bg-slate-800"
            >
              <span className="material-symbols-outlined text-lg">rainy</span>
              <span className="whitespace-nowrap text-sm font-semibold">Simulate Rain</span>
            </button>
            <button
              disabled={!canRun || loading}
              onClick={() => void simulate("crowd", { crowd_index: 0.95, queue_minutes: 130 })}
              className="flex shrink-0 items-center gap-2 rounded-xl border border-transparent bg-slate-100 px-4 py-2.5 transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary disabled:opacity-70 dark:bg-slate-800"
            >
              <span className="material-symbols-outlined text-lg">traffic</span>
              <span className="whitespace-nowrap text-sm font-semibold">Heavy Traffic</span>
            </button>
            <button
              disabled={!canRun || loading}
              onClick={() => void simulate("user_status", { status: "tired", duration_minutes: 150 })}
              className="flex shrink-0 items-center gap-2 rounded-xl border border-transparent bg-slate-100 px-4 py-2.5 transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary disabled:opacity-70 dark:bg-slate-800"
            >
              <span className="material-symbols-outlined text-lg">hotel_class</span>
              <span className="whitespace-nowrap text-sm font-semibold">User Is Tired</span>
            </button>
            <button
              disabled={!canRun || loading}
              onClick={() => void simulate("user_status", { status: "hungry", duration_minutes: 130 })}
              className="flex shrink-0 items-center gap-2 rounded-xl border border-transparent bg-slate-100 px-4 py-2.5 transition-all hover:border-primary/20 hover:bg-primary/10 hover:text-primary disabled:opacity-70 dark:bg-slate-800"
            >
              <span className="material-symbols-outlined text-lg">attach_money</span>
              <span className="whitespace-nowrap text-sm font-semibold">I Am Hungry</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
