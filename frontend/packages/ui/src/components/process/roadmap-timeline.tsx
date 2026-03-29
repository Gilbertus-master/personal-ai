'use client';

export interface RoadmapTimelineProps {
  roadmap: { quarter: string; items: { name: string; [key: string]: unknown }[] }[];
  labelKey?: string;
}

export function RoadmapTimeline({ roadmap, labelKey = 'name' }: RoadmapTimelineProps) {
  if (roadmap.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--text-secondary)]">
        Brak danych roadmapy
      </div>
    );
  }

  return (
    <div className="relative space-y-0">
      {roadmap.map((group, gi) => (
        <div key={group.quarter} className="relative flex gap-6 pb-6 last:pb-0">
          {/* Vertical connecting line */}
          {gi < roadmap.length - 1 && (
            <div className="absolute left-[59px] top-6 bottom-0 w-px bg-[var(--border)]" />
          )}

          {/* Quarter label */}
          <div className="flex w-[120px] shrink-0 items-start pt-0.5">
            <span className="rounded-md bg-[var(--accent)]/10 px-2.5 py-1 text-xs font-semibold text-[var(--accent)]">
              {group.quarter}
            </span>
          </div>

          {/* Items */}
          <div className="flex-1 space-y-2">
            {group.items.map((item, ii) => {
              const label = String(item[labelKey] ?? item.name ?? '');
              return (
                <div
                  key={`${group.quarter}-${ii}`}
                  className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 transition-colors hover:bg-[var(--surface-hover)]"
                >
                  <p className="text-sm font-medium text-[var(--text)]">{label}</p>
                  {/* Show additional metadata keys (excluding the label key and name) */}
                  {Object.entries(item)
                    .filter(([k]) => k !== labelKey && k !== 'name' && typeof item[k] !== 'object')
                    .slice(0, 3)
                    .map(([k, v]) => (
                      <span key={k} className="mr-3 text-[10px] text-[var(--text-secondary)]">
                        {k}: {String(v)}
                      </span>
                    ))}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
