"""
Coding Engine

Main engine that generates GL coding for invoices:
1. Categorize line items
2. Look up GL mappings (Vendor → Entity → Global → Suspense)
3. Apply dimension rules
4. Return complete coding with missing mappings list
"""

from decimal import Decimal
from typing import Optional, Dict, Any, List

from .models import (
    GLMapping,
    DimensionRule,
    DimensionValue,
    LineCoding,
    InvoiceCoding,
    MappingLevel,
    SuspenseConfig,
    categorize_line_item,
)
from .db import (
    init_coding_engine_db,
    get_gl_mapping,
    get_dimension_rules,
)
from .rules import (
    DimensionContext,
    resolve_all_dimensions,
)


class CodingEngine:
    """
    ERP-agnostic coding engine that generates GL coding for invoices.
    
    Usage:
        engine = CodingEngine(entity_id="BF2", vendor_id="V-BF2")
        coding = engine.code_invoice(invoice_data, vendor_info, statement_data)
    """
    
    def __init__(
        self,
        entity_id: str,
        vendor_id: Optional[str] = None,
        suspense_config: Optional[SuspenseConfig] = None,
    ):
        """
        Initialize the coding engine.
        
        Args:
            entity_id: Entity ID for mapping lookup
            vendor_id: Vendor ID for vendor-level mappings
            suspense_config: Configuration for unmapped items
        """
        self.entity_id = entity_id
        self.vendor_id = vendor_id
        self.suspense_config = suspense_config or SuspenseConfig()
        
        # Ensure database tables exist
        init_coding_engine_db()
        
        # Cache dimension rules for this entity
        self._dimension_rules = get_dimension_rules(entity_id)
    
    def code_invoice(
        self,
        invoice: Dict[str, Any],
        vendor: Optional[Dict[str, Any]] = None,
        statement: Optional[Dict[str, Any]] = None,
        entity: Optional[Dict[str, Any]] = None,
    ) -> InvoiceCoding:
        """
        Generate complete coding for an invoice.
        
        Args:
            invoice: Invoice data (canonical format)
            vendor: Vendor resolution result
            statement: Statement data (optional, for dimensions)
            entity: Entity data (optional)
            
        Returns:
            InvoiceCoding with line codings and missing mappings
        """
        # Build context for dimension resolution
        entity_data = entity or {"entity_id": self.entity_id, "code": self.entity_id}
        vendor_data = vendor or {}
        
        context = DimensionContext(
            invoice=invoice,
            statement=statement or {},
            entity=entity_data,
            vendor=vendor_data,
        )
        
        # Extract invoice header info
        invoice_number = invoice.get("invoice_number", "UNKNOWN")
        invoice_date = invoice.get("invoice_date", "")
        total_amount = Decimal(str(invoice.get("total", 0)))
        
        # Vendor info
        vendor_ref = vendor_data.get("vendor_id", vendor_data.get("id", ""))
        vendor_number = vendor_data.get("vendor_number", vendor_data.get("number", ""))
        vendor_name = vendor_data.get("vendor_name", vendor_data.get("name", ""))
        
        # Process each line item
        line_codings = []
        missing_categories = set()
        missing_dimensions = set()
        warnings = []
        
        line_items = invoice.get("line_items", [])
        
        for idx, line in enumerate(line_items):
            line_coding = self._code_line(
                line_index=idx,
                line=line,
                context=context,
            )
            line_codings.append(line_coding)
            
            # Track missing mappings
            if line_coding.mapping_level == MappingLevel.SUSPENSE:
                missing_categories.add(line_coding.category)
            
            # Track missing dimensions
            for dim in line_coding.missing_dimensions:
                missing_dimensions.add(dim)
        
        # Add warning for uncategorized items
        uncategorized_count = sum(
            1 for lc in line_codings 
            if lc.category == "UNCATEGORIZED"
        )
        if uncategorized_count > 0:
            warnings.append(f"{uncategorized_count} line(s) could not be categorized")
        
        # Add warning for suspense items
        suspense_count = sum(
            1 for lc in line_codings 
            if lc.mapping_level == MappingLevel.SUSPENSE
        )
        if suspense_count > 0:
            warnings.append(f"{suspense_count} line(s) mapped to suspense account")
        
        # Determine completeness
        is_complete = (
            len(missing_categories) == 0 
            and len(missing_dimensions) == 0
        )
        
        return InvoiceCoding(
            invoice_number=invoice_number,
            entity_id=self.entity_id,
            vendor_ref=vendor_ref,
            vendor_number=vendor_number,
            vendor_name=vendor_name,
            invoice_date=str(invoice_date),
            total_amount=total_amount,
            line_codings=line_codings,
            is_complete=is_complete,
            missing_mappings=list(missing_categories),
            missing_dimensions=list(missing_dimensions),
            warnings=warnings,
        )
    
    def _code_line(
        self,
        line_index: int,
        line: Dict[str, Any],
        context: DimensionContext,
    ) -> LineCoding:
        """
        Generate coding for a single line item.
        
        Args:
            line_index: Position in line_items list
            line: Line item data
            context: DimensionContext for dimension resolution
            
        Returns:
            LineCoding with GL ref and dimensions
        """
        description = line.get("description", "")
        amount = Decimal(str(line.get("amount", 0)))
        
        # Step 1: Categorize the line
        category = categorize_line_item(description)
        
        # Step 2: Look up GL mapping (Vendor → Entity → Global → Suspense)
        mapping = get_gl_mapping(
            category=category,
            entity_id=self.entity_id,
            vendor_id=self.vendor_id,
        )
        
        if mapping:
            gl_ref = mapping.gl_account_ref
            mapping_level = mapping.level
        else:
            # Fall back to suspense
            gl_ref = self.suspense_config.gl_account_ref
            mapping_level = MappingLevel.SUSPENSE
        
        # Step 3: Resolve dimensions
        dimensions, missing_dims = resolve_all_dimensions(
            rules=self._dimension_rules,
            context=context,
            line_data=line,
        )
        
        return LineCoding(
            line_index=line_index,
            description=description,
            amount=amount,
            category=category,
            gl_ref=gl_ref,
            mapping_level=mapping_level,
            dimensions=dimensions,
            is_complete=len(missing_dims) == 0,
            missing_dimensions=missing_dims,
        )
    
    def get_mapping_summary(self) -> Dict[str, Any]:
        """
        Get a summary of available mappings for this entity.
        
        Returns:
            Dict with mapping counts and categories
        """
        from .db import get_all_mappings_for_entity
        
        mappings = get_all_mappings_for_entity(self.entity_id)
        
        by_level = {
            MappingLevel.VENDOR.value: 0,
            MappingLevel.ENTITY.value: 0,
            MappingLevel.GLOBAL.value: 0,
        }
        categories = set()
        
        for m in mappings:
            by_level[m.level.value] = by_level.get(m.level.value, 0) + 1
            categories.add(m.category)
        
        return {
            "entity_id": self.entity_id,
            "vendor_id": self.vendor_id,
            "mappings_by_level": by_level,
            "total_mappings": len(mappings),
            "categories_covered": sorted(categories),
            "dimension_rules": len(self._dimension_rules),
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def code_invoice(
    invoice: Dict[str, Any],
    entity_id: str,
    vendor_id: Optional[str] = None,
    vendor: Optional[Dict[str, Any]] = None,
    statement: Optional[Dict[str, Any]] = None,
) -> InvoiceCoding:
    """
    Convenience function to code an invoice.
    
    Args:
        invoice: Invoice data
        entity_id: Entity ID
        vendor_id: Vendor ID (optional)
        vendor: Vendor resolution data (optional)
        statement: Statement data (optional)
        
    Returns:
        InvoiceCoding result
    """
    engine = CodingEngine(entity_id=entity_id, vendor_id=vendor_id)
    return engine.code_invoice(
        invoice=invoice,
        vendor=vendor,
        statement=statement,
    )


def preview_coding(
    line_descriptions: List[str],
    entity_id: str,
    vendor_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Preview how line descriptions would be coded.
    
    Useful for testing categorization and mapping lookup.
    
    Args:
        line_descriptions: List of line item descriptions
        entity_id: Entity ID
        vendor_id: Vendor ID (optional)
        
    Returns:
        List of {description, category, gl_ref, level}
    """
    results = []
    
    for desc in line_descriptions:
        category = categorize_line_item(desc)
        mapping = get_gl_mapping(
            category=category,
            entity_id=entity_id,
            vendor_id=vendor_id,
        )
        
        if mapping:
            gl_ref = mapping.gl_account_ref
            level = mapping.level.value
        else:
            gl_ref = "9999-00"
            level = "suspense"
        
        results.append({
            "description": desc,
            "category": category,
            "gl_ref": gl_ref,
            "level": level,
        })
    
    return results
