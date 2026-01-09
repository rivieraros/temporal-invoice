"""Dashboard endpoints for Mission Control.

Provides the main dashboard view and role-based insights.
Uses the shared Pydantic response models from models/api_responses.py.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Path

from models.api_responses import (
    # Enums
    StakeholderRole,
    PackageStatus,
    InvoiceStatus,
    PipelineStage,
    AlertType,
    TrendDirection,
    
    # Response models
    MissionControlResponse,
    PackageSummary,
    PackageDetailResponse,
    PackageDetailHeader,
    InvoiceSummary,
    InvoiceDetailResponse,
    DrilldownResponse,
    PipelineSnapshot,
    PipelineStageData,
    HumanReviewSummary,
    ReviewReasonSummary,
    ReviewQueueItem,
    TodayStats,
    
    # Actions
    ApprovalAction,
    ApprovalResult,
    ReviewDecision,
    ReviewDecisionResult,
)

from api.services.mock_data import (
    MOCK_PACKAGES,
    MOCK_INVOICES,
    get_mock_invoice_detail,
    get_mock_drilldown,
    build_package_summary,
    build_invoice_summary,
)


router = APIRouter()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _relative_time(dt: datetime) -> str:
    """Convert datetime to relative time string."""
    delta = datetime.now() - dt
    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours} hr{'s' if hours > 1 else ''} ago"
    minutes = delta.seconds // 60
    if minutes > 0:
        return f"{minutes} min ago"
    return "just now"


def _build_pipeline_snapshot() -> PipelineSnapshot:
    """Build pipeline snapshot from mock data."""
    return PipelineSnapshot(
        received=PipelineStageData(
            stage=PipelineStage.RECEIVED,
            count=215,
            dollars=Decimal("892341.50"),
            label="Received",
            color="info",
            is_active=False,
            is_highlighted=False,
        ),
        processing=PipelineStageData(
            stage=PipelineStage.PROCESSING,
            count=3,
            dollars=Decimal("12450.00"),
            label="Processing",
            color="purple",
            is_active=True,
            is_highlighted=False,
        ),
        auto_approved=PipelineStageData(
            stage=PipelineStage.AUTO_APPROVED,
            count=187,
            dollars=Decimal("692841.20"),
            label="Auto-Approved",
            color="success",
            is_active=False,
            is_highlighted=False,
        ),
        human_review=PipelineStageData(
            stage=PipelineStage.HUMAN_REVIEW,
            count=12,
            dollars=Decimal("89234.50"),
            label="Human Review",
            color="warn",
            is_active=False,
            is_highlighted=True,
        ),
        ready_to_post=PipelineStageData(
            stage=PipelineStage.READY_TO_POST,
            count=195,
            dollars=Decimal("758923.45"),
            label="Ready to Post",
            color="success",
            is_active=False,
            is_highlighted=False,
        ),
        posted=PipelineStageData(
            stage=PipelineStage.POSTED,
            count=178,
            dollars=Decimal("687234.20"),
            label="Posted to ERP",
            color="success",
            is_active=False,
            is_highlighted=False,
        ),
    )


def _build_human_review_summary() -> HumanReviewSummary:
    """Build human review summary from mock data."""
    now = datetime.now()
    return HumanReviewSummary(
        total_count=12,
        total_dollars=Decimal("89234.50"),
        by_reason=[
            ReviewReasonSummary(reason="Suspense GL Coding", count=4, dollars=Decimal("32180.00"), is_urgent=False),
            ReviewReasonSummary(reason="Missing Source Document", count=3, dollars=Decimal("28450.75"), is_urgent=True),
            ReviewReasonSummary(reason="Amount Variance", count=2, dollars=Decimal("15890.00"), is_urgent=False),
            ReviewReasonSummary(reason="Entity Resolution", count=2, dollars=Decimal("8713.75"), is_urgent=False),
            ReviewReasonSummary(reason="Duplicate Detection", count=1, dollars=Decimal("4000.00"), is_urgent=True),
        ],
        recent_items=[
            ReviewQueueItem(
                invoice_id="INV-13304",
                package_id="PKG-2025-11-BF2-001",
                lot_number="20-3927",
                feedlot="Bovina",
                amount=Decimal("301.36"),
                reason="Medicine only, zero head",
                time_ago="5 min ago",
                queued_at=now - timedelta(minutes=5),
            ),
            ReviewQueueItem(
                invoice_id="INV-13508",
                package_id="PKG-2025-11-BF2-001",
                lot_number="20-4263",
                feedlot="Bovina",
                amount=Decimal("7427.87"),
                reason="Contains credit adjustment",
                time_ago="12 min ago",
                queued_at=now - timedelta(minutes=12),
            ),
            ReviewQueueItem(
                invoice_id="INV-M2901",
                package_id="PKG-2025-11-MC1-001",
                lot_number="M-2901",
                feedlot="Mesquite",
                amount=Decimal("8742.30"),
                reason="Hospital feed >15%",
                time_ago="28 min ago",
                queued_at=now - timedelta(minutes=28),
            ),
        ],
    )


def _build_today_stats() -> TodayStats:
    """Build today's statistics."""
    return TodayStats(
        invoices_processed=47,
        avg_processing_time="4.2 sec",
        avg_processing_seconds=4.2,
        auto_approval_rate=89,
        dollars_processed=Decimal("198432.50"),
    )


