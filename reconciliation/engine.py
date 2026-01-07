"""Reconciliation engine for AP invoice and statement validation.

Exposes high-level function:
- reconcile(statement, invoices) -> ReconciliationReport
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from models.canonical import StatementDocument, InvoiceDocument
from models.refs import ReconciliationReport, DataReference
from storage.artifacts import put_json


# =============================================================================
# Known Missing Invoices Registry
# =============================================================================

KNOWN_MISSING_FROM_SOURCE_PDF = {
    "bovina": {
        "13304": "Invoice for lot 20-3927 - listed on statement but invoice page not in PDF",
    },
    "mesquite": {},
}


# =============================================================================
# Configuration & Data Structures
# =============================================================================

AMOUNT_TOLERANCE = Decimal("0.05")


class Severity(str, Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"
    INFO = "INFO"


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CheckResult:
    """Result of a single reconciliation check."""
    
    def __init__(
        self,
        check_id: str,
        severity: Severity,
        passed: bool,
        message: str,
        evidence: Optional[Dict] = None,
    ):
        self.check_id = check_id
        self.severity = severity
        self.passed = passed
        self.message = message
        self.evidence = evidence or {}
    
    def to_dict(self) -> Dict:
        return {
            "check_id": self.check_id,
            "severity": self.severity.value,
            "passed": self.passed,
            "message": self.message,
            "evidence": self.evidence,
        }


# =============================================================================
# Utility Functions
# =============================================================================

def to_decimal(value) -> Optional[Decimal]:
    """Convert value to Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


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
                total += to_decimal(item.total)
        if total > 0:
            return total
    
    return None


# =============================================================================
# Individual Check Functions
# =============================================================================

def check_b1_invoice_schema(invoice: InvoiceDocument, invoice_id: str) -> CheckResult:
    """B1: Verify required fields are present."""
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
        return CheckResult(
            check_id="B1_REQUIRED_FIELDS",
            severity=Severity.BLOCK,
            passed=False,
            message=f"Invoice {invoice_id} missing required fields: {missing}",
            evidence={"invoice_number": invoice_id, "missing_fields": missing},
        )
    
    return CheckResult(
        check_id="B1_REQUIRED_FIELDS",
        severity=Severity.INFO,
        passed=True,
        message=f"Invoice {invoice_id} has all required fields",
        evidence={"invoice_number": invoice_id},
    )


def check_b2_line_sum(invoice: InvoiceDocument, invoice_id: str) -> CheckResult:
    """B2: Verify line item sum matches invoice total."""
    if not invoice.line_items:
        return CheckResult(
            check_id="B2_LINE_SUM",
            severity=Severity.WARN,
            passed=False,
            message=f"Invoice {invoice_id} has no line items to sum",
            evidence={"invoice_number": invoice_id},
        )
    
    line_sum = Decimal("0")
    for item in invoice.line_items:
        if item.total is not None:
            line_sum += to_decimal(item.total)
    
    invoice_total = get_invoice_total(invoice)
    
    if invoice_total is None:
        return CheckResult(
            check_id="B2_LINE_SUM",
            severity=Severity.WARN,
            passed=False,
            message=f"Invoice {invoice_id} has no total for comparison",
            evidence={"invoice_number": invoice_id, "line_sum": str(line_sum)},
        )
    
    if amounts_match(line_sum, invoice_total):
        return CheckResult(
            check_id="B2_LINE_SUM",
            severity=Severity.INFO,
            passed=True,
            message=f"Invoice {invoice_id} line sum matches total",
            evidence={
                "invoice_number": invoice_id,
                "line_sum": str(line_sum),
                "invoice_total": str(invoice_total),
                "difference": str(abs(line_sum - invoice_total)),
            },
        )
    else:
        return CheckResult(
            check_id="B2_LINE_SUM",
            severity=Severity.BLOCK,
            passed=False,
            message=f"Invoice {invoice_id} line sum mismatch: {line_sum} vs {invoice_total}",
            evidence={
                "invoice_number": invoice_id,
                "line_sum": str(line_sum),
                "invoice_total": str(invoice_total),
                "difference": str(abs(line_sum - invoice_total)),
            },
        )


