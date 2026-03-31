# TASK T11: Data Coverage Dashboard
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T11.done

## Context
Currently there's no visibility into which months/sources have data gaps.
We know 2023 H1 is sparse, but there's no visual overview.
Need: backend heatmap endpoint + frontend page showing coverage per source/month.

## What to do

### Step 1: Add /coverage/heatmap endpoint to main.py

Find a good place (near other analytics endpoints) in app/api/main.py and add:

```python
@app.get("/coverage/heatmap")
def coverage_heatmap(
    years: int = 3,
    source_types: str | None = None,
) -> dict:
    """Return document count per source_type per year-month for coverage visualization."""
    try:
        source_filter = ""
        params: list = [years]
        if source_types:
            types = [t.strip() for t in source_types.split(",")]
            placeholders = ",".join(["%s"] * len(types))
            source_filter = f"AND s.source_type IN ({placeholders})"
            params = types + params

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        s.source_type,
                        TO_CHAR(d.created_at, 'YYYY-MM') as year_month,
                        COUNT(d.id) as doc_count
                    FROM documents d
                    JOIN sources s ON s.id = d.source_id
                    WHERE d.created_at >= NOW() - (%s || ' years')::interval
                    {source_filter}
                    GROUP BY s.source_type, year_month
                    ORDER BY year_month, s.source_type
                """, params)
                rows = cur.fetchall()

        # Organize into heatmap structure
        from collections import defaultdict
        heatmap: dict = defaultdict(dict)
        all_months: set = set()
        all_types: set = set()

        for source_type, year_month, count in rows:
            heatmap[source_type][year_month] = count
            all_months.add(year_month)
            all_types.add(source_type)

        # Sort months
        sorted_months = sorted(all_months)

        return {
            "months": sorted_months,
            "source_types": sorted(all_types),
            "data": {st: heatmap[st] for st in sorted(all_types)},
            "thresholds": {"low": 10, "medium": 50, "high": 200},
        }
    except Exception as e:
        return {"error": str(e)}
```

### Step 2: Test backend endpoint
```
systemctl --user restart gilbertus-api
sleep 3
curl -s http://127.0.0.1:8000/coverage/heatmap | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('months:', len(d.get('months', [])))
print('source_types:', d.get('source_types', []))
print('first month data:', list(d.get('data', {}).items())[:2])
"
```

### Step 3: Add coverage page to frontend

First, find the app structure:
```
ls /home/sebastian/personal-ai/frontend/apps/web/app/\(app\)/
```

Create a new page. Find a logical place (e.g., under intelligence or a new data section).

Create `/home/sebastian/personal-ai/frontend/apps/web/app/(app)/data-coverage/page.tsx`:

```tsx
'use client';

import { useEffect, useState } from 'react';

interface HeatmapData {
  months: string[];
  source_types: string[];
  data: Record<string, Record<string, number>>;
  thresholds: { low: number; medium: number; high: number };
}

const SOURCE_LABELS: Record<string, string> = {
  email: 'Email',
  teams: 'Teams',
  whatsapp: 'WhatsApp',
  whatsapp_live: 'WA Live',
  audio_transcript: 'Audio',
  chatgpt: 'ChatGPT',
  document: 'Dokumenty',
  spreadsheet: 'Arkusze',
  calendar: 'Kalendarz',
  claude_code_full: 'Claude Code',
};

function getCellColor(count: number, thresholds: HeatmapData['thresholds']): string {
  if (count === 0) return 'bg-red-950 text-red-400';
  if (count < thresholds.low) return 'bg-red-900/60 text-red-300';
  if (count < thresholds.medium) return 'bg-yellow-900/60 text-yellow-300';
  return 'bg-green-900/60 text-green-300';
}

export default function DataCoveragePage() {
  const [data, setData] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [years, setYears] = useState(3);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/proxy/coverage/heatmap?years=${years}`)
      .then(r => r.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [years]);

  if (loading) return <div className="p-8 text-[var(--text-muted)]">Ładowanie...</div>;
  if (!data || data.error) return <div className="p-8 text-red-400">Błąd pobierania danych</div>;

  const recentMonths = data.months.slice(-24); // last 24 months

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Pokrycie danych</h1>
          <p className="text-[var(--text-muted)] text-sm mt-1">
            Ile dokumentów mamy per źródło per miesiąc
          </p>
        </div>
        <select
          value={years}
          onChange={e => setYears(Number(e.target.value))}
          className="px-3 py-1.5 rounded-md bg-[var(--surface-secondary)] text-sm border border-[var(--border)]"
        >
          <option value={1}>Ostatni rok</option>
          <option value={2}>Ostatnie 2 lata</option>
          <option value={3}>Ostatnie 3 lata</option>
        </select>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs">
        <span className="px-2 py-1 rounded bg-red-950 text-red-400">0 — brak</span>
        <span className="px-2 py-1 rounded bg-red-900/60 text-red-300">1-9 — minimalne</span>
        <span className="px-2 py-1 rounded bg-yellow-900/60 text-yellow-300">10-49 — częściowe</span>
        <span className="px-2 py-1 rounded bg-green-900/60 text-green-300">50+ — dobre</span>
      </div>

      {/* Heatmap */}
      <div className="overflow-x-auto">
        <table className="text-xs border-collapse min-w-max">
          <thead>
            <tr>
              <th className="text-left px-2 py-1 text-[var(--text-muted)] w-28">Źródło</th>
              {recentMonths.map(m => (
                <th key={m} className="px-1 py-1 text-[var(--text-muted)] text-center min-w-[36px]">
                  {m.slice(5)} {/* MM only */}
                  <br />
                  <span className="text-[10px] opacity-50">{m.slice(0,4)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.source_types.map(sourceType => (
              <tr key={sourceType} className="hover:bg-[var(--surface-hover)]">
                <td className="px-2 py-1 text-[var(--text-muted)] font-medium">
                  {SOURCE_LABELS[sourceType] || sourceType}
                </td>
                {recentMonths.map(month => {
                  const count = data.data[sourceType]?.[month] ?? 0;
                  return (
                    <td
                      key={month}
                      className={`px-1 py-1 text-center rounded-sm mx-0.5 ${getCellColor(count, data.thresholds)}`}
                      title={`${sourceType} ${month}: ${count} dok.`}
                    >
                      {count > 0 ? count : '–'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary of gaps */}
      <div className="text-sm text-[var(--text-muted)]">
        {Object.entries(data.data).map(([st, months]) => {
          const gapMonths = recentMonths.filter(m => !months[m] || months[m] < data.thresholds.low);
          if (gapMonths.length === 0) return null;
          return (
            <p key={st}>
              ⚠️ <strong>{SOURCE_LABELS[st] || st}</strong>: brakuje danych w {gapMonths.length} miesiącach
            </p>
          );
        })}
      </div>
    </div>
  );
}
```

### Step 4: Add to navigation

Find the navigation/sidebar component and add a link to /data-coverage.
Search for where other nav links are defined:
```
find /home/sebastian/personal-ai/frontend -name "*.tsx" | xargs grep -l "href.*intelligence\|href.*brief\|sidebar.*nav" 2>/dev/null | grep -v node_modules | head -5
```

Add `{ href: '/data-coverage', label: 'Pokrycie danych', icon: 'BarChart2' }` or similar.

### Step 5: Test and commit
```
# Verify dev server loads the page (it should hot-reload)
curl -s http://localhost:3000/data-coverage | grep -i "loading\|Pokrycie\|error" | head -3

cd /home/sebastian/personal-ai
git add app/api/main.py frontend/
git commit -m "feat(dashboard): add data coverage heatmap

- GET /coverage/heatmap endpoint
- Frontend page showing doc count per source/month
- Color coding: red=gap, yellow=partial, green=good"
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T11.done
openclaw system event --text "Upgrade T11 done: data coverage heatmap live" --mode now
```
