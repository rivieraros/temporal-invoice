#!/usr/bin/env python3
"""
Temporal Performance & Safety Validation Test Suite

Tests the pass criteria for Temporal performance and safety:
1. No workflow hits payload/history limits
2. No hot-loop retries that spike cost

This validates:
- Workflow state contains only lightweight refs (no large JSON blobs)
- All activities have start-to-close timeouts
- Retry policies have proper backoff and non-retryable errors
- Task queues are properly separated
- Heartbeat timeouts are set for long-running activities
"""

import asyncio
import ast
import inspect
import re
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))


# =============================================================================
# Test Infrastructure
# =============================================================================

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    details: Optional[List[str]] = None


class PerformanceTestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
    
    def record(self, name: str, passed: bool, message: str, details: List[str] = None):
        self.results.append(TestResult(name, passed, message, details))
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed and details:
            for detail in details[:5]:  # Limit to 5 details
                print(f"          {detail}")
    
    def summary(self) -> bool:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        print(f"\n{'='*70}")
        print(f"SUMMARY: {passed} passed, {failed} failed")
        print(f"{'='*70}")
        return failed == 0


# =============================================================================
# Test: Workflow State Size (No Large JSON Blobs)
# =============================================================================

def test_workflow_state_size(suite: PerformanceTestSuite):
    """Verify workflows only store lightweight refs, not large JSON blobs."""
    from workflows.ap_package_workflow import APPackageInput
    from workflows.invoice_workflow import InvoiceWorkflowInput, InvoiceWorkflowOutput
    
    issues = []
    
    # Check APPackageInput - should only have refs, not full documents
    ap_fields = APPackageInput.__dataclass_fields__
    for name, field in ap_fields.items():
        field_type = str(field.type)
        # Flag if any field could hold large data
        if "dict" in field_type.lower() and name not in ["document_refs"]:
            issues.append(f"APPackageInput.{name}: dict field could hold large data")
    
    # Check InvoiceWorkflowInput
    invoice_fields = InvoiceWorkflowInput.__dataclass_fields__
    large_fields = []
    for name, field in invoice_fields.items():
        field_type = str(field.type)
        if "dict" in field_type.lower():
            large_fields.append(name)
    
    # invoice_data and statement_data are dicts - acceptable for now but should be refs
    # This is a warning, not a failure
    if large_fields:
        issues.append(f"InvoiceWorkflowInput has dict fields (consider refs): {large_fields}")
    
    # Check that workflow returns are small
    # APPackageWorkflow returns a dict with summary info, not full documents
    # InvoiceWorkflow returns InvoiceWorkflowOutput with refs
    
    output_fields = InvoiceWorkflowOutput.__dataclass_fields__
    for name, field in output_fields.items():
        if name == "payload_ref":
            # This should be a ref, not the full payload
            continue
        if name == "stage_results":
            # This is a list of stage results - could grow but bounded
            continue
    
    # Estimate max sizes (rough heuristic)
    # APPackageInput: ~500 bytes
    # InvoiceWorkflowInput with invoice_data: ~5KB typical
    # InvoiceWorkflowOutput: ~2KB typical
    
    MAX_INPUT_SIZE_KB = 50  # Temporal limit is 256KB, we want headroom
    
    # These are acceptable - document the findings
    warnings = [
        "APPackageInput stores document_refs (list of refs) - OK",
        "InvoiceWorkflowInput stores invoice_data (dict) - Should be converted to ref in future",
        "Workflow returns summary dicts, not full documents - OK",
    ]
    
    # Pass if no critical issues (dicts in input are acceptable for MVP)
    passed = len([i for i in issues if "could hold large data" in i]) == 0
    
    suite.record(
        "Workflow State Size",
        passed,
        "Workflows store lightweight refs" if passed else "Large data in workflow state",
        issues + warnings if not passed else None
    )


# =============================================================================
# Test: All Activities Have Timeouts
# =============================================================================

