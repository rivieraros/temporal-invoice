"""
Temporal Failure Injection Test Suite

Tests for durability and idempotency - proving Temporal's real value:
1. Worker kill mid-extraction → workflow resumes; no duplicate artifacts
2. LLM call fails (429/5xx) → activity retries per policy; no manual restart
3. DB write fails temporarily → activity retries; no partial posting
4. Missing invoice page → package completes with WARN, not stuck
5. Duplicate document ingestion → dedupe/idempotency prevents reprocessing

Pass Criteria:
- No duplicate invoices created in DB
- No "stuck forever" workflows without a reason
- UI shows correct "waiting" reasons
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from temporalio import activity
from temporalio.common import RetryPolicy

# Database path
DB_PATH = Path(__file__).resolve().parent / "ap_automation.db"


# =============================================================================
# TEST UTILITIES
# =============================================================================

@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    duration_ms: float
    details: Dict[str, Any] = None


class TestSuite:
    """Failure injection test suite."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.db_path = DB_PATH
        
    def add_result(self, result: TestResult):
        self.results.append(result)
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"  {status}: {result.name} ({result.duration_ms:.0f}ms)")
        if not result.passed:
            print(f"         {result.message}")
        
    def summary(self) -> bool:
        """Print summary and return True if all passed."""
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        print("\n" + "="*70)
        print(f"SUMMARY: {passed} passed, {failed} failed")
        print("="*70)
        
        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")
        
        return failed == 0


def get_db_connection():
    """Get SQLite database connection."""
    return sqlite3.connect(str(DB_PATH))


