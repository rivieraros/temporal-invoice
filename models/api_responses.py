"""
API Response Models for AP Automation Mission Control.

These Pydantic models define the shared data contracts between the backend API
and frontend UI. They are designed to prevent drift and enable OpenAPI generation.

Hierarchy:
- MissionControlResponse: Main dashboard overview
- PackageSummary: Package list items and package header
- InvoiceSummary: Invoice list items within packages
- InvoiceDetailResponse: Full invoice detail with line items, validation, etc.
- DrilldownResponse: Role-based insights (CFO, COO, CIO, Accounting views)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Literal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# ENUMS
# =============================================================================

class PipelineStage(str, Enum):
    """Invoice pipeline stages."""
    RECEIVED = "received"
    PROCESSING = "processing"
    AUTO_APPROVED = "auto_approved"
    HUMAN_REVIEW = "human_review"
    READY_TO_POST = "ready_to_post"
    POSTED = "posted"


class PackageStatus(str, Enum):
    """Package status values."""
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"


class InvoiceStatus(str, Enum):
    """Invoice status values."""
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"
    PROCESSING = "processing"


class ValidationStatus(str, Enum):
    """Validation check status."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class ReconciliationStatus(str, Enum):
    """Reconciliation match status."""
    MATCHED = "matched"
    VARIANCE = "variance"
    UNMATCHED = "unmatched"


class GLMappingStatus(str, Enum):
    """GL code mapping status."""
    MAPPED = "mapped"
    SUSPENSE = "suspense"
    UNMAPPED = "unmapped"


class StakeholderRole(str, Enum):
    """Stakeholder roles for role-based views."""
    CFO = "CFO"
    COO = "COO"
    CIO = "CIO"
    ACCOUNTING = "Accounting"


class AlertType(str, Enum):
    """Alert severity types."""
    SUCCESS = "success"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class TrendDirection(str, Enum):
    """Trend direction indicators."""
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"
    GOOD = "good"
    BAD = "bad"


# =============================================================================
# BASE MODELS
# =============================================================================

class ResponseBase(BaseModel):
    """Base class for all API responses."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={Decimal: lambda v: float(v) if v else None}
    )


# =============================================================================
# PIPELINE MODELS
# =============================================================================

class PipelineStageData(ResponseBase):
    """Single pipeline stage data."""
    stage: PipelineStage
    count: int = Field(..., description="Number of invoices in this stage")
    dollars: Decimal = Field(..., description="Total dollar amount in this stage")
    label: str = Field(..., description="Display label for the stage")
    color: str = Field(default="info", description="Color theme: info, success, warn, error, purple")
    is_active: bool = Field(default=False, description="Whether stage is currently processing")
    is_highlighted: bool = Field(default=False, description="Whether stage needs attention")


class PipelineSnapshot(ResponseBase):
    """Complete pipeline state snapshot."""
    received: PipelineStageData
    processing: PipelineStageData
    auto_approved: PipelineStageData
    human_review: PipelineStageData
    ready_to_post: PipelineStageData
    posted: PipelineStageData


# =============================================================================
# HUMAN REVIEW MODELS
# =============================================================================

class ReviewReasonSummary(ResponseBase):
    """Summary of invoices grouped by review reason."""
    reason: str = Field(..., description="Human-readable reason for review")
    count: int = Field(..., description="Number of invoices with this reason")
    dollars: Decimal = Field(..., description="Total dollar amount")
    is_urgent: bool = Field(default=False, description="Whether this requires urgent attention")


class ReviewQueueItem(ResponseBase):
    """Single item in the human review queue."""
    invoice_id: str = Field(..., description="Invoice identifier (e.g., INV-13304)")
    package_id: str = Field(..., description="Package identifier containing this invoice")
    lot_number: str = Field(..., description="Lot identifier")
    feedlot: str = Field(..., description="Feedlot name")
    amount: Decimal = Field(..., description="Invoice amount")
    reason: str = Field(..., description="Reason for human review")
    time_ago: str = Field(..., description="Relative time since queued (e.g., '5 min ago')")
    queued_at: datetime = Field(..., description="Absolute timestamp")


class HumanReviewSummary(ResponseBase):
    """Summary of all items awaiting human review."""
    total_count: int = Field(..., description="Total invoices needing review")
    total_dollars: Decimal = Field(..., description="Total dollar amount needing review")
    by_reason: List[ReviewReasonSummary] = Field(default_factory=list)
    recent_items: List[ReviewQueueItem] = Field(default_factory=list, max_length=10)


# =============================================================================
# TODAY'S ACTIVITY MODELS
# =============================================================================

class TodayStats(ResponseBase):
    """Today's processing statistics."""
    invoices_processed: int = Field(..., description="Invoices processed today")
    avg_processing_time: str = Field(..., description="Average processing time (e.g., '4.2 sec')")
    avg_processing_seconds: float = Field(..., description="Average processing time in seconds")
    auto_approval_rate: int = Field(..., description="Auto-approval percentage (0-100)")
    dollars_processed: Decimal = Field(..., description="Total dollars processed today")