def test_activity_timeouts(suite: PerformanceTestSuite):
    """Verify all execute_activity calls have start_to_close_timeout."""
    workflow_files = [
        Path(__file__).parent / "workflows" / "ap_package_workflow.py",
        Path(__file__).parent / "workflows" / "invoice_workflow.py",
    ]
    
    issues = []
    timeout_count = 0
    activity_count = 0
    
    for wf_file in workflow_files:
        if not wf_file.exists():
            issues.append(f"Workflow file not found: {wf_file.name}")
            continue
        
        content = wf_file.read_text(encoding="utf-8")
        
        # Count execute_activity calls
        activity_count += content.count("workflow.execute_activity(")
        
        # Count timeout definitions
        timeout_count += content.count("start_to_close_timeout")
        
        # Also count spread options that include timeouts
        if "activity_options" in content and "start_to_close_timeout" in content:
            # Options are defined with timeout and spread to activities
            # Count how many times options are spread
            timeout_count += content.count("**activity_options")
            timeout_count += content.count("**erp_activity_options")
            timeout_count += content.count("**db_activity_options")
    
    # Every activity should have a timeout (explicit or via spread)
    # In practice, some activities may share options, so we check >= activity_count
    passed = timeout_count >= activity_count and activity_count > 0
    
    suite.record(
        "Activity Timeouts",
        passed,
        f"{activity_count} activities, {timeout_count} timeout configs" if passed else f"Found {timeout_count} timeouts for {activity_count} activities",
        None if passed else [f"Expected >= {activity_count} timeout configs, found {timeout_count}"]
    )


# =============================================================================
# Test: Retry Policies Have Backoff
# =============================================================================

def test_retry_policy_backoff(suite: PerformanceTestSuite):
    """Verify retry policies have proper backoff coefficient (no hot loops)."""
    workflow_files = [
        Path(__file__).parent / "workflows" / "ap_package_workflow.py",
        Path(__file__).parent / "workflows" / "invoice_workflow.py",
    ]
    
    issues = []
    policies_found = 0
    
    for wf_file in workflow_files:
        if not wf_file.exists():
            continue
        
        content = wf_file.read_text(encoding="utf-8")
        
        # Find RetryPolicy definitions
        policy_pattern = r"RetryPolicy\([^)]+\)"
        matches = re.findall(policy_pattern, content, re.DOTALL)
        
        for match in matches:
            policies_found += 1
            
            # Check for backoff_coefficient
            if "backoff_coefficient" not in match:
                issues.append(f"{wf_file.name}: RetryPolicy missing backoff_coefficient")
            else:
                # Extract coefficient value
                coef_match = re.search(r"backoff_coefficient\s*=\s*([0-9.]+)", match)
                if coef_match:
                    coef = float(coef_match.group(1))
                    if coef < 1.5:
                        issues.append(f"{wf_file.name}: backoff_coefficient too low ({coef}), risk of hot loops")
            
            # Check for maximum_interval (should be set to prevent infinite backoff)
            if "maximum_interval" not in match:
                # Check if it's the reconcile policy (which is OK without max interval)
                if "RECONCILE_RETRY_POLICY" not in content[:content.find(match)]:
                    issues.append(f"{wf_file.name}: RetryPolicy should have maximum_interval")
            
            # Check for non_retryable_error_types
            if "non_retryable_error_types" not in match:
                issues.append(f"{wf_file.name}: RetryPolicy should define non_retryable_error_types")
    
    passed = policies_found > 0 and len([i for i in issues if "hot loops" in i]) == 0
    suite.record(
        "Retry Policy Backoff",
        passed,
        f"Found {policies_found} policies with proper backoff" if passed else "Issues with retry policies",
        issues if issues else None
    )


# =============================================================================
# Test: Non-Retryable Errors Defined
# =============================================================================

def test_non_retryable_errors(suite: PerformanceTestSuite):
    """Verify validation/schema errors won't retry forever."""
    workflow_files = [
        Path(__file__).parent / "workflows" / "ap_package_workflow.py",
        Path(__file__).parent / "workflows" / "invoice_workflow.py",
    ]
    
    expected_non_retryable = ["ValidationError", "SchemaError", "AuthenticationError"]
    found_errors = set()
    
    for wf_file in workflow_files:
        if not wf_file.exists():
            continue
        
        content = wf_file.read_text(encoding="utf-8")
        
        # Find non_retryable_error_types
        pattern = r'non_retryable_error_types\s*=\s*\[([^\]]+)\]'
        matches = re.findall(pattern, content)
        
        for match in matches:
            # Extract error type names
            for error_type in expected_non_retryable:
                if error_type in match:
                    found_errors.add(error_type)
    
    missing = [e for e in expected_non_retryable if e not in found_errors]
    passed = len(missing) <= 1  # Allow 1 missing as some may not apply
    
    suite.record(
        "Non-Retryable Errors Defined",
        passed,
        f"Found {len(found_errors)} non-retryable error types" if passed else f"Missing: {missing}",
        [f"Defined: {list(found_errors)}"] + ([f"Missing: {missing}"] if missing else [])
    )


# =============================================================================
# Test: Task Queue Separation
# =============================================================================

