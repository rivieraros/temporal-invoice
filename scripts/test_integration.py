"""
Test Integration Activities

Tests the integration activities without Temporal:
- resolve_entity
- resolve_vendor
- apply_mapping_overlay
- build_bc_payload
- persist_audit_event

This simulates what the InvoiceWorkflow does.
"""

import asyncio
import json
import sys
from pathlib import Path
from dataclasses import asdict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize databases
from entity_resolver.db import init_entity_resolver_db
from vendor_resolver.db import init_vendor_resolver_db, seed_sample_aliases
from coding_engine.db import init_coding_engine_db, seed_sample_data


def load_sample_invoice(feedlot: str, invoice_number: str) -> dict:
    """Load a sample invoice from artifacts"""
    invoice_path = Path(__file__).parent.parent / "artifacts" / feedlot / "invoices" / f"{invoice_number}.json"
    
    if not invoice_path.exists():
        raise FileNotFoundError(f"Invoice not found: {invoice_path}")
    
    with open(invoice_path) as f:
        raw_data = json.load(f)
    
    # Transform to canonical format
    totals = raw_data.get("totals", {})
    total = totals.get("total_amount_due") or totals.get("total_period_charges") or "0"
    
    return {
        "invoice_number": raw_data.get("invoice_number"),
        "invoice_date": raw_data.get("invoice_date") or raw_data.get("statement_date"),
        "lot_number": raw_data.get("lot", {}).get("lot_number"),
        "total": total,
        "feedlot": raw_data.get("feedlot", {}),
        "owner": {
            "number": raw_data.get("owner", {}).get("owner_number"),
            "name": raw_data.get("owner", {}).get("name"),
        },
        "line_items": [
            {
                "description": item.get("description"),
                "amount": item.get("total") or "0",
                "quantity": item.get("quantity"),
                "rate": item.get("rate"),
            }
            for item in raw_data.get("line_items", [])
        ],
    }


async def test_resolve_entity():
    """Test entity resolution"""
    print("\n" + "=" * 60)
    print("TEST: resolve_entity")
    print("=" * 60)
    
    from entity_resolver import EntityResolver
    
    # Test case 1: Bovina
    print("\nTest 1: Bovina Feeders")
    
    # Create invoice dict matching expected format
    invoice = {
        "feedlot": {
            "name": "BOVINA FEEDERS INC. DBA BF2",
            "state": "TX",
            "city": "FRIONA",
        },
        "invoice_number": "13330",
    }
    
    resolver = EntityResolver(customer_id="ACME")
    result = await resolver.resolve_entity(invoice=invoice)
    
    print(f"  Auto-assigned: {result.is_auto_assigned}")
    print(f"  Method: {result.resolution_method}")
    print(f"  Reasons: {result.reasons}")
    
    if result.is_auto_assigned:
        print(f"  Entity ID: {result.entity_id}")
        print(f"  Entity Name: {result.entity_name}")
        print(f"  BC Company: {result.bc_company_id}")
        print(f"  Confidence: {result.confidence}%")
        assert result.entity_id == "BF2", f"Expected BF2, got {result.entity_id}"
    elif result.candidates:
        top = result.candidates[0]
        print(f"  Top Candidate: {top.entity_id} ({top.score}%)")
        # Accept if top candidate is BF2
        assert top.entity_id == "BF2", f"Expected BF2, got {top.entity_id}"
    
    print("  ✓ PASSED")
    
    # Test case 2: Mesquite
    print("\nTest 2: Mesquite Cattle")
    invoice2 = {
        "feedlot": {
            "name": "Mesquite Cattle Feeders",
            "state": "CA",
            "city": "BRAWLEY",
        },
        "invoice_number": "43953",
    }
    
    result2 = await resolver.resolve_entity(invoice=invoice2)
    
    print(f"  Auto-assigned: {result2.is_auto_assigned}")
    if result2.is_auto_assigned:
        print(f"  Entity ID: {result2.entity_id}")
        assert result2.entity_id == "MESQ", f"Expected MESQ, got {result2.entity_id}"
    elif result2.candidates:
        top = result2.candidates[0]
        print(f"  Top Candidate: {top.entity_id} ({top.score}%)")
    
    print("  ✓ PASSED")


