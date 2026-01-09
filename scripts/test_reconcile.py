"""Test reconciliation activity with existing Bovina artifacts.

Tests the reconciliation without needing PDFs - uses pre-extracted JSON files.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from activities.reconcile import reconcile_package, ReconcilePackageInput
from models.refs import DataReference
import hashlib


def make_ref(path: Path) -> dict:
    """Create a DataReference dict for a JSON file."""
    content = path.read_bytes()
    ref = DataReference(
        storage_uri=str(path),
        content_hash=hashlib.sha256(content).hexdigest(),
        content_type="application/json",
        size_bytes=len(content),
    )
    return ref.model_dump()


async def test_bovina_reconciliation():
    """Test reconciliation on Bovina artifacts."""
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts" / "bovina"
    
    # Get statement ref
    statement_path = artifacts_dir / "statement.json"
    if not statement_path.exists():
        print(f"❌ Statement not found: {statement_path}")
        return
    
    statement_ref = make_ref(statement_path)
    print(f"✓ Loaded statement reference")
    
    # Get all invoice refs
    invoices_dir = artifacts_dir / "invoices"
    invoice_refs = []
    invoice_files = sorted(invoices_dir.glob("*.json"))
    for inv_path in invoice_files:
        invoice_refs.append(make_ref(inv_path))
    
    print(f"✓ Loaded {len(invoice_refs)} invoice references")
    
    # Create input
    input_data = ReconcilePackageInput(
        statement_ref=statement_ref,
        invoice_refs=invoice_refs,
        feedlot_type="BOVINA",
        ap_package_id="test-bovina-reconcile",
    )
    
    # Run reconciliation (bypassing Temporal activity decorator)
    print("\n" + "=" * 60)
    print("Running Bovina reconciliation...")
    print("=" * 60)
    
    # Import the underlying function directly
    from models.canonical import StatementDocument, InvoiceDocument
    from reconciliation.engine import reconcile
    
    # Load statement
    with open(statement_path, "r", encoding="utf-8") as f:
        statement_data = json.load(f)
    statement = StatementDocument.model_validate(statement_data)
    
    # Load invoices
    invoices = []
    for inv_path in invoice_files:
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        invoice = InvoiceDocument.model_validate(inv_data)
        invoices.append(invoice)
    
    # Run reconciliation
    report = reconcile(statement, invoices, feedlot_key="bovina")
    
    # Print results
    print(f"\n📊 Reconciliation Results:")
    print(f"   Status: {report.status}")
    print(f"   Feedlot: {report.feedlot_key}")
    
    print(f"\n📋 Summary:")
    for key, val in report.summary.items():
        print(f"   {key}: {val}")
    
    print(f"\n📈 Metrics:")
    for key, val in report.metrics.items():
        print(f"   {key}: {val}")
    
    print(f"\n🔍 Check Results (sample):")
    if isinstance(report.checks, list):
        for check_data in report.checks[:10]:  # Show first 10
            check_id = check_data.get("check_id", "unknown")
            severity = check_data.get("severity")
            status_emoji = "✓" if severity is None else ("⚠" if severity == "WARN" else "✗")
            msg = check_data.get("message", "")[:50]
            print(f"   {status_emoji} {check_id}: {msg}")
    else:
        for check_id, check_data in report.checks.items():
            status_emoji = "✓" if check_data.get("severity") is None else ("⚠" if check_data.get("severity") == "WARN" else "✗")
            print(f"   {status_emoji} {check_id}: {check_data.get('passed', 'N/A')} - {check_data.get('message', '')[:60]}")
            if check_data.get("details"):
                for detail in check_data["details"][:3]:  # Show first 3 details
                    print(f"      → {detail}")
    
    # Verify expected behavior
    print("\n" + "=" * 60)
    if report.status == "WARN":
        print("✓ EXPECTED: Bovina should have WARN status (missing invoice 13304)")
    elif report.status == "PASS":
        print("⚠ UNEXPECTED: Bovina should have WARN, but got PASS")
    else:
        print(f"✗ UNEXPECTED: Bovina has {report.status} status")
    print("=" * 60)
    
    return report


async def test_mesquite_reconciliation():
    """Test reconciliation on Mesquite artifacts."""
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts" / "mesquite"
    
    # Get statement ref
    statement_path = artifacts_dir / "statement.json"
    if not statement_path.exists():
        print(f"❌ Mesquite statement not found: {statement_path}")
        return
    
    # Get all invoice refs
    invoices_dir = artifacts_dir / "invoices"
    invoice_files = sorted(invoices_dir.glob("*.json"))
    
    print(f"\n✓ Loaded Mesquite: statement + {len(invoice_files)} invoices")
    
    # Load and run
    from models.canonical import StatementDocument, InvoiceDocument
    from reconciliation.engine import reconcile
    
    with open(statement_path, "r", encoding="utf-8") as f:
        statement_data = json.load(f)
    statement = StatementDocument.model_validate(statement_data)
    
    invoices = []
    for inv_path in invoice_files:
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        invoice = InvoiceDocument.model_validate(inv_data)
        invoices.append(invoice)
    
    # Run reconciliation
    print("\n" + "=" * 60)
    print("Running Mesquite reconciliation...")
    print("=" * 60)
    
    report = reconcile(statement, invoices, feedlot_key="mesquite")
    
    print(f"\n📊 Reconciliation Results:")
    print(f"   Status: {report.status}")
    print(f"   Feedlot: {report.feedlot_key}")
    print(f"\n📋 Summary:")
    for key, val in report.summary.items():
        print(f"   {key}: {val}")
    
    print("\n" + "=" * 60)
    if report.status == "PASS":
        print("✓ EXPECTED: Mesquite should have PASS status")
    else:
        print(f"⚠ UNEXPECTED: Mesquite has {report.status} status (expected PASS)")
    print("=" * 60)
    
    return report


if __name__ == "__main__":
    print("=" * 60)
    print("RECONCILIATION ACTIVITY TEST")
    print("=" * 60)
    
    # Test Bovina
    asyncio.run(test_bovina_reconciliation())
    
    # Test Mesquite
    asyncio.run(test_mesquite_reconciliation())
    
    print("\n✓ Reconciliation tests complete")