# =============================================================================
# PACKAGE MODELS
# =============================================================================

class PackageSummary(ResponseBase):
    """Summary of a feedlot package for list display."""
    package_id: str = Field(..., description="Package identifier (e.g., PKG-2025-1130-531)")
    feedlot_name: str = Field(..., description="Feedlot display name")
    feedlot_code: str = Field(..., description="Short feedlot code (e.g., BF2, MC1)")
    owner_name: str = Field(..., description="Cattle owner name")
    
    # Counts
    total_invoices: int = Field(..., description="Total invoices in package")
    total_lots: int = Field(..., description="Total unique lots")
    ready_count: int = Field(default=0, description="Invoices ready to post")
    review_count: int = Field(default=0, description="Invoices needing review")
    blocked_count: int = Field(default=0, description="Invoices blocked")
    
    # Financials
    total_dollars: Decimal = Field(..., description="Total package amount")
    
    # Status
    status: PackageStatus = Field(..., description="Overall package status")
    statement_date: date = Field(..., description="Statement date")
    last_activity: str = Field(..., description="Relative time of last activity")
    last_activity_at: datetime = Field(..., description="Absolute timestamp of last activity")


class PackageDetailHeader(ResponseBase):
    """Extended package info for detail view header."""
    package_id: str
    feedlot_name: str
    feedlot_code: str
    owner_name: str
    period: str = Field(..., description="Display period (e.g., 'November 2025')")
    
    # Reconciliation totals
    statement_total: Decimal = Field(..., description="Total from statement")
    invoice_total: Decimal = Field(..., description="Sum of all invoices")
    variance: Decimal = Field(..., description="Difference between statement and invoices")
    
    # Summary counts
    total_invoices: int
    ready_count: int
    review_count: int
    blocked_count: int
    
    # AI confidence
    overall_confidence: int = Field(..., description="Overall AI confidence percentage (0-100)")


# =============================================================================
# INVOICE MODELS
# =============================================================================

class InvoiceSummary(ResponseBase):
    """Summary of an invoice for list display within a package."""
    invoice_id: str = Field(..., description="Invoice identifier (e.g., INV-13304)")
    lot_number: str = Field(..., description="Lot identifier")
    amount: Decimal = Field(..., description="Invoice total amount")
    status: InvoiceStatus = Field(..., description="Current invoice status")
    
    # Optional context
    reason: Optional[str] = Field(None, description="Reason if status is review/blocked")
    feed_type: Optional[str] = Field(None, description="Primary feed type")
    head_count: Optional[int] = Field(None, description="Number of head")
    days_on_feed: Optional[int] = Field(None, description="Days on feed")
    cost_per_head: Optional[Decimal] = Field(None, description="Cost per head")
    confidence: Optional[int] = Field(None, description="AI extraction confidence (0-100)")


class ExtractedField(ResponseBase):
    """Single extracted field with confidence."""
    field_name: str
    value: str
    confidence: int = Field(..., ge=0, le=100, description="Confidence percentage")


class InvoiceLineItem(ResponseBase):
    """Single line item from an invoice."""
    line_id: int = Field(..., description="Line item sequence number")
    description: str = Field(..., description="Line item description")
    gl_code: str = Field(..., description="GL account code")
    amount: Decimal = Field(..., description="Line item amount")
    quantity: Optional[Decimal] = Field(None, description="Quantity")
    unit: Optional[str] = Field(None, description="Unit of measure")
    rate: Optional[str] = Field(None, description="Rate with unit (e.g., '0.45/HD/DAY')")
    category: str = Field(..., description="Category: FEED, YARDAGE, VET, etc.")
    warning: Optional[str] = Field(None, description="Warning message if applicable")