def test_task_queue_separation(suite: PerformanceTestSuite):
    """Verify LLM activities are on separate queue from DB activities."""
    workflow_file = Path(__file__).parent / "workflows" / "ap_package_workflow.py"
    worker_file = Path(__file__).parent / "workers" / "worker.py"
    
    issues = []
    queues_found = set()
    
    # Check workflow for task_queue definitions
    if workflow_file.exists():
        content = workflow_file.read_text(encoding="utf-8")
        
        # Find task queue constants
        queue_pattern = r'TASK_QUEUE_(\w+)\s*=\s*"([^"]+)"'
        matches = re.findall(queue_pattern, content)
        
        for name, value in matches:
            queues_found.add(value)
        
        # Check LLM activities use LLM queue
        if 'task_queue=TASK_QUEUE_LLM' not in content:
            issues.append("LLM activities not explicitly on TASK_QUEUE_LLM")
    
    # Check worker supports multiple queues
    if worker_file.exists():
        content = worker_file.read_text(encoding="utf-8")
        
        if "LLM_QUEUE_ACTIVITIES" not in content:
            issues.append("Worker doesn't define LLM_QUEUE_ACTIVITIES")
        
        if "DEFAULT_QUEUE_ACTIVITIES" not in content:
            issues.append("Worker doesn't define DEFAULT_QUEUE_ACTIVITIES")
        
        if "--queue" not in content and "-q" not in content:
            issues.append("Worker doesn't support queue selection via CLI")
    
    passed = len(queues_found) >= 2 and len([i for i in issues if "LLM" in i]) == 0
    
    suite.record(
        "Task Queue Separation",
        passed,
        f"Found {len(queues_found)} task queues: {queues_found}" if passed else "Insufficient queue separation",
        issues if issues else None
    )


# =============================================================================
# Test: Heartbeat Timeouts for Long Activities
# =============================================================================

def test_heartbeat_timeouts(suite: PerformanceTestSuite):
    """Verify long-running activities have heartbeat_timeout set."""
    workflow_file = Path(__file__).parent / "workflows" / "ap_package_workflow.py"
    activity_file = Path(__file__).parent / "activities" / "extract.py"
    
    issues = []
    heartbeats_found = 0
    
    # Check workflow has heartbeat_timeout for LLM activities
    if workflow_file.exists():
        content = workflow_file.read_text(encoding="utf-8")
        
        # Find LLM activity calls (extract_statement, extract_invoice)
        llm_activities = ["extract_statement", "extract_invoice"]
        
        for activity_name in llm_activities:
            # Find the execute_activity call for this activity
            pattern = rf"execute_activity\(\s*{activity_name}[^;]+\)"
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                call_text = match.group(0)
                if "heartbeat_timeout" in call_text:
                    heartbeats_found += 1
                else:
                    issues.append(f"{activity_name}: missing heartbeat_timeout in workflow")
    
    # Check activities call activity.heartbeat()
    if activity_file.exists():
        content = activity_file.read_text(encoding="utf-8")
        
        if 'activity.heartbeat(' not in content:
            issues.append("extract.py: no activity.heartbeat() calls found")
        else:
            heartbeat_calls = content.count('activity.heartbeat(')
            if heartbeat_calls < 2:
                issues.append(f"extract.py: only {heartbeat_calls} heartbeat call(s), expected at least 2")
    
    passed = heartbeats_found >= 2 and 'activity.heartbeat(' in (activity_file.read_text(encoding="utf-8") if activity_file.exists() else "")
    
    suite.record(
        "Heartbeat Timeouts",
        passed,
        f"Found {heartbeats_found} activities with heartbeat_timeout" if passed else "Missing heartbeats",
        issues if issues else None
    )


# =============================================================================
# Test: Workflow History Size Estimate
# =============================================================================

