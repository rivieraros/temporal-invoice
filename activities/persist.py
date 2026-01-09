"""Persistence activities for AP automation pipeline.

Activities for persisting workflow state and data to the database.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List
from dataclasses import dataclass

from temporalio import activity


# Database path - relative to repo root
DB_PATH = Path(__file__).resolve().parents[1] / "ap_automation.db"


@dataclass
class PersistPackageInput:
    """Input for persist_package_started activity.
    
    Attributes:
        ap_package_id: Unique identifier for the AP package
        feedlot_type: Type of feedlot (BOVINA or MESQUITE)
        document_refs: List of document references (serialized as dicts)
    """
    ap_package_id: str
    feedlot_type: str
    document_refs: List[dict]


@dataclass
class PersistInvoiceInput:
    """Input for persist_invoice activity.
    
    Attributes:
        ap_package_id: Parent package ID
        invoice_number: Invoice number
        lot_number: Lot number (optional)
        invoice_date: Invoice date (optional)
        total_amount: Total amount (optional)
        invoice_ref: Serialized DataReference to invoice JSON
    """
    ap_package_id: str
    invoice_number: str
    lot_number: str | None
    invoice_date: str | None
    total_amount: str | None
    invoice_ref: dict


@dataclass
class UpdatePackageStatusInput:
    """Input for update_package_status activity.
    
    Attributes:
        ap_package_id: Package ID to update
        status: New status value
        statement_ref: Optional statement reference (serialized)
    """
    ap_package_id: str
    status: str
    statement_ref: dict | None = None


@dataclass
class UpdateInvoiceStatusInput:
    """Input for update_invoice_status activity.
    
    Attributes:
        ap_package_id: Package ID
        invoice_number: Invoice number to update
        status: New status value (VALIDATED_PASS or VALIDATED_FAIL)
        validation_ref: Optional validation result reference (serialized)
    """
    ap_package_id: str
    invoice_number: str
    status: str
    validation_ref: dict | None = None


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize the database with required tables.
    
    Creates ap_packages, ap_invoices, and extraction_progress tables if they don't exist.
    
    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ap_packages (
                ap_package_id TEXT PRIMARY KEY,
                feedlot_type TEXT NOT NULL CHECK(feedlot_type IN ('BOVINA', 'MESQUITE')),
                status TEXT NOT NULL DEFAULT 'STARTED',
                document_refs TEXT,
                statement_ref TEXT,
                total_invoices INTEGER DEFAULT 0,
                extracted_invoices INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ap_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ap_package_id TEXT NOT NULL,
                invoice_number TEXT NOT NULL,
                lot_number TEXT,
                invoice_date TEXT,
                total_amount TEXT,
                status TEXT NOT NULL DEFAULT 'EXTRACTED',
                invoice_ref TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (ap_package_id) REFERENCES ap_packages(ap_package_id),
                UNIQUE(ap_package_id, invoice_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ap_package_id TEXT NOT NULL,
                step TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (ap_package_id) REFERENCES ap_packages(ap_package_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def log_progress(ap_package_id: str, step: str, message: str, db_path: Path = DB_PATH) -> None:
    """Log extraction progress to database.
    
    Args:
        ap_package_id: Package ID
        step: Step name (e.g., "split_pdf", "extract_statement", "extract_invoice")
        message: Progress message
        db_path: Path to SQLite database
    """
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO extraction_progress (ap_package_id, step, message, created_at)
            VALUES (?, ?, ?, ?)
        """, (ap_package_id, step, message, now))
        conn.commit()
    finally:
        conn.close()


