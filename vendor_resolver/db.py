"""Vendor Resolver Database Operations.

This module handles all database operations for vendor resolution:
- Schema initialization
- CRUD operations for vendor aliases
- Sample data seeding

The vendor_alias table provides fast exact-match lookups for
previously confirmed vendor matches.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from vendor_resolver.models import VendorAlias
from vendor_resolver.normalize import normalize_vendor_name


# Default database path (same as main AP automation database)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "ap_automation.db"


def init_vendor_resolver_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize vendor resolver database tables.
    
    Creates:
    - vendor_alias: Maps normalized names to vendor IDs per entity
    
    The table uses a composite unique index on (customer_id, entity_id, alias_normalized)
    for fast lookups.
    
    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Vendor Alias table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendor_alias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                alias_normalized TEXT NOT NULL,
                alias_original TEXT,
                vendor_id TEXT NOT NULL,
                vendor_number TEXT NOT NULL,
                vendor_name TEXT,
                created_by TEXT DEFAULT 'system',
                created_at TEXT NOT NULL,
                UNIQUE(customer_id, entity_id, alias_normalized)
            )
        """)
        
        # Indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vendor_alias_lookup 
            ON vendor_alias(customer_id, entity_id, alias_normalized)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vendor_alias_entity 
            ON vendor_alias(entity_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_vendor_alias_vendor 
            ON vendor_alias(vendor_id)
        """)
        
        conn.commit()
        print("Vendor resolver tables initialized successfully")
        
    finally:
        conn.close()


# =============================================================================
# CRUD Operations
# =============================================================================

def add_vendor_alias(
    alias: VendorAlias,
    db_path: Path = DEFAULT_DB_PATH
) -> VendorAlias:
    """Add a new vendor alias to the database.
    
    If the alias already exists, it will be updated with the new vendor.
    
    Args:
        alias: VendorAlias to add
        db_path: Path to database
        
    Returns:
        VendorAlias with id populated
    """
    now = datetime.utcnow().isoformat()
    
    # Normalize the alias if not already
    normalized = alias.alias_normalized
    if not normalized and alias.alias_original:
        normalized = normalize_vendor_name(alias.alias_original)
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Use INSERT OR REPLACE to handle updates
        cursor.execute("""
            INSERT OR REPLACE INTO vendor_alias 
            (customer_id, entity_id, alias_normalized, alias_original,
             vendor_id, vendor_number, vendor_name, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alias.customer_id,
            alias.entity_id,
            normalized,
            alias.alias_original,
            alias.vendor_id,
            alias.vendor_number,
            alias.vendor_name,
            alias.created_by,
            now,
        ))
        conn.commit()
        
        alias.id = cursor.lastrowid
        alias.alias_normalized = normalized
        alias.created_at = datetime.fromisoformat(now)
        
        return alias
    finally:
        conn.close()


def get_vendor_alias(
    normalized_name: str,
    entity_id: str,
    customer_id: str = "default",
    db_path: Path = DEFAULT_DB_PATH
) -> Optional[VendorAlias]:
    """Look up a vendor alias by normalized name.
    
    This is the fast path for vendor resolution - if an alias exists,
    we can immediately return the vendor without fuzzy matching.
    
    Args:
        normalized_name: Normalized vendor name to look up
        entity_id: BC company GUID
        customer_id: Customer/tenant identifier
        db_path: Path to database
        
    Returns:
        VendorAlias if found, None otherwise
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM vendor_alias 
            WHERE customer_id = ? AND entity_id = ? AND alias_normalized = ?
        """, (customer_id, entity_id, normalized_name))
        
        row = cursor.fetchone()
        if row:
            return _row_to_vendor_alias(row)
        return None
    finally:
        conn.close()


