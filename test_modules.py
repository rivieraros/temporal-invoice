"""Test module imports and function calls."""

import json
from pathlib import Path
from decimal import Decimal

# Test imports
print("Testing module imports...")
try:
    from models.canonical import StatementDocument, InvoiceDocument
    print("  ✓ models.canonical")
except Exception as e:
    print(f"  ✗ models.canonical: {e}")

try:
    from models.refs import DataReference, ExtractedPackageRefs, ReconciliationReport
    print("  ✓ models.refs")
except Exception as e:
    print(f"  ✗ models.refs: {e}")

try:
    from storage.artifacts import put_json, get_json, list_artifacts
    print("  ✓ storage.artifacts")
except Exception as e:
    print(f"  ✗ storage.artifacts: {e}")

try:
    from extraction.runner import extract_package, extract_statement, extract_invoice
    print("  ✓ extraction.runner")
except Exception as e:
    print(f"  ✗ extraction.runner: {e}")

try:
    from reconciliation.engine import reconcile
    print("  ✓ reconciliation.engine")
except Exception as e:
    print(f"  ✗ reconciliation.engine: {e}")

print("\n" + "="*70)
print("Testing storage layer...")
print("="*70)

# Test storage layer
test_obj = {"test": "data", "nested": {"value": 123}}
test_path = Path("artifacts/test_artifact.json")

try:
    ref = put_json(test_obj, test_path)
    print(f"✓ put_json created artifact: {ref.storage_uri}")
    print(f"  - SHA256: {ref.content_hash[:16]}...")
    print(f"  - Size: {ref.size_bytes} bytes")
except Exception as e:
    print(f"✗ put_json failed: {e}")

try:
    retrieved = get_json(ref)
    if retrieved == test_obj:
        print(f"✓ get_json retrieved correct data")
    else:
        print(f"✗ get_json data mismatch")
except Exception as e:
    print(f"✗ get_json failed: {e}")

print("\n" + "="*70)
print("Testing reconciliation with existing data...")
print("="*70)

# Load existing extracted data
bovina_dir = Path("artifacts/bovina")
mesquite_dir = Path("artifacts/mesquite")

try:
    # Load Bovina statement
    with open(bovina_dir / "statement.json") as f:
        bovina_stmt_data = json.load(f)
    bovina_stmt = StatementDocument.model_validate(bovina_stmt_data)
    print(f"✓ Loaded Bovina statement: {bovina_stmt.feedlot.name if bovina_stmt.feedlot else 'Unknown'}")
    
    # Load Bovina invoices
    bovina_invoices = []
    bovina_invoices_dir = bovina_dir / "invoices"
    if bovina_invoices_dir.exists():
        for invoice_file in sorted(bovina_invoices_dir.glob("*.json")):
            with open(invoice_file) as f:
                inv_data = json.load(f)
            inv = InvoiceDocument.model_validate(inv_data)
            bovina_invoices.append(inv)
    print(f"✓ Loaded {len(bovina_invoices)} Bovina invoices")
    
    # Reconcile
    from reconciliation.engine import reconcile
    report = reconcile(bovina_stmt, bovina_invoices, feedlot_key="bovina")
    print(f"✓ Reconciliation complete: {report.status}")
    print(f"  - {report.summary.get('passed_checks')} passed checks")
    print(f"  - {report.summary.get('blocking_issues')} blocking issues")
    print(f"  - {report.summary.get('warnings')} warnings")
    print(f"  - {report.metrics.get('matched_invoices')}/{report.metrics.get('expected_invoices')} invoices matched")
    
except Exception as e:
    print(f"✗ Reconciliation test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Testing DataReference model...")
print("="*70)

try:
    # Create a DataReference
    ref = DataReference(
        storage_uri="/path/to/artifact.json",
        content_hash="abc123" + "0"*58,
        content_type="application/json",
        size_bytes=1024,
        stored_at="2026-01-07T12:00:00",
    )
    
    # Convert to dict
    ref_dict = ref.model_dump()
    print(f"✓ DataReference created and serialized")
    
    # Recreate from dict
    ref2 = DataReference.model_validate(ref_dict)
    print(f"✓ DataReference deserialized from dict")
    
except Exception as e:
    print(f"✗ DataReference test failed: {e}")

print("\n" + "="*70)
print("All tests complete!")
print("="*70)
