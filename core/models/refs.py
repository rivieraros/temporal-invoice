"""Data reference and audit models for artifact storage and tracking."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class DataReference(BaseModel):
    """Reference to a stored artifact with metadata for retrieval and verification.
    
    Attributes:
        storage_uri: Absolute file path to the artifact
        content_hash: SHA256 hash of the content for integrity verification
        content_type: MIME type (e.g., "application/json", "image/png")
        size_bytes: Size of the artifact in bytes
        stored_at: Timestamp when the artifact was stored
    """
    storage_uri: str = Field(..., description="Absolute file path to the artifact")
    content_hash: str = Field(..., description="SHA256 hash of content")
    content_type: str = Field(default="application/json", description="MIME type")
    size_bytes: int = Field(..., description="Size in bytes")
    stored_at: datetime = Field(default_factory=datetime.utcnow, description="Storage timestamp")


class ExtractedPackageRefs(BaseModel):
    """References to all extracted artifacts from a single feedlot package.
    
    Attributes:
        feedlot_key: Identifier for the feedlot (e.g., "bovina", "mesquite")
        statement_ref: Reference to the extracted statement JSON
        invoice_refs: List of references to extracted invoice JSONs
        extraction_metadata: Metadata about the extraction run
    """
    feedlot_key: str = Field(..., description="Feedlot identifier")
    statement_ref: Optional[DataReference] = Field(None, description="Statement artifact reference")
    invoice_refs: list[DataReference] = Field(default_factory=list, description="Invoice artifact references")
    extraction_metadata: dict = Field(default_factory=dict, description="Extraction run metadata")


class ReconciliationReport(BaseModel):
    """Reconciliation results for a feedlot package.
    
    Attributes:
        feedlot_key: Identifier for the feedlot (e.g., "bovina", "mesquite")
        status: Overall status ("PASS", "WARN", "FAIL")
        checks: List of individual check results
        summary: Human-readable summary
        metrics: Key metrics (matched_invoices, total_sum, etc.)
        report_ref: Reference to full report JSON if saved
    """
    feedlot_key: str = Field(..., description="Feedlot identifier")
    status: str = Field(..., description="Overall status: PASS, WARN, or FAIL")
    checks: list[dict] = Field(default_factory=list, description="Individual check results")
    summary: dict = Field(default_factory=dict, description="Summary information")
    metrics: dict = Field(default_factory=dict, description="Key metrics")
    report_ref: Optional[DataReference] = Field(None, description="Report artifact reference")


# =============================================================================
# Audit Event Models
# =============================================================================

class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    BLOCK = "BLOCK"


class AuditEvent(BaseModel):
    """An audit event for tracking system actions.
    
    Provides complete traceability of all actions taken by the system,
    from extraction through ERP posting.
    """
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    event_type: str = Field(..., description="Type of event (EXTRACTION, VALIDATION, POSTING, etc.)")
    severity: AuditSeverity = Field(default=AuditSeverity.INFO, description="Event severity")
    
    # Context
    ap_package_id: Optional[str] = Field(None, description="Associated AP package")
    invoice_number: Optional[str] = Field(None, description="Associated invoice")
    workflow_id: Optional[str] = Field(None, description="Temporal workflow ID")
    activity_name: Optional[str] = Field(None, description="Activity that generated event")
    
    # Details
    message: str = Field(..., description="Human-readable message")
    details: dict = Field(default_factory=dict, description="Additional event details")
    
    # Actor
    actor: str = Field(default="system", description="Who/what performed the action")
    
    # Evidence
    artifact_refs: list[DataReference] = Field(default_factory=list, description="Related artifacts")


class ERPPostingResult(BaseModel):
    """Result of posting to an ERP system.
    
    ERP-neutral representation of a posting result that can be
    implemented by any connector.
    """
    success: bool = Field(..., description="Whether posting succeeded")
    erp_document_id: Optional[str] = Field(None, description="ID in ERP system if created")
    erp_document_number: Optional[str] = Field(None, description="Document number in ERP")
    posted_at: Optional[datetime] = Field(None, description="When posted to ERP")
    
    # Error handling
    error_code: Optional[str] = Field(None, description="Error code if failed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Mapping used
    vendor_id: Optional[str] = Field(None, description="Mapped vendor ID in ERP")
    gl_account: Optional[str] = Field(None, description="Mapped GL account in ERP")
    
    # Raw response (for debugging)
    raw_response: Optional[dict] = Field(None, description="Raw ERP response")