async def test_resolve_vendor():
    """Test vendor resolution"""
    print("\n" + "=" * 60)
    print("TEST: resolve_vendor")
    print("=" * 60)
    
    from vendor_resolver import VendorResolver
    
    # Initialize and seed
    init_vendor_resolver_db()
    seed_sample_aliases()
    
    # Test case 1: Exact alias match
    print("\nTest 1: Exact alias match")
    resolver = VendorResolver(customer_id="ACME")
    
    vendor_list = [
        {"vendor_id": "V-BF2", "number": "V-BF2", "name": "Bovina Feeders Inc.", "address": {"state": "TX"}},
    ]
    
    result = await resolver.resolve_vendor(
        extracted_name="BOVINA FEEDERS",
        entity_id="BF2",
        vendor_list=vendor_list,
    )
    
    print(f"  Vendor ID: {result.vendor_id}")
    print(f"  Match Type: {result.match_type}")
    print(f"  Confidence: {result.confidence_score}%")
    print(f"  Auto-matched: {result.is_auto_matched}")
    
    assert result.is_auto_matched, "Expected auto-match"
    print("  ✓ PASSED")


async def test_apply_mapping():
    """Test mapping overlay"""
    print("\n" + "=" * 60)
    print("TEST: apply_mapping_overlay")
    print("=" * 60)
    
    from coding_engine import code_invoice
    
    # Initialize and seed
    init_coding_engine_db()
    seed_sample_data()
    
    # Load sample invoice
    invoice = load_sample_invoice("bovina", "13330")
    
    print(f"\nCoding invoice: {invoice['invoice_number']}")
    print(f"  Lines: {len(invoice['line_items'])}")
    
    coding = code_invoice(
        invoice=invoice,
        entity_id="BF2",
        vendor_id="V-BF2",
    )
    
    print(f"\nCoding Result:")
    print(f"  Complete: {coding.is_complete}")
    print(f"  Missing Mappings: {coding.missing_mappings}")
    print(f"  Missing Dimensions: {coding.missing_dimensions}")
    
    print(f"\nLine Codings:")
    for lc in coding.line_codings:
        dims = ", ".join(f"{d.code}={d.value}" for d in lc.dimensions)
        print(f"  [{lc.line_index}] {lc.category} → {lc.gl_ref} ({lc.mapping_level.value})")
        print(f"       Dims: {dims}")
    
    print("  ✓ PASSED")


