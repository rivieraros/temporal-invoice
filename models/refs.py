"""Data reference models for artifact storage and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
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