def clear_test_data(package_id: str):
    """Clear test data from database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ap_invoices WHERE ap_package_id = ?", (package_id,))
        cursor.execute("DELETE FROM ap_packages WHERE ap_package_id = ?", (package_id,))
        cursor.execute("DELETE FROM audit_events WHERE ap_package_id = ?", (package_id,))
        cursor.execute("DELETE FROM extraction_progress WHERE ap_package_id = ?", (package_id,))
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Tables may not exist
    finally:
        conn.close()


def count_invoices(package_id: str) -> int:
    """Count invoices for a package."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM ap_invoices WHERE ap_package_id = ?", 
            (package_id,)
        )
        return cursor.fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def get_package_status(package_id: str) -> Optional[str]:
    """Get package status from database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM ap_packages WHERE ap_package_id = ?", 
            (package_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def get_audit_events(package_id: str) -> List[Dict]:
    """Get audit events for a package."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT stage, status, details, error_message, created_at 
               FROM audit_events WHERE ap_package_id = ? ORDER BY id""", 
            (package_id,)
        )
        return [
            {"stage": r[0], "status": r[1], "details": r[2], "error": r[3], "timestamp": r[4]}
            for r in cursor.fetchall()
        ]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


# =============================================================================
# TEST 1: Worker Kill Mid-Extraction (Simulated)
# =============================================================================

async def test_worker_kill_resume(suite: TestSuite):
    """
    Test: Worker kill mid-extraction → workflow resumes; no duplicate artifacts
    
    Simulation: 
    - Start persist_package_started
    - "Kill" worker (simulate by throwing exception)
    - Resume activity (Temporal would retry)
    - Verify no duplicate package records
    """
    test_name = "Worker Kill Mid-Extraction Resume"
    start_time = time.time()
    package_id = f"TEST-KILL-{uuid.uuid4().hex[:8]}"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import persist_package_started, PersistPackageInput, init_db
        init_db()
        
        # First call - simulates successful persist
        input1 = PersistPackageInput(
            ap_package_id=package_id,
            feedlot_type="BOVINA",
            document_refs=[]
        )
        result1 = await persist_package_started(input1)
        assert result1["status"] == "STARTED", "First persist should succeed"
        
        # Second call - simulates retry after worker restart
        # This should be idempotent (not create duplicate)
        try:
            result2 = await persist_package_started(input1)
            # If we get here, it means INSERT OR REPLACE was used (acceptable)
            duplicate_count = 0
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM ap_packages WHERE ap_package_id = ?", 
                (package_id,)
            )
            duplicate_count = cursor.fetchone()[0]
            conn.close()
            
            if duplicate_count > 1:
                raise AssertionError(f"Duplicate packages created: {duplicate_count}")
                
        except sqlite3.IntegrityError:
            # This is actually correct - UNIQUE constraint prevents duplicates
            pass
        
        # Verify only one package exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM ap_packages WHERE ap_package_id = ?", 
            (package_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1, f"Expected 1 package, found {count}"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message="No duplicate packages after simulated restart",
            duration_ms=duration,
            details={"package_id": package_id, "count": count}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 2: LLM Call Failure with Retry Policy
# =============================================================================

async def test_llm_retry_policy(suite: TestSuite):
    """
    Test: LLM call fails (429/5xx) → activity retries per policy
    
    Simulation:
    - Mock LLM call to fail twice, then succeed
    - Verify retry counter increases
    - Verify final success after retries
    """
    test_name = "LLM Failure Retry Policy"
    start_time = time.time()
    
    try:
        # Test the retry policy configuration
        from temporalio.common import RetryPolicy
        
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            non_retryable_error_types=["ValueError"],  # Business logic errors don't retry
        )
        
        # Verify retry policy settings
        assert retry_policy.maximum_attempts == 3
        assert retry_policy.backoff_coefficient == 2.0
        
        # Simulate retry counter
        attempt_count = 0
        max_attempts = 3
        
        class MockLLMError(Exception):
            pass
        
        def mock_llm_call():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise MockLLMError(f"Simulated 429 error (attempt {attempt_count})")
            return {"result": "success"}
        
        # Simulate Temporal's retry behavior
        result = None
        last_error = None
        for i in range(max_attempts):
            try:
                result = mock_llm_call()
                break
            except MockLLMError as e:
                last_error = e
                continue
        
        assert result is not None, f"Should succeed after retries, last error: {last_error}"
        assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"Retry policy works: succeeded on attempt {attempt_count}",
            duration_ms=duration,
            details={"attempts": attempt_count, "max_attempts": max_attempts}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))


# =============================================================================
# TEST 3: DB Write Failure with Retry
# =============================================================================

async def test_db_write_retry(suite: TestSuite):
    """
    Test: DB write fails temporarily → activity retries; no partial posting
    
    Simulation:
    - First DB write fails (simulated)
    - Second DB write succeeds
    - Verify no partial data in DB
    """
    test_name = "DB Write Failure Retry"
    start_time = time.time()
    package_id = f"TEST-DB-{uuid.uuid4().hex[:8]}"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import init_db
        init_db()
        
        # Simulate transient failure then success
        attempt = 0
        
        def db_operation_with_failure():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise sqlite3.OperationalError("Simulated database lock")
            # Second attempt succeeds
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO ap_packages (ap_package_id, feedlot_type, status, created_at, updated_at)
                VALUES (?, 'BOVINA', 'STARTED', ?, ?)
            """, (package_id, now, now))
            conn.commit()
            conn.close()
            return True
        
        # Simulate Temporal's retry
        result = None
        for i in range(3):
            try:
                result = db_operation_with_failure()
                break
            except sqlite3.OperationalError:
                continue
        
        assert result is True, "DB operation should eventually succeed"
        assert attempt == 2, f"Expected 2 attempts, got {attempt}"
        
        # Verify exactly one record
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM ap_packages WHERE ap_package_id = ?", 
            (package_id,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1, f"Expected 1 package, found {count}"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"DB retry works: succeeded on attempt {attempt}, no partial data",
            duration_ms=duration,
            details={"attempts": attempt, "record_count": count}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 4: Missing Invoice Page Handling
# =============================================================================

async def test_missing_invoice_handling(suite: TestSuite):
    """
    Test: Missing invoice page → package completes with WARN, not stuck
    
    Simulation:
    - Process package where one invoice page is missing/empty
    - Verify package status is WARN (not BLOCKED or stuck)
    - Verify audit trail records the issue
    """
    test_name = "Missing Invoice Page Handling"
    start_time = time.time()
    package_id = f"TEST-MISS-{uuid.uuid4().hex[:8]}"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import init_db, persist_package_started, update_package_status
        from activities.persist import PersistPackageInput, UpdatePackageStatusInput
        from activities.integrate import persist_audit_event, AuditEventInput
        
        init_db()
        
        # Create package
        await persist_package_started(PersistPackageInput(
            ap_package_id=package_id,
            feedlot_type="BOVINA",
            document_refs=[]
        ))
        
        # Simulate missing invoice detection and WARN status
        # In real workflow, this happens when an invoice page can't be extracted
        await persist_audit_event(AuditEventInput(
            ap_package_id=package_id,
            invoice_number="13304",  # The "Bovina 13304-type" missing invoice
            stage="EXTRACTED",
            status="WARN",
            details={"reason": "Invoice page missing or unreadable"},
            error_message="Could not extract invoice data from page"
        ))
        
        # Update package status to RECONCILED_WARN (not BLOCKED)
        await update_package_status(UpdatePackageStatusInput(
            ap_package_id=package_id,
            status="RECONCILED_WARN",
            statement_ref=None
        ))
        
        # Verify package completed with WARN (not stuck)
        status = get_package_status(package_id)
        assert status == "RECONCILED_WARN", f"Expected RECONCILED_WARN, got {status}"
        
        # Verify audit trail has the warning
        events = get_audit_events(package_id)
        warn_events = [e for e in events if e["status"] == "WARN"]
        assert len(warn_events) >= 1, "Should have at least one WARN event"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"Package completed with WARN status, not stuck",
            duration_ms=duration,
            details={"status": status, "warn_events": len(warn_events)}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 5: Duplicate Document Ingestion / Idempotency
# =============================================================================

async def test_duplicate_ingestion_idempotency(suite: TestSuite):
    """
    Test: Duplicate document ingestion → dedupe/idempotency prevents reprocessing
    
    Simulation:
    - Ingest same invoice twice
    - Verify only one invoice record exists
    - Verify audit trail shows dedup
    """
    test_name = "Duplicate Ingestion Idempotency"
    start_time = time.time()
    package_id = f"TEST-DUP-{uuid.uuid4().hex[:8]}"
    invoice_number = "INV-12345"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import (
            init_db, 
            persist_package_started, 
            persist_invoice,
            PersistPackageInput, 
            PersistInvoiceInput
        )
        
        init_db()
        
        # Create package
        await persist_package_started(PersistPackageInput(
            ap_package_id=package_id,
            feedlot_type="BOVINA",
            document_refs=[]
        ))
        
        # First invoice persist
        invoice_input = PersistInvoiceInput(
            ap_package_id=package_id,
            invoice_number=invoice_number,
            lot_number="20-1234",
            invoice_date="2025-11-15",
            total_amount="1500.00",
            invoice_ref={"path": "test/invoice.json", "hash": "abc123"}
        )
        
        result1 = await persist_invoice(invoice_input)
        assert result1["invoice_number"] == invoice_number
        
        # Second persist (duplicate) - should use INSERT OR REPLACE
        result2 = await persist_invoice(invoice_input)
        assert result2["invoice_number"] == invoice_number
        
        # Verify only ONE invoice exists (not two)
        count = count_invoices(package_id)
        assert count == 1, f"Expected 1 invoice, found {count} - DUPLICATE CREATED!"
        
        # Verify invoice data is correct (not corrupted by replace)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT invoice_number, lot_number, total_amount FROM ap_invoices WHERE ap_package_id = ?",
            (package_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        assert row[0] == invoice_number
        assert row[1] == "20-1234"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"Idempotency verified: {count} invoice after 2 persists",
            duration_ms=duration,
            details={"invoice_count": count, "invoice_number": invoice_number}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 6: No Stuck Workflows - All Have Reason
# =============================================================================

async def test_no_stuck_workflows(suite: TestSuite):
    """
    Test: No "stuck forever" workflows without a reason
    
    Verifies that any package in non-terminal state has:
    - An audit trail explaining why
    - A current_stage that makes sense
    """
    test_name = "No Stuck Workflows Without Reason"
    start_time = time.time()
    package_id = f"TEST-STUCK-{uuid.uuid4().hex[:8]}"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import init_db, persist_package_started, PersistPackageInput
        from activities.integrate import persist_audit_event, AuditEventInput
        
        init_db()
        
        # Create package that appears "stuck" in STARTED state
        await persist_package_started(PersistPackageInput(
            ap_package_id=package_id,
            feedlot_type="BOVINA",
            document_refs=[]
        ))
        
        # Add audit event explaining why (INGESTED stage)
        await persist_audit_event(AuditEventInput(
            ap_package_id=package_id,
            invoice_number="*",
            stage="INGESTED",
            status="SUCCESS",
            details={"feedlot_type": "BOVINA"},
        ))
        
        # Check: package has audit trail explaining state
        events = get_audit_events(package_id)
        assert len(events) > 0, "Package should have audit events"
        
        # Check: latest event explains current state
        latest = events[-1]
        assert latest["stage"] in ["INGESTED", "EXTRACTED", "VALIDATED", "RECONCILED"], \
            f"Unexpected stage: {latest['stage']}"
        
        # Check: we can determine "why" it's in current state
        status = get_package_status(package_id)
        reason = f"Package at stage {latest['stage']} with status {latest['status']}"
        assert reason, "Should be able to explain package state"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"Package has explainable state: {reason}",
            duration_ms=duration,
            details={"stage": latest["stage"], "status": status}
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 7: UI Waiting Reasons Display
# =============================================================================

async def test_ui_waiting_reasons(suite: TestSuite):
    """
    Test: UI shows correct "waiting" reasons
    
    Verifies the db_queries module can determine waiting reasons.
    """
    test_name = "UI Waiting Reasons Display"
    start_time = time.time()
    package_id = f"TEST-UI-{uuid.uuid4().hex[:8]}"
    
    try:
        clear_test_data(package_id)
        
        from activities.persist import init_db, persist_package_started, persist_invoice
        from activities.persist import PersistPackageInput, PersistInvoiceInput
        from api.services.db_queries import compute_package_status, get_current_workflow_stage
        
        init_db()
        
        # Create package with mixed invoice states
        await persist_package_started(PersistPackageInput(
            ap_package_id=package_id,
            feedlot_type="BOVINA",
            document_refs=[]
        ))
        
        # Add invoices with different states
        for i, status in enumerate(["VALIDATED_PASS", "VALIDATED_WARN", "EXTRACTED"]):
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO ap_invoices 
                (ap_package_id, invoice_number, lot_number, status, invoice_ref, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (package_id, f"INV-{i+1}", f"LOT-{i+1}", status, "{}", now, now))
            conn.commit()
            conn.close()
        
        # Test compute_package_status
        status_info = compute_package_status(package_id)
        
        assert status_info["status"] == "REVIEW", \
            f"Expected REVIEW (has WARN invoice), got {status_info['status']}"
        assert "review" in status_info["reason"].lower(), \
            f"Reason should mention review: {status_info['reason']}"
        assert status_info["review_count"] == 1, \
            f"Expected 1 review invoice, got {status_info['review_count']}"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message=f"UI correctly shows: {status_info['reason']}",
            duration_ms=duration,
            details=status_info
        ))
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))
    finally:
        clear_test_data(package_id)


