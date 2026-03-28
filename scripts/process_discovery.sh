#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Process Intelligence: full discovery cycle..."

echo "Step 1: Business Line Discovery..."
python -c "
from app.analysis.business_lines import discover_business_lines
import json
print(json.dumps(discover_business_lines(force=True), ensure_ascii=False, indent=2, default=str))
"

echo "Step 2: Process Mining..."
python -c "
from app.analysis.process_mining import mine_processes
import json
print(json.dumps(mine_processes(force=True), ensure_ascii=False, indent=2, default=str))
"

echo "Step 3: Application Inventory..."
python -c "
from app.analysis.app_inventory import scan_applications
import json
print(json.dumps(scan_applications(), ensure_ascii=False, indent=2, default=str))
"

echo "Step 4: Data Flow Mapping..."
python -c "
from app.analysis.data_flow_mapper import map_data_flows
import json
print(json.dumps(map_data_flows(), ensure_ascii=False, indent=2, default=str))
"

echo "Step 5: Optimization Planning..."
python -c "
from app.analysis.optimization_planner import generate_plans
import json
print(json.dumps(generate_plans(), ensure_ascii=False, indent=2, default=str))
"

echo "Step 6: Deep App Analysis + Costs..."
python -c "
from app.analysis.app_inventory import scan_applications_deep, analyze_app_costs, rank_replacement_priority
import json
print(json.dumps(scan_applications_deep(), ensure_ascii=False, indent=2, default=str))
print(json.dumps(analyze_app_costs(), ensure_ascii=False, indent=2, default=str))
print(json.dumps(rank_replacement_priority()[:5], ensure_ascii=False, indent=2, default=str))
"

echo "Step 7: Tech Radar Refresh..."
python -c "
from app.analysis.tech_radar import discover_solutions, calculate_priority_scores, generate_roadmap, link_to_strategic_goals
import json
result = discover_solutions()
if not result.get('skipped'):
    calculate_priority_scores()
    link_to_strategic_goals()
    print(json.dumps(generate_roadmap(), ensure_ascii=False, indent=2, default=str))
else:
    print('Tech Radar: recent solutions exist, skipping.')
"

echo "[$(date)] Process Intelligence cycle complete."
