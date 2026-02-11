import { Itinerary } from "@/lib/api";

type TripTimelineProps = {
  itinerary: Itinerary;
};

export function TripTimeline({ itinerary }: TripTimelineProps) {
  return (
    <section className="rounded-3xl bg-surface p-5 shadow-card md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-xl text-ink">Trip Timeline</h2>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
          {itinerary.city}
        </span>
      </div>
      <div className="mt-5 space-y-5">
        {itinerary.days.map((day) => (
          <article key={`${day.day}-${day.date}`} className="rounded-2xl border border-slate-200 p-4">
            <p className="text-sm font-semibold text-ink">
              Day {day.day} · {day.date}
            </p>
            <div className="mt-3 grid gap-3">
              {day.items.map((item) => (
                <div
                  key={item.slot_id}
                  className="grid gap-2 rounded-xl bg-slate-50 p-3 text-sm md:grid-cols-[120px_1fr_auto]"
                >
                  <div className="font-medium text-slate-700">
                    {item.start_time} - {item.end_time}
                  </div>
                  <div>
                    <p className="font-semibold text-ink">
                      {item.name}
                      <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs text-slate-600">
                        {item.category}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-slate-600">{item.notes}</p>
                  </div>
                  <div className="flex gap-2 self-start">
                    <button className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs">
                      Book
                    </button>
                    <button className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs">
                      Navigate
                    </button>
                    <button className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs">
                      Replace
                    </button>
                  </div>
                  <div className="md:col-start-2 md:flex md:gap-2">
                    <span className="text-xs text-slate-600">
                      crowd {item.crowd_index.toFixed(2)} / queue {item.queue_minutes}m
                    </span>
                    <span className="text-xs text-slate-600">tickets {item.ticket_left}</span>
                  </div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
