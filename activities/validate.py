"""Validation activities for AP automation pipeline.

Temporal activities that validate extracted invoices using B1/B2 checks.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from temporalio import activity

from models.canonical import InvoiceDocument
from models.refs import DataReference
from storage.artifacts import put_json, get_json


# =============================================================================
# Configuration
# =============================================================================

AMOUNT_TOLERANCE = Decimal("0.05")
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ValidateInvoiceInput:
    """Input for validate_invoice activity.
    
    Attributes:
        invoice_ref: Serialized DataReference to invoice JSON
        ap_package_id: Parent package ID for tracking
        invoice_number: Invoice number for logging
    """
    invoice_ref: dict
    ap_package_id: str
    invoice_number: str


@dataclass
class ValidateInvoiceOutput:
    """Output from validate_invoice activity.
    
    Attributes:
        validation_ref: DataReference to validation result JSON
        status: VALIDATED_PASS or VALIDATED_FAIL
        passed: True if all checks passed
        checks: List of check results
    """
    validation_ref: dict  # Serialized DataReference
    status: str  # VALIDATED_PASS or VALIDATED_FAIL
    passed: bool
    checks: List[dict]


# =============================================================================
# Utility Functions
# =============================================================================

def to_decimal(value) -> Optional[Decimal]:
    """Convert value to Decimal safely."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def amounts_match(
    a: Optional[Decimal],
    b: Optional[Decimal],
    tolerance: Decimal = AMOUNT_TOLERANCE,
) -> bool:
    """Check if two amounts match within tolerance."""
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


def get_invoice_total(invoice: InvoiceDocument) -> Optional[Decimal]:
    """Get invoice total with fallback chain.
    
    Priority:
    1. total_amount_due
    2. total_period_charges
    3. Sum of line items
    """
    if invoice.totals:
        if invoice.totals.total_amount_due is not None:
            return to_decimal(invoice.totals.total_amount_due)
        if invoice.totals.total_period_charges is not None:
            return to_decimal(invoice.totals.total_period_charges)
    
    # Fallback to sum of line items
    if invoice.line_items:
        total = Decimal("0")
        for item in invoice.line_items:
            if item.total is not None:
                total += to_decimal(item.total) or Decimal("0")
        if total > 0:
            return total
    
    return None


# =============================================================================
# Check Functions (B1, B2)
# =============================================================================

def check_b1_required_fields(invoice: InvoiceDocument, invoice_id: str) -> dict:
    """B1: Verify required fields are present.
    
    Required fields:
    - invoice_number
    - lot.lot_number  
    - statement_date or invoice_date
    - totals (any of: total_amount_due, total_period_charges, or line_items)
    - line_items[]
    
    Returns:
        dict with check_id, passed, severity, message, evidence
    """
    missing = []
    
    if not invoice.invoice_number:
        missing.append("invoice_number")
    if not invoice.lot or not invoice.lot.lot_number:
        missing.append("lot.lot_number")
    if invoice.statement_date is None and invoice.invoice_date is None:
        missing.append("statement_date or invoice_date")
    if get_invoice_total(invoice) is None:
        missing.append("totals (total_amount_due or total_period_charges or line_items)")
    if not invoice.line_items:
        missing.append("line_items[]")
    
    if missing:
        return {
            "check_id": "B1_REQUIRED_FIELDS",
            "severity": "BLOCK",
            "passed": False,
            "message": f"Invoice {invoice_id} missing required fields: {missing}",
            "evidence": {"invoice_number": invoice_id, "missing_fields": missing},
        }
    
    return {
        "check_id": "B1_REQUIRED_FIELDS",
        "severity": "INFO",
        "passed": True,
        "message": f"Invoice {invoice_id} has all required fields",
        "evidence": {"invoice_number": invoice_id},
    }


def check_b2_line_sum(invoice: InvoiceDocument, invoice_id: str) -> dict:
    """B2: Verify line item sum matches invoice total.
    
    Sums all line_item.total values and compares to invoice total.
    Uses tolerance of $0.05 for floating point and rounding differences.
    
    Returns:
        dict with check_id, passed, severity, message, evidence
    """
    if not invoice.line_items:
        return {
            "check_id": "B2_LINE_SUM",
            "severity": "WARN",
            "passed": False,
            "message": f"Invoice {invoice_id} has no line items to sum",
            "evidence": {"invoice_number": invoice_id},
        }
    
    line_sum = Decimal("0")
    for item in invoice.line_items:
        if item.total is not None:
            item_total = to_decimal(item.total)
            if item_total:
                line_sum += item_total
    
    invoice_total = get_invoice_total(invoice)
    
    if invoice_total is None:
        return {
            "check_id": "B2_LINE_SUM",
            "severity": "WARN",
            "passed": False,
            "message": f"Invoice {invoice_id} has no total for comparison",
            "evidence": {"invoice_number": invoice_id, "line_sum": str(line_sum)},
        }
    
    if amounts_match(line_sum, invoice_total):
        return {
            "check_id": "B2_LINE_SUM",
            "severity": "INFO",
            "passed": True,
            "message": f"Invoice {invoice_id} line sum matches total",
            "evidence": {
                "invoice_number": invoice_id,
                "line_sum": str(line_sum),
                "invoice_total": str(invoice_total),
                "difference": str(abs(line_sum - invoice_total)),
            },
        }
    else:
        return {
            "check_id": "B2_LINE_SUM",
            "severity": "BLOCK",
            "passed": False,
            "message": f"Invoice {invoice_id} line sum mismatch: {line_sum} vs {invoice_total}",
            "evidence": {
                "invoice_number": invoice_id,
                "line_sum": str(line_sum),
                "invoice_total": str(invoice_total),
                "difference": str(abs(line_sum - invoice_total)),
            },
        }


