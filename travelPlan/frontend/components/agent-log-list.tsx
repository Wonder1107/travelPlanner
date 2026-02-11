import { AgentLog } from "@/lib/api";

type AgentLogListProps = {
  logs: AgentLog[];
};

export function AgentLogList({ logs }: AgentLogListProps) {
  return (
    <section className="rounded-3xl bg-surface p-5 shadow-card md:p-6">
      <h3 className="font-serif text-xl text-ink">Agent Trace</h3>
      <p className="mt-1 text-sm text-slate-600">
        Planner / Monitor / Replanner tool invocations and decision rationale.
      </p>
      <div className="mt-4 space-y-3">
        {logs.length === 0 ? (
          <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-600">No logs yet.</p>
        ) : (
          logs.map((log) => (
            <article key={log.id} className="rounded-xl border border-slate-200 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{log.stage}</span>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                  {log.tool_name ?? "unknown-tool"}
                </span>
                <span className="text-xs text-slate-500">{log.created_at}</span>
              </div>
              <p className="mt-2 text-slate-700">{log.message}</p>
              {log.payload ? (
                <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-2 text-xs text-slate-100">
                  {JSON.stringify(log.payload, null, 2)}
                </pre>
              ) : null}
            </article>
          ))
        )}
      </div>
    </section>
  );
}