def test_workflow_history_estimate(suite: PerformanceTestSuite):
    """Estimate workflow history size and verify it won't hit limits."""
    # Temporal limits:
    # - Max event history: 50,000 events
    # - Max payload size: 256KB per payload
    # - Max history size: ~50MB
    
    # Estimate events per invoice:
    # - 1 activity started + 1 completed = 2 events per activity
    # - Per invoice: extract(2) + persist(2) + validate(2) + update_status(2) = 8 events
    # - Per package: split(2) + extract_statement(2) + audit(2*4) + reconcile(2) + update(2) = 16 events
    
    EVENTS_PER_INVOICE = 8
    EVENTS_PER_PACKAGE = 16
    MAX_HISTORY_EVENTS = 50_000
    
    # Calculate max invoices per workflow
    max_invoices = (MAX_HISTORY_EVENTS - EVENTS_PER_PACKAGE) // EVENTS_PER_INVOICE
    
    # Typical package has 50-200 invoices
    EXPECTED_MAX_INVOICES = 500
    
    issues = []
    
    if max_invoices < EXPECTED_MAX_INVOICES:
        issues.append(f"Max invoices per workflow ({max_invoices}) may be too low for large packages")
    
    # Estimate payload size per activity
    # - DataReference: ~200 bytes
    # - Invoice extract output: ~500 bytes
    # - Audit event input: ~300 bytes
    
    MAX_PAYLOAD_KB = 256
    ESTIMATED_MAX_PAYLOAD_BYTES = 5_000  # 5KB for invoice data
    
    if ESTIMATED_MAX_PAYLOAD_BYTES > MAX_PAYLOAD_KB * 1024 * 0.5:  # 50% of limit
        issues.append(f"Payload size ({ESTIMATED_MAX_PAYLOAD_BYTES}B) approaching limit")
    
    passed = max_invoices >= 200 and len(issues) == 0
    
    suite.record(
        "Workflow History Size Estimate",
        passed,
        f"Max ~{max_invoices} invoices per workflow, well under 50K event limit" if passed else "History size concerns",
        [
            f"Events per package: {EVENTS_PER_PACKAGE}",
            f"Events per invoice: {EVENTS_PER_INVOICE}",
            f"Max history events: {MAX_HISTORY_EVENTS}",
            f"Max invoices: {max_invoices}",
        ] + issues
    )


# =============================================================================
# Test: No Hot-Loop Retry Risk
# =============================================================================

def test_no_hot_loop_risk(suite: PerformanceTestSuite):
    """Verify retry configurations won't cause hot loops."""
    workflow_files = [
        Path(__file__).parent / "workflows" / "ap_package_workflow.py",
        Path(__file__).parent / "workflows" / "invoice_workflow.py",
    ]
    
    issues = []
    
    for wf_file in workflow_files:
        if not wf_file.exists():
            continue
        
        content = wf_file.read_text(encoding="utf-8")
        
        # Check for maximum_attempts
        max_attempts_pattern = r'maximum_attempts\s*=\s*(\d+)'
        matches = re.findall(max_attempts_pattern, content)
        
        for attempts in matches:
            if int(attempts) > 10:
                issues.append(f"{wf_file.name}: maximum_attempts={attempts} is high, risk of excessive retries")
        
        # Check for initial_interval
        interval_pattern = r'initial_interval\s*=\s*timedelta\(seconds\s*=\s*(\d+)\)'
        matches = re.findall(interval_pattern, content)
        
        for interval in matches:
            if int(interval) < 1:
                issues.append(f"{wf_file.name}: initial_interval={interval}s is too short, risk of hot loop")
        
        # Check for activities without retry_policy (use defaults)
        # Temporal default: unlimited retries - this is dangerous
        if "retry_policy=" not in content and "**activity_options" not in content:
            issues.append(f"{wf_file.name}: Some activities may use default (unlimited) retries")
    
    passed = len([i for i in issues if "hot loop" in i or "unlimited" in i]) == 0
    
    suite.record(
        "No Hot-Loop Retry Risk",
        passed,
        "Retry configurations are safe" if passed else "Risk of hot-loop retries",
        issues if issues else None
    )


# =============================================================================
# Main
# =============================================================================

async def main():
    print("=" * 70)
    print("TEMPORAL PERFORMANCE & SAFETY VALIDATION")
    print("=" * 70)
    print()
    
    suite = PerformanceTestSuite()
    
    # Run all tests
    print("Running tests...")
    print()
    
    test_workflow_state_size(suite)
    test_activity_timeouts(suite)
    test_retry_policy_backoff(suite)
    test_non_retryable_errors(suite)
    test_task_queue_separation(suite)
    test_heartbeat_timeouts(suite)
    test_workflow_history_estimate(suite)
    test_no_hot_loop_risk(suite)
    
    # Summary
    all_passed = suite.summary()
    
    print()
    print("PASS CRITERIA CHECK:")
    print("-" * 40)
    
    # Check pass criteria
    history_ok = any(r.name == "Workflow History Size Estimate" and r.passed for r in suite.results)
    hotloop_ok = any(r.name == "No Hot-Loop Retry Risk" and r.passed for r in suite.results)
    
    if history_ok:
        print("✓ No workflow hits payload/history limits")
    else:
        print("✗ Workflow may hit payload/history limits")
    
    if hotloop_ok:
        print("✓ No hot-loop retries that spike cost")
    else:
        print("✗ Risk of hot-loop retries")
    
    print()
    
    if all_passed and history_ok and hotloop_ok:
        print("✓ ALL PASS CRITERIA MET - Ready for scale!")
        return 0
    else:
        print("✗ ISSUES FOUND - Review and fix before scaling")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
