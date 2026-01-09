"""
Coding Engine Models

Defines data structures for:
- GL mappings (global, entity, vendor)
- Dimension rules and values
- Coding results
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from decimal import Decimal


class MappingLevel(str, Enum):
    """Mapping precedence levels (higher = more specific)"""
    VENDOR = "vendor"      # Most specific: entity + vendor + category
    ENTITY = "entity"      # Entity-level: entity + category
    GLOBAL = "global"      # Global default: category only
    SUSPENSE = "suspense"  # Fallback when no mapping found


class DimensionSource(str, Enum):
    """Source fields for dimension values"""
    INVOICE_LOT_NUMBER = "invoice.lot_number"
    INVOICE_DATE = "invoice.invoice_date"
    INVOICE_NUMBER = "invoice.invoice_number"
    OWNER_NUMBER = "owner.number"
    OWNER_NAME = "owner.name"
    FEEDLOT_NAME = "feedlot.name"
    STATEMENT_PERIOD_START = "statement.period_start"
    STATEMENT_PERIOD_END = "statement.period_end"
    ENTITY_CODE = "entity.code"
    VENDOR_NUMBER = "vendor.number"
    LINE_DESCRIPTION = "line.description"
    FIXED_VALUE = "fixed"


class TransformType(str, Enum):
    """Transformation types for dimension values"""
    NONE = "none"                    # Use as-is
    UPPERCASE = "uppercase"          # Convert to uppercase
    EXTRACT_YEAR_MONTH = "yyyy_mm"   # Extract YYYY-MM from date
    EXTRACT_YEAR = "yyyy"            # Extract YYYY from date
    NORMALIZE_CODE = "normalize"     # Normalize to standard code
    PREFIX = "prefix"                # Add prefix
    SUFFIX = "suffix"                # Add suffix
    TRUNCATE = "truncate"            # Truncate to max length
    MAP_VALUE = "map"                # Map to different value


# =============================================================================
# GL Mapping Models
# =============================================================================

@dataclass
class GLMapping:
    """
    A single GL account mapping.
    
    Attributes:
        id: Database ID
        level: Mapping level (vendor, entity, global)
        entity_id: Entity ID (required for entity/vendor level)
        vendor_id: Vendor ID (required for vendor level)
        category: Line item category (e.g., "FEED", "YARDAGE", "VET")
        gl_account_ref: GL account reference/number
        description: Human-readable description
        is_active: Whether mapping is active
    """
    category: str
    gl_account_ref: str
    level: MappingLevel = MappingLevel.GLOBAL
    entity_id: Optional[str] = None
    vendor_id: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    id: Optional[int] = None
    
    def __post_init__(self):
        # Normalize category to uppercase
        self.category = self.category.upper().strip()


@dataclass
class DimensionRule:
    """
    A rule for generating a dimension value.
    
    Attributes:
        id: Database ID
        entity_id: Entity this rule applies to (None = global)
        dimension_code: Dimension identifier (e.g., "LOT", "FEEDLOT", "PERIOD")
        source_field: Source of the dimension value
        transform: Transformation to apply
        transform_params: Parameters for the transformation
        default_value: Default if source is empty
        is_required: Whether dimension is required
    """
    dimension_code: str
    source_field: DimensionSource
    transform: TransformType = TransformType.NONE
    entity_id: Optional[str] = None
    transform_params: Optional[Dict[str, Any]] = None
    default_value: Optional[str] = None
    is_required: bool = False
    id: Optional[int] = None
    
    def __post_init__(self):
        self.dimension_code = self.dimension_code.upper().strip()
        if self.transform_params is None:
            self.transform_params = {}


# =============================================================================
# Coding Result Models
# =============================================================================

@dataclass
class DimensionValue:
    """A resolved dimension value"""
    code: str           # Dimension code (e.g., "LOT")
    value: str          # Resolved value (e.g., "20-3883")
    source: str         # Where it came from
    

@dataclass
class LineCoding:
    """
    Coding for a single invoice line.
    
    Attributes:
        line_index: Index of the line in the invoice
        description: Line description from invoice
        amount: Line amount
        category: Resolved category
        gl_ref: GL account reference
        mapping_level: Which level provided the mapping
        dimensions: List of dimension values
        is_complete: Whether all required dimensions are present
        missing_dimensions: List of missing required dimensions
    """
    line_index: int
    description: str
    amount: Decimal
    category: str
    gl_ref: str
    mapping_level: MappingLevel
    dimensions: List[DimensionValue] = field(default_factory=list)
    is_complete: bool = True
    missing_dimensions: List[str] = field(default_factory=list)


@dataclass
class InvoiceCoding:
    """
    Complete coding for an invoice.
    
    Attributes:
        invoice_number: Invoice identifier
        entity_id: Resolved entity ID
        vendor_ref: Vendor reference for posting
        vendor_number: Vendor number
        vendor_name: Vendor name
        invoice_date: Invoice date
        total_amount: Invoice total
        line_codings: Coding for each line
        is_complete: Whether all lines are fully coded
        missing_mappings: Categories that need mapping
        missing_dimensions: Dimensions that need rules
        warnings: Non-blocking issues
    """
    invoice_number: str
    entity_id: str
    vendor_ref: str
    vendor_number: str
    vendor_name: str
    invoice_date: str
    total_amount: Decimal
    line_codings: List[LineCoding] = field(default_factory=list)
    is_complete: bool = True
    missing_mappings: List[str] = field(default_factory=list)
    missing_dimensions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "invoice_number": self.invoice_number,
            "entity_id": self.entity_id,
            "vendor_ref": self.vendor_ref,
            "vendor_number": self.vendor_number,
            "vendor_name": self.vendor_name,
            "invoice_date": self.invoice_date,
            "total_amount": str(self.total_amount),
            "is_complete": self.is_complete,
            "missing_mappings": self.missing_mappings,
            "missing_dimensions": self.missing_dimensions,
            "warnings": self.warnings,
            "line_codings": [
                {
                    "line_index": lc.line_index,
                    "description": lc.description,
                    "amount": str(lc.amount),
                    "category": lc.category,
                    "gl_ref": lc.gl_ref,
                    "mapping_level": lc.mapping_level.value,
                    "dimensions": [
                        {"code": d.code, "value": d.value, "source": d.source}
                        for d in lc.dimensions
                    ],
                    "is_complete": lc.is_complete,
                    "missing_dimensions": lc.missing_dimensions,
                }
                for lc in self.line_codings
            ],
        }


# =============================================================================
# Category Extraction Helpers
# =============================================================================

# Common feedlot line item categories
CATEGORY_PATTERNS = {
    # Feed categories
    "FEED": ["feed", "ration", "corn", "grain", "hay", "silage", "supplement"],
    "YARDAGE": ["yardage", "yard", "pen", "housing"],
    "VET": ["vet", "veterinary", "medicine", "medical", "health", "treatment", "vaccine"],
    "PROCESSING": ["processing", "process", "handling"],
    "FREIGHT": ["freight", "shipping", "hauling", "transport", "trucking"],
    "INTEREST": ["interest", "finance", "carrying"],
    "DEATH_LOSS": ["death", "mortality", "loss", "dead"],
    "INSURANCE": ["insurance", "coverage"],
    "COMMISSION": ["commission", "marketing", "sales"],
    "CHECKOFF": ["checkoff", "beef checkoff", "assessment"],
    "BRAND": ["brand", "branding", "inspection"],
    "MISC": ["misc", "miscellaneous", "other", "sundry"],
}


def categorize_line_item(description: str) -> str:
    """
    Categorize a line item description.
    
    Args:
        description: Line item description from invoice
        
    Returns:
        Category code (e.g., "FEED", "VET", "YARDAGE")
    """
    if not description:
        return "UNCATEGORIZED"
    
    desc_lower = description.lower()
    
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern in desc_lower:
                return category
    
    return "UNCATEGORIZED"


# =============================================================================
# Suspense Account Configuration
# =============================================================================

@dataclass
class SuspenseConfig:
    """Configuration for suspense account handling"""
    gl_account_ref: str = "9999-00"  # Default suspense account
    description: str = "Unmapped - Requires Review"
    require_review: bool = True
