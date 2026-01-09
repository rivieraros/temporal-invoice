"""Reconciliation activities for AP automation pipeline.

Temporal activities that reconcile statement against invoices using A1/A5/A6 checks.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from temporalio import activity

from models.canonical import StatementDocument, InvoiceDocument
from models.refs import DataReference
from reconciliation.engine import reconcile


# =============================================================================
# Configuration
# =============================================================================

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ReconcilePackageInput:
    """Input for reconcile_package activity.
    
    Attributes:
        statement_ref: Serialized DataReference to statement JSON
        invoice_refs: List of serialized DataReferences to invoice JSONs
        feedlot_type: BOVINA or MESQUITE
        ap_package_id: Package ID for tracking
    """
    statement_ref: dict
    invoice_refs: List[dict]
    feedlot_type: str
    ap_package_id: str


@dataclass
class ReconcilePackageOutput:
    """Output from reconcile_package activity.
    
    Attributes:
        reconciliation_ref: DataReference to reconciliation report JSON
        status: RECONCILED_PASS, RECONCILED_WARN, or RECONCILED_FAIL
        passed_checks: Number of checks that passed
        total_checks: Total number of checks run
        blocking_issues: Number of blocking issues
        warnings: Number of warnings
    """
    reconciliation_ref: dict  # Serialized DataReference
    status: str
    passed_checks: int
    total_checks: int
    blocking_issues: int
    warnings: int


# =============================================================================
# Activity Definition
# =============================================================================

@activity.defn
async def reconcile_package(input: ReconcilePackageInput) -> ReconcilePackageOutput:
    """Reconcile a package's statement against its invoices.
    
    Runs reconciliation checks including:
    - A1: Package completeness (all referenced invoices exist)
    - A5: Invoice amount reconciliation vs statement
    - A6: Package total check
    - Plus B1/B2/D1 and other checks from the engine
    
    Args:
        input: ReconcilePackageInput with statement and invoice references
        
    Returns:
        ReconcilePackageOutput with reconciliation results and artifact reference
    """
    activity.logger.info(f"Reconciling package {input.ap_package_id} ({input.feedlot_type})")
    
    # Load statement
    statement_ref = DataReference.model_validate(input.statement_ref)
    statement_path = Path(statement_ref.storage_uri)
    
    if not statement_path.exists():
        activity.logger.error(f"Statement file not found: {statement_path}")
        raise FileNotFoundError(f"Statement file not found: {statement_path}")
    
    with open(statement_path, "r", encoding="utf-8") as f:
        statement_data = json.load(f)
    statement = StatementDocument.model_validate(statement_data)
    
    activity.logger.info(f"Loaded statement (feedlot: {statement.feedlot.name if statement.feedlot else 'unknown'})")
    
    # Load invoices
    invoices = []
    for inv_ref_dict in input.invoice_refs:
        inv_ref = DataReference.model_validate(inv_ref_dict)
        inv_path = Path(inv_ref.storage_uri)
        
        if not inv_path.exists():
            activity.logger.warning(f"Invoice file not found: {inv_path}")
            continue
        
        with open(inv_path, "r", encoding="utf-8") as f:
            inv_data = json.load(f)
        invoice = InvoiceDocument.model_validate(inv_data)
        invoices.append(invoice)
    
    activity.logger.info(f"Loaded {len(invoices)} invoices")
    
    # Run reconciliation
    feedlot_key = input.feedlot_type.lower()
    report = reconcile(statement, invoices, feedlot_key=feedlot_key)
    
    # Map engine status to workflow status
    if report.status == "FAIL":
        workflow_status = "RECONCILED_FAIL"
    elif report.status == "WARN":
        workflow_status = "RECONCILED_WARN"
    else:
        workflow_status = "RECONCILED_PASS"
    
    # Persist reconciliation report
    reconciliation_dir = ARTIFACTS_DIR / feedlot_key
    reconciliation_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = reconciliation_dir / "_reconciliation_report.json"
    
    report_data = {
        "feedlot_key": report.feedlot_key,
        "status": report.status,
        "workflow_status": workflow_status,
        "ap_package_id": input.ap_package_id,
        "checks": report.checks,
        "summary": report.summary,
        "metrics": report.metrics,
        "reconciled_at": datetime.utcnow().isoformat(),
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    
    # Create DataReference for the report
    content = report_path.read_bytes()
    reconciliation_ref = DataReference(
        storage_uri=str(report_path),
        content_hash=hashlib.sha256(content).hexdigest(),
        content_type="application/json",
        size_bytes=len(content),
    )
    
    # Log summary
    passed_checks = report.summary.get("passed_checks", 0)
    total_checks = report.summary.get("total_checks", 0)
    blocking = report.summary.get("blocking_issues", 0)
    warnings = report.summary.get("warnings", 0)
    
    if workflow_status == "RECONCILED_PASS":
        activity.logger.info(f"✓ Package {input.ap_package_id} reconciliation: PASS ({passed_checks}/{total_checks} checks)")
    elif workflow_status == "RECONCILED_WARN":
        activity.logger.warning(f"⚠ Package {input.ap_package_id} reconciliation: WARN ({warnings} warnings)")
    else:
        activity.logger.error(f"✗ Package {input.ap_package_id} reconciliation: FAIL ({blocking} blocking issues)")
    
    return ReconcilePackageOutput(
        reconciliation_ref=reconciliation_ref.model_dump(),
        status=workflow_status,
        passed_checks=passed_checks,
        total_checks=total_checks,
        blocking_issues=blocking,
        warnings=warnings,
    )
