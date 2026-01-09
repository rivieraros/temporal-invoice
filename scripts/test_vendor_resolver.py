"""Test script for Vendor Resolver.

This script tests the vendor resolution system with sample data
from the Bovina and Mesquite feedlots.

Usage:
    python scripts/test_vendor_resolver.py [--seed]
    
Options:
    --seed    Clear and re-seed sample data before testing
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vendor_resolver import (
    VendorResolver,
    VendorResolution,
    VendorAlias,
    MatchType,
    init_vendor_resolver_db,
    seed_sample_aliases,
    get_aliases_for_entity,
    normalize_vendor_name,
    tokenize_name,
)
from vendor_resolver.db import clear_vendor_aliases, DEFAULT_DB_PATH


# Sample vendor lists (simulating BC API response)
SAMPLE_VENDOR_LISTS = {
    "bf2-company-guid-001": [
        {
            "id": "bovina-vendor-guid-001",
            "code": "V-BF2",
            "name": "Bovina Feeders Inc.",
            "address_line1": "1741 Co Rd S",
            "city": "Friona",
            "state": "TX",
        },
        {
            "id": "bovina-vendor-guid-002",
            "code": "V-FEED1",
            "name": "Friona Feed Supply",
            "address_line1": "123 Main St",
            "city": "Friona",
            "state": "TX",
        },
        {
            "id": "bovina-vendor-guid-003",
            "code": "V-VET1",
            "name": "Panhandle Veterinary Services",
            "address_line1": "456 Vet Blvd",
            "city": "Amarillo",
            "state": "TX",
        },
    ],
    "mesquite-company-guid-002": [
        {
            "id": "mesquite-vendor-guid-001",
            "code": "V-MCF",
            "name": "Mesquite Cattle Feeders",
            "address_line1": "1504 E. Highway 78",
            "city": "Brawley",
            "state": "CA",
        },
        {
            "id": "mesquite-vendor-guid-002",
            "code": "V-FEED2",
            "name": "Imperial Valley Feed Co",
            "address_line1": "789 Farm Rd",
            "city": "El Centro",
            "state": "CA",
        },
    ],
}


def load_sample_invoices() -> list:
    """Load sample invoices from artifacts folder."""
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    invoices = []
    
    # Load Bovina invoices
    bovina_dir = artifacts_dir / "bovina" / "invoices"
    if bovina_dir.exists():
        for inv_file in list(bovina_dir.glob("*.json"))[:2]:
            with open(inv_file) as f:
                inv = json.load(f)
                inv["_source"] = f"bovina/{inv_file.name}"
                inv["_entity_id"] = "bf2-company-guid-001"
                invoices.append(inv)
    
    # Load Mesquite invoices
    mesquite_dir = artifacts_dir / "mesquite" / "invoices"
    if mesquite_dir.exists():
        for inv_file in list(mesquite_dir.glob("*.json"))[:2]:
            with open(inv_file) as f:
                inv = json.load(f)
                inv["_source"] = f"mesquite/{inv_file.name}"
                inv["_entity_id"] = "mesquite-company-guid-002"
                invoices.append(inv)
    
    return invoices


def test_normalization():
    """Test the normalization functions."""
    print("=" * 70)
    print("Normalization Tests")
    print("=" * 70)
    
    test_cases = [
        ("BOVINA FEEDERS INC. DBA BF2", "BOVINA FEEDERS BF2"),
        ("Mesquite Cattle Feeders, LLC", "MESQUITE CATTLE FEEDERS"),
        ("Sugar Mountain Livestock", "SUGAR MOUNTAIN LIVESTOCK"),
        ("ABC Company, Inc.", "ABC COMPANY"),
        ("The Acme Corporation, Ltd.", "ACME CORPORATION"),
        ("XYZ & Associates, P.A.", "XYZ ASSOCIATES"),
    ]
    
    passed = 0
    failed = 0
    
    for input_name, expected in test_cases:
        result = normalize_vendor_name(input_name)
        if result == expected:
            print(f"  ✓ '{input_name}' → '{result}'")
            passed += 1
        else:
            print(f"  ✗ '{input_name}' → '{result}' (expected '{expected}')")
            failed += 1
    
    print()
    print(f"Passed: {passed}/{len(test_cases)}")
    print()
    
    # Test tokenization
    print("Tokenization examples:")
    for name in ["BOVINA FEEDERS BF2", "MESQUITE CATTLE FEEDERS"]:
        tokens = tokenize_name(name)
        print(f"  '{name}' → {tokens}")
    print()


async def test_resolver():
    """Test the vendor resolver with sample invoices."""
    print("=" * 70)
    print("Vendor Resolver Test")
    print("=" * 70)
    print()
    
    # Check if we should seed data
    if "--seed" in sys.argv:
        print("Clearing existing data...")
        clear_vendor_aliases()
        print()
    
    # Initialize and seed if needed
    init_vendor_resolver_db()
    
    # Check if we have aliases
    aliases_bf2 = get_aliases_for_entity("bf2-company-guid-001", customer_id="skalable")
    aliases_mesq = get_aliases_for_entity("mesquite-company-guid-002", customer_id="skalable")
    
    total_aliases = len(aliases_bf2) + len(aliases_mesq)
    if total_aliases == 0 and "--seed" in sys.argv:
        print("No vendor aliases found. Seeding sample data...")
        seed_sample_aliases()
        aliases_bf2 = get_aliases_for_entity("bf2-company-guid-001", customer_id="skalable")
        aliases_mesq = get_aliases_for_entity("mesquite-company-guid-002", customer_id="skalable")
        total_aliases = len(aliases_bf2) + len(aliases_mesq)
    
    print(f"Found {total_aliases} vendor aliases:")
    for alias in aliases_bf2:
        print(f"  [BF2] '{alias.alias_normalized}' → {alias.vendor_name} ({alias.vendor_number})")
    for alias in aliases_mesq:
        print(f"  [MESQ] '{alias.alias_normalized}' → {alias.vendor_name} ({alias.vendor_number})")
    print()
    
    # Load sample invoices
    invoices = load_sample_invoices()
    if not invoices:
        print("ERROR: No sample invoices found in artifacts/")
        return
    
    print(f"Loaded {len(invoices)} sample invoices")
    print()
    
    # Create resolver
    resolver = VendorResolver(customer_id="skalable")
    
    # Test each invoice
    print("=" * 70)
    print("Resolution Results")
    print("=" * 70)
    
    alias_count = 0
    fuzzy_count = 0
    no_match_count = 0
    
    for invoice in invoices:
        source = invoice.get("_source", "unknown")
        entity_id = invoice.get("_entity_id")
        
        # Get feedlot name from invoice
        feedlot = invoice.get("feedlot", {}) or {}
        feedlot_name = feedlot.get("name", "")
        feedlot_state = feedlot.get("state", "")
        feedlot_city = feedlot.get("city", "")
        feedlot_address = feedlot.get("address_line1", "")
        
        print(f"\n--- Invoice: {source} ---")
        print(f"  Feedlot name: '{feedlot_name}'")
        print(f"  Location: {feedlot_city}, {feedlot_state}")
        
        # Get vendor list for this entity
        vendor_list = SAMPLE_VENDOR_LISTS.get(entity_id, [])
        
        # Resolve
        resolution = await resolver.resolve_vendor(
            extracted_name=feedlot_name,
            entity_id=entity_id,
            vendor_list=vendor_list,
            extracted_address={
                "address_line1": feedlot_address,
                "city": feedlot_city,
                "state": feedlot_state,
            },
        )
        
        if resolution.is_auto_matched:
            if resolution.match_type == MatchType.EXACT_ALIAS:
                alias_count += 1
            else:
                fuzzy_count += 1
            
            print(f"\n  ✓ AUTO-MATCHED: {resolution.vendor_name}")
            print(f"    Vendor ID: {resolution.vendor_id}")
            print(f"    Vendor #: {resolution.vendor_number}")
            print(f"    Match type: {resolution.match_type.value}")
            print(f"    Confidence: {float(resolution.confidence_score):.1f}%")
            print(f"    Reasons:")
            for reason in resolution.reasons[:3]:
                print(f"      - {reason}")
        else:
            no_match_count += 1
            print(f"\n  ⚠ REQUIRES CONFIRMATION")
            print(f"    Normalized as: '{resolution.normalized_name}'")
            print(f"    Reasons:")
            for reason in resolution.reasons:
                print(f"      - {reason}")
            if resolution.candidates:
                print(f"    Candidates:")
                for i, c in enumerate(resolution.candidates):
                    print(f"      {i+1}. {c.vendor_name} ({c.vendor_number}) - {float(c.score):.1f}%")
        
        print(f"    Resolution time: {resolution.resolution_time_ms}ms")
    
    # Summary
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Total invoices tested: {len(invoices)}")
    print(f"  Alias matches: {alias_count}")
    print(f"  Fuzzy matches: {fuzzy_count}")
    print(f"  Need confirmation: {no_match_count}")
    print()


async def test_specific_scenarios():
    """Test specific resolution scenarios."""
    print("\n")
    print("=" * 70)
    print("Specific Scenario Tests")
    print("=" * 70)
    
    resolver = VendorResolver(customer_id="skalable")
    
    # Scenario 1: Exact alias match (after seeding)
    print("\nScenario 1: Exact alias match")
    res1 = await resolver.resolve_vendor(
        extracted_name="BOVINA FEEDERS INC. DBA BF2",
        entity_id="bf2-company-guid-001",
        vendor_list=SAMPLE_VENDOR_LISTS["bf2-company-guid-001"],
    )
    print(resolver.explain_resolution(res1))
    
    # Scenario 2: Fuzzy match with high confidence
    print("\nScenario 2: Fuzzy match (new name variation)")
    res2 = await resolver.resolve_vendor(
        extracted_name="Bovina Feeders",
        entity_id="bf2-company-guid-001",
        vendor_list=SAMPLE_VENDOR_LISTS["bf2-company-guid-001"],
    )
    print(resolver.explain_resolution(res2))
    
    # Scenario 3: Confirm a match and verify alias is created
    print("\nScenario 3: Confirm match and create alias")
    new_alias = await resolver.confirm_match(
        extracted_name="BF2 Cattle Feeders",
        entity_id="bf2-company-guid-001",
        vendor_id="bovina-vendor-guid-001",
        vendor_number="V-BF2",
        vendor_name="Bovina Feeders Inc.",
        created_by="test_user",
    )
    print(f"  Created alias: '{new_alias.alias_normalized}' → {new_alias.vendor_name}")
    
    # Verify the alias works
    res3 = await resolver.resolve_vendor(
        extracted_name="BF2 Cattle Feeders",
        entity_id="bf2-company-guid-001",
        vendor_list=SAMPLE_VENDOR_LISTS["bf2-company-guid-001"],
    )
    print(f"  Re-resolution: {'Alias match!' if res3.match_type == MatchType.EXACT_ALIAS else 'Not alias match'}")
    
    # Scenario 4: Low confidence match
    print("\nScenario 4: Low confidence (unrelated name)")
    res4 = await resolver.resolve_vendor(
        extracted_name="XYZ Completely Different Company",
        entity_id="bf2-company-guid-001",
        vendor_list=SAMPLE_VENDOR_LISTS["bf2-company-guid-001"],
    )
    print(resolver.explain_resolution(res4))


if __name__ == "__main__":
    print("Vendor Resolver Test Script")
    print("-" * 40)
    print()
    
    # Run normalization tests first
    test_normalization()
    
    # Run async tests
    asyncio.run(test_resolver())
    asyncio.run(test_specific_scenarios())