def check_d1_duplicates(invoices: List[InvoiceDocument], feedlot_name: str) -> List[CheckResult]:
    """D1: Detect duplicate invoices."""
    results = []
    seen: Dict[Tuple, str] = {}
    
    for inv in invoices:
        owner_num = inv.owner.owner_number if inv.owner else None
        inv_num = inv.invoice_number
        stmt_date = str(inv.statement_date) if inv.statement_date else str(inv.invoice_date)
        
        key = (feedlot_name, owner_num, inv_num, stmt_date)
        
        if key in seen:
            results.append(CheckResult(
                check_id="D1_DUPLICATE_INVOICE",
                severity=Severity.BLOCK,
                passed=False,
                message=f"Duplicate invoice detected: {inv_num}",
                evidence={
                    "invoice_number": inv_num,
                    "owner_number": owner_num,
                    "statement_date": stmt_date,
                    "duplicate_of": seen[key],
                },
            ))
        else:
            seen[key] = inv_num
    
    if not results:
        results.append(CheckResult(
            check_id="D1_DUPLICATE_INVOICE",
            severity=Severity.INFO,
            passed=True,
            message="No duplicate invoices detected",
            evidence={"invoice_count": len(invoices)},
        ))
    
    return results


def check_a1_package_completeness(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
    feedlot_key: str = "",
) -> Tuple[CheckResult, Set[str], Set[str]]:
    """A1: Verify all statement-referenced invoices exist."""
    
    expected_invoice_nums: Set[str] = set()
    for ref in statement.lot_references:
        if ref.invoice_number:
            expected_invoice_nums.add(ref.invoice_number)
    
    for txn in statement.transactions:
        if txn.ref_number and txn.type and "inv" in txn.type.lower():
            expected_invoice_nums.add(txn.ref_number)
    
    extracted_invoice_nums: Set[str] = set()
    for inv in invoices:
        if inv.invoice_number:
            extracted_invoice_nums.add(inv.invoice_number)
    
    missing = expected_invoice_nums - extracted_invoice_nums
    
    # Separate into extraction failures vs source PDF issues
    known_missing = KNOWN_MISSING_FROM_SOURCE_PDF.get(feedlot_key.lower(), {})
    source_missing = missing & set(known_missing.keys())
    extraction_missing = missing - source_missing
    
    if extraction_missing:
        return (
            CheckResult(
                check_id="A1_PACKAGE_COMPLETENESS",
                severity=Severity.BLOCK,
                passed=False,
                message=f"Missing {len(extraction_missing)} invoices (extraction failure)",
                evidence={
                    "missing_invoices": list(extraction_missing),
                    "source_pdf_missing": list(source_missing),
                    "expected_count": len(expected_invoice_nums),
                    "extracted_count": len(extracted_invoice_nums),
                },
            ),
            expected_invoice_nums,
            extracted_invoice_nums,
        )
    
    if source_missing:
        return (
            CheckResult(
                check_id="A1_PACKAGE_COMPLETENESS",
                severity=Severity.WARN,
                passed=True,
                message=f"{len(source_missing)} invoices missing from source PDF (not extraction failure)",
                evidence={
                    "source_pdf_missing": list(source_missing),
                    "source_pdf_missing_reasons": {k: known_missing[k] for k in source_missing},
                    "expected_count": len(expected_invoice_nums),
                    "extracted_count": len(extracted_invoice_nums),
                },
            ),
            expected_invoice_nums,
            extracted_invoice_nums,
        )
    
    return (
        CheckResult(
            check_id="A1_PACKAGE_COMPLETENESS",
            severity=Severity.INFO,
            passed=True,
            message=f"All {len(expected_invoice_nums)} referenced invoices found",
            evidence={
                "expected_count": len(expected_invoice_nums),
                "extracted_count": len(extracted_invoice_nums),
            },
        ),
        expected_invoice_nums,
        extracted_invoice_nums,
    )


