"""
Database Query Service for AP Automation UI.

Provides functions to query actual workflow state from the database.
This enables the UI to show correct in-progress / waiting states
even after worker restarts.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Dict, Any

from models.api_responses import (
    PackageStatus,
    InvoiceStatus,
    ValidationStatus,
)


# Database path
DB_PATH = Path(__file__).resolve().parents[2] / "ap_automation.db"


def get_db_connection():
    """Get SQLite database connection."""
    return sqlite3.connect(str(DB_PATH))


# =============================================================================
# PACKAGE QUERIES
# =============================================================================

def get_package_from_db(ap_package_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a package from the database.
    
    Returns the durable workflow state, not transient mock data.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                ap_package_id, 
                feedlot_type, 
                status, 
                document_refs,
                statement_ref,
                total_invoices,
                extracted_invoices,
                created_at, 
                updated_at
            FROM ap_packages
            WHERE ap_package_id = ?
        """, (ap_package_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        return {
            "ap_package_id": row[0],
            "feedlot_type": row[1],
            "status": row[2],
            "document_refs": json.loads(row[3]) if row[3] else [],
            "statement_ref": json.loads(row[4]) if row[4] else None,
            "total_invoices": row[5] or 0,
            "extracted_invoices": row[6] or 0,
            "created_at": row[7],
            "updated_at": row[8],
        }
    finally:
        conn.close()


def list_packages_from_db(
    status: Optional[str] = None,
    feedlot_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    List packages from the database with optional filters.
    
    Returns durable workflow state for all matching packages.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                ap_package_id, 
                feedlot_type, 
                status, 
                total_invoices,
                extracted_invoices,
                created_at, 
                updated_at
            FROM ap_packages
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if feedlot_type:
            query += " AND feedlot_type = ?"
            params.append(feedlot_type)
            
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            {
                "ap_package_id": row[0],
                "feedlot_type": row[1],
                "status": row[2],
                "total_invoices": row[3] or 0,
                "extracted_invoices": row[4] or 0,
                "created_at": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]
    finally:
        conn.close()


# =============================================================================
# INVOICE QUERIES
# =============================================================================

def get_invoices_from_db(ap_package_id: str) -> List[Dict[str, Any]]:
    """
    Get all invoices for a package from the database.
    
    Returns durable invoice state with validation status.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                invoice_number,
                lot_number,
                invoice_date,
                total_amount,
                status,
                invoice_ref,
                created_at,
                updated_at
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
                "total_amount": Decimal(row[3]) if row[3] else Decimal("0"),
                "status": row[4],
                "invoice_ref": json.loads(row[5]) if row[5] else None,
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_invoice_from_db(
    ap_package_id: str, 
    invoice_number: str
) -> Optional[Dict[str, Any]]:
    """
    Get a single invoice from the database.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                invoice_number,
                lot_number,
                invoice_date,
                total_amount,
                status,
                invoice_ref,
                validation_ref,
                created_at,
                updated_at
            FROM ap_invoices
            WHERE ap_package_id = ? AND invoice_number = ?
        """, (ap_package_id, invoice_number))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        return {
            "invoice_number": row[0],
            "lot_number": row[1],
            "invoice_date": row[2],
            "total_amount": Decimal(row[3]) if row[3] else Decimal("0"),
            "status": row[4],
            "invoice_ref": json.loads(row[5]) if row[5] else None,
            "validation_ref": json.loads(row[6]) if row[6] else None,
            "created_at": row[7],
            "updated_at": row[8],
        }
    finally:
        conn.close()


# =============================================================================
# AUDIT EVENT QUERIES
# =============================================================================

def get_audit_events(
    ap_package_id: str,
    invoice_number: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get audit events for a package or invoice.
    
    This is the timeline/commentary data the UI displays.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        query = """
            SELECT 
                id,
                ap_package_id,
                invoice_number,
                stage,
                status,
                details,
                error_message,
                created_at
            FROM audit_events
            WHERE ap_package_id = ?
        """
        params = [ap_package_id]
        
        if invoice_number:
            query += " AND (invoice_number = ? OR invoice_number = '*')"
            params.append(invoice_number)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "ap_package_id": row[1],
                "invoice_number": row[2],
                "stage": row[3],
                "status": row[4],
                "details": json.loads(row[5]) if row[5] else {},
                "error_message": row[6],
                "timestamp": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_extraction_progress(ap_package_id: str) -> List[Dict[str, Any]]:
    """
    Get extraction progress log for a package.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT step, message, created_at
            FROM extraction_progress
            WHERE ap_package_id = ?
            ORDER BY id ASC
        """, (ap_package_id,))
        rows = cursor.fetchall()
        
        return [
            {
                "step": row[0],
                "message": row[1],
                "timestamp": row[2],
            }
            for row in rows
        ]
    finally:
        conn.close()


# =============================================================================
# PACKAGE STATUS ROLLUP (Deterministic)
# =============================================================================

def compute_package_status(ap_package_id: str) -> Dict[str, Any]:
    """
    Deterministically compute package status from invoice states.
    
    Rules:
    - If any invoice is BLOCKED → Package is BLOCKED
    - If any invoice needs REVIEW → Package is REVIEW
    - If all invoices are READY → Package is READY
    - Default to current DB status if no invoices
    """
    package = get_package_from_db(ap_package_id)
    if not package:
        return {"status": "unknown", "reason": "Package not found"}
    
    invoices = get_invoices_from_db(ap_package_id)
    
    if not invoices:
        # No invoices yet, use package DB status
        return {
            "status": package["status"],
            "reason": "No invoices extracted yet",
            "invoice_count": 0,
        }
    
    # Count invoice states
    ready_count = 0
    review_count = 0
    blocked_count = 0
    
    for inv in invoices:
        status = inv.get("status", "").upper()
        if "FAIL" in status or "BLOCKED" in status:
            blocked_count += 1
        elif "WARN" in status or "REVIEW" in status:
            review_count += 1
        else:
            ready_count += 1
    
    # Determine package status
    if blocked_count > 0:
        computed_status = "BLOCKED"
        reason = f"{blocked_count} invoice(s) blocked"
    elif review_count > 0:
        computed_status = "REVIEW"
        reason = f"{review_count} invoice(s) need review"
    else:
        computed_status = "READY"
        reason = "All invoices ready"
    
    return {
        "status": computed_status,
        "reason": reason,
        "invoice_count": len(invoices),
        "ready_count": ready_count,
        "review_count": review_count,
        "blocked_count": blocked_count,
        "db_status": package["status"],  # Original DB status for comparison
    }


# =============================================================================
# WORKFLOW STATE HELPERS
# =============================================================================

def get_current_workflow_stage(ap_package_id: str) -> Dict[str, Any]:
    """
    Determine the current workflow stage from audit events.
    
    This enables showing correct in-progress states after worker restart.
    """
    events = get_audit_events(ap_package_id, invoice_number="*", limit=10)
    
    if not events:
        package = get_package_from_db(ap_package_id)
        if package:
            return {
                "current_stage": "STARTED",
                "status": package["status"],
                "last_activity": package["updated_at"],
            }
        return {"current_stage": "UNKNOWN", "status": "not_found"}
    
    # Most recent event is current state
    latest = events[0]
    
    return {
        "current_stage": latest["stage"],
        "status": latest["status"],
        "last_activity": latest["timestamp"],
        "details": latest["details"],
    }


def is_package_complete(ap_package_id: str) -> bool:
    """
    Check if package workflow has completed.
    """
    stage = get_current_workflow_stage(ap_package_id)
    return stage.get("current_stage") in [
        "RECONCILED", 
        "PAYLOAD_GENERATED",
        "INTEGRATION_BLOCKED",
    ]