def update_extraction_counts(ap_package_id: str, total: int = None, extracted: int = None, extracted_increment: int = None, db_path: Path = DB_PATH) -> None:
    """Update extraction counts for a package.
    
    Args:
        ap_package_id: Package ID
        total: Total invoices to extract (set once)
        extracted: Number of invoices extracted so far (absolute value)
        extracted_increment: Amount to increment extracted_invoices by
        db_path: Path to SQLite database
    """
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        if total is not None:
            cursor.execute("""
                UPDATE ap_packages SET total_invoices = ?, updated_at = ? WHERE ap_package_id = ?
            """, (total, now, ap_package_id))
        if extracted is not None:
            cursor.execute("""
                UPDATE ap_packages SET extracted_invoices = ?, updated_at = ? WHERE ap_package_id = ?
            """, (extracted, now, ap_package_id))
        if extracted_increment is not None:
            cursor.execute("""
                UPDATE ap_packages 
                SET extracted_invoices = COALESCE(extracted_invoices, 0) + ?, updated_at = ? 
                WHERE ap_package_id = ?
            """, (extracted_increment, now, ap_package_id))
        conn.commit()
    finally:
        conn.close()


def get_progress(ap_package_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """Get progress log for a package.
    
    Args:
        ap_package_id: Package ID
        db_path: Path to SQLite database
        
    Returns:
        List of progress entries
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT step, message, created_at FROM extraction_progress
            WHERE ap_package_id = ? ORDER BY id
        """, (ap_package_id,))
        return [{"step": r[0], "message": r[1], "created_at": r[2]} for r in cursor.fetchall()]
    finally:
        conn.close()


@activity.defn
async def persist_package_started(input: PersistPackageInput) -> dict:
    """Persist a new AP package record with STARTED status.
    
    Creates a new row in ap_packages table with the given package details.
    
    Args:
        input: Package input containing ap_package_id, feedlot_type, and document_refs
        
    Returns:
        dict with ap_package_id, status, and created_at
        
    Raises:
        ValueError: If feedlot_type is not BOVINA or MESQUITE
        sqlite3.IntegrityError: If ap_package_id already exists
    """
    import json
    
    # Validate feedlot_type
    if input.feedlot_type not in ("BOVINA", "MESQUITE"):
        raise ValueError(f"Invalid feedlot_type: {input.feedlot_type}. Must be BOVINA or MESQUITE")
    
    # Ensure database is initialized
    init_db()
    
    now = datetime.utcnow().isoformat()
    document_refs_json = json.dumps(input.document_refs)
    
    activity.logger.info(f"Persisting package {input.ap_package_id} with status STARTED")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ap_packages (ap_package_id, feedlot_type, status, document_refs, created_at, updated_at)
            VALUES (?, ?, 'STARTED', ?, ?, ?)
        """, (input.ap_package_id, input.feedlot_type, document_refs_json, now, now))
        conn.commit()
        
        activity.logger.info(f"Package {input.ap_package_id} persisted successfully")
        
        return {
            "ap_package_id": input.ap_package_id,
            "status": "STARTED",
            "created_at": now
        }
    finally:
        conn.close()


def get_package(ap_package_id: str, db_path: Path = DB_PATH) -> dict | None:
    """Retrieve a package record by ID.
    
    Args:
        ap_package_id: The package ID to look up
        db_path: Path to SQLite database file
        
    Returns:
        dict with package details or None if not found
    """
    import json
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ap_package_id, feedlot_type, status, document_refs, created_at, updated_at
            FROM ap_packages
            WHERE ap_package_id = ?
        """, (ap_package_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                "ap_package_id": row[0],
                "feedlot_type": row[1],
                "status": row[2],
                "document_refs": json.loads(row[3]) if row[3] else [],
                "created_at": row[4],
                "updated_at": row[5]
            }
        return None
    finally:
        conn.close()


