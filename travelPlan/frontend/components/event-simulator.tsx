type EventSimulatorProps = {
  onWeather: () => Promise<void>;
  onCrowd: () => Promise<void>;
  onTired: () => Promise<void>;
  loading: boolean;
};

export function EventSimulator({
  onWeather,
  onCrowd,
  onTired,
  loading,
}: EventSimulatorProps) {
  return (
    <section className="rounded-3xl bg-surface p-5 shadow-card md:p-6">
      <h3 className="font-serif text-xl text-ink">Live Replan Simulator</h3>
      <p className="mt-1 text-sm text-slate-600">
        Trigger real-world events and inspect how the itinerary adapts.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          disabled={loading}
          onClick={onWeather}
          className="rounded-xl bg-warm px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          Simulate Rain
        </button>
        <button
          disabled={loading}
          onClick={onCrowd}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          Simulate Overcrowded Queue
        </button>
        <button
          disabled={loading}
          onClick={onTired}
          className="rounded-xl bg-slate-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
        >
          Simulate User Tired
        </button>
      </div>
    </section>
  );
}
