"""Entity Resolver - Automatic BC company selection for invoices.

This package provides intelligent entity (BC company) resolution for invoices
based on configurable routing rules and scoring algorithms.

Key Features:
- Minimal configuration for 50+ entities
- Multiple routing key types (owner_number, remit_state, lot_prefix, feedlot_name)
- Confidence scoring with auto-assign or top-3 candidates
- Integration with BC connector for vendor existence checks

Usage:
    from entity_resolver import EntityResolver, EntityResolution

    resolver = EntityResolver(db_path="ap_automation.db")
    resolution = await resolver.resolve_entity(invoice, statement, bc_connector)
    
    if resolution.is_auto_assigned:
        # Use resolution.entity directly
        entity_id = resolution.entity.id
    else:
        # Show resolution.candidates to user for confirmation
        for candidate in resolution.candidates:
            print(f"{candidate.entity.name}: {candidate.score} ({candidate.reasons})")
"""

from entity_resolver.models import (
    EntityProfile,
    EntityRoutingKey,
    RoutingKeyType,
    ConfidenceLevel,
    EntityCandidate,
    EntityResolution,
)
from entity_resolver.resolver import EntityResolver
from entity_resolver.db import (
    init_entity_resolver_db,
    seed_sample_data,
    get_entity_profile,
    get_all_entity_profiles,
    get_routing_keys,
    add_entity_profile,
    add_routing_key,
)

__all__ = [
    # Models
    "EntityProfile",
    "EntityRoutingKey",
    "RoutingKeyType",
    "ConfidenceLevel",
    "EntityCandidate",
    "EntityResolution",
    # Resolver
    "EntityResolver",
    # Database
    "init_entity_resolver_db",
    "seed_sample_data",
    "get_entity_profile",
    "get_all_entity_profiles",
    "get_routing_keys",
    "add_entity_profile",
    "add_routing_key",
]