# =============================================================================
# MAIN MISSION CONTROL ENDPOINT
# =============================================================================

@router.get(
    "",
    response_model=MissionControlResponse,
    summary="Get Mission Control Dashboard",
    description="Returns the complete Mission Control dashboard data including pipeline state, packages, and statistics."
)
async def get_mission_control(
    period: Optional[str] = Query(None, description="Period filter (e.g., '2025-11' or 'November 2025')", alias="period")
) -> MissionControlResponse:
    """
    Get the complete Mission Control dashboard.
    
    This is the main endpoint that powers the dashboard view.
    Returns pipeline state, human review queue, package list, and today's stats.
    """
    now = datetime.now()
    
    # Build package list
    packages = [build_package_summary(pkg) for pkg in MOCK_PACKAGES.values()]
    
    # Sort by status priority (blocked > review > ready), then by last activity
    status_order = {PackageStatus.BLOCKED: 0, PackageStatus.REVIEW: 1, PackageStatus.READY: 2}
    packages.sort(key=lambda p: (status_order.get(p.status, 3), -p.last_activity_at.timestamp()))
    
    return MissionControlResponse(
        period="November 2025",
        period_start=date(2025, 11, 1),
        period_end=date(2025, 11, 30),
        last_sync="2 min ago",
        last_sync_at=now - timedelta(minutes=2),
        pipeline=_build_pipeline_snapshot(),
        human_review=_build_human_review_summary(),
        packages=packages,
        today_stats=_build_today_stats(),
        insights_available=list(StakeholderRole),
    )


# =============================================================================
# PIPELINE ENDPOINTS
# =============================================================================

@router.get(
    "/pipeline",
    response_model=PipelineSnapshot,
    summary="Get Pipeline State",
    description="Returns current pipeline stage counts and dollar amounts."
)
async def get_pipeline() -> PipelineSnapshot:
    """Get current invoice pipeline state."""
    return _build_pipeline_snapshot()


@router.get(
    "/today-stats",
    response_model=TodayStats,
    summary="Get Today's Statistics",
    description="Returns today's processing metrics."
)
async def get_today_stats() -> TodayStats:
    """Get today's processing statistics."""
    return _build_today_stats()


@router.get(
    "/review-queue",
    response_model=HumanReviewSummary,
    summary="Get Human Review Queue",
    description="Returns summary of invoices awaiting human review."
)
async def get_review_queue() -> HumanReviewSummary:
    """Get human review queue summary."""
    return _build_human_review_summary()


# =============================================================================
# INSIGHT/DRILLDOWN ENDPOINTS
# =============================================================================

@router.get(
    "/insights/{role}",
    response_model=DrilldownResponse,
    summary="Get Role-Based Insights",
    description="Returns drill-down insights for a specific stakeholder role."
)
async def get_insights(
    role: StakeholderRole = Path(..., description="Stakeholder role")
) -> DrilldownResponse:
    """Get role-specific insights."""
    return get_mock_drilldown(role)