@activity.defn
async def persist_invoice(input: PersistInvoiceInput) -> dict:
    """Persist an invoice record to the database.
    
    Creates a new row in ap_invoices table with the given invoice details.
    
    Args:
        input: Invoice input containing ap_package_id, invoice_number, etc.
        
    Returns:
        dict with invoice details
    """
    import json
    
    # Ensure database is initialized
    init_db()
    
    now = datetime.utcnow().isoformat()
    invoice_ref_json = json.dumps(input.invoice_ref)
    
    activity.logger.info(f"Persisting invoice {input.invoice_number} for package {input.ap_package_id}")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ap_invoices 
            (ap_package_id, invoice_number, lot_number, invoice_date, total_amount, status, invoice_ref, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'EXTRACTED', ?, ?, ?)
        """, (
            input.ap_package_id, 
            input.invoice_number, 
            input.lot_number,
            input.invoice_date,
            input.total_amount,
            invoice_ref_json, 
            now, 
            now
        ))
        conn.commit()
        
        activity.logger.info(f"Invoice {input.invoice_number} persisted successfully")
        
        return {
            "ap_package_id": input.ap_package_id,
            "invoice_number": input.invoice_number,
            "status": "EXTRACTED",
            "created_at": now
        }
    finally:
        conn.close()


@activity.defn
async def update_package_status(input: UpdatePackageStatusInput) -> dict:
    """Update package status in the database.
    
    Args:
        input: UpdatePackageStatusInput with ap_package_id and new status
        
    Returns:
        dict with updated package info
    """
    import json
    
    # Ensure database is initialized
    init_db()
    
    now = datetime.utcnow().isoformat()
    
    activity.logger.info(f"Updating package {input.ap_package_id} status to {input.status}")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        if input.statement_ref:
            statement_ref_json = json.dumps(input.statement_ref)
            cursor.execute("""
                UPDATE ap_packages 
                SET status = ?, statement_ref = ?, updated_at = ?
                WHERE ap_package_id = ?
            """, (input.status, statement_ref_json, now, input.ap_package_id))
        else:
            cursor.execute("""
                UPDATE ap_packages 
                SET status = ?, updated_at = ?
                WHERE ap_package_id = ?
            """, (input.status, now, input.ap_package_id))
        
        conn.commit()
        
        activity.logger.info(f"Package {input.ap_package_id} updated to {input.status}")
        
        return {
            "ap_package_id": input.ap_package_id,
            "status": input.status,
            "updated_at": now
        }
    finally:
        conn.close()


@activity.defn
async def update_invoice_status(input: UpdateInvoiceStatusInput) -> dict:
    """Update invoice status in the database.
    
    Sets invoice status to VALIDATED_PASS or VALIDATED_FAIL based on validation result.
    
    Args:
        input: UpdateInvoiceStatusInput with ap_package_id, invoice_number, status
        
    Returns:
        dict with updated invoice info
    """
    import json
    
    # Ensure database is initialized
    init_db()
    
    now = datetime.utcnow().isoformat()
    
    activity.logger.info(f"Updating invoice {input.invoice_number} status to {input.status}")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        # Try to add validation_ref column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE ap_invoices ADD COLUMN validation_ref TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        if input.validation_ref:
            validation_ref_json = json.dumps(input.validation_ref)
            cursor.execute("""
                UPDATE ap_invoices 
                SET status = ?, validation_ref = ?, updated_at = ?
                WHERE ap_package_id = ? AND invoice_number = ?
            """, (input.status, validation_ref_json, now, input.ap_package_id, input.invoice_number))
        else:
            cursor.execute("""
                UPDATE ap_invoices 
                SET status = ?, updated_at = ?
                WHERE ap_package_id = ? AND invoice_number = ?
            """, (input.status, now, input.ap_package_id, input.invoice_number))
        
        conn.commit()
        
        activity.logger.info(f"Invoice {input.invoice_number} updated to {input.status}")
        
        return {
            "ap_package_id": input.ap_package_id,
            "invoice_number": input.invoice_number,
            "status": input.status,
            "updated_at": now
        }
    finally:
        conn.close()


def get_invoices(ap_package_id: str, db_path: Path = DB_PATH) -> list[dict]:
    """Retrieve all invoices for a package.
    
    Args:
        ap_package_id: The package ID to look up
        db_path: Path to SQLite database file
        
    Returns:
        List of invoice dicts
    """
    import json
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT invoice_number, lot_number, invoice_date, total_amount, status, invoice_ref, created_at
            FROM ap_invoices
            WHERE ap_package_id = ?
            ORDER BY invoice_number
        """, (ap_package_id,))
        rows = cursor.fetchall()
        
        return [
            {
                "invoice_number": row[0],
                "lot_number": row[1],
                "invoice_date": row[2],
                "total_amount": row[3],
                "status": row[4],
                "invoice_ref": json.loads(row[5]) if row[5] else None,
                "created_at": row[6]
            }
            for row in rows
        ]
    finally:
        conn.close()
