"""
Coding Engine Database

Creates and manages the GL mapping tables:
- gl_mapping_global: category → gl_account_ref
- gl_mapping_entity: entity_id + category → gl_account_ref
- gl_mapping_vendor: entity_id + vendor_id + category → gl_account_ref
- dimension_rule: entity_id + dimension_code → source_field + transform
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import (
    GLMapping,
    DimensionRule,
    MappingLevel,
    DimensionSource,
    TransformType,
)

DB_PATH = Path(__file__).parent.parent / "ap_automation.db"


def get_db_connection() -> sqlite3.Connection:
    """Get database connection with row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_coding_engine_db() -> None:
    """
    Initialize the coding engine database tables.
    
    Creates:
    - gl_mapping: Unified table for all mapping levels
    - dimension_rule: Dimension generation rules
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # GL Mapping table (unified for all levels)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gl_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            entity_id TEXT,
            vendor_id TEXT,
            category TEXT NOT NULL,
            gl_account_ref TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints based on level
            UNIQUE(level, entity_id, vendor_id, category)
        )
    """)
    
    # Indexes for efficient lookup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gl_mapping_category 
        ON gl_mapping(category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gl_mapping_entity 
        ON gl_mapping(entity_id, category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gl_mapping_vendor 
        ON gl_mapping(entity_id, vendor_id, category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_gl_mapping_level 
        ON gl_mapping(level)
    """)
    
    # Dimension Rules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dimension_rule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT,
            dimension_code TEXT NOT NULL,
            source_field TEXT NOT NULL,
            transform TEXT DEFAULT 'none',
            transform_params TEXT,
            default_value TEXT,
            is_required INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(entity_id, dimension_code)
        )
    """)
    
    # Index for dimension rules
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dimension_rule_entity 
        ON dimension_rule(entity_id)
    """)
    
    conn.commit()
    conn.close()
    print("Coding engine database tables initialized")


# =============================================================================
# GL Mapping CRUD Operations
# =============================================================================

def add_gl_mapping(mapping: GLMapping) -> GLMapping:
    """
    Add or update a GL mapping.
    
    Uses INSERT OR REPLACE for upsert behavior.
    
    Args:
        mapping: GLMapping to add/update
        
    Returns:
        Updated GLMapping with ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO gl_mapping 
        (level, entity_id, vendor_id, category, gl_account_ref, description, is_active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        mapping.level.value,
        mapping.entity_id,
        mapping.vendor_id,
        mapping.category,
        mapping.gl_account_ref,
        mapping.description,
        1 if mapping.is_active else 0,
    ))
    
    mapping.id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return mapping


def get_gl_mapping(
    category: str,
    entity_id: Optional[str] = None,
    vendor_id: Optional[str] = None,
) -> Optional[GLMapping]:
    """
    Get GL mapping with precedence: Vendor → Entity → Global.
    
    Args:
        category: Line item category
        entity_id: Entity ID for entity/vendor-level lookup
        vendor_id: Vendor ID for vendor-level lookup
        
    Returns:
        GLMapping if found, None otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    category = category.upper().strip()
    
    # Try vendor-level first (most specific)
    if entity_id and vendor_id:
        cursor.execute("""
            SELECT * FROM gl_mapping 
            WHERE level = 'vendor' 
              AND entity_id = ? 
              AND vendor_id = ? 
              AND category = ?
              AND is_active = 1
        """, (entity_id, vendor_id, category))
        row = cursor.fetchone()
        if row:
            conn.close()
            return _row_to_gl_mapping(row)
    
    # Try entity-level
    if entity_id:
        cursor.execute("""
            SELECT * FROM gl_mapping 
            WHERE level = 'entity' 
              AND entity_id = ? 
              AND category = ?
              AND is_active = 1
        """, (entity_id, category))
        row = cursor.fetchone()
        if row:
            conn.close()
            return _row_to_gl_mapping(row)
    
    # Try global-level
    cursor.execute("""
        SELECT * FROM gl_mapping 
        WHERE level = 'global' 
          AND category = ?
          AND is_active = 1
    """, (category,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return _row_to_gl_mapping(row)
    
    return None


def get_all_mappings_for_entity(entity_id: str) -> List[GLMapping]:
    """Get all mappings applicable to an entity (vendor + entity + global)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM gl_mapping 
        WHERE is_active = 1
          AND (
              level = 'global'
              OR (level = 'entity' AND entity_id = ?)
              OR (level = 'vendor' AND entity_id = ?)
          )
        ORDER BY 
            CASE level 
                WHEN 'vendor' THEN 1 
                WHEN 'entity' THEN 2 
                WHEN 'global' THEN 3 
            END,
            category
    """, (entity_id, entity_id))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [_row_to_gl_mapping(row) for row in rows]


def get_global_mappings() -> List[GLMapping]:
    """Get all global GL mappings"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM gl_mapping 
        WHERE level = 'global' AND is_active = 1
        ORDER BY category
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    return [_row_to_gl_mapping(row) for row in rows]


def _row_to_gl_mapping(row: sqlite3.Row) -> GLMapping:
    """Convert database row to GLMapping"""
    return GLMapping(
        id=row["id"],
        level=MappingLevel(row["level"]),
        entity_id=row["entity_id"],
        vendor_id=row["vendor_id"],
        category=row["category"],
        gl_account_ref=row["gl_account_ref"],
        description=row["description"],
        is_active=bool(row["is_active"]),
    )


# =============================================================================
# Dimension Rule CRUD Operations
# =============================================================================

def add_dimension_rule(rule: DimensionRule) -> DimensionRule:
    """
    Add or update a dimension rule.
    
    Args:
        rule: DimensionRule to add/update
        
    Returns:
        Updated DimensionRule with ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    transform_params_json = json.dumps(rule.transform_params) if rule.transform_params else None
    
    cursor.execute("""
        INSERT OR REPLACE INTO dimension_rule 
        (entity_id, dimension_code, source_field, transform, transform_params, 
         default_value, is_required, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        rule.entity_id,
        rule.dimension_code,
        rule.source_field.value if isinstance(rule.source_field, DimensionSource) else rule.source_field,
        rule.transform.value if isinstance(rule.transform, TransformType) else rule.transform,
        transform_params_json,
        rule.default_value,
        1 if rule.is_required else 0,
    ))
    
    rule.id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return rule


