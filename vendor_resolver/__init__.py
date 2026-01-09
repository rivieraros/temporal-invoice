"""Vendor Resolver - Automatic vendor matching within a BC entity.

This package provides intelligent vendor resolution for invoices based on:
- Exact alias matching (fast path)
- Fuzzy name matching with token similarity
- Address matching for disambiguation

Key Features:
- Per-entity vendor alias table for minimal configuration
- Normalization of vendor/feedlot names
- One-time alias confirmation creates permanent mapping
- Integrates with BC connector for vendor list queries

Usage:
    from vendor_resolver import VendorResolver, VendorResolution

    resolver = VendorResolver(db_path="ap_automation.db")
    resolution = await resolver.resolve_vendor(
        extracted_name="BOVINA FEEDERS INC. DBA BF2",
        entity_id="bf2-company-guid-001",
        vendor_list=bc_vendors,  # From BC connector
    )
    
    if resolution.is_auto_matched:
        vendor_id = resolution.vendor.id
    else:
        # Show resolution.candidates to user for confirmation
        for candidate in resolution.candidates:
            print(f"{candidate.vendor.name}: {candidate.score}")
"""

from vendor_resolver.models import (
    VendorAlias,
    VendorCandidate,
    VendorResolution,
    MatchType,
)
from vendor_resolver.resolver import VendorResolver
from vendor_resolver.normalize import normalize_vendor_name, tokenize_name
from vendor_resolver.db import (
    init_vendor_resolver_db,
    add_vendor_alias,
    get_vendor_alias,
    get_aliases_for_entity,
    delete_vendor_alias,
    seed_sample_aliases,
)

__all__ = [
    # Models
    "VendorAlias",
    "VendorCandidate",
    "VendorResolution",
    "MatchType",
    # Resolver
    "VendorResolver",
    # Normalization
    "normalize_vendor_name",
    "tokenize_name",
    # Database
    "init_vendor_resolver_db",
    "add_vendor_alias",
    "get_vendor_alias",
    "get_aliases_for_entity",
    "delete_vendor_alias",
    "seed_sample_aliases",
]