def check_a2_extra_invoices(
    expected_invoice_nums: Set[str],
    extracted_invoice_nums: Set[str],
) -> CheckResult:
    """A2: Detect invoices not referenced on statement."""
    extra = extracted_invoice_nums - expected_invoice_nums
    
    if extra:
        return CheckResult(
            check_id="A2_EXTRA_INVOICES",
            severity=Severity.WARN,
            passed=True,
            message=f"{len(extra)} invoices not referenced on statement",
            evidence={"extra_invoices": list(extra)},
        )
    
    return CheckResult(
        check_id="A2_EXTRA_INVOICES",
        severity=Severity.INFO,
        passed=True,
        message="No extra invoices found",
        evidence={},
    )


def check_a3_period_consistency(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
) -> CheckResult:
    """A3: Verify invoice dates align with statement period."""
    mismatches = []
    
    stmt_start = statement.period_start
    stmt_end = statement.period_end
    
    for inv in invoices:
        inv_date = inv.statement_date or inv.invoice_date
        if inv_date is None:
            continue
        
        if stmt_start and stmt_end:
            if not (stmt_start <= inv_date <= stmt_end):
                mismatches.append({
                    "invoice_number": inv.invoice_number,
                    "invoice_date": str(inv_date),
                    "period_start": str(stmt_start),
                    "period_end": str(stmt_end),
                })
    
    if mismatches:
        return CheckResult(
            check_id="A3_PERIOD_CONSISTENCY",
            severity=Severity.WARN,
            passed=False,
            message=f"{len(mismatches)} invoices outside statement period",
            evidence={"mismatches": mismatches},
        )
    
    return CheckResult(
        check_id="A3_PERIOD_CONSISTENCY",
        severity=Severity.INFO,
        passed=True,
        message="All invoices within statement period",
        evidence={
            "period_start": str(stmt_start) if stmt_start else None,
            "period_end": str(stmt_end) if stmt_end else None,
        },
    )


def check_a4_feedlot_owner_consistency(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
) -> CheckResult:
    """A4: Verify all invoices match statement feedlot and owner."""
    mismatches = []
    
    stmt_feedlot = statement.feedlot.name if statement.feedlot else None
    stmt_owner = statement.owner.owner_number if statement.owner else None
    
    for inv in invoices:
        inv_feedlot = inv.feedlot.name if inv.feedlot else None
        inv_owner = inv.owner.owner_number if inv.owner else None
        
        feedlot_match = (stmt_feedlot is None or inv_feedlot is None or 
                         stmt_feedlot.lower() in inv_feedlot.lower() or 
                         inv_feedlot.lower() in stmt_feedlot.lower())
        owner_match = (stmt_owner is None or inv_owner is None or stmt_owner == inv_owner)
        
        if not feedlot_match or not owner_match:
            mismatches.append({
                "invoice_number": inv.invoice_number,
                "invoice_feedlot": inv_feedlot,
                "invoice_owner": inv_owner,
                "statement_feedlot": stmt_feedlot,
                "statement_owner": stmt_owner,
            })
    
    if mismatches:
        return CheckResult(
            check_id="A4_FEEDLOT_OWNER_CONSISTENCY",
            severity=Severity.BLOCK,
            passed=False,
            message=f"{len(mismatches)} invoices with feedlot/owner mismatch",
            evidence={"mismatches": mismatches},
        )
    
    return CheckResult(
        check_id="A4_FEEDLOT_OWNER_CONSISTENCY",
        severity=Severity.INFO,
        passed=True,
        message="All invoices match statement feedlot and owner",
        evidence={"feedlot": stmt_feedlot, "owner_number": stmt_owner},
    )


def check_a5_invoice_amount_reconciliation(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
) -> List[CheckResult]:
    """A5: Compare invoice totals to statement charges (trust invoice)."""
    results = []
    
    stmt_amounts: Dict[str, Decimal] = {}
    stmt_lot_amounts: Dict[str, Decimal] = {}
    
    for ref in statement.lot_references:
        if ref.invoice_number and ref.statement_charge is not None:
            stmt_amounts[ref.invoice_number] = to_decimal(ref.statement_charge)
        if ref.lot_number and ref.statement_charge is not None:
            stmt_lot_amounts[ref.lot_number] = to_decimal(ref.statement_charge)
    
    for txn in statement.transactions:
        if txn.ref_number and txn.charge is not None:
            stmt_amounts[txn.ref_number] = to_decimal(txn.charge)
    
    matched = 0
    for inv in invoices:
        inv_num = inv.invoice_number
        inv_total = get_invoice_total(inv)
        
        if inv_total is None:
            results.append(CheckResult(
                check_id="A5_INVOICE_AMOUNT_RECONCILIATION",
                severity=Severity.WARN,
                passed=False,
                message=f"Invoice {inv_num} has no extractable total",
                evidence={"invoice_number": inv_num},
            ))
            continue
        
        # Try to find statement amount by invoice number or lot
        stmt_amount = stmt_amounts.get(inv_num)
        if stmt_amount is None and inv.lot and inv.lot.lot_number:
            stmt_amount = stmt_lot_amounts.get(inv.lot.lot_number)
        
        if stmt_amount is None:
            results.append(CheckResult(
                check_id="A5_INVOICE_AMOUNT_RECONCILIATION",
                severity=Severity.INFO,
                passed=True,
                message=f"Invoice {inv_num} not found on statement (no comparison)",
                evidence={"invoice_number": inv_num, "invoice_total": str(inv_total)},
            ))
            continue
        
        if amounts_match(inv_total, stmt_amount):
            matched += 1
            results.append(CheckResult(
                check_id="A5_INVOICE_AMOUNT_RECONCILIATION",
                severity=Severity.INFO,
                passed=True,
                message=f"Invoice {inv_num} amount matches statement",
                evidence={
                    "invoice_number": inv_num,
                    "invoice_total": str(inv_total),
                    "statement_amount": str(stmt_amount),
                },
            ))
        else:
            results.append(CheckResult(
                check_id="A5_INVOICE_AMOUNT_RECONCILIATION",
                severity=Severity.WARN,
                passed=True,  # Trust invoice, just warn about difference
                message=f"Invoice {inv_num} differs from statement (trusting invoice): {inv_total} vs {stmt_amount}",
                evidence={
                    "invoice_number": inv_num,
                    "invoice_total": str(inv_total),
                    "statement_amount": str(stmt_amount),
                    "difference": str(abs(inv_total - stmt_amount)),
                    "trusted_source": "invoice",
                },
            ))
    
    if not results:
        results.append(CheckResult(
            check_id="A5_INVOICE_AMOUNT_RECONCILIATION",
            severity=Severity.INFO,
            passed=True,
            message="All invoices amount verified",
            evidence={"matched_count": matched, "total_count": len(invoices)},
        ))
    
    return results


def check_a6_package_total_bovina(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
) -> CheckResult:
    """A6 for Bovina: Verify package totals."""
    invoice_sum = Decimal("0")
    for inv in invoices:
        inv_total = get_invoice_total(inv)
        if inv_total is not None:
            invoice_sum += inv_total
    
    stmt_total = to_decimal(statement.total_balance)
    
    if stmt_total is None:
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_BOVINA",
            severity=Severity.WARN,
            passed=False,
            message="Statement has no total_balance for comparison",
            evidence={"invoice_sum": str(invoice_sum)},
        )
    
    if amounts_match(invoice_sum, stmt_total, tolerance=Decimal("1.00")):
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_BOVINA",
            severity=Severity.INFO,
            passed=True,
            message="Package totals match",
            evidence={
                "invoice_sum": str(invoice_sum),
                "statement_total": str(stmt_total),
                "difference": str(abs(invoice_sum - stmt_total)),
            },
        )
    else:
        diff = abs(invoice_sum - stmt_total)
        diff_pct = (diff / stmt_total * 100) if stmt_total != 0 else 0
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_BOVINA",
            severity=Severity.WARN,
            passed=True,  # Trust invoice sum, just warn
            message=f"Package total differs (trusting invoices): invoices={invoice_sum} vs statement={stmt_total} (diff={diff}, {diff_pct:.2f}%)",
            evidence={
                "invoice_sum": str(invoice_sum),
                "statement_total": str(stmt_total),
                "difference": str(diff),
                "difference_pct": f"{diff_pct:.2f}%",
                "trusted_source": "invoices",
            },
        )


def check_a6_package_total_mesquite(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
) -> CheckResult:
    """A6 for Mesquite: Verify package totals."""
    invoice_sum = Decimal("0")
    for inv in invoices:
        inv_total = get_invoice_total(inv)
        if inv_total is not None:
            invoice_sum += inv_total
    
    stmt_total = to_decimal(statement.total_balance)
    
    if stmt_total is None:
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_MESQUITE",
            severity=Severity.WARN,
            passed=False,
            message="Statement has no total_balance for comparison",
            evidence={"invoice_sum": str(invoice_sum)},
        )
    
    if amounts_match(invoice_sum, stmt_total, tolerance=Decimal("1.00")):
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_MESQUITE",
            severity=Severity.INFO,
            passed=True,
            message="Package totals match",
            evidence={
                "invoice_sum": str(invoice_sum),
                "statement_total": str(stmt_total),
                "difference": str(abs(invoice_sum - stmt_total)),
            },
        )
    else:
        diff = abs(invoice_sum - stmt_total)
        diff_pct = (diff / stmt_total * 100) if stmt_total != 0 else 0
        return CheckResult(
            check_id="A6_PACKAGE_TOTAL_MESQUITE",
            severity=Severity.WARN,
            passed=True,  # Trust invoice sum, just warn
            message=f"Package total differs (trusting invoices): invoices={invoice_sum} vs statement={stmt_total} (diff={diff}, {diff_pct:.2f}%)",
            evidence={
                "invoice_sum": str(invoice_sum),
                "statement_total": str(stmt_total),
                "difference": str(diff),
                "difference_pct": f"{diff_pct:.2f}%",
                "trusted_source": "invoices",
            },
        )


def check_a7_lot_completeness(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
    feedlot_key: str = "",
) -> CheckResult:
    """A7: Ensure every lot with an invoice has an extracted invoice."""
    stmt_lots: Set[str] = set()
    lot_to_invoice: Dict[str, str] = {}
    
    for ref in statement.lot_references:
        if ref.lot_number:
            stmt_lots.add(ref.lot_number)
            if ref.invoice_number:
                lot_to_invoice[ref.lot_number] = ref.invoice_number
    
    inv_lots: Set[str] = set()
    for inv in invoices:
        if inv.lot and inv.lot.lot_number:
            inv_lots.add(inv.lot.lot_number)
    
    missing_lots = stmt_lots - inv_lots
    
    # Separate into extraction failures vs source PDF issues
    known_missing = KNOWN_MISSING_FROM_SOURCE_PDF.get(feedlot_key.lower(), {})
    source_missing_lots = set()
    extraction_missing_lots = set()
    
    for lot in missing_lots:
        inv_num = lot_to_invoice.get(lot)
        if inv_num and inv_num in known_missing:
            source_missing_lots.add(lot)
        else:
            extraction_missing_lots.add(lot)
    
    if extraction_missing_lots:
        return CheckResult(
            check_id="A7_LOT_COMPLETENESS",
            severity=Severity.BLOCK,
            passed=False,
            message=f"{len(extraction_missing_lots)} lots on statement without invoices (extraction failure)",
            evidence={
                "missing_lots": list(extraction_missing_lots),
                "source_pdf_missing_lots": list(source_missing_lots),
                "statement_lots": len(stmt_lots),
                "invoice_lots": len(inv_lots),
            },
        )
    
    if source_missing_lots:
        return CheckResult(
            check_id="A7_LOT_COMPLETENESS",
            severity=Severity.WARN,
            passed=True,
            message=f"{len(source_missing_lots)} lots missing from source PDF (not extraction failure)",
            evidence={
                "source_pdf_missing_lots": list(source_missing_lots),
                "statement_lots": len(stmt_lots),
                "invoice_lots": len(inv_lots),
            },
        )
    
    return CheckResult(
        check_id="A7_LOT_COMPLETENESS",
        severity=Severity.INFO,
        passed=True,
        message=f"All {len(stmt_lots)} lots have corresponding invoices",
        evidence={
            "statement_lots": len(stmt_lots),
            "invoice_lots": len(inv_lots),
        },
    )