def get_dimension_rules(entity_id: Optional[str] = None) -> List[DimensionRule]:
    """
    Get dimension rules for an entity.
    
    Returns entity-specific rules merged with global rules.
    Entity rules override global rules for the same dimension.
    
    Args:
        entity_id: Entity ID (None for global only)
        
    Returns:
        List of DimensionRule objects
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get global rules first
    cursor.execute("""
        SELECT * FROM dimension_rule 
        WHERE entity_id IS NULL
        ORDER BY dimension_code
    """)
    global_rows = cursor.fetchall()
    
    # Build dict with global rules
    rules_dict: Dict[str, DimensionRule] = {}
    for row in global_rows:
        rule = _row_to_dimension_rule(row)
        rules_dict[rule.dimension_code] = rule
    
    # Overlay entity-specific rules if entity_id provided
    if entity_id:
        cursor.execute("""
            SELECT * FROM dimension_rule 
            WHERE entity_id = ?
            ORDER BY dimension_code
        """, (entity_id,))
        entity_rows = cursor.fetchall()
        
        for row in entity_rows:
            rule = _row_to_dimension_rule(row)
            rules_dict[rule.dimension_code] = rule  # Override global
    
    conn.close()
    
    return list(rules_dict.values())


def get_dimension_rule(dimension_code: str, entity_id: Optional[str] = None) -> Optional[DimensionRule]:
    """
    Get a specific dimension rule.
    
    Tries entity-specific first, then global.
    
    Args:
        dimension_code: Dimension code to look up
        entity_id: Entity ID (optional)
        
    Returns:
        DimensionRule if found, None otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    dimension_code = dimension_code.upper().strip()
    
    # Try entity-specific first
    if entity_id:
        cursor.execute("""
            SELECT * FROM dimension_rule 
            WHERE entity_id = ? AND dimension_code = ?
        """, (entity_id, dimension_code))
        row = cursor.fetchone()
        if row:
            conn.close()
            return _row_to_dimension_rule(row)
    
    # Try global
    cursor.execute("""
        SELECT * FROM dimension_rule 
        WHERE entity_id IS NULL AND dimension_code = ?
    """, (dimension_code,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return _row_to_dimension_rule(row)
    
    return None


def _row_to_dimension_rule(row: sqlite3.Row) -> DimensionRule:
    """Convert database row to DimensionRule"""
    transform_params = None
    if row["transform_params"]:
        try:
            transform_params = json.loads(row["transform_params"])
        except json.JSONDecodeError:
            transform_params = {}
    
    # Handle source_field conversion
    source_field_str = row["source_field"]
    try:
        source_field = DimensionSource(source_field_str)
    except ValueError:
        # If not a standard source, treat as custom
        source_field = source_field_str
    
    # Handle transform conversion
    transform_str = row["transform"]
    try:
        transform = TransformType(transform_str)
    except ValueError:
        transform = TransformType.NONE
    
    return DimensionRule(
        id=row["id"],
        entity_id=row["entity_id"],
        dimension_code=row["dimension_code"],
        source_field=source_field,
        transform=transform,
        transform_params=transform_params,
        default_value=row["default_value"],
        is_required=bool(row["is_required"]),
    )


# =============================================================================
# Seed Data Functions
# =============================================================================

def seed_global_mappings() -> int:
    """
    Seed standard global GL mappings for feedlot categories.
    
    Returns:
        Number of mappings seeded
    """
    global_mappings = [
        # Feed and related
        GLMapping("FEED", "5100-00", MappingLevel.GLOBAL, description="Feed Expense"),
        GLMapping("YARDAGE", "5200-00", MappingLevel.GLOBAL, description="Yardage/Pen Expense"),
        GLMapping("VET", "5300-00", MappingLevel.GLOBAL, description="Veterinary Expense"),
        GLMapping("PROCESSING", "5310-00", MappingLevel.GLOBAL, description="Processing Expense"),
        
        # Transportation
        GLMapping("FREIGHT", "5400-00", MappingLevel.GLOBAL, description="Freight/Hauling Expense"),
        
        # Financial
        GLMapping("INTEREST", "6100-00", MappingLevel.GLOBAL, description="Interest Expense"),
        GLMapping("INSURANCE", "6200-00", MappingLevel.GLOBAL, description="Insurance Expense"),
        
        # Cattle-specific
        GLMapping("DEATH_LOSS", "5500-00", MappingLevel.GLOBAL, description="Death Loss Expense"),
        GLMapping("COMMISSION", "5600-00", MappingLevel.GLOBAL, description="Commission Expense"),
        GLMapping("CHECKOFF", "5610-00", MappingLevel.GLOBAL, description="Beef Checkoff Assessment"),
        GLMapping("BRAND", "5620-00", MappingLevel.GLOBAL, description="Brand Inspection"),
        
        # Catch-all
        GLMapping("MISC", "5900-00", MappingLevel.GLOBAL, description="Miscellaneous Expense"),
        GLMapping("UNCATEGORIZED", "9999-00", MappingLevel.GLOBAL, description="Uncategorized - Needs Review"),
    ]
    
    for mapping in global_mappings:
        add_gl_mapping(mapping)
    
    print(f"Seeded {len(global_mappings)} global GL mappings")
    return len(global_mappings)


def seed_entity_mappings(entity_id: str, mappings: List[Dict[str, str]]) -> int:
    """
    Seed entity-specific GL mappings.
    
    Args:
        entity_id: Entity ID
        mappings: List of {"category": ..., "gl_account_ref": ..., "description": ...}
        
    Returns:
        Number of mappings seeded
    """
    count = 0
    for m in mappings:
        mapping = GLMapping(
            category=m["category"],
            gl_account_ref=m["gl_account_ref"],
            level=MappingLevel.ENTITY,
            entity_id=entity_id,
            description=m.get("description"),
        )
        add_gl_mapping(mapping)
        count += 1
    
    print(f"Seeded {count} entity mappings for {entity_id}")
    return count


def seed_dimension_rules() -> int:
    """
    Seed standard dimension rules.
    
    Returns:
        Number of rules seeded
    """
    global_rules = [
        # LOT = invoice.lot_number
        DimensionRule(
            dimension_code="LOT",
            source_field=DimensionSource.INVOICE_LOT_NUMBER,
            transform=TransformType.UPPERCASE,
            is_required=True,
        ),
        
        # PERIOD = YYYY-MM from invoice date
        DimensionRule(
            dimension_code="PERIOD",
            source_field=DimensionSource.INVOICE_DATE,
            transform=TransformType.EXTRACT_YEAR_MONTH,
            is_required=True,
        ),
        
        # OWNER = owner number
        DimensionRule(
            dimension_code="OWNER",
            source_field=DimensionSource.OWNER_NUMBER,
            transform=TransformType.NONE,
            is_required=False,
        ),
        
        # FEEDLOT = normalized feedlot code
        DimensionRule(
            dimension_code="FEEDLOT",
            source_field=DimensionSource.FEEDLOT_NAME,
            transform=TransformType.NORMALIZE_CODE,
            is_required=True,
        ),
    ]
    
    for rule in global_rules:
        add_dimension_rule(rule)
    
    print(f"Seeded {len(global_rules)} global dimension rules")
    return len(global_rules)


def seed_sample_data() -> Dict[str, int]:
    """
    Seed all sample data for testing.
    
    Returns:
        Dict with counts of seeded items
    """
    init_coding_engine_db()
    
    counts = {
        "global_mappings": seed_global_mappings(),
        "dimension_rules": seed_dimension_rules(),
    }
    
    # Entity-specific mappings for BF2 (Bovina)
    bf2_mappings = [
        {"category": "FEED", "gl_account_ref": "5100-01", "description": "BF2 Feed Expense"},
        {"category": "YARDAGE", "gl_account_ref": "5200-01", "description": "BF2 Yardage"},
    ]
    counts["bf2_entity_mappings"] = seed_entity_mappings("BF2", bf2_mappings)
    
    # Entity-specific mappings for MESQ (Mesquite)
    mesq_mappings = [
        {"category": "FEED", "gl_account_ref": "5100-02", "description": "Mesquite Feed Expense"},
    ]
    counts["mesq_entity_mappings"] = seed_entity_mappings("MESQ", mesq_mappings)
    
    # Entity-specific dimension rule for ENTITY
    add_dimension_rule(DimensionRule(
        dimension_code="ENTITY",
        source_field=DimensionSource.ENTITY_CODE,
        entity_id="BF2",
        default_value="BF2",
        is_required=True,
    ))
    add_dimension_rule(DimensionRule(
        dimension_code="ENTITY",
        source_field=DimensionSource.ENTITY_CODE,
        entity_id="MESQ",
        default_value="MESQ",
        is_required=True,
    ))
    counts["entity_dimension_rules"] = 2
    
    print(f"\nTotal items seeded: {sum(counts.values())}")
    return counts
