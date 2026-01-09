#!/usr/bin/env python
"""Watch extraction progress in real-time.

Usage:
    python scripts/watch_progress.py <ap_package_id>
    python scripts/watch_progress.py pkg-12345678
    python scripts/watch_progress.py --latest
"""

import argparse
import sqlite3
import time
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "ap_automation.db"


def clear_line():
    """Clear the current line in terminal."""
    sys.stdout.write('\r' + ' ' * 80 + '\r')
    sys.stdout.flush()


def get_package_info(conn: sqlite3.Connection, ap_package_id: str) -> dict:
    """Get package status and extraction counts."""
    cursor = conn.execute(
        """
        SELECT feedlot_type, status, total_invoices, extracted_invoices, created_at
        FROM ap_packages
        WHERE ap_package_id = ?
        """,
        (ap_package_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "feedlot_type": row[0],
            "status": row[1],
            "total_invoices": row[2] or 0,
            "extracted_invoices": row[3] or 0,
            "created_at": row[4],
        }
    return None


def get_latest_progress(conn: sqlite3.Connection, ap_package_id: str, since_id: int = 0) -> list:
    """Get progress entries since the given ID."""
    cursor = conn.execute(
        """
        SELECT id, step, message, created_at
        FROM extraction_progress
        WHERE ap_package_id = ? AND id > ?
        ORDER BY id ASC
        """,
        (ap_package_id, since_id)
    )
    return cursor.fetchall()


def get_latest_package_id(conn: sqlite3.Connection) -> str:
    """Get the most recently created package ID."""
    cursor = conn.execute(
        """
        SELECT ap_package_id FROM ap_packages
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    return row[0] if row else None


def format_progress_bar(extracted: int, total: int, width: int = 30) -> str:
    """Create a progress bar string."""
    if total == 0:
        return "[" + "-" * width + "]"
    
    filled = int(width * extracted / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = (extracted / total) * 100
    return f"[{bar}] {pct:.0f}%"


def watch_progress(ap_package_id: str, poll_interval: float = 1.0):
    """Watch progress for a package in real-time."""
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get initial package info
    pkg = get_package_info(conn, ap_package_id)
    if not pkg:
        print(f"Error: Package {ap_package_id} not found")
        conn.close()
        return
    
    print("=" * 60)
    print(f"Monitoring: {ap_package_id}")
    print(f"Feedlot: {pkg['feedlot_type']}")
    print(f"Started: {pkg['created_at']}")
    print("=" * 60)
    print()
    
    last_progress_id = 0
    last_extracted = 0
    
    while True:
        try:
            # Refresh package info
            pkg = get_package_info(conn, ap_package_id)
            if not pkg:
                break
            
            # Get new progress entries
            new_entries = get_latest_progress(conn, ap_package_id, last_progress_id)
            
            for entry in new_entries:
                entry_id, step, message, created_at = entry
                timestamp = created_at.split("T")[1][:8] if "T" in created_at else created_at[-8:]
                
                # Color-code by step
                if step == "split_pdf":
                    prefix = "📄"
                elif step == "extract_statement":
                    prefix = "📋"
                elif step == "extract_invoice":
                    prefix = "📝"
                else:
                    prefix = "•"
                
                print(f"  {prefix} [{timestamp}] {message}")
                last_progress_id = entry_id
            
            # Update progress bar if extraction count changed
            if pkg['extracted_invoices'] != last_extracted or new_entries:
                total = pkg['total_invoices']
                extracted = pkg['extracted_invoices']
                bar = format_progress_bar(extracted, total)
                
                if total > 0:
                    clear_line()
                    sys.stdout.write(f"  Progress: {bar} {extracted}/{total} invoices")
                    sys.stdout.flush()
                
                last_extracted = extracted
            
            # Check if complete
            if pkg['status'] == "EXTRACTED":
                print()
                print()
                print("✅ Extraction complete!")
                print(f"   Total invoices extracted: {pkg['extracted_invoices']}")
                break
            
            time.sleep(poll_interval)
            
        except KeyboardInterrupt:
            print()
            print("\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Watch extraction progress in real-time")
    parser.add_argument("package_id", nargs="?", help="AP Package ID to monitor (e.g., pkg-12345678)")
    parser.add_argument("--latest", action="store_true", help="Monitor the most recent package")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds (default: 1.0)")
    
    args = parser.parse_args()
    
    ap_package_id = args.package_id
    
    if args.latest or not ap_package_id:
        if not DB_PATH.exists():
            print(f"Error: Database not found at {DB_PATH}")
            return
        
        conn = sqlite3.connect(DB_PATH)
        ap_package_id = get_latest_package_id(conn)
        conn.close()
        
        if not ap_package_id:
            print("No packages found in database")
            return
        
        print(f"Monitoring latest package: {ap_package_id}")
    
    watch_progress(ap_package_id, args.interval)


if __name__ == "__main__":
    main()
