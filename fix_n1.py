#!/usr/bin/env python3
"""Fix the N+1 query issue in save_health_metrics"""

with open('app/guardian/data_guardian.py', 'r') as f:
    lines = f.readlines()

# Find the function definition
func_start = None
for i, line in enumerate(lines):
    if 'def save_health_metrics' in line:
        func_start = i
        break

if func_start is None:
    print("ERROR: Function not found")
    exit(1)

# Find the exact lines to replace
replace_start = None
replace_end = None
for i in range(func_start, min(func_start + 100, len(lines))):
    if 'for src in sources:' in lines[i] and i+1 < len(lines) and 'Count docs in last 24h' in lines[i+1]:
        replace_start = i
        # Find the end - after the docs_7d_avg assignment
        for j in range(i, min(i+20, len(lines))):
            if 'docs_7d_avg = round(float(row[1])' in lines[j]:
                replace_end = j + 1
                break
        break

if replace_start is None:
    print(f"ERROR: Could not find target lines")
    exit(1)

print(f"Replacing lines {replace_start} to {replace_end}")
print(f"Old lines: {repr(lines[replace_start:min(replace_start+3, replace_end)])}")

# Build replacement
new_lines = [
    '            # Fetch metrics for all sources in a single query using GROUP BY\n',
    '            cur.execute("""\n',
    '                SELECT\n',
    '                    s.source_type,\n',
    '                    COUNT(*) FILTER (WHERE d.created_at > NOW() - INTERVAL \'24 hours\') as docs_24h,\n',
    '                    COUNT(*)::numeric / GREATEST(\n',
    '                        EXTRACT(EPOCH FROM NOW() - MIN(d.created_at)) / 86400 / 7, 1\n',
    '                    ) as docs_7d_avg\n',
    '                FROM sources s\n',
    '                JOIN documents d ON d.source_id = s.id\n',
    '                WHERE d.created_at > NOW() - INTERVAL \'7 days\'\n',
    '                GROUP BY s.source_type\n',
    '            """)\n',
    '            metrics = {}\n',
    '            for row in cur.fetchall():\n',
    '                source_type = row[0]\n',
    '                metrics[source_type] = {\n',
    '                    \'docs_24h\': row[1] if row[1] else 0,\n',
    '                    \'docs_7d_avg\': round(float(row[2]), 1) if row[2] else 0.0\n',
    '                }\n',
    '\n',
    '            for src in sources:\n',
    '                source_type = src["source_type"]\n',
    '                metric = metrics.get(source_type, {\'docs_24h\': 0, \'docs_7d_avg\': 0.0})\n',
    '                docs_24h = metric[\'docs_24h\']\n',
    '                docs_7d_avg = metric[\'docs_7d_avg\']\n',
]

# Replace
new_file = lines[:replace_start] + new_lines + lines[replace_end:]

with open('app/guardian/data_guardian.py', 'w') as f:
    f.writelines(new_file)

print(f"✓ Fixed! Replaced {replace_end - replace_start} lines with {len(new_lines)} new lines")