def get_aliases_for_entity(
    entity_id: str,
    customer_id: str = "default",
    db_path: Path = DEFAULT_DB_PATH
) -> List[VendorAlias]:
    """Get all vendor aliases for an entity.
    
    Useful for viewing/managing the alias table.
    
    Args:
        entity_id: BC company GUID
        customer_id: Customer/tenant identifier
        db_path: Path to database
        
    Returns:
        List of VendorAlias objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM vendor_alias 
            WHERE customer_id = ? AND entity_id = ?
            ORDER BY alias_normalized
        """, (customer_id, entity_id))
        
        return [_row_to_vendor_alias(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_aliases_for_vendor(
    vendor_id: str,
    entity_id: str,
    customer_id: str = "default",
    db_path: Path = DEFAULT_DB_PATH
) -> List[VendorAlias]:
    """Get all aliases that map to a specific vendor.
    
    Args:
        vendor_id: BC vendor GUID
        entity_id: BC company GUID
        customer_id: Customer/tenant identifier
        db_path: Path to database
        
    Returns:
        List of VendorAlias objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM vendor_alias 
            WHERE customer_id = ? AND entity_id = ? AND vendor_id = ?
            ORDER BY alias_normalized
        """, (customer_id, entity_id, vendor_id))
        
        return [_row_to_vendor_alias(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def delete_vendor_alias(
    alias_id: int,
    db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Delete a vendor alias by ID.
    
    Args:
        alias_id: Database row ID
        db_path: Path to database
        
    Returns:
        True if deleted, False if not found
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendor_alias WHERE id = ?", (alias_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_vendor_alias_by_name(
    normalized_name: str,
    entity_id: str,
    customer_id: str = "default",
    db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Delete a vendor alias by normalized name.
    
    Args:
        normalized_name: Normalized vendor name
        entity_id: BC company GUID
        customer_id: Customer/tenant identifier
        db_path: Path to database
        
    Returns:
        True if deleted, False if not found
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM vendor_alias 
            WHERE customer_id = ? AND entity_id = ? AND alias_normalized = ?
        """, (customer_id, entity_id, normalized_name))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _row_to_vendor_alias(row: sqlite3.Row) -> VendorAlias:
    """Convert a database row to VendorAlias."""
    return VendorAlias(
        id=row["id"],
        customer_id=row["customer_id"],
        entity_id=row["entity_id"],
        alias_normalized=row["alias_normalized"],
        alias_original=row["alias_original"],
        vendor_id=row["vendor_id"],
        vendor_number=row["vendor_number"],
        vendor_name=row["vendor_name"],
        created_by=row["created_by"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


# =============================================================================
# Sample Data Seeding
# =============================================================================

def seed_sample_aliases(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """Seed the database with sample vendor aliases.
    
    Creates sample aliases for Bovina and Mesquite feedlots.
    
    Args:
        db_path: Path to database
        
    Returns:
        Dict with count of created aliases
    """
    # Initialize tables first
    init_vendor_resolver_db(db_path)
    
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    
    created = {"aliases": 0}
    
    try:
        cursor = conn.cursor()
        
        # Sample aliases - these would normally be created when user confirms matches
        aliases = [
            # Bovina entity aliases
            {
                "customer_id": "skalable",
                "entity_id": "bf2-company-guid-001",
                "alias_normalized": "BOVINA FEEDERS BF2",
                "alias_original": "BOVINA FEEDERS INC. DBA BF2",
                "vendor_id": "bovina-vendor-guid-001",
                "vendor_number": "V-BF2",
                "vendor_name": "Bovina Feeders Inc.",
            },
            {
                "customer_id": "skalable",
                "entity_id": "bf2-company-guid-001",
                "alias_normalized": "BOVINA FEEDERS",
                "alias_original": "Bovina Feeders",
                "vendor_id": "bovina-vendor-guid-001",
                "vendor_number": "V-BF2",
                "vendor_name": "Bovina Feeders Inc.",
            },
            # Mesquite entity aliases
            {
                "customer_id": "skalable",
                "entity_id": "mesquite-company-guid-002",
                "alias_normalized": "MESQUITE CATTLE FEEDERS",
                "alias_original": "Mesquite Cattle Feeders",
                "vendor_id": "mesquite-vendor-guid-001",
                "vendor_number": "V-MCF",
                "vendor_name": "Mesquite Cattle Feeders",
            },
            {
                "customer_id": "skalable",
                "entity_id": "mesquite-company-guid-002",
                "alias_normalized": "MESQUITE CATTLE",
                "alias_original": "Mesquite Cattle",
                "vendor_id": "mesquite-vendor-guid-001",
                "vendor_number": "V-MCF",
                "vendor_name": "Mesquite Cattle Feeders",
            },
        ]
        
        for alias_data in aliases:
            try:
                cursor.execute("""
                    INSERT INTO vendor_alias 
                    (customer_id, entity_id, alias_normalized, alias_original,
                     vendor_id, vendor_number, vendor_name, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alias_data["customer_id"],
                    alias_data["entity_id"],
                    alias_data["alias_normalized"],
                    alias_data["alias_original"],
                    alias_data["vendor_id"],
                    alias_data["vendor_number"],
                    alias_data["vendor_name"],
                    "seed",
                    now,
                ))
                created["aliases"] += 1
            except sqlite3.IntegrityError:
                pass  # Already exists
        
        conn.commit()
        print(f"Seeded {created['aliases']} vendor aliases")
        
    finally:
        conn.close()
    
    return created


def clear_vendor_aliases(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Clear all vendor aliases (for testing).
    
    Args:
        db_path: Path to database
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM vendor_alias WHERE 1=1")
        conn.commit()
        print("Cleared all vendor aliases")
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        pass
    finally:
        conn.close()