# =============================================================================
# Activity Definition
# =============================================================================

@activity.defn
async def validate_invoice(input: ValidateInvoiceInput) -> ValidateInvoiceOutput:
    """Validate an extracted invoice using B1 and B2 checks.
    
    B1: Required fields present
    B2: Line item sum matches invoice total
    
    Args:
        input: ValidateInvoiceInput with invoice_ref and metadata
        
    Returns:
        ValidateInvoiceOutput with validation results and artifact reference
        
    Note:
        This activity never raises exceptions for validation failures.
        Failures are recorded in the output, not thrown as errors.
    """
    activity.logger.info(f"Validating invoice {input.invoice_number} for package {input.ap_package_id}")
    
    # Load the invoice from its reference
    invoice_ref = DataReference.model_validate(input.invoice_ref)
    invoice_path = Path(invoice_ref.storage_uri)
    
    if not invoice_path.exists():
        activity.logger.error(f"Invoice file not found: {invoice_path}")
        # Return a failed validation result
        validation_result = {
            "invoice_number": input.invoice_number,
            "ap_package_id": input.ap_package_id,
            "status": "VALIDATED_FAIL",
            "passed": False,
            "checks": [{
                "check_id": "LOAD_ERROR",
                "severity": "BLOCK",
                "passed": False,
                "message": f"Invoice file not found: {invoice_path}",
                "evidence": {"storage_uri": str(invoice_path)},
            }],
            "validated_at": datetime.utcnow().isoformat(),
        }
    else:
        # Load and validate the invoice
        with open(invoice_path, "r", encoding="utf-8") as f:
            invoice_data = json.load(f)
        
        invoice = InvoiceDocument.model_validate(invoice_data)
        invoice_id = invoice.invoice_number or input.invoice_number
        
        # Run B1 and B2 checks
        b1_result = check_b1_required_fields(invoice, invoice_id)
        b2_result = check_b2_line_sum(invoice, invoice_id)
        
        checks = [b1_result, b2_result]
        all_passed = all(c["passed"] for c in checks)
        
        validation_result = {
            "invoice_number": invoice_id,
            "ap_package_id": input.ap_package_id,
            "status": "VALIDATED_PASS" if all_passed else "VALIDATED_FAIL",
            "passed": all_passed,
            "checks": checks,
            "validated_at": datetime.utcnow().isoformat(),
        }
    
    # Persist validation result as artifact
    # Store in artifacts/{feedlot}/validations/{invoice_number}_validation.json
    # Determine feedlot from invoice path
    feedlot_key = "unknown"
    if "bovina" in str(invoice_path).lower():
        feedlot_key = "bovina"
    elif "mesquite" in str(invoice_path).lower():
        feedlot_key = "mesquite"
    
    validation_dir = ARTIFACTS_DIR / feedlot_key / "validations"
    validation_dir.mkdir(parents=True, exist_ok=True)
    
    safe_name = "".join(ch for ch in str(input.invoice_number) if ch.isalnum() or ch in ("-", "_"))
    validation_path = validation_dir / f"{safe_name}_validation.json"
    
    with open(validation_path, "w", encoding="utf-8") as f:
        json.dump(validation_result, f, indent=2)
    
    # Create DataReference for the validation artifact
    content = validation_path.read_bytes()
    validation_ref = DataReference(
        storage_uri=str(validation_path),
        content_hash=hashlib.sha256(content).hexdigest(),
        content_type="application/json",
        size_bytes=len(content),
    )
    
    status = validation_result["status"]
    passed = validation_result["passed"]
    
    if passed:
        activity.logger.info(f"✓ Invoice {input.invoice_number} validated: {status}")
    else:
        failed_checks = [c["check_id"] for c in checks if not c.get("passed", True)]
        activity.logger.warning(f"✗ Invoice {input.invoice_number} validation failed: {failed_checks}")
    
    return ValidateInvoiceOutput(
        validation_ref=validation_ref.model_dump(),
        status=status,
        passed=passed,
        checks=validation_result["checks"],
    )
