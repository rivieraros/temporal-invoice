"""Entity Resolver Database Operations.

This module handles all database operations for entity resolution:
- Schema initialization
- CRUD operations for entity profiles and routing keys
- Sample data seeding for testing

The database schema is designed to be minimal yet support 50+ entities
with efficient lookups via indexed routing keys.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from entity_resolver.models import (
    EntityProfile,
    EntityRoutingKey,
    RoutingKeyType,
    ConfidenceLevel,
)


# Default database path (same as main AP automation database)
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "ap_automation.db"


def init_entity_resolver_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize entity resolver database tables.
    
    Creates:
    - entity_profile: BC company profiles with aliases and defaults
    - entity_routing_key: Routing keys for entity lookup
    
    Both tables use indexes for efficient lookups.
    
    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Entity Profile table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                entity_code TEXT,
                aliases TEXT DEFAULT '[]',
                routing_rules TEXT DEFAULT '{}',
                default_dimensions TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(customer_id, entity_id)
            )
        """)
        
        # Indexes for entity_profile
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_profile_customer 
            ON entity_profile(customer_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_profile_entity_id 
            ON entity_profile(entity_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_entity_profile_active 
            ON entity_profile(is_active)
        """)
        
        # Entity Routing Key table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entity_routing_key (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_type TEXT NOT NULL,
                key_value TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                confidence TEXT NOT NULL DEFAULT 'soft',
                priority INTEGER DEFAULT 100,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(key_type, key_value)
            )
        """)
        
        # Indexes for efficient routing key lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_routing_key_type_value 
            ON entity_routing_key(key_type, key_value)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_routing_key_entity 
            ON entity_routing_key(entity_id)
        """)
        
        conn.commit()
        print("Entity resolver tables initialized successfully")
        
    finally:
        conn.close()


# =============================================================================
# CRUD Operations: Entity Profile
# =============================================================================

def add_entity_profile(
    profile: EntityProfile,
    db_path: Path = DEFAULT_DB_PATH
) -> EntityProfile:
    """Add a new entity profile to the database.
    
    Args:
        profile: EntityProfile to add
        db_path: Path to database
        
    Returns:
        EntityProfile with id populated
        
    Raises:
        sqlite3.IntegrityError: If entity_id already exists for customer
    """
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entity_profile 
            (customer_id, entity_id, entity_name, entity_code, aliases, 
             routing_rules, default_dimensions, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile.customer_id,
            profile.entity_id,
            profile.entity_name,
            profile.entity_code,
            json.dumps(profile.aliases),
            json.dumps(profile.routing_rules),
            json.dumps(profile.default_dimensions),
            1 if profile.is_active else 0,
            now,
            now,
        ))
        conn.commit()
        profile.id = cursor.lastrowid
        profile.created_at = datetime.fromisoformat(now)
        profile.updated_at = datetime.fromisoformat(now)
        return profile
    finally:
        conn.close()


def get_entity_profile(
    entity_id: str,
    customer_id: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH
) -> Optional[EntityProfile]:
    """Get an entity profile by entity_id.
    
    Args:
        entity_id: BC company GUID
        customer_id: Optional customer filter
        db_path: Path to database
        
    Returns:
        EntityProfile if found, None otherwise
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        if customer_id:
            cursor.execute("""
                SELECT * FROM entity_profile 
                WHERE entity_id = ? AND customer_id = ?
            """, (entity_id, customer_id))
        else:
            cursor.execute("""
                SELECT * FROM entity_profile WHERE entity_id = ?
            """, (entity_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_entity_profile(row)
        return None
    finally:
        conn.close()


def get_all_entity_profiles(
    customer_id: Optional[str] = None,
    active_only: bool = True,
    db_path: Path = DEFAULT_DB_PATH
) -> List[EntityProfile]:
    """Get all entity profiles, optionally filtered.
    
    Args:
        customer_id: Optional customer filter
        active_only: Only return active entities
        db_path: Path to database
        
    Returns:
        List of EntityProfile objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM entity_profile WHERE 1=1"
        params = []
        
        if customer_id:
            query += " AND customer_id = ?"
            params.append(customer_id)
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY entity_name"
        cursor.execute(query, params)
        
        return [_row_to_entity_profile(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _row_to_entity_profile(row: sqlite3.Row) -> EntityProfile:
    """Convert a database row to EntityProfile."""
    return EntityProfile(
        id=row["id"],
        customer_id=row["customer_id"],
        entity_id=row["entity_id"],
        entity_name=row["entity_name"],
        entity_code=row["entity_code"],
        aliases=json.loads(row["aliases"]) if row["aliases"] else [],
        routing_rules=json.loads(row["routing_rules"]) if row["routing_rules"] else {},
        default_dimensions=json.loads(row["default_dimensions"]) if row["default_dimensions"] else {},
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
    )


# =============================================================================
# CRUD Operations: Routing Keys
# =============================================================================

def add_routing_key(
    routing_key: EntityRoutingKey,
    db_path: Path = DEFAULT_DB_PATH
) -> EntityRoutingKey:
    """Add a new routing key to the database.
    
    Args:
        routing_key: EntityRoutingKey to add
        db_path: Path to database
        
    Returns:
        EntityRoutingKey with id populated
        
    Raises:
        sqlite3.IntegrityError: If key_type + key_value already exists
    """
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entity_routing_key 
            (key_type, key_value, entity_id, confidence, priority, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            routing_key.key_type.value,
            routing_key.key_value,
            routing_key.entity_id,
            routing_key.confidence.value,
            routing_key.priority,
            routing_key.notes,
            now,
        ))
        conn.commit()
        routing_key.id = cursor.lastrowid
        routing_key.created_at = datetime.fromisoformat(now)
        return routing_key
    finally:
        conn.close()


def get_routing_keys(
    key_type: Optional[RoutingKeyType] = None,
    key_value: Optional[str] = None,
    entity_id: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH
) -> List[EntityRoutingKey]:
    """Get routing keys with optional filters.
    
    Args:
        key_type: Filter by key type
        key_value: Filter by key value (exact match)
        entity_id: Filter by entity
        db_path: Path to database
        
    Returns:
        List of matching EntityRoutingKey objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM entity_routing_key WHERE 1=1"
        params = []
        
        if key_type:
            query += " AND key_type = ?"
            params.append(key_type.value)
        if key_value:
            query += " AND key_value = ?"
            params.append(key_value)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        
        query += " ORDER BY priority DESC, key_type, key_value"
        cursor.execute(query, params)
        
        return [_row_to_routing_key(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_routing_keys_by_value_pattern(
    key_type: RoutingKeyType,
    value: str,
    db_path: Path = DEFAULT_DB_PATH
) -> List[EntityRoutingKey]:
    """Get routing keys where the value matches as a prefix of the input.
    
    Useful for lot_prefix matching where key_value="20-" matches lot "20-3883".
    
    Args:
        key_type: Type of key to search
        value: The full value to match against key prefixes
        db_path: Path to database
        
    Returns:
        List of matching EntityRoutingKey objects
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        # Find keys where the key_value is a prefix of the input value
        cursor.execute("""
            SELECT * FROM entity_routing_key 
            WHERE key_type = ? AND ? LIKE key_value || '%'
            ORDER BY LENGTH(key_value) DESC, priority DESC
        """, (key_type.value, value))
        
        return [_row_to_routing_key(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def _row_to_routing_key(row: sqlite3.Row) -> EntityRoutingKey:
    """Convert a database row to EntityRoutingKey."""
    return EntityRoutingKey(
        id=row["id"],
        key_type=RoutingKeyType(row["key_type"]),
        key_value=row["key_value"],
        entity_id=row["entity_id"],
        confidence=ConfidenceLevel(row["confidence"]),
        priority=row["priority"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


# =============================================================================
# Sample Data Seeding
# =============================================================================

def seed_sample_data(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """Seed the database with sample entity profiles and routing keys.
    
    Creates sample data for Bovina and Mesquite feedlots to demonstrate
    the entity resolution system.
    
    Args:
        db_path: Path to database
        
    Returns:
        Dict with counts of created entities and routing keys
    """
    # Initialize tables first
    init_entity_resolver_db(db_path)
    
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    
    created = {"profiles": 0, "routing_keys": 0}
    
    try:
        cursor = conn.cursor()
        
        # Sample entity profiles
        profiles = [
            {
                "customer_id": "skalable",
                "entity_id": "bf2-company-guid-001",
                "entity_name": "Bovina Feeders Inc. DBA BF2",
                "entity_code": "BF2",
                "aliases": ["BOVINA FEEDERS INC. DBA BF2", "BOVINA FEEDERS", "BF2", "BOVINA"],
                "default_dimensions": {"DEPT": "FEED", "LOCATION": "TX"},
            },
            {
                "customer_id": "skalable",
                "entity_id": "mesquite-company-guid-002",
                "entity_name": "Mesquite Cattle Feeders",
                "entity_code": "MESQ",
                "aliases": ["MESQUITE CATTLE", "MESQUITE FEEDERS", "MESQ"],
                "default_dimensions": {"DEPT": "FEED", "LOCATION": "CA"},  # Mesquite is in CA
            },
            {
                "customer_id": "skalable",
                "entity_id": "sugar-mountain-guid-003",
                "entity_name": "Sugar Mountain Livestock",
                "entity_code": "SML",
                "aliases": ["SUGAR MOUNTAIN LIVESTOCK", "SUGAR MOUNTAIN", "SML"],
                "default_dimensions": {"DEPT": "CATTLE", "LOCATION": "WA"},
            },
        ]
        
        for p in profiles:
            try:
                cursor.execute("""
                    INSERT INTO entity_profile 
                    (customer_id, entity_id, entity_name, entity_code, aliases, 
                     routing_rules, default_dimensions, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["customer_id"],
                    p["entity_id"],
                    p["entity_name"],
                    p["entity_code"],
                    json.dumps(p["aliases"]),
                    json.dumps({}),
                    json.dumps(p["default_dimensions"]),
                    1,
                    now,
                    now,
                ))
                created["profiles"] += 1
            except sqlite3.IntegrityError:
                pass  # Already exists
        
        # Sample routing keys
        routing_keys = [
            # Owner numbers → entities
            {
                "key_type": "owner_number",
                "key_value": "531",
                "entity_id": "bf2-company-guid-001",
                "confidence": "hard",
                "priority": 100,
                "notes": "Sugar Mountain's owner number at Bovina",
            },
            {
                "key_type": "owner_number",
                "key_value": "702",
                "entity_id": "mesquite-company-guid-002",
                "confidence": "hard",
                "priority": 100,
                "notes": "Sugar Mountain's owner number at Mesquite",
            },
            
            # Lot prefixes → entities
            {
                "key_type": "lot_prefix",
                "key_value": "20-",
                "entity_id": "bf2-company-guid-001",
                "confidence": "soft",
                "priority": 50,
                "notes": "Bovina uses 20- prefix for lots",
            },
            {
                "key_type": "lot_prefix",
                "key_value": "05",
                "entity_id": "mesquite-company-guid-002",
                "confidence": "soft",
                "priority": 50,
                "notes": "Mesquite uses 05xx for lots",
            },
            
            # Remit states → entities (feedlot location states)
            {
                "key_type": "remit_state",
                "key_value": "TX",
                "entity_id": "bf2-company-guid-001",
                "confidence": "soft",
                "priority": 30,
                "notes": "Bovina is in Texas",
            },
            {
                "key_type": "remit_state",
                "key_value": "CA",
                "entity_id": "mesquite-company-guid-002",
                "confidence": "soft",
                "priority": 30,
                "notes": "Mesquite is in California",
            },
            
            # Feedlot names → entities
            {
                "key_type": "feedlot_name",
                "key_value": "BOVINA",
                "entity_id": "bf2-company-guid-001",
                "confidence": "hard",
                "priority": 90,
                "notes": "Feedlot name contains BOVINA",
            },
            {
                "key_type": "feedlot_name",
                "key_value": "MESQUITE",
                "entity_id": "mesquite-company-guid-002",
                "confidence": "hard",
                "priority": 90,
                "notes": "Feedlot name contains MESQUITE",
            },
        ]
        
        for rk in routing_keys:
            try:
                cursor.execute("""
                    INSERT INTO entity_routing_key 
                    (key_type, key_value, entity_id, confidence, priority, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    rk["key_type"],
                    rk["key_value"],
                    rk["entity_id"],
                    rk["confidence"],
                    rk["priority"],
                    rk["notes"],
                    now,
                ))
                created["routing_keys"] += 1
            except sqlite3.IntegrityError:
                pass  # Already exists
        
        conn.commit()
        print(f"Seeded {created['profiles']} profiles and {created['routing_keys']} routing keys")
        
    finally:
        conn.close()
    
    return created


def clear_entity_resolver_data(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Clear all entity resolver data (for testing).
    
    Args:
        db_path: Path to database
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Use IF EXISTS to avoid errors if tables don't exist yet
        cursor.execute("DELETE FROM entity_routing_key WHERE 1=1")
        cursor.execute("DELETE FROM entity_profile WHERE 1=1")
        conn.commit()
        print("Cleared all entity resolver data")
    except sqlite3.OperationalError:
        # Tables don't exist yet, that's fine
        pass
    finally:
        conn.close()
