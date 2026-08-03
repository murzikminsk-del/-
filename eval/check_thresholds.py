import json
import sys
import yaml
from pathlib import Path

runs_dir = Path("eval/runs")
thresholds_file = Path("eval/thresholds.yaml")

with open(thresholds_file) as f:
    thresholds = yaml.safe_load(f)

run_files = sorted(runs_dir.glob("*.json"))
if not run_files:
    print("Нет файлов в eval/runs/")
    sys.exit(1)

with open(run_files[-1], encoding="utf-8") as f:
    run = json.load(f)

aggregates = run["aggregates"]
failed = False

if aggregates["correctness_avg"] < thresholds["correctness_avg"]:
    print(f"FAIL: correctness_avg={aggregates['correctness_avg']:.2f} < {thresholds['correctness_avg']}")
    failed = True

if aggregates["min_correctness"] < thresholds["min_correctness"]:
    print(f"FAIL: min_correctness={aggregates['min_correctness']:.2f} < {thresholds['min_correctness']}")
    failed = True

if failed:
    sys.exit(1)

print("OK: все пороги соблюдены")