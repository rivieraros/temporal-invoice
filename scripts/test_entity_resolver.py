"""Test script for Entity Resolver.

This script tests the entity resolution system with sample invoices
from the Bovina and Mesquite feedlots.

Usage:
    python scripts/test_entity_resolver.py [--seed]
    
Options:
    --seed    Clear and re-seed sample data before testing
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from entity_resolver import (
    EntityResolver,
    EntityResolution,
    init_entity_resolver_db,
    seed_sample_data,
    get_all_entity_profiles,
    get_routing_keys,
)
from entity_resolver.db import clear_entity_resolver_data, DEFAULT_DB_PATH


def load_sample_invoices() -> list:
    """Load sample invoices from artifacts folder."""
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    invoices = []
    
    # Load Bovina invoices
    bovina_dir = artifacts_dir / "bovina" / "invoices"
    if bovina_dir.exists():
        for inv_file in list(bovina_dir.glob("*.json"))[:3]:  # Just first 3
            with open(inv_file) as f:
                inv = json.load(f)
                inv["_source"] = f"bovina/{inv_file.name}"
                invoices.append(inv)
    
    # Load Mesquite invoices
    mesquite_dir = artifacts_dir / "mesquite" / "invoices"
    if mesquite_dir.exists():
        for inv_file in list(mesquite_dir.glob("*.json"))[:2]:  # Just first 2
            with open(inv_file) as f:
                inv = json.load(f)
                inv["_source"] = f"mesquite/{inv_file.name}"
                invoices.append(inv)
    
    return invoices


def load_statements() -> dict:
    """Load statements for additional context."""
    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    statements = {}
    
    for feedlot in ["bovina", "mesquite"]:
        stmt_file = artifacts_dir / feedlot / "statement.json"
        if stmt_file.exists():
            with open(stmt_file) as f:
                statements[feedlot] = json.load(f)
    
    return statements


async def test_resolver():
    """Test the entity resolver with sample invoices."""
    print("=" * 70)
    print("Entity Resolver Test")
    print("=" * 70)
    print()
    
    # Check if we should seed data
    if "--seed" in sys.argv:
        print("Clearing existing data...")
        clear_entity_resolver_data()
        print()
    
    # Initialize and seed if needed
    init_entity_resolver_db()
    
    # Check if we have profiles
    profiles = get_all_entity_profiles()
    if not profiles:
        print("No entity profiles found. Seeding sample data...")
        seed_sample_data()
        profiles = get_all_entity_profiles()
    
    print(f"Found {len(profiles)} entity profiles:")
    for p in profiles:
        print(f"  • {p.entity_code or 'N/A'}: {p.entity_name} ({p.entity_id})")
    print()
    
    # Show routing keys
    routing_keys = get_routing_keys()
    print(f"Found {len(routing_keys)} routing keys:")
    for rk in routing_keys[:10]:  # Show first 10
        print(f"  • [{rk.key_type.value}] {rk.key_value} → {rk.entity_id[:20]}... ({rk.confidence.value})")
    if len(routing_keys) > 10:
        print(f"  ... and {len(routing_keys) - 10} more")
    print()
    
    # Load sample invoices
    invoices = load_sample_invoices()
    if not invoices:
        print("ERROR: No sample invoices found in artifacts/")
        return
    
    print(f"Loaded {len(invoices)} sample invoices")
    print()
    
    # Load statements
    statements = load_statements()
    
    # Create resolver
    resolver = EntityResolver()
    
    # Test each invoice
    print("=" * 70)
    print("Resolution Results")
    print("=" * 70)
    
    auto_count = 0
    manual_count = 0
    
    for invoice in invoices:
        source = invoice.get("_source", "unknown")
        feedlot = source.split("/")[0] if "/" in source else None
        statement = statements.get(feedlot)
        
        print(f"\n--- Invoice: {source} ---")
        print(f"  Invoice #: {invoice.get('invoice_number')}")
        print(f"  Owner: {invoice.get('owner', {}).get('name')} (#{invoice.get('owner', {}).get('owner_number')})")
        print(f"  Feedlot: {invoice.get('feedlot', {}).get('name')}")
        print(f"  Lot: {invoice.get('lot', {}).get('lot_number')}")
        
        # Resolve
        resolution = await resolver.resolve_entity(invoice, statement)
        
        if resolution.is_auto_assigned:
            auto_count += 1
            print(f"\n  ✓ AUTO-ASSIGNED: {resolution.entity.entity_name}")
            print(f"    Entity ID: {resolution.entity_id}")
            print(f"    Confidence: {float(resolution.confidence_score):.1f}/100")
            print(f"    Reasons:")
            for reason in resolution.reasons[:3]:
                print(f"      - {reason}")
        else:
            manual_count += 1
            print(f"\n  ⚠ REQUIRES CONFIRMATION")
            print(f"    Top score: {float(resolution.confidence_score):.1f}/100")
            print(f"    Reasons for manual review:")
            for reason in resolution.reasons:
                print(f"      - {reason}")
            print(f"    Candidates:")
            for i, c in enumerate(resolution.candidates):
                print(f"      {i+1}. {c.entity.entity_name} (score: {float(c.score):.1f})")
                for r in c.reasons[:2]:
                    print(f"         - {r}")
        
        print(f"    Resolution time: {resolution.resolution_time_ms}ms")
    
    # Summary
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"  Total invoices tested: {len(invoices)}")
    print(f"  Auto-assigned: {auto_count} ({100*auto_count/len(invoices):.0f}%)")
    print(f"  Manual confirmation: {manual_count} ({100*manual_count/len(invoices):.0f}%)")
    print()
    
    if auto_count == len(invoices):
        print("✓ All invoices auto-resolved successfully!")
    elif auto_count > 0:
        print("✓ Entity resolver working. Some invoices need confirmation (expected for edge cases).")
    else:
        print("⚠ No invoices auto-resolved. Check routing key configuration.")


async def test_specific_scenarios():
    """Test specific resolution scenarios."""
    print("\n")
    print("=" * 70)
    print("Specific Scenario Tests")
    print("=" * 70)
    
    resolver = EntityResolver()
    
    # Scenario 1: Invoice with owner number 531 (should route to Bovina)
    print("\nScenario 1: Owner #531 invoice (should → Bovina)")
    invoice1 = {
        "owner": {"owner_number": "531", "name": "SUGAR MOUNTAIN LIVESTOCK", "state": "WA"},
        "feedlot": {"name": "BOVINA FEEDERS INC. DBA BF2", "state": "TX"},
        "lot": {"lot_number": "20-3883"},
        "invoice_number": "TEST-001",
    }
    res1 = await resolver.resolve_entity(invoice1)
    print(resolver.explain_resolution(res1))
    
    # Scenario 2: Invoice with ambiguous state (TX matches multiple entities)
    print("\nScenario 2: Ambiguous state only (should need confirmation)")
    invoice2 = {
        "owner": {"owner_number": "999", "name": "UNKNOWN OWNER", "state": "TX"},
        "feedlot": {"name": "GENERIC FEEDLOT", "state": "TX"},
        "lot": {"lot_number": "50-1234"},
        "invoice_number": "TEST-002",
    }
    res2 = await resolver.resolve_entity(invoice2)
    print(resolver.explain_resolution(res2))
    
    # Scenario 3: Invoice with feedlot name match only
    print("\nScenario 3: Feedlot name 'MESQUITE' (should → Mesquite)")
    invoice3 = {
        "owner": {"owner_number": "777", "name": "ANOTHER OWNER", "state": "AZ"},
        "feedlot": {"name": "MESQUITE CATTLE FEEDERS", "state": "TX"},
        "lot": {"lot_number": "43999"},
        "invoice_number": "TEST-003",
    }
    res3 = await resolver.resolve_entity(invoice3)
    print(resolver.explain_resolution(res3))


if __name__ == "__main__":
    print("Entity Resolver Test Script")
    print("-" * 40)
    print()
    
    asyncio.run(test_resolver())
    asyncio.run(test_specific_scenarios())
