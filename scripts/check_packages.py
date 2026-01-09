"""Check AP package records in the database.

This script reads the ap_packages and ap_invoices tables and displays records.
"""

import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from activities.persist import DB_PATH, get_package, get_invoices, init_db
import sqlite3


def list_packages():
    """List all AP packages in the database."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run start_ap_package.py first to create the database.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ap_package_id, feedlot_type, status, created_at, updated_at
            FROM ap_packages
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        
        if not rows:
            print("No packages found in database.")
            return
        
        print("\n=== AP PACKAGES ===")
        print(f"{'Package ID':<20} {'Feedlot':<10} {'Status':<12} {'Created At'}")
        print("-" * 70)
        for row in rows:
            print(f"{row[0]:<20} {row[1]:<10} {row[2]:<12} {row[3]}")
        print(f"\nTotal: {len(rows)} package(s)")
        print("===================\n")
        
    finally:
        conn.close()


def list_invoices(ap_package_id: str = None):
    """List invoices, optionally filtered by package."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        if ap_package_id:
            cursor.execute("""
                SELECT ap_package_id, invoice_number, lot_number, total_amount, status, created_at
                FROM ap_invoices
                WHERE ap_package_id = ?
                ORDER BY invoice_number
            """, (ap_package_id,))
        else:
            cursor.execute("""
                SELECT ap_package_id, invoice_number, lot_number, total_amount, status, created_at
                FROM ap_invoices
                ORDER BY ap_package_id, invoice_number
            """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print("No invoices found.")
            return
        
        print("\n=== AP INVOICES ===")
        print(f"{'Package ID':<16} {'Invoice #':<12} {'Lot #':<10} {'Amount':<12} {'Status':<10}")
        print("-" * 70)
        for row in rows:
            pkg_id = row[0][:14] + ".." if len(row[0]) > 16 else row[0]
            inv_num = row[1] or "-"
            lot_num = row[2] or "-"
            amount = row[3] or "-"
            status = row[4] or "-"
            print(f"{pkg_id:<16} {inv_num:<12} {lot_num:<10} {amount:<12} {status:<10}")
        print(f"\nTotal: {len(rows)} invoice(s)")
        print("===================\n")
        
    finally:
        conn.close()


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check AP packages and invoices in database")
    parser.add_argument("--id", help="Specific package ID to look up")
    parser.add_argument("--invoices", action="store_true", help="Show invoices instead of packages")
    parser.add_argument("--all", action="store_true", help="Show both packages and invoices")
    args = parser.parse_args()
    
    # Ensure DB is initialized
    init_db()
    
    if args.id:
        # Look up specific package
        pkg = get_package(args.id)
        if pkg:
            print("\n=== PACKAGE DETAILS ===")
            for key, value in pkg.items():
                print(f"  {key}: {value}")
            print("========================\n")
            
            # Also show invoices for this package
            invoices = get_invoices(args.id)
            if invoices:
                print(f"=== INVOICES ({len(invoices)}) ===")
                for inv in invoices:
                    print(f"  - {inv['invoice_number']}: lot={inv['lot_number']}, amount={inv['total_amount']}")
                print("========================\n")
        else:
            print(f"Package not found: {args.id}")
            return 1
    elif args.invoices:
        list_invoices()
    elif args.all:
        list_packages()
        list_invoices()
    else:
        list_packages()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
