"""
Dimension Rules Engine

Applies dimension rules to extract values from invoice/statement context.
Supports various transformations (YYYY-MM, normalize, uppercase, etc.)
"""

import re
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from .models import (
    DimensionRule,
    DimensionValue,
    DimensionSource,
    TransformType,
)


# =============================================================================
# Feedlot Code Normalization
# =============================================================================

FEEDLOT_CODE_MAP = {
    # Bovina variations
    "BOVINA FEEDERS": "BF2",
    "BOVINA FEEDERS INC": "BF2",
    "BOVINA FEEDERS INC DBA BF2": "BF2",
    "BF2": "BF2",
    
    # Mesquite variations
    "MESQUITE CATTLE": "MESQ",
    "MESQUITE CATTLE FEEDERS": "MESQ",
    "MESQUITE": "MESQ",
    "MCF": "MESQ",
}


def normalize_feedlot_code(name: str) -> str:
    """
    Normalize feedlot name to standard code.
    
    Args:
        name: Feedlot name from document
        
    Returns:
        Normalized code (e.g., "BF2", "MESQ")
    """
    if not name:
        return ""
    
    # Uppercase and clean
    clean_name = name.upper().strip()
    
    # Remove punctuation
    clean_name = re.sub(r'[.,;:\-\'"()]+', ' ', clean_name)
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    # Try direct lookup
    if clean_name in FEEDLOT_CODE_MAP:
        return FEEDLOT_CODE_MAP[clean_name]
    
    # Try partial matches
    for pattern, code in FEEDLOT_CODE_MAP.items():
        if pattern in clean_name or clean_name in pattern:
            return code
    
    # Return first word as fallback
    words = clean_name.split()
    return words[0] if words else clean_name


# =============================================================================
# Transformation Functions
# =============================================================================

