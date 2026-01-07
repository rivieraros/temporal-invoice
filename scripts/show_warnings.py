"""Show reconciliation warnings."""
import json
from pathlib import Path

results = json.loads(Path("artifacts/reconciliation_results.json").read_text())

for result in results:
    feedlot = result["feedlot"]
    checks = result["checks"]
    warns = [c for c in checks if c["severity"] == "WARN"]
    print(f"\n{feedlot} WARNINGS ({len(warns)}):")
    for c in warns:
        print(f"  - [{c['check_id']}] {c['message']}")
        if "trusted_source" in c.get("evidence", {}):
            ev = c["evidence"]
            print(f"      Invoice: {ev.get('invoice_total')}, Statement: {ev.get('statement_amount')}, Diff: {ev.get('difference')}")
