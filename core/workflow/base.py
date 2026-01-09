"""Base workflow types and utilities."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkflowStatus(str, Enum):
    """Workflow status values."""
    STARTED = "STARTED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    RECONCILING = "RECONCILING"
    RECONCILED_PASS = "RECONCILED_PASS"
    RECONCILED_WARN = "RECONCILED_WARN"
    RECONCILED_FAIL = "RECONCILED_FAIL"
    MAPPING = "MAPPING"
    MAPPED = "MAPPED"
    POSTING = "POSTING"
    POSTED = "POSTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class WorkflowResult:
    """Standard workflow result structure."""
    workflow_id: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Core results
    ap_package_id: Optional[str] = None
    feedlot_type: Optional[str] = None
    
    # Extraction results
    statement_extracted: bool = False
    invoices_extracted: int = 0
    invoice_numbers: List[str] = field(default_factory=list)
    
    # Validation results
    invoices_validated_pass: int = 0
    invoices_validated_fail: int = 0
    
    # Reconciliation results
    reconciliation_status: Optional[str] = None
    reconciliation_checks_passed: int = 0
    reconciliation_checks_total: int = 0
    reconciliation_warnings: int = 0
    reconciliation_blocking: int = 0
    
    # Mapping results
    mapping_status: Optional[str] = None
    mappings_applied: int = 0
    mappings_missing: int = 0
    
    # ERP posting results
    posting_status: Optional[str] = None
    erp_document_id: Optional[str] = None
    erp_document_number: Optional[str] = None
    
    # Error information
    error_message: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    
    # Artifacts
    artifact_refs: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "ap_package_id": self.ap_package_id,
            "feedlot_type": self.feedlot_type,
            "extraction": {
                "statement_extracted": self.statement_extracted,
                "invoices_extracted": self.invoices_extracted,
                "invoice_numbers": self.invoice_numbers,
            },
            "validation": {
                "passed": self.invoices_validated_pass,
                "failed": self.invoices_validated_fail,
            },
            "reconciliation": {
                "status": self.reconciliation_status,
                "checks_passed": self.reconciliation_checks_passed,
                "checks_total": self.reconciliation_checks_total,
                "warnings": self.reconciliation_warnings,
                "blocking": self.reconciliation_blocking,
            },
            "mapping": {
                "status": self.mapping_status,
                "applied": self.mappings_applied,
                "missing": self.mappings_missing,
            },
            "posting": {
                "status": self.posting_status,
                "erp_document_id": self.erp_document_id,
                "erp_document_number": self.erp_document_number,
            },
            "error": {
                "message": self.error_message,
                "details": self.error_details,
            } if self.error_message else None,
            "artifacts": self.artifact_refs,
        }