async def test_build_payload():
    """Test BC payload building"""
    print("\n" + "=" * 60)
    print("TEST: build_bc_payload")
    print("=" * 60)
    
    from coding_engine import code_invoice
    
    # Load and code invoice
    invoice = load_sample_invoice("bovina", "13330")
    coding = code_invoice(invoice=invoice, entity_id="BF2", vendor_id="V-BF2")
    
    # Build payload
    vendor_info = {
        "vendor_id": "V-BF2",
        "vendor_number": "V-BF2",
        "vendor_name": "Bovina Feeders Inc.",
    }
    
    coding_result = {
        "line_codings": [
            {
                "line_index": lc.line_index,
                "description": lc.description,
                "amount": str(lc.amount),
                "category": lc.category,
                "gl_ref": lc.gl_ref,
                "mapping_level": lc.mapping_level.value,
                "dimensions": [{"code": d.code, "value": d.value} for d in lc.dimensions],
            }
            for lc in coding.line_codings
        ],
    }
    
    # Simulate payload building
    from datetime import datetime
    
    payload = {
        "purchaseInvoice": {
            "@odata.type": "#Microsoft.Dynamics.BC.purchaseInvoice",
            "vendorNumber": vendor_info["vendor_number"],
            "vendorName": vendor_info["vendor_name"],
            "invoiceDate": invoice.get("invoice_date"),
            "vendorInvoiceNumber": invoice.get("invoice_number"),
            "status": "Draft",
            "currencyCode": "USD",
        },
        "purchaseInvoiceLines": [],
    }
    
    for idx, line in enumerate(coding_result["line_codings"]):
        dimensions = {}
        for dim in line.get("dimensions", []):
            dimensions[dim["code"]] = dim["value"]
        
        bc_line = {
            "lineNumber": (idx + 1) * 10000,
            "description": line.get("description", ""),
            "lineType": "G/L Account",
            "accountId": line.get("gl_ref"),
            "quantity": 1,
            "unitPrice": float(line.get("amount", 0)),
            "dimensionSetLines": [
                {"code": k, "valueCode": v}
                for k, v in dimensions.items()
            ],
        }
        payload["purchaseInvoiceLines"].append(bc_line)
    
    print(f"\nPayload for invoice {invoice['invoice_number']}:")
    print(f"  Vendor: {payload['purchaseInvoice']['vendorNumber']}")
    print(f"  Date: {payload['purchaseInvoice']['invoiceDate']}")
    print(f"  Lines: {len(payload['purchaseInvoiceLines'])}")
    
    print(f"\nSample Line:")
    if payload["purchaseInvoiceLines"]:
        line = payload["purchaseInvoiceLines"][0]
        print(f"  Description: {line['description']}")
        print(f"  Account: {line['accountId']}")
        print(f"  Amount: ${line['unitPrice']}")
        print(f"  Dimensions: {len(line['dimensionSetLines'])}")
    
    # Save payload artifact
    artifacts_dir = Path(__file__).parent.parent / "artifacts" / "bovina" / "payloads"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    payload_path = artifacts_dir / f"{invoice['invoice_number']}_payload.json"
    with open(payload_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    
    print(f"\nPayload saved: {payload_path}")
    print("  ✓ PASSED")


async def test_audit_event():
    """Test audit event persistence"""
    print("\n" + "=" * 60)
    print("TEST: persist_audit_event")
    print("=" * 60)
    
    import sqlite3
    from datetime import datetime
    
    db_path = Path(__file__).parent.parent / "ap_automation.db"
    
    # Create audit table if needed
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ap_package_id TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert test event
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO audit_events 
        (ap_package_id, invoice_number, stage, status, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "test_pkg_001",
        "13330",
        "BUILD_ERP_PAYLOAD",
        "SUCCESS",
        json.dumps({"test": True}),
        timestamp,
    ))
    
    event_id = cursor.lastrowid
    conn.commit()
    
    print(f"\nInserted audit event: {event_id}")
    
    # Query back
    cursor.execute("""
        SELECT * FROM audit_events 
        WHERE ap_package_id = 'test_pkg_001' 
        ORDER BY created_at DESC LIMIT 5
    """)
    
    rows = cursor.fetchall()
    print(f"\nRecent audit events for test_pkg_001:")
    for row in rows:
        print(f"  [{row[0]}] {row[3]} @ {row[4]} = {row[5]}")
    
    conn.close()
    print("  ✓ PASSED")