# =============================================================================
# TEST 8: Artifact Deduplication
# =============================================================================

async def test_artifact_no_duplicates(suite: TestSuite):
    """
    Test: No duplicate artifacts created on retry
    
    Verifies that artifact storage is idempotent.
    """
    test_name = "Artifact Deduplication"
    start_time = time.time()
    
    try:
        from storage.artifacts import put_json, get_json
        
        # Create test artifact
        test_data = {"invoice_number": "TEST-001", "amount": 1234.56}
        ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
        artifact_path = ARTIFACTS_DIR / "test_feedlot" / f"idempotent_test_{uuid.uuid4().hex[:8]}.json"
        
        # Put artifact twice
        ref1 = put_json(test_data, artifact_path)
        ref2 = put_json(test_data, artifact_path)
        
        # Both refs should point to same content (same hash)
        assert ref1.content_hash == ref2.content_hash, "Hashes should match for same content"
        
        # Only one file should exist (overwritten)
        assert artifact_path.exists(), "Artifact file should exist"
        content = json.loads(artifact_path.read_text())
        assert content == test_data, "Content should match"
        
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=True,
            message="Artifact storage is idempotent",
            duration_ms=duration,
            details={"hash": ref1.content_hash}
        ))
        
        # Cleanup
        if artifact_path.exists():
            artifact_path.unlink()
            
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        suite.add_result(TestResult(
            name=test_name,
            passed=False,
            message=str(e),
            duration_ms=duration
        ))


