"""Entity and GL account mapping engine.

Provides a flexible mapping system that translates extracted canonical data
to ERP-specific codes (vendors, GL accounts, dimensions, etc.).

This is ERP-neutral - the actual mapping rules are provided by configuration
and connectors implement ERP-specific logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import json
import re
from pathlib import Path


class MappingType(str, Enum):
    """Types of mappings supported."""
    VENDOR = "VENDOR"           # Feedlot name → ERP Vendor ID
    GL_ACCOUNT = "GL_ACCOUNT"   # Charge type → GL Account code
    DIMENSION = "DIMENSION"      # Category → Dimension value
    LOCATION = "LOCATION"        # Feedlot → Location code
    PROJECT = "PROJECT"          # Lot → Project code
    COST_CENTER = "COST_CENTER"  # Owner → Cost center
    TAX_CODE = "TAX_CODE"        # Item type → Tax code


@dataclass
class MappingRule:
    """A single mapping rule.
    
    Rules can use exact match, pattern match, or custom logic.
    """
    rule_id: str
    mapping_type: MappingType
    source_field: str           # Field in canonical model to match
    source_pattern: str         # Regex pattern or exact value
    target_code: str            # ERP code to map to
    target_name: Optional[str] = None  # Human-readable name
    priority: int = 0           # Higher = checked first
    is_regex: bool = False      # True if source_pattern is regex
    is_default: bool = False    # True if this is a fallback rule
    conditions: Dict[str, Any] = field(default_factory=dict)  # Additional conditions
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, value: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if this rule matches the given value."""
        if value is None:
            return False
        
        if self.is_default:
            return True
        
        if self.is_regex:
            pattern = re.compile(self.source_pattern, re.IGNORECASE)
            if not pattern.search(value):
                return False
        else:
            if value.upper() != self.source_pattern.upper():
                return False
        
        # Check additional conditions
        if self.conditions and context:
            for key, expected in self.conditions.items():
                actual = context.get(key)
                if actual != expected:
                    return False
        
        return True


@dataclass
class MappingResult:
    """Result of a mapping operation."""
    success: bool
    mapping_type: MappingType
    source_value: str
    target_code: Optional[str] = None
    target_name: Optional[str] = None
    rule_id: Optional[str] = None
    confidence: float = 1.0     # 1.0 = exact match, <1.0 = fuzzy
    warnings: List[str] = field(default_factory=list)
    
    @classmethod
    def not_found(cls, mapping_type: MappingType, source_value: str) -> "MappingResult":
        """Create a failed mapping result."""
        return cls(
            success=False,
            mapping_type=mapping_type,
            source_value=source_value,
            warnings=[f"No mapping found for {mapping_type.value}: {source_value}"]
        )


@dataclass
class EntityMapping:
    """Mapping for an entity (vendor, customer, etc.)."""
    entity_type: str            # "VENDOR", "CUSTOMER", etc.
    source_name: str            # Name in extracted data
    erp_code: str              # Code in ERP
    erp_name: Optional[str] = None
    additional_codes: Dict[str, str] = field(default_factory=dict)  # e.g., {"tax_group": "EXEMPT"}


@dataclass
class GLAccountMapping:
    """Mapping for a GL account."""
    description_pattern: str    # Pattern to match in line item description
    gl_account: str            # GL account code
    gl_name: Optional[str] = None
    is_regex: bool = False
    dimension_values: Dict[str, str] = field(default_factory=dict)  # e.g., {"department": "FEED"}