class InvoiceTotals(ResponseBase):
    """Invoice totals breakdown."""
    subtotal: Decimal = Field(..., description="Sum of line items before adjustments")
    adjustments: Decimal = Field(default=Decimal("0"), description="Total adjustments/credits")
    total: Decimal = Field(..., description="Final invoice total")


class AgentCommentary(ResponseBase):
    """AI agent processing commentary entry."""
    timestamp: datetime
    time_display: str = Field(..., description="Display time (e.g., '10:43 AM')")
    icon: str = Field(..., description="Icon type: upload, extract, warn, info, review")
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")


class GLCodingEntry(ResponseBase):
    """GL coding for a line item."""
    description: str = Field(..., description="Line item description")
    category: str = Field(..., description="Expense category")
    gl_code: str = Field(..., description="GL account code")
    status: GLMappingStatus = Field(..., description="Mapping status")


class ValidationCheck(ResponseBase):
    """Single validation check result."""
    field: str = Field(..., description="Field being validated")
    status: ValidationStatus = Field(..., description="Check result")
    extracted: str = Field(..., description="Value extracted from document")
    matched: str = Field(..., description="Value matched against (or '—' if none)")
    note: Optional[str] = Field(None, description="Additional note if warn/fail")


class ReconciliationResult(ResponseBase):
    """Invoice-to-statement reconciliation result."""
    statement_amount: Decimal = Field(..., description="Amount from statement")
    invoice_amount: Decimal = Field(..., description="Amount from invoice")
    variance: Decimal = Field(..., description="Difference")
    status: ReconciliationStatus = Field(..., description="Match status")


class InvoiceDetailResponse(ResponseBase):
    """Complete invoice detail for the detail panel."""
    # Core identification
    invoice_id: str
    lot_number: str
    amount: Decimal
    status: InvoiceStatus
    reason: Optional[str] = None
    
    # Invoice metadata
    feed_type: Optional[str] = None
    head_count: int
    days_on_feed: int
    cost_per_head: Decimal
    confidence: int = Field(..., ge=0, le=100)
    
    # Extracted fields
    extracted_fields: List[ExtractedField] = Field(default_factory=list)
    
    # Line items
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    totals: InvoiceTotals
    
    # Agent processing trail
    agent_commentary: List[AgentCommentary] = Field(default_factory=list)
    
    # GL coding
    gl_coding: List[GLCodingEntry] = Field(default_factory=list)
    
    # Validation
    validation_checks: List[ValidationCheck] = Field(default_factory=list)
    
    # Reconciliation
    reconciliation: ReconciliationResult
    
    # Source document references
    source_pdf_url: Optional[str] = Field(None, description="URL to source PDF")
    statement_highlight_region: Optional[dict] = Field(None, description="Region to highlight in statement")


# =============================================================================
# ROLE-BASED INSIGHT MODELS (DRILLDOWN)
# =============================================================================

class MetricItem(ResponseBase):
    """Single metric for dashboard display."""
    label: str = Field(..., description="Metric label")
    value: str = Field(..., description="Display value (formatted)")
    raw_value: Optional[Decimal] = Field(None, description="Raw numeric value if applicable")
    trend: Optional[str] = Field(None, description="Trend indicator (e.g., '+12%', '-2')")
    trend_direction: Optional[TrendDirection] = Field(None, description="Trend direction for styling")


class AlertItem(ResponseBase):
    """Alert/notification for stakeholder view."""
    alert_type: AlertType = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    is_actionable: bool = Field(default=False, description="Whether user can take action")
    action_url: Optional[str] = Field(None, description="URL for action if actionable")


class DetailListItem(ResponseBase):
    """Single item in a detail list."""
    label: str
    value: str
    status: Optional[Literal["success", "warn", "error", "neutral"]] = None


class DetailSection(ResponseBase):
    """Section of details for drilldown view."""
    title: str = Field(..., description="Section title")
    items: List[DetailListItem] = Field(default_factory=list)


class DrilldownResponse(ResponseBase):
    """Role-based drilldown view data."""
    role: StakeholderRole = Field(..., description="Stakeholder role")
    title: str = Field(..., description="View title (e.g., 'Financial Overview')")
    icon: str = Field(..., description="Icon identifier for the view")
    
    # Key metrics (typically 4)
    metrics: List[MetricItem] = Field(default_factory=list, max_length=6)
    
    # Alerts/notifications
    alerts: List[AlertItem] = Field(default_factory=list)
    
    # Detailed sections
    details: List[DetailSection] = Field(default_factory=list)
    
    # Timestamp
    as_of: datetime = Field(..., description="Data freshness timestamp")