# =============================================================================
# Main Reconciliation Engine
# =============================================================================

def reconcile(
    statement: StatementDocument,
    invoices: List[InvoiceDocument],
    feedlot_key: str = "",
) -> ReconciliationReport:
    """Run all reconciliation checks and return report.
    
    Args:
        statement: Extracted statement document
        invoices: List of extracted invoice documents
        feedlot_key: Identifier for feedlot (e.g., "bovina", "mesquite")
        
    Returns:
        ReconciliationReport with status, checks, and metrics
    """
    feedlot_name = statement.feedlot.name if statement.feedlot else feedlot_key
    checks = []
    
    # =========================================================================
    # Invoice-level checks (B1, B2)
    # =========================================================================
    for inv in invoices:
        inv_id = inv.invoice_number or "unknown"
        checks.append(check_b1_invoice_schema(inv, inv_id))
        checks.append(check_b2_line_sum(inv, inv_id))
    
    # =========================================================================
    # Duplicate detection (D1)
    # =========================================================================
    checks.extend(check_d1_duplicates(invoices, feedlot_name))
    
    # =========================================================================
    # Package-level checks (A1-A7)
    # =========================================================================
    a1_result, expected_nums, extracted_nums = check_a1_package_completeness(
        statement, invoices, feedlot_key
    )
    checks.append(a1_result)
    
    checks.append(check_a2_extra_invoices(expected_nums, extracted_nums))
    checks.append(check_a3_period_consistency(statement, invoices))
    checks.append(check_a4_feedlot_owner_consistency(statement, invoices))
    checks.extend(check_a5_invoice_amount_reconciliation(statement, invoices))
    
    if feedlot_key.lower() == "bovina":
        a6_result = check_a6_package_total_bovina(statement, invoices)
    else:
        a6_result = check_a6_package_total_mesquite(statement, invoices)
    checks.append(a6_result)
    
    checks.append(check_a7_lot_completeness(statement, invoices, feedlot_key))
    
    # =========================================================================
    # Calculate metrics
    # =========================================================================
    total_invoice_sum = Decimal("0")
    for inv in invoices:
        inv_total = get_invoice_total(inv)
        if inv_total is not None:
            total_invoice_sum += inv_total
    
    stmt_total = to_decimal(statement.total_balance)
    
    # =========================================================================
    # Determine overall status
    # =========================================================================
    has_blocks = any(c.get("severity") == "BLOCK" for c in [ch.to_dict() for ch in checks])
    has_warns = any(c.get("severity") == "WARN" for c in [ch.to_dict() for ch in checks])
    
    if has_blocks:
        overall_status = CheckStatus.FAIL.value
    elif has_warns:
        overall_status = CheckStatus.WARN.value
    else:
        overall_status = CheckStatus.PASS.value
    
    # =========================================================================
    # Build report
    # =========================================================================
    report = ReconciliationReport(
        feedlot_key=feedlot_key,
        status=overall_status,
        checks=[c.to_dict() for c in checks],
        summary={
            "feedlot_name": feedlot_name,
            "status": overall_status,
            "total_checks": len(checks),
            "passed_checks": sum(1 for c in checks if c.passed),
            "blocking_issues": sum(1 for c in checks if not c.passed and c.severity == Severity.BLOCK),
            "warnings": sum(1 for c in checks if not c.passed and c.severity == Severity.WARN),
        },
        metrics={
            "matched_invoices": len(expected_nums & extracted_nums),
            "expected_invoices": len(expected_nums),
            "extracted_invoices": len(extracted_nums),
            "total_invoice_sum": str(total_invoice_sum),
            "statement_total": str(stmt_total) if stmt_total else None,
        },
    )
    
    return report