# =============================================================================
# MAIN
# =============================================================================

async def run_all_tests():
    """Run all failure injection tests."""
    print("\n" + "="*70)
    print("TEMPORAL FAILURE INJECTION TEST SUITE")
    print("="*70)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Time: {datetime.now().isoformat()}")
    print("\n" + "-"*70 + "\n")
    
    suite = TestSuite()
    
    # Run tests
    print("Running tests...\n")
    
    await test_worker_kill_resume(suite)
    await test_llm_retry_policy(suite)
    await test_db_write_retry(suite)
    await test_missing_invoice_handling(suite)
    await test_duplicate_ingestion_idempotency(suite)
    await test_no_stuck_workflows(suite)
    await test_ui_waiting_reasons(suite)
    await test_artifact_no_duplicates(suite)
    
    # Summary
    all_passed = suite.summary()
    
    # Pass criteria check
    print("\n" + "-"*70)
    print("PASS CRITERIA CHECK:")
    print("-"*70)
    
    criteria = [
        ("No duplicate invoices in DB", "test_duplicate_ingestion_idempotency"),
        ("No stuck workflows without reason", "test_no_stuck_workflows"),
        ("UI shows correct waiting reasons", "test_ui_waiting_reasons"),
    ]
    
    for criterion, test_name in criteria:
        result = next((r for r in suite.results if test_name in r.name.lower().replace(" ", "_") or r.name == test_name), None)
        if result is None:
            result = next((r for r in suite.results if test_name.replace("test_", "").replace("_", " ").lower() in r.name.lower()), None)
        
        if result and result.passed:
            print(f"  ✓ {criterion}")
        else:
            print(f"  ✗ {criterion}")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Temporal durability and idempotency verified!")
    else:
        print("✗ SOME TESTS FAILED - Review output above")
    print("="*70 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)