class MappingEngine:
    """Engine for mapping canonical data to ERP codes.
    
    This is ERP-neutral - it loads rules from configuration and applies them.
    ERP-specific connectors can extend this with custom logic.
    """
    
    def __init__(self, rules: Optional[List[MappingRule]] = None):
        """Initialize mapping engine.
        
        Args:
            rules: Initial list of mapping rules
        """
        self._rules: Dict[MappingType, List[MappingRule]] = {mt: [] for mt in MappingType}
        if rules:
            for rule in rules:
                self.add_rule(rule)
    
    def add_rule(self, rule: MappingRule) -> None:
        """Add a mapping rule."""
        self._rules[rule.mapping_type].append(rule)
        # Keep sorted by priority (descending)
        self._rules[rule.mapping_type].sort(key=lambda r: -r.priority)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if removed."""
        for mapping_type in MappingType:
            rules = self._rules[mapping_type]
            for i, rule in enumerate(rules):
                if rule.rule_id == rule_id:
                    del rules[i]
                    return True
        return False
    
    def map(self, mapping_type: MappingType, value: str, 
            context: Optional[Dict[str, Any]] = None) -> MappingResult:
        """Map a value using the configured rules.
        
        Args:
            mapping_type: Type of mapping to perform
            value: Value to map
            context: Additional context for conditional rules
            
        Returns:
            MappingResult with success status and mapped code
        """
        if not value:
            return MappingResult.not_found(mapping_type, value or "")
        
        rules = self._rules.get(mapping_type, [])
        
        # First pass: non-default rules
        for rule in rules:
            if not rule.is_default and rule.matches(value, context):
                return MappingResult(
                    success=True,
                    mapping_type=mapping_type,
                    source_value=value,
                    target_code=rule.target_code,
                    target_name=rule.target_name,
                    rule_id=rule.rule_id,
                    confidence=1.0 if not rule.is_regex else 0.9,
                )
        
        # Second pass: default rules
        for rule in rules:
            if rule.is_default:
                return MappingResult(
                    success=True,
                    mapping_type=mapping_type,
                    source_value=value,
                    target_code=rule.target_code,
                    target_name=rule.target_name,
                    rule_id=rule.rule_id,
                    confidence=0.5,
                    warnings=[f"Using default mapping for: {value}"]
                )
        
        return MappingResult.not_found(mapping_type, value)
    
    def map_vendor(self, vendor_name: str, context: Optional[Dict] = None) -> MappingResult:
        """Convenience method to map a vendor name."""
        return self.map(MappingType.VENDOR, vendor_name, context)
    
    def map_gl_account(self, description: str, context: Optional[Dict] = None) -> MappingResult:
        """Convenience method to map a GL account from description."""
        return self.map(MappingType.GL_ACCOUNT, description, context)
    
    def map_location(self, feedlot_name: str, context: Optional[Dict] = None) -> MappingResult:
        """Convenience method to map a location code."""
        return self.map(MappingType.LOCATION, feedlot_name, context)
    
    def load_rules_from_json(self, path: Path) -> int:
        """Load mapping rules from a JSON file.
        
        Expected format:
        {
            "rules": [
                {
                    "rule_id": "vendor_bovina",
                    "mapping_type": "VENDOR",
                    "source_field": "feedlot.name",
                    "source_pattern": "BOVINA FEEDERS",
                    "target_code": "V00001",
                    "target_name": "Bovina Feeders Inc",
                    "priority": 100,
                    "is_regex": true
                }
            ]
        }
        
        Returns:
            Number of rules loaded
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        count = 0
        for rule_data in data.get("rules", []):
            rule = MappingRule(
                rule_id=rule_data["rule_id"],
                mapping_type=MappingType(rule_data["mapping_type"]),
                source_field=rule_data.get("source_field", ""),
                source_pattern=rule_data["source_pattern"],
                target_code=rule_data["target_code"],
                target_name=rule_data.get("target_name"),
                priority=rule_data.get("priority", 0),
                is_regex=rule_data.get("is_regex", False),
                is_default=rule_data.get("is_default", False),
                conditions=rule_data.get("conditions", {}),
                metadata=rule_data.get("metadata", {}),
            )
            self.add_rule(rule)
            count += 1
        
        return count
    
    def save_rules_to_json(self, path: Path) -> None:
        """Save all rules to a JSON file."""
        rules_data = []
        for mapping_type in MappingType:
            for rule in self._rules[mapping_type]:
                rules_data.append({
                    "rule_id": rule.rule_id,
                    "mapping_type": rule.mapping_type.value,
                    "source_field": rule.source_field,
                    "source_pattern": rule.source_pattern,
                    "target_code": rule.target_code,
                    "target_name": rule.target_name,
                    "priority": rule.priority,
                    "is_regex": rule.is_regex,
                    "is_default": rule.is_default,
                    "conditions": rule.conditions,
                    "metadata": rule.metadata,
                })
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"rules": rules_data}, f, indent=2)
    
    def get_rules(self, mapping_type: Optional[MappingType] = None) -> List[MappingRule]:
        """Get all rules, optionally filtered by type."""
        if mapping_type:
            return list(self._rules.get(mapping_type, []))
        
        all_rules = []
        for rules in self._rules.values():
            all_rules.extend(rules)
        return all_rules
    
    def get_stats(self) -> Dict[str, int]:
        """Get count of rules by type."""
        return {mt.value: len(rules) for mt, rules in self._rules.items()}
