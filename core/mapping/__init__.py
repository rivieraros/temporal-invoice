"""Core mapping engine - entity and GL account mapping.

This module provides ERP-neutral mapping interfaces and a base engine
for mapping extracted data to ERP-specific codes.

The actual mapping values are stored in configuration (JSON/DB) and
are ERP-specific implementations provided by connectors.
"""

from core.mapping.engine import (
    MappingEngine,
    MappingResult,
    MappingRule,
    MappingType,
    EntityMapping,
    GLAccountMapping,
)

__all__ = [
    "MappingEngine",
    "MappingResult",
    "MappingRule",
    "MappingType",
    "EntityMapping",
    "GLAccountMapping",
]
