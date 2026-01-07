"""Analyze Bovina discrepancies between invoices and statement."""
import json
from pathlib import Path
from decimal import Decimal

ARTIFACTS = Path(__file__).parent.parent / "artifacts" / "bovina"


def main():
    # Load statement
    stmt = json.loads((ARTIFACTS / "statement.json").read_text())
    
    # Problem invoices with discrepancies
    problem_invoices = ["13335", "13347", "13355", "13490", "13491", "13496", "13506", "13508"]
    
    # Build statement lookup
    stmt_lookup = {ref["invoice_number"]: Decimal(str(ref["statement_charge"])) for ref in stmt["lot_references"]}
    
    print("=" * 80)
    print("BOVINA DISCREPANCY ANALYSIS")
    print("=" * 80)
    
    total_diff = Decimal("0")
    
    for inv_num in problem_invoices:
        inv_path = ARTIFACTS / "invoices" / f"{inv_num}.json"
        if not inv_path.exists():
            print(f"\nInvoice {inv_num}: FILE NOT FOUND")
            continue
        
        inv = json.loads(inv_path.read_text())
        
        # Calculate line sum
        line_sum = sum(Decimal(str(item["total"])) for item in inv["line_items"] if item.get("total"))
        
        inv_total = Decimal(str(inv["totals"]["total_amount_due"])) if inv["totals"].get("total_amount_due") else None
        stmt_amount = stmt_lookup.get(inv_num, Decimal("0"))
        
        lot_num = inv["lot"]["lot_number"]
        diff = inv_total - stmt_amount if inv_total else Decimal("0")
        total_diff += diff
        
        print(f"\n{'='*40}")
        print(f"Invoice {inv_num} (Lot {lot_num})")
        print(f"{'='*40}")
        print(f"  Line items sum:     ${line_sum:>12,.2f}")
        print(f"  Invoice total:      ${inv_total:>12,.2f}")
        print(f"  Statement charge:   ${stmt_amount:>12,.2f}")
        print(f"  DIFFERENCE:         ${diff:>12,.2f}")
        print(f"\n  Line items breakdown:")
        for item in inv["line_items"]:
            desc = item.get("description", "Unknown")
            t = item.get("total", "N/A")
            qty = item.get("quantity", "")
            unit = item.get("quantity_unit", "")
            rate = item.get("rate", "")
            rate_unit = item.get("rate_unit", "")
            if t != "N/A":
                print(f"    ${float(t):>10,.2f}  {desc}")
                if rate and qty:
                    print(f"               ({qty} {unit} @ ${rate}/{rate_unit})")
    
    print(f"\n{'='*80}")
    print(f"TOTAL DIFFERENCE: ${total_diff:,.2f}")
    print(f"{'='*80}")
    
    # Check for missing invoice 13304
    print(f"\n\nMISSING INVOICE ANALYSIS:")
    print("-" * 40)
    missing_inv = "13304"
    missing_ref = next((ref for ref in stmt["lot_references"] if ref["invoice_number"] == missing_inv), None)
    if missing_ref:
        print(f"Invoice {missing_inv}:")
        print(f"  Lot: {missing_ref['lot_number']}")
        print(f"  Statement charge: ${missing_ref['statement_charge']}")
        print(f"  Description: {missing_ref['description']}")
    
    # Check how many pages were processed
    inv_files = list((ARTIFACTS / "invoices").glob("*.json"))
    print(f"\nExtracted {len(inv_files)} invoice files")
    print(f"Statement references {len(stmt['lot_references'])} invoices")
    
    # Look for 13304 in transactions
    print(f"\n\nTransactions for lot 20-3927 (missing invoice):")
    print("-" * 40)
    for txn in stmt.get("transactions", []):
        if txn.get("lot_number") == "20-3927":
            print(f"  Date: {txn.get('date')}, Type: {txn.get('type')}, Ref: {txn.get('ref_number')}, Charge: {txn.get('charge')}")


if __name__ == "__main__":
    main()