# =============================================================================
# MAIN DASHBOARD RESPONSE
# =============================================================================

class MissionControlResponse(ResponseBase):
    """
    Complete Mission Control dashboard response.
    
    This is the primary API response for the main dashboard view.
    It includes:
    - Period information
    - Pipeline state
    - Human review queue
    - Package list
    - Today's statistics
    - Role-based insights summary
    """
    # Period and sync info
    period: str = Field(..., description="Current period (e.g., 'November 2025')")
    period_start: date = Field(..., description="Period start date")
    period_end: date = Field(..., description="Period end date")
    last_sync: str = Field(..., description="Relative time since last sync")
    last_sync_at: datetime = Field(..., description="Absolute sync timestamp")
    
    # Pipeline state
    pipeline: PipelineSnapshot
    
    # Human review summary
    human_review: HumanReviewSummary
    
    # Package list
    packages: List[PackageSummary] = Field(default_factory=list)
    
    # Today's activity
    today_stats: TodayStats
    
    # Quick insights per role (just counts, not full drilldown)
    insights_available: List[StakeholderRole] = Field(
        default_factory=lambda: list(StakeholderRole),
        description="Available insight views"
    )


# =============================================================================
# PACKAGE DETAIL RESPONSE
# =============================================================================

class PackageDetailResponse(ResponseBase):
    """
    Complete package detail response for the package drill-down view.
    
    Includes package header, invoice list, and reconciliation summary.
    """
    header: PackageDetailHeader
    invoices: List[InvoiceSummary] = Field(default_factory=list)
    
    # Optional: pre-loaded invoice details for the first invoice or selected invoice
    selected_invoice_detail: Optional[InvoiceDetailResponse] = None


# =============================================================================
# ACTION RESPONSES
# =============================================================================

class ApprovalAction(ResponseBase):
    """Request to approve an invoice or package."""
    entity_type: Literal["invoice", "package"]
    entity_id: str
    approver_id: str
    notes: Optional[str] = None


class ApprovalResult(ResponseBase):
    """Result of an approval action."""
    success: bool
    entity_id: str
    new_status: str
    message: str
    posted_at: Optional[datetime] = None


class ReviewDecision(ResponseBase):
    """Human review decision."""
    invoice_id: str
    decision: Literal["approve", "reject", "escalate"]
    reviewer_id: str
    notes: Optional[str] = None
    gl_overrides: Optional[dict] = Field(None, description="GL code overrides if any")


class ReviewDecisionResult(ResponseBase):
    """Result of a review decision."""
    success: bool
    invoice_id: str
    new_status: InvoiceStatus
    message: str
    audit_id: str = Field(..., description="Audit trail entry ID")


# =============================================================================
# EXPORT HELPERS
# =============================================================================

# All response models for easy import
__all__ = [
    # Enums
    "PipelineStage",
    "PackageStatus", 
    "InvoiceStatus",
    "ValidationStatus",
    "ReconciliationStatus",
    "GLMappingStatus",
    "StakeholderRole",
    "AlertType",
    "TrendDirection",
    
    # Pipeline
    "PipelineStageData",
    "PipelineSnapshot",
    
    # Human Review
    "ReviewReasonSummary",
    "ReviewQueueItem", 
    "HumanReviewSummary",
    
    # Today Stats
    "TodayStats",
    
    # Package
    "PackageSummary",
    "PackageDetailHeader",
    "PackageDetailResponse",
    
    # Invoice
    "InvoiceSummary",
    "ExtractedField",
    "InvoiceLineItem",
    "InvoiceTotals",
    "AgentCommentary",
    "GLCodingEntry",
    "ValidationCheck",
    "ReconciliationResult",
    "InvoiceDetailResponse",
    
    # Drilldown
    "MetricItem",
    "AlertItem",
    "DetailListItem",
    "DetailSection",
    "DrilldownResponse",
    
    # Main Response
    "MissionControlResponse",
    
    # Actions
    "ApprovalAction",
    "ApprovalResult",
    "ReviewDecision",
    "ReviewDecisionResult",
]