def apply_transform(
    value: str,
    transform: TransformType,
    params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Apply a transformation to a value.
    
    Args:
        value: Input value
        transform: Transform type to apply
        params: Optional parameters for the transform
        
    Returns:
        Transformed value
    """
    if not value:
        return ""
    
    params = params or {}
    
    if transform == TransformType.NONE:
        return value
    
    if transform == TransformType.UPPERCASE:
        return value.upper()
    
    if transform == TransformType.EXTRACT_YEAR_MONTH:
        return extract_year_month(value)
    
    if transform == TransformType.EXTRACT_YEAR:
        return extract_year(value)
    
    if transform == TransformType.NORMALIZE_CODE:
        return normalize_feedlot_code(value)
    
    if transform == TransformType.PREFIX:
        prefix = params.get("prefix", "")
        return f"{prefix}{value}"
    
    if transform == TransformType.SUFFIX:
        suffix = params.get("suffix", "")
        return f"{value}{suffix}"
    
    if transform == TransformType.TRUNCATE:
        max_len = params.get("max_length", 20)
        return value[:max_len]
    
    if transform == TransformType.MAP_VALUE:
        value_map = params.get("map", {})
        return value_map.get(value, value)
    
    return value


def extract_year_month(date_value: str) -> str:
    """
    Extract YYYY-MM from a date string or date object.
    
    Handles:
    - ISO format: 2025-11-15
    - Date object
    - US format: 11/15/2025
    - Various other formats
    
    Args:
        date_value: Date string or date object
        
    Returns:
        YYYY-MM string
    """
    if not date_value:
        return ""
    
    # If already a date object
    if isinstance(date_value, (date, datetime)):
        return date_value.strftime("%Y-%m")
    
    date_str = str(date_value).strip()
    
    # Try ISO format first (YYYY-MM-DD)
    iso_match = re.match(r'(\d{4})-(\d{2})-\d{2}', date_str)
    if iso_match:
        return f"{iso_match.group(1)}-{iso_match.group(2)}"
    
    # Try US format (MM/DD/YYYY or M/D/YYYY)
    us_match = re.match(r'(\d{1,2})/\d{1,2}/(\d{4})', date_str)
    if us_match:
        month = us_match.group(1).zfill(2)
        year = us_match.group(2)
        return f"{year}-{month}"
    
    # Try to parse with datetime
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue
    
    # Last resort: extract any YYYY-MM pattern
    pattern_match = re.search(r'(\d{4})-(\d{2})', date_str)
    if pattern_match:
        return pattern_match.group(0)
    
    return ""


def extract_year(date_value: str) -> str:
    """
    Extract YYYY from a date string.
    
    Args:
        date_value: Date string or date object
        
    Returns:
        YYYY string
    """
    year_month = extract_year_month(date_value)
    if year_month and "-" in year_month:
        return year_month.split("-")[0]
    return ""


# =============================================================================
# Context Extraction
# =============================================================================

class DimensionContext:
    """
    Context object holding all data sources for dimension resolution.
    
    Attributes:
        invoice: Invoice data dict
        statement: Statement data dict (optional)
        entity: Entity data dict
        vendor: Vendor data dict
    """
    
    def __init__(
        self,
        invoice: Optional[Dict[str, Any]] = None,
        statement: Optional[Dict[str, Any]] = None,
        entity: Optional[Dict[str, Any]] = None,
        vendor: Optional[Dict[str, Any]] = None,
    ):
        self.invoice = invoice or {}
        self.statement = statement or {}
        self.entity = entity or {}
        self.vendor = vendor or {}
    
    def get_value(self, source: DimensionSource) -> Optional[str]:
        """
        Get a value from the context based on source specification.
        
        Args:
            source: DimensionSource enum
            
        Returns:
            Value string or None if not found
        """
        # Check for DimensionSource enum first (before str check, since DimensionSource extends str)
        if isinstance(source, DimensionSource):
            source_map = {
                DimensionSource.INVOICE_LOT_NUMBER: lambda: self._get_nested(self.invoice, "lot_number"),
                DimensionSource.INVOICE_DATE: lambda: self._get_nested(self.invoice, "invoice_date"),
                DimensionSource.INVOICE_NUMBER: lambda: self._get_nested(self.invoice, "invoice_number"),
                DimensionSource.OWNER_NUMBER: lambda: self._get_nested(self.invoice, "owner", "number") 
                                                       or self._get_nested(self.statement, "owner", "number"),
                DimensionSource.OWNER_NAME: lambda: self._get_nested(self.invoice, "owner", "name")
                                                     or self._get_nested(self.statement, "owner", "name"),
                DimensionSource.FEEDLOT_NAME: lambda: self._get_nested(self.invoice, "feedlot", "name")
                                                       or self._get_nested(self.invoice, "feedlot_name")
                                                       or self._get_nested(self.statement, "feedlot", "name"),
                DimensionSource.STATEMENT_PERIOD_START: lambda: self._get_nested(self.statement, "period_start"),
                DimensionSource.STATEMENT_PERIOD_END: lambda: self._get_nested(self.statement, "period_end"),
                DimensionSource.ENTITY_CODE: lambda: self._get_nested(self.entity, "code")
                                                      or self._get_nested(self.entity, "entity_id"),
                DimensionSource.VENDOR_NUMBER: lambda: self._get_nested(self.vendor, "number")
                                                        or self._get_nested(self.vendor, "vendor_number"),
                DimensionSource.LINE_DESCRIPTION: lambda: None,  # Handled at line level
                DimensionSource.FIXED_VALUE: lambda: None,  # Use default_value instead
            }
            
            getter = source_map.get(source)
            if getter:
                value = getter()
                return str(value) if value is not None else None
            
            return None
        
        # Handle custom source paths (plain strings)
        if isinstance(source, str):
            return self._get_by_path(source)
        
        return None
    
    def _get_nested(self, data: Dict[str, Any], *keys: str) -> Optional[Any]:
        """Get nested value from dict"""
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current
    
    def _get_by_path(self, path: str) -> Optional[str]:
        """
        Get value by dot-notation path.
        
        Example: "invoice.lot_number" → self.invoice["lot_number"]
        """
        parts = path.split(".")
        if len(parts) < 2:
            return None
        
        root = parts[0]
        keys = parts[1:]
        
        data_map = {
            "invoice": self.invoice,
            "statement": self.statement,
            "entity": self.entity,
            "vendor": self.vendor,
            "line": {},  # Handled separately
        }
        
        data = data_map.get(root, {})
        value = self._get_nested(data, *keys)
        return str(value) if value is not None else None


# =============================================================================
# Dimension Resolution
# =============================================================================

def resolve_dimension(
    rule: DimensionRule,
    context: DimensionContext,
    line_data: Optional[Dict[str, Any]] = None,
) -> Optional[DimensionValue]:
    """
    Resolve a single dimension value using a rule and context.
    
    Args:
        rule: DimensionRule to apply
        context: DimensionContext with data sources
        line_data: Optional line-level data
        
    Returns:
        DimensionValue if resolved, None if no value found
    """
    # Get raw value from source
    raw_value = None
    
    if rule.source_field == DimensionSource.LINE_DESCRIPTION and line_data:
        raw_value = line_data.get("description", "")
    elif rule.source_field == DimensionSource.FIXED_VALUE:
        raw_value = rule.default_value
    else:
        raw_value = context.get_value(rule.source_field)
    
    # Apply default if no value
    if not raw_value and rule.default_value:
        raw_value = rule.default_value
    
    # If still no value, return None
    if not raw_value:
        return None
    
    # Apply transformation
    transformed_value = apply_transform(
        raw_value,
        rule.transform,
        rule.transform_params,
    )
    
    if not transformed_value:
        return None
    
    # Build source description
    source_desc = rule.source_field.value if isinstance(rule.source_field, DimensionSource) else str(rule.source_field)
    if rule.transform != TransformType.NONE:
        source_desc += f" ({rule.transform.value})"
    
    return DimensionValue(
        code=rule.dimension_code,
        value=transformed_value,
        source=source_desc,
    )


def resolve_all_dimensions(
    rules: List[DimensionRule],
    context: DimensionContext,
    line_data: Optional[Dict[str, Any]] = None,
) -> tuple[List[DimensionValue], List[str]]:
    """
    Resolve all dimensions using rules and context.
    
    Args:
        rules: List of DimensionRule objects
        context: DimensionContext with data sources
        line_data: Optional line-level data
        
    Returns:
        Tuple of (resolved dimensions, missing required dimensions)
    """
    resolved = []
    missing = []
    
    for rule in rules:
        dim_value = resolve_dimension(rule, context, line_data)
        
        if dim_value:
            resolved.append(dim_value)
        elif rule.is_required:
            missing.append(rule.dimension_code)
    
    return resolved, missing