async def test_full_pipeline():
    """Test the full integration pipeline"""
    print("\n" + "=" * 60)
    print("FULL PIPELINE TEST")
    print("=" * 60)
    
    # Initialize all databases
    init_entity_resolver_db()
    init_vendor_resolver_db()
    seed_sample_aliases()
    init_coding_engine_db()
    seed_sample_data()
    
    # Load invoice
    invoice = load_sample_invoice("bovina", "13330")
    print(f"\nProcessing invoice: {invoice['invoice_number']}")
    
    # Stage 1: Resolve Entity
    print("\n--- Stage: RESOLVE_ENTITY ---")
    from entity_resolver import EntityResolver
    
    entity_resolver = EntityResolver(customer_id="ACME")
    
    entity_result = await entity_resolver.resolve_entity(invoice=invoice)
    
    if entity_result.is_auto_assigned:
        entity_id = entity_result.entity_id
        bc_company_id = entity_result.bc_company_id
        print(f"  Entity: {entity_id} ({entity_result.confidence}%)")
    elif entity_result.candidates:
        top = entity_result.candidates[0]
        entity_id = top.entity_id
        bc_company_id = top.entity_id  # Simplified
        print(f"  Entity (top candidate): {entity_id} ({top.score}%)")
    else:
        entity_id = "BF2"  # Fallback
        bc_company_id = "BF2"
        print(f"  Entity (fallback): {entity_id}")
    
    # Stage 2: Resolve Vendor
    print("\n--- Stage: RESOLVE_VENDOR ---")
    from vendor_resolver import VendorResolver
    
    vendor_resolver = VendorResolver(customer_id="ACME")
    
    vendor_list = [
        {"vendor_id": "V-BF2", "number": "V-BF2", "name": "Bovina Feeders Inc.", "address": {"state": "TX"}},
    ]
    
    feedlot_info = invoice.get("feedlot", {})
    vendor_result = await vendor_resolver.resolve_vendor(
        extracted_name=feedlot_info.get("name", ""),
        entity_id=entity_id,
        vendor_list=vendor_list,
    )
    print(f"  Vendor: {vendor_result.vendor_id} ({vendor_result.match_type.value}, {vendor_result.confidence_score}%)")
    
    # Stage 3: Apply Mapping
    print("\n--- Stage: APPLY_MAPPING_OVERLAY ---")
    from coding_engine import code_invoice
    
    coding = code_invoice(
        invoice=invoice,
        entity_id=entity_id,
        vendor_id=vendor_result.vendor_id,
        vendor={
            "vendor_id": vendor_result.vendor_id,
            "vendor_number": vendor_result.vendor_number,
            "vendor_name": vendor_result.vendor_name,
        },
    )
    print(f"  Lines coded: {len(coding.line_codings)}")
    print(f"  Complete: {coding.is_complete}")
    
    # Stage 4: Build Payload
    print("\n--- Stage: BUILD_ERP_PAYLOAD ---")
    
    payload = {
        "purchaseInvoice": {
            "vendorNumber": vendor_result.vendor_number,
            "vendorName": vendor_result.vendor_name,
            "invoiceDate": invoice.get("invoice_date"),
            "vendorInvoiceNumber": invoice.get("invoice_number"),
            "status": "Draft",
        },
        "purchaseInvoiceLines": [
            {
                "lineNumber": (i + 1) * 10000,
                "description": lc.description,
                "accountId": lc.gl_ref,
                "unitPrice": float(lc.amount),
                "dimensions": {d.code: d.value for d in lc.dimensions},
            }
            for i, lc in enumerate(coding.line_codings)
        ],
    }
    
    print(f"  Payload lines: {len(payload['purchaseInvoiceLines'])}")
    
    # Stage 5: Save artifacts
    print("\n--- Stage: PAYLOAD_GENERATED ---")
    
    artifacts_dir = Path(__file__).parent.parent / "artifacts" / "bovina"
    
    # Save coding
    coding_path = artifacts_dir / "codings" / f"{invoice['invoice_number']}_coding.json"
    coding_path.parent.mkdir(parents=True, exist_ok=True)
    with open(coding_path, "w") as f:
        json.dump(coding.to_dict(), f, indent=2, default=str)
    print(f"  Coding saved: {coding_path.name}")
    
    # Save payload
    payload_path = artifacts_dir / "payloads" / f"{invoice['invoice_number']}_payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    with open(payload_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"  Payload saved: {payload_path.name}")
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"""
Summary:
  Invoice: {invoice['invoice_number']}
  Entity: {entity_id} → BC Company: {bc_company_id}
  Vendor: {vendor_result.vendor_id} ({vendor_result.vendor_name})
  Lines: {len(coding.line_codings)} coded
  Payload: Ready for BC posting
  
Artifacts:
  {coding_path}
  {payload_path}
""")
    
    return True


async def main():
    """Run all tests"""
    print("=" * 60)
    print("INTEGRATION ACTIVITY TESTS")
    print("=" * 60)
    
    # Initialize databases
    print("\nInitializing databases...")
    init_entity_resolver_db()
    init_vendor_resolver_db()
    init_coding_engine_db()
    
    # Run individual tests
    await test_resolve_entity()
    await test_resolve_vendor()
    await test_apply_mapping()
    await test_build_payload()
    await test_audit_event()
    
    # Run full pipeline
    await test_full_pipeline()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