@router.get(
    "/insights",
    response_model=List[DrilldownResponse],
    summary="Get All Insights",
    description="Returns insights for all stakeholder roles."
)
async def get_all_insights() -> List[DrilldownResponse]:
    """Get insights for all roles."""
    return [get_mock_drilldown(role) for role in StakeholderRole]


# =============================================================================
# PACKAGE ENDPOINTS
# =============================================================================

@router.get(
    "/packages",
    response_model=List[PackageSummary],
    summary="List Packages",
    description="Returns list of feedlot packages with optional filtering."
)
async def list_packages(
    period: Optional[str] = Query(None, description="Period filter (e.g., '2025-11')"),
    status: Optional[PackageStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by feedlot name or owner"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> List[PackageSummary]:
    """List packages with optional filters."""
    packages = [build_package_summary(pkg) for pkg in MOCK_PACKAGES.values()]
    
    # Apply filters
    if status:
        packages = [p for p in packages if p.status == status]
    
    if search:
        search_lower = search.lower()
        packages = [
            p for p in packages 
            if search_lower in p.feedlot_name.lower() 
            or search_lower in p.owner_name.lower()
            or search_lower in p.feedlot_code.lower()
        ]
    
    # Sort by status priority, then by last activity
    status_order = {PackageStatus.BLOCKED: 0, PackageStatus.REVIEW: 1, PackageStatus.READY: 2}
    packages.sort(key=lambda p: (status_order.get(p.status, 3), -p.last_activity_at.timestamp()))
    
    # Apply pagination
    return packages[offset:offset + limit]


@router.get(
    "/packages/{package_id}",
    response_model=PackageDetailResponse,
    summary="Get Package Details",
    description="Returns complete package details including all invoices."
)
async def get_package(
    package_id: str = Path(..., description="Package identifier")
) -> PackageDetailResponse:
    """Get detailed package information."""
    pkg = MOCK_PACKAGES.get(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    # Build header
    header = PackageDetailHeader(
        package_id=pkg["package_id"],
        feedlot_name=pkg["feedlot_name"],
        feedlot_code=pkg["feedlot_code"],
        owner_name=pkg["owner_name"],
        period=pkg["period"],
        statement_total=pkg["statement_total"],
        invoice_total=pkg["invoice_total"],
        variance=pkg["variance"],
        total_invoices=pkg["total_invoices"],
        ready_count=pkg["ready_count"],
        review_count=pkg["review_count"],
        blocked_count=pkg["blocked_count"],
        overall_confidence=pkg["overall_confidence"],
    )
    
    # Get invoices for this package
    package_invoices = [
        build_invoice_summary(inv) 
        for inv in MOCK_INVOICES.values() 
        if inv.get("package_id") == package_id
    ]
    
    # Sort by status priority
    status_order = {InvoiceStatus.BLOCKED: 0, InvoiceStatus.REVIEW: 1, InvoiceStatus.READY: 2}
    package_invoices.sort(key=lambda i: status_order.get(i.status, 3))
    
    return PackageDetailResponse(
        header=header,
        invoices=package_invoices,
        selected_invoice_detail=None,
    )


@router.get(
    "/packages/{package_id}/invoices",
    response_model=List[InvoiceSummary],
    summary="List Package Invoices",
    description="Returns all invoices in a package."
)
async def list_package_invoices(
    package_id: str = Path(..., description="Package identifier"),
    status: Optional[InvoiceStatus] = Query(None, description="Filter by invoice status"),
) -> List[InvoiceSummary]:
    """List invoices in a package."""
    if package_id not in MOCK_PACKAGES:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    invoices = [
        build_invoice_summary(inv) 
        for inv in MOCK_INVOICES.values() 
        if inv.get("package_id") == package_id
    ]
    
    if status:
        invoices = [i for i in invoices if i.status == status]
    
    return invoices


@router.get(
    "/packages/{package_id}/invoices/{invoice_id}",
    response_model=InvoiceDetailResponse,
    summary="Get Invoice Details",
    description="Returns complete invoice details including line items, validation, and reconciliation."
)
async def get_package_invoice(
    package_id: str = Path(..., description="Package identifier"),
    invoice_id: str = Path(..., description="Invoice identifier"),
) -> InvoiceDetailResponse:
    """Get detailed invoice information within a package context."""
    if package_id not in MOCK_PACKAGES:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    detail = get_mock_invoice_detail(invoice_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    
    # Verify invoice belongs to package
    inv = MOCK_INVOICES.get(invoice_id)
    if inv and inv.get("package_id") != package_id:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found in package {package_id}")
    
    return detail


# =============================================================================
# DRILLDOWN ENDPOINT
# =============================================================================

@router.get(
    "/drilldown",
    response_model=DrilldownResponse,
    summary="Get Drilldown Data",
    description="Returns filtered drilldown data with recommended focus target."
)
async def get_drilldown(
    type: str = Query(..., description="Drilldown type: stage, reason, check, role"),
    id: Optional[str] = Query(None, description="Specific ID to filter by"),
    period: Optional[str] = Query(None, description="Period filter (e.g., '2025-11')"),
) -> DrilldownResponse:
    """
    Get drilldown data based on type.
    
    Types:
    - stage: Pipeline stage drilldown (received, processing, etc.)
    - reason: Review reason drilldown (suspense_gl, missing_doc, etc.)
    - check: Validation check drilldown
    - role: Role-based insight (CFO, COO, CIO, Accounting)
    """
    # Handle role-based drilldown
    if type == "role" and id:
        try:
            role = StakeholderRole(id)
            return get_mock_drilldown(role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {id}")
    
    # For stage drilldown, return CFO view as it has financial focus
    if type == "stage":
        drilldown = get_mock_drilldown(StakeholderRole.CFO)
        drilldown.title = f"Pipeline Stage: {id or 'All'}"
        return drilldown
    
    # For reason drilldown, return Accounting view
    if type == "reason":
        drilldown = get_mock_drilldown(StakeholderRole.ACCOUNTING)
        drilldown.title = f"Review Reason: {id or 'All'}"
        return drilldown
    
    # For check drilldown, return CIO view
    if type == "check":
        drilldown = get_mock_drilldown(StakeholderRole.CIO)
        drilldown.title = f"Validation Check: {id or 'All'}"
        return drilldown
    
    # Default to CFO view
    return get_mock_drilldown(StakeholderRole.CFO)


# =============================================================================
# ACTION ENDPOINTS
# =============================================================================

@router.post(
    "/packages/{package_id}/approve",
    response_model=ApprovalResult,
    summary="Approve Package",
    description="Approve an entire package for posting to ERP."
)
async def approve_package(
    package_id: str = Path(..., description="Package identifier"),
    action: Optional[ApprovalAction] = None,
) -> ApprovalResult:
    """Approve a package."""
    if package_id not in MOCK_PACKAGES:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    return ApprovalResult(
        success=True,
        entity_id=package_id,
        new_status="approved",
        message=f"Package {package_id} approved for posting",
        posted_at=datetime.now(),
    )


@router.post(
    "/invoices/{invoice_id}/approve",
    response_model=ApprovalResult,
    summary="Approve Invoice",
    description="Approve a single invoice for posting."
)
async def approve_invoice(
    invoice_id: str = Path(..., description="Invoice identifier"),
    action: Optional[ApprovalAction] = None,
) -> ApprovalResult:
    """Approve an invoice."""
    if invoice_id not in MOCK_INVOICES:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    
    return ApprovalResult(
        success=True,
        entity_id=invoice_id,
        new_status="approved",
        message=f"Invoice {invoice_id} approved for posting",
        posted_at=datetime.now(),
    )


@router.post(
    "/invoices/{invoice_id}/review-decision",
    response_model=ReviewDecisionResult,
    summary="Submit Review Decision",
    description="Submit a human review decision for an invoice."
)
async def submit_review_decision(
    invoice_id: str = Path(..., description="Invoice identifier"),
    decision: Optional[ReviewDecision] = None,
) -> ReviewDecisionResult:
    """Submit review decision."""
    if invoice_id not in MOCK_INVOICES:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    
    decision_type = decision.decision if decision else "approve"
    
    return ReviewDecisionResult(
        success=True,
        invoice_id=invoice_id,
        new_status=InvoiceStatus.READY if decision_type == "approve" else InvoiceStatus.BLOCKED,
        message=f"Review decision '{decision_type}' applied to {invoice_id}",
        audit_id=f"AUD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{invoice_id}",
    )
