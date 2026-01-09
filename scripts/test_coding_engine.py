"""
Test Coding Engine

Tests the coding engine with real invoice data from artifacts.
"""

import json
import sys
from pathlib import Path
from decimal import Decimal

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from coding_engine import (
    CodingEngine,
    code_invoice,
    preview_coding,
    categorize_line_item,
    seed_sample_data,
    init_coding_engine_db,
    get_global_mappings,
    get_dimension_rules,
    MappingLevel,
)


def test_categorization():
    """Test line item categorization"""
    print("\n" + "=" * 60)
    print("CATEGORIZATION TESTS")
    print("=" * 60)
    
    test_cases = [
        ("Feed & Rations", "FEED"),
        ("TCFA DUES", "MISC"),  # No specific category
        ("CATTLE INSURANCE", "INSURANCE"),
        ("Yardage - Daily", "YARDAGE"),
        ("Vet Supplies", "VET"),
        ("Freight Charges", "FREIGHT"),
        ("Death Loss Adjustment", "DEATH_LOSS"),
        ("Interest on Account", "INTEREST"),
        ("Processing Fee", "PROCESSING"),
        ("Beef Checkoff", "CHECKOFF"),
        ("Brand Inspection", "BRAND"),
        ("Random Other Charge", "UNCATEGORIZED"),
    ]
    
    passed = 0
    for description, expected in test_cases:
        result = categorize_line_item(description)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        print(f"  {status} '{description}' → {result} (expected: {expected})")
    
    print(f"\nCategorization: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_preview_coding():
    """Test preview coding function"""
    print("\n" + "=" * 60)
    print("PREVIEW CODING TESTS")
    print("=" * 60)
    
    # Seed data first
    seed_sample_data()
    
    descriptions = [
        "Feed & Rations",
        "Yardage - Daily",
        "Vet Supplies",
        "Unknown Charge Type",
    ]
    
    # Test with BF2 entity (has entity-level override for FEED)
    print("\nPreview for entity BF2:")
    results = preview_coding(descriptions, entity_id="BF2")
    
    for r in results:
        print(f"  {r['description']}")
        print(f"    Category: {r['category']}")
        print(f"    GL Ref: {r['gl_ref']}")
        print(f"    Level: {r['level']}")
    
    # Verify entity-level override
    feed_result = next(r for r in results if r['category'] == 'FEED')
    if feed_result['gl_ref'] == '5100-01' and feed_result['level'] == 'entity':
        print("\n  ✓ Entity-level override for FEED working (5100-01)")
    else:
        print(f"\n  ✗ Expected entity override 5100-01, got {feed_result['gl_ref']}")
    
    # Test with MESQ entity
    print("\nPreview for entity MESQ:")
    results = preview_coding(descriptions, entity_id="MESQ")
    
    for r in results:
        print(f"  {r['description']}: {r['category']} → {r['gl_ref']} ({r['level']})")


def test_code_invoice():
    """Test full invoice coding with real data"""
    print("\n" + "=" * 60)
    print("INVOICE CODING TESTS")
    print("=" * 60)
    
    # Load a real invoice
    invoice_path = Path(__file__).parent.parent / "artifacts" / "bovina" / "invoices" / "13330.json"
    
    if not invoice_path.exists():
        print(f"  ✗ Invoice file not found: {invoice_path}")
        return False
    
    with open(invoice_path) as f:
        invoice_data = json.load(f)
    
    # Transform to canonical format
    invoice = {
        "invoice_number": invoice_data.get("invoice_number"),
        "invoice_date": invoice_data.get("invoice_date") or invoice_data.get("statement_date"),
        "lot_number": invoice_data.get("lot", {}).get("lot_number"),
        "total": invoice_data.get("totals", {}).get("total_amount_due", 0),
        "feedlot": invoice_data.get("feedlot", {}),
        "owner": {
            "number": invoice_data.get("owner", {}).get("owner_number"),
            "name": invoice_data.get("owner", {}).get("name"),
        },
        "line_items": [
            {
                "description": item.get("description"),
                "amount": item.get("total", 0),
                "quantity": item.get("quantity"),
                "rate": item.get("rate"),
            }
            for item in invoice_data.get("line_items", [])
        ],
    }
    
    # Create vendor info (simulating vendor resolution)
    vendor = {
        "vendor_id": "V-BF2",
        "vendor_number": "V-BF2",
        "vendor_name": "Bovina Feeders Inc.",
    }
    
    # Code the invoice
    print(f"\nCoding invoice: {invoice['invoice_number']}")
    print(f"  Lot: {invoice['lot_number']}")
    print(f"  Date: {invoice['invoice_date']}")
    print(f"  Total: ${invoice['total']}")
    print(f"  Lines: {len(invoice['line_items'])}")
    
    engine = CodingEngine(entity_id="BF2", vendor_id="V-BF2")
    coding = engine.code_invoice(invoice, vendor=vendor)
    
    print(f"\nCoding Result:")
    print(f"  Invoice #: {coding.invoice_number}")
    print(f"  Entity: {coding.entity_id}")
    print(f"  Vendor Ref: {coding.vendor_ref}")
    print(f"  Complete: {'✓' if coding.is_complete else '✗'}")
    
    if coding.missing_mappings:
        print(f"  Missing Mappings: {coding.missing_mappings}")
    if coding.missing_dimensions:
        print(f"  Missing Dimensions: {coding.missing_dimensions}")
    if coding.warnings:
        print(f"  Warnings: {coding.warnings}")
    
    print(f"\nLine Codings:")
    for lc in coding.line_codings:
        print(f"  [{lc.line_index}] {lc.description[:30]:<30}")
        print(f"      Category: {lc.category}")
        print(f"      GL Ref: {lc.gl_ref} ({lc.mapping_level.value})")
        print(f"      Amount: ${lc.amount}")
        if lc.dimensions:
            dims = ", ".join(f"{d.code}={d.value}" for d in lc.dimensions)
            print(f"      Dimensions: {dims}")
        if lc.missing_dimensions:
            print(f"      Missing: {lc.missing_dimensions}")
    
    return True


def test_multiple_invoices():
    """Test coding multiple invoices from artifacts"""
    print("\n" + "=" * 60)
    print("MULTIPLE INVOICE TESTS")
    print("=" * 60)
    
    artifacts_dir = Path(__file__).parent.parent / "artifacts"
    
    results = {
        "total": 0,
        "complete": 0,
        "with_warnings": 0,
        "missing_mappings": set(),
        "missing_dimensions": set(),
    }
    
    for feedlot_dir in ["bovina", "mesquite"]:
        invoices_dir = artifacts_dir / feedlot_dir / "invoices"
        if not invoices_dir.exists():
            continue
        
        entity_id = "BF2" if feedlot_dir == "bovina" else "MESQ"
        engine = CodingEngine(entity_id=entity_id)
        
        print(f"\n{feedlot_dir.upper()} ({entity_id}):")
        
        for invoice_file in sorted(invoices_dir.glob("*.json"))[:5]:  # Limit to 5
            with open(invoice_file) as f:
                invoice_data = json.load(f)
            
            # Transform to canonical format
            totals = invoice_data.get("totals", {})
            total = totals.get("total_amount_due") or totals.get("total_period_charges") or "0"
            
            invoice = {
                "invoice_number": invoice_data.get("invoice_number"),
                "invoice_date": invoice_data.get("invoice_date") or invoice_data.get("statement_date"),
                "lot_number": invoice_data.get("lot", {}).get("lot_number"),
                "total": total,
                "feedlot": invoice_data.get("feedlot", {}),
                "owner": {
                    "number": invoice_data.get("owner", {}).get("owner_number"),
                    "name": invoice_data.get("owner", {}).get("name"),
                },
                "line_items": [
                    {
                        "description": item.get("description"),
                        "amount": item.get("total") or "0",
                    }
                    for item in invoice_data.get("line_items", [])
                ],
            }
            
            coding = engine.code_invoice(invoice)
            results["total"] += 1
            
            status = "✓" if coding.is_complete else "⚠"
            if coding.is_complete:
                results["complete"] += 1
            if coding.warnings:
                results["with_warnings"] += 1
            
            results["missing_mappings"].update(coding.missing_mappings)
            results["missing_dimensions"].update(coding.missing_dimensions)
            
            print(f"  {status} Invoice {coding.invoice_number}: {len(coding.line_codings)} lines")
    
    print(f"\n{'=' * 40}")
    print(f"Summary:")
    print(f"  Total invoices: {results['total']}")
    print(f"  Complete: {results['complete']}")
    print(f"  With warnings: {results['with_warnings']}")
    
    if results["missing_mappings"]:
        print(f"  Missing category mappings: {sorted(results['missing_mappings'])}")
    else:
        print(f"  All categories mapped ✓")
    
    if results["missing_dimensions"]:
        print(f"  Missing dimensions: {sorted(results['missing_dimensions'])}")
    
    return results["complete"] > 0


def test_mapping_summary():
    """Test mapping summary for entities"""
    print("\n" + "=" * 60)
    print("MAPPING SUMMARY")
    print("=" * 60)
    
    for entity_id in ["BF2", "MESQ"]:
        engine = CodingEngine(entity_id=entity_id)
        summary = engine.get_mapping_summary()
        
        print(f"\n{entity_id}:")
        print(f"  Total mappings: {summary['total_mappings']}")
        print(f"  By level: {summary['mappings_by_level']}")
        print(f"  Categories: {summary['categories_covered']}")
        print(f"  Dimension rules: {summary['dimension_rules']}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("CODING ENGINE TEST SUITE")
    print("=" * 60)
    
    # Check for --seed flag
    if "--seed" in sys.argv:
        print("\nSeeding sample data...")
        counts = seed_sample_data()
        print(f"Seeded: {counts}")
    else:
        # Just init DB
        init_coding_engine_db()
    
    # Run tests
    test_categorization()
    test_preview_coding()
    test_code_invoice()
    test_multiple_invoices()
    test_mapping_summary()
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
