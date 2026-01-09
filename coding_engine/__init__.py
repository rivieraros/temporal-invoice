"""
Coding Engine Package

ERP-agnostic mapping/coding engine that generates GL coding for invoices.

Features:
- Hierarchical GL mappings (Vendor → Entity → Global → Suspense)
- Dimension rules with transformations
- Category-based line item coding
- Missing mapping detection

Usage:
    from coding_engine import CodingEngine, code_invoice
    
    # Using the engine class
    engine = CodingEngine(entity_id="BF2", vendor_id="V-BF2")
    coding = engine.code_invoice(invoice_data, vendor_info)
    
    # Using convenience function
    coding = code_invoice(invoice_data, entity_id="BF2")
"""

from .models import (
    # Enums
    MappingLevel,
    DimensionSource,
    TransformType,
    
    # Data classes
    GLMapping,
    DimensionRule,
    DimensionValue,
    LineCoding,
    InvoiceCoding,
    SuspenseConfig,
    
    # Helpers
    categorize_line_item,
    CATEGORY_PATTERNS,
)

from .db import (
    # Database init
    init_coding_engine_db,
    
    # GL Mapping CRUD
    add_gl_mapping,
    get_gl_mapping,
    get_all_mappings_for_entity,
    get_global_mappings,
    
    # Dimension Rule CRUD
    add_dimension_rule,
    get_dimension_rules,
    get_dimension_rule,
    
    # Seeding
    seed_global_mappings,
    seed_entity_mappings,
    seed_dimension_rules,
    seed_sample_data,
)

from .rules import (
    # Context
    DimensionContext,
    
    # Resolution
    resolve_dimension,
    resolve_all_dimensions,
    
    # Transforms
    apply_transform,
    extract_year_month,
    normalize_feedlot_code,
)

from .engine import (
    CodingEngine,
    code_invoice,
    preview_coding,
)

__all__ = [
    # Enums
    "MappingLevel",
    "DimensionSource",
    "TransformType",
    
    # Data classes
    "GLMapping",
    "DimensionRule",
    "DimensionValue",
    "LineCoding",
    "InvoiceCoding",
    "SuspenseConfig",
    
    # Engine
    "CodingEngine",
    "code_invoice",
    "preview_coding",
    
    # Database
    "init_coding_engine_db",
    "add_gl_mapping",
    "get_gl_mapping",
    "get_all_mappings_for_entity",
    "get_global_mappings",
    "add_dimension_rule",
    "get_dimension_rules",
    "get_dimension_rule",
    "seed_sample_data",
    
    # Rules
    "DimensionContext",
    "resolve_dimension",
    "resolve_all_dimensions",
    "categorize_line_item",
]
