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
    TimelineEvent,
    TimelineResponse,
    
    # Actions
    ApprovalAction,
    ApprovalResult,
    ReviewDecision,
    ReviewDecisionResult,
    
    # Configuration
    ConnectorConfig,
    ConnectorStatus,
    EntityMapping,
    VendorMapping,
    ConfigurationResponse,
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
            ReviewReasonSummary(
                reason="Suspense GL Coding",
                count=4,
                dollars=Decimal("32180.00"),
                is_urgent=False,
                check_id="gl_suspense",
                top_package_id="PKG-2025-11-BF2-001",
                top_invoice_id="INV-13508",
            ),
            ReviewReasonSummary(
                reason="Missing Source Document",
                count=3,
                dollars=Decimal("28450.75"),
                is_urgent=True,
                check_id="doc_missing",
                top_package_id="PKG-2025-11-BF2-001",
                top_invoice_id="INV-13304",
            ),
            ReviewReasonSummary(
                reason="Amount Variance",
                count=2,
                dollars=Decimal("15890.00"),
                is_urgent=False,
                check_id="recon_variance",
                top_package_id="PKG-2025-11-MC1-001",
                top_invoice_id="INV-M2901",
            ),
            ReviewReasonSummary(
                reason="Entity Resolution",
                count=2,
                dollars=Decimal("8713.75"),
                is_urgent=False,
                check_id="entity_ambiguous",
                top_package_id="PKG-2025-11-CF4-001",
            ),
            ReviewReasonSummary(
                reason="Duplicate Detection",
                count=1,
                dollars=Decimal("4000.00"),
                is_urgent=True,
                check_id="dup_detected",
                top_package_id="PKG-2025-11-BF2-001",
            ),
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
                check_id="val_zero_head",
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
                check_id="val_credit_adj",
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
                check_id="val_hospital_ratio",
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
# TIMELINE ENDPOINT
# =============================================================================

def _relative_time_short(dt: datetime) -> str:
    """Convert datetime to short relative time string."""
    delta = datetime.now() - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    minutes = delta.seconds // 60
    if minutes > 0:
        return f"{minutes}m ago"
    return "just now"


def _build_mock_timeline(invoice_id: str, inv: dict) -> List[TimelineEvent]:
    """Build mock timeline events for an invoice."""
    events = []
    base_time = datetime.now() - timedelta(hours=2)
    
    # Event 1: PDF Upload
    events.append(TimelineEvent(
        id=f"{invoice_id}-evt-1",
        timestamp=base_time,
        time_display=base_time.strftime("%I:%M %p"),
        relative_time=_relative_time_short(base_time),
        event_type="upload",
        severity="info",
        title="PDF received",
        description="Document received via email integration from feedlot@bovinalivestock.com",
        agent_state="processing",
    ))
    
    # Event 2: OCR/Extraction
    t2 = base_time + timedelta(seconds=45)
    events.append(TimelineEvent(
        id=f"{invoice_id}-evt-2",
        timestamp=t2,
        time_display=t2.strftime("%I:%M %p"),
        relative_time=_relative_time_short(t2),
        event_type="extract",
        severity="success",
        title="Document parsed",
        description="GPT-4o Vision extracted 12 fields and 1 line item in 2.3s",
        agent_state="processing",
        progress_current=1,
        progress_total=5,
    ))
    
    # Event 3: Entity Resolution
    t3 = base_time + timedelta(minutes=1)
    events.append(TimelineEvent(
        id=f"{invoice_id}-evt-3",
        timestamp=t3,
        time_display=t3.strftime("%I:%M %p"),
        relative_time=_relative_time_short(t3),
        event_type="resolve",
        severity="success",
        title="Entities resolved",
        description=f"Matched lot {inv.get('lot_number', 'N/A')} to BC Lot ID 4892. Vendor: Bovina Feeders Inc.",
        agent_state="processing",
        progress_current=2,
        progress_total=5,
    ))
    
    # Event 4: GL Coding
    t4 = base_time + timedelta(minutes=1, seconds=30)
    events.append(TimelineEvent(
        id=f"{invoice_id}-evt-4",
        timestamp=t4,
        time_display=t4.strftime("%I:%M %p"),
        relative_time=_relative_time_short(t4),
        event_type="code",
        severity="success",
        title="GL codes assigned",
        description="Auto-coded FEED → 5200-01 using feedlot template",
        agent_state="processing",
        progress_current=3,
        progress_total=5,
    ))
    
    # Event 5: Validation
    t5 = base_time + timedelta(minutes=2)
    status = inv.get("status", "ready")
    if status == "review":
        reason = inv.get("reason", "Validation check failed")
        events.append(TimelineEvent(
            id=f"{invoice_id}-evt-5",
            timestamp=t5,
            time_display=t5.strftime("%I:%M %p"),
            relative_time=_relative_time_short(t5),
            event_type="validate",
            severity="warning",
            title="Validation flagged issue",
            description=reason,
            agent_state="paused",
            pause_reason=reason,
            related_field="Head Count" if "head" in reason.lower() else None,
            progress_current=4,
            progress_total=5,
        ))
        
        # Event 6: Agent paused
        t6 = base_time + timedelta(minutes=2, seconds=5)
        events.append(TimelineEvent(
            id=f"{invoice_id}-evt-6",
            timestamp=t6,
            time_display=t6.strftime("%I:%M %p"),
            relative_time=_relative_time_short(t6),
            event_type="pause",
            severity="warning",
            title="Awaiting human review",
            description=f"Agent paused: {reason}. Queued for operator decision.",
            agent_state="waiting",
            pause_reason=reason,
        ))
    elif status == "blocked":
        reason = inv.get("reason", "Critical error")
        events.append(TimelineEvent(
            id=f"{invoice_id}-evt-5",
            timestamp=t5,
            time_display=t5.strftime("%I:%M %p"),
            relative_time=_relative_time_short(t5),
            event_type="error",
            severity="error",
            title="Processing blocked",
            description=reason,
            agent_state="paused",
            pause_reason=reason,
            progress_current=4,
            progress_total=5,
        ))
    else:
        events.append(TimelineEvent(
            id=f"{invoice_id}-evt-5",
            timestamp=t5,
            time_display=t5.strftime("%I:%M %p"),
            relative_time=_relative_time_short(t5),
            event_type="validate",
            severity="success",
            title="All validations passed",
            description="Invoice verified against statement. Head count, amounts, and lot data match.",
            agent_state="processing",
            progress_current=4,
            progress_total=5,
        ))
        
        # Event 6: Ready
        t6 = base_time + timedelta(minutes=2, seconds=10)
        events.append(TimelineEvent(
            id=f"{invoice_id}-evt-6",
            timestamp=t6,
            time_display=t6.strftime("%I:%M %p"),
            relative_time=_relative_time_short(t6),
            event_type="approve",
            severity="success",
            title="Auto-approved",
            description="Invoice ready for posting. No human review required.",
            agent_state="complete",
            progress_current=5,
            progress_total=5,
        ))
    
    return events


@router.get(
    "/packages/{package_id}/invoices/{invoice_id}/timeline",
    response_model=TimelineResponse,
    summary="Get Invoice Timeline",
    description="Returns the agent activity timeline for an invoice. Supports polling for live updates."
)
async def get_invoice_timeline(
    package_id: str = Path(..., description="Package identifier"),
    invoice_id: str = Path(..., description="Invoice identifier"),
) -> TimelineResponse:
    """
    Get the agent processing timeline for an invoice.
    
    Returns:
    - Chronological list of processing events
    - Current agent state (processing, waiting_for_human, paused, complete)
    - Recommended polling interval
    
    Frontend should poll this endpoint every 15 seconds to show live progress.
    """
    if package_id not in MOCK_PACKAGES:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    inv = MOCK_INVOICES.get(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    
    if inv.get("package_id") != package_id:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found in package {package_id}")
    
    # Build timeline events
    events = _build_mock_timeline(invoice_id, inv)
    
    # Determine current state
    status = inv.get("status", "ready")
    if status == "review":
        current_state = "waiting_for_human"
    elif status == "blocked":
        current_state = "paused"
    elif status == "processing":
        current_state = "processing"
    else:
        current_state = "complete"
    
    return TimelineResponse(
        invoice_id=invoice_id,
        events=events,
        current_state=current_state,
        last_updated=datetime.now(),
        polling_interval_ms=15000,  # 15 seconds
    )


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


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

# Mock configuration data
MOCK_CONNECTORS: List[ConnectorConfig] = [
    ConnectorConfig(
        id="bc-prod",
        name="Business Central - Production",
        connector_type="business_central",
        status=ConnectorStatus.CONNECTED,
        tenant_id="a1b2c3d4-****-****-****-************",
        client_id="app-****-****-****-************",
        company_id="CRONUS USA",
        environment="production",
        last_connected=datetime.now() - timedelta(minutes=5),
        last_sync=datetime.now() - timedelta(hours=1),
    ),
]

MOCK_ENTITIES: List[EntityMapping] = [
    EntityMapping(
        id="ent-1",
        entity_name="Bovina Feeders II",
        entity_code="BF2",
        bc_company_id="d290f1ee-6c54-4b01-90e6-d701748f0851",
        aliases=["Bovina Feeders", "Bovina II", "BF2"],
        routing_keys=["owner:12345", "state:TX", "lot:BV-"],
        default_dimensions={"DEPT": "CATTLE", "LOCATION": "BOVINA"},
        is_active=True,
        invoice_count=847,
        last_used=datetime.now() - timedelta(hours=2),
    ),
    EntityMapping(
        id="ent-2",
        entity_name="Mesquite Cattle Feeders",
        entity_code="MCF",
        bc_company_id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
        aliases=["Mesquite Cattle", "Mesquite", "MCF"],
        routing_keys=["owner:67890", "state:TX", "lot:MQ-"],
        default_dimensions={"DEPT": "CATTLE", "LOCATION": "MESQUITE"},
        is_active=True,
        invoice_count=623,
        last_used=datetime.now() - timedelta(hours=4),
    ),
    EntityMapping(
        id="ent-3",
        entity_name="Caprock Cattle Company",
        entity_code="CCC",
        bc_company_id="b3a8e7f2-1234-5678-9abc-def012345678",
        aliases=["Caprock Cattle", "Caprock", "CCC"],
        routing_keys=["owner:11111", "state:TX", "lot:CR-"],
        default_dimensions={"DEPT": "CATTLE", "LOCATION": "CAPROCK"},
        is_active=True,
        invoice_count=412,
        last_used=datetime.now() - timedelta(days=1),
    ),
]

MOCK_VENDORS: List[VendorMapping] = [
    VendorMapping(
        id="vm-1",
        entity_id="ent-1",
        entity_name="Bovina Feeders II",
        alias_normalized="merck animal health",
        alias_original="Merck Animal Health",
        vendor_id="V00010",
        vendor_number="V00010",
        vendor_name="Merck Animal Health Inc.",
        match_count=156,
        created_by="system",
        created_at=datetime.now() - timedelta(days=90),
    ),
    VendorMapping(
        id="vm-2",
        entity_id="ent-1",
        entity_name="Bovina Feeders II",
        alias_normalized="zoetis",
        alias_original="Zoetis Inc",
        vendor_id="V00011",
        vendor_number="V00011",
        vendor_name="Zoetis Inc.",
        match_count=89,
        created_by="operator",
        created_at=datetime.now() - timedelta(days=60),
    ),
    VendorMapping(
        id="vm-3",
        entity_id="ent-2",
        entity_name="Mesquite Cattle Feeders",
        alias_normalized="cargill",
        alias_original="Cargill Animal Nutrition",
        vendor_id="V00020",
        vendor_number="V00020",
        vendor_name="Cargill Incorporated",
        match_count=234,
        created_by="system",
        created_at=datetime.now() - timedelta(days=120),
    ),
    VendorMapping(
        id="vm-4",
        entity_id="ent-1",
        entity_name="Bovina Feeders II",
        alias_normalized="purina mills",
        alias_original="Purina Mills LLC",
        vendor_id="V00012",
        vendor_number="V00012",
        vendor_name="Purina Animal Nutrition LLC",
        match_count=67,
        created_by="system",
        created_at=datetime.now() - timedelta(days=45),
    ),
    VendorMapping(
        id="vm-5",
        entity_id="ent-2",
        entity_name="Mesquite Cattle Feeders",
        alias_normalized="elanco",
        alias_original="Elanco Animal Health",
        vendor_id="V00021",
        vendor_number="V00021",
        vendor_name="Elanco Animal Health Incorporated",
        match_count=45,
        created_by="operator",
        created_at=datetime.now() - timedelta(days=30),
    ),
]


@router.get(
    "/configuration",
    response_model=ConfigurationResponse,
    summary="Get Configuration",
    description="Retrieve all configuration settings including connectors, entities, and vendor mappings."
)
async def get_configuration() -> ConfigurationResponse:
    """Get complete configuration state."""
    return ConfigurationResponse(
        connectors=MOCK_CONNECTORS,
        entities=MOCK_ENTITIES,
        vendors=MOCK_VENDORS,
        stats={
            "total_entities": len(MOCK_ENTITIES),
            "active_entities": sum(1 for e in MOCK_ENTITIES if e.is_active),
            "total_vendor_mappings": len(MOCK_VENDORS),
            "connectors_connected": sum(1 for c in MOCK_CONNECTORS if c.status == ConnectorStatus.CONNECTED),
        }
    )


@router.get(
    "/configuration/connectors",
    response_model=List[ConnectorConfig],
    summary="Get Connectors",
    description="List all configured ERP connectors."
)
async def get_connectors() -> List[ConnectorConfig]:
    """Get connector configurations."""
    return MOCK_CONNECTORS


@router.get(
    "/configuration/entities",
    response_model=List[EntityMapping],
    summary="Get Entity Mappings",
    description="List all entity/company routing mappings."
)
async def get_entity_mappings() -> List[EntityMapping]:
    """Get entity mappings."""
    return MOCK_ENTITIES


@router.get(
    "/configuration/vendors",
    response_model=List[VendorMapping],
    summary="Get Vendor Mappings",
    description="List all vendor alias mappings."
)
async def get_vendor_mappings(
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
) -> List[VendorMapping]:
    """Get vendor mappings, optionally filtered by entity."""
    if entity_id:
        return [v for v in MOCK_VENDORS if v.entity_id == entity_id]
    return MOCK_VENDORS


@router.post(
    "/configuration/connectors/{connector_id}/test",
    summary="Test Connector",
    description="Test connectivity to an ERP connector."
)
async def test_connector(
    connector_id: str = Path(..., description="Connector identifier"),
) -> dict:
    """Test connector connectivity."""
    connector = next((c for c in MOCK_CONNECTORS if c.id == connector_id), None)
    if not connector:
        raise HTTPException(status_code=404, detail=f"Connector {connector_id} not found")
    
    return {
        "success": True,
        "connector_id": connector_id,
        "latency_ms": 142,
        "message": "Connection successful",
        "details": {
            "api_version": "v2.0",
            "company_count": 3,
            "vendor_count": 127,
            "gl_account_count": 456,
        }
    }


# =============================================================================
# OBSERVABILITY / TRACING ENDPOINTS
# =============================================================================

@router.get(
    "/tracing/package/{ap_package_id}",
    summary="Get Package Tracing Info",
    description="Get workflow execution info for tracing a package through Temporal."
)
async def get_package_tracing(
    ap_package_id: str = Path(..., description="AP Package ID"),
) -> dict:
    """
    Get tracing information for a package.
    
    Returns:
        Workflow execution info, activity history, and Temporal Cloud UI link
    """
    from core.observability.tracing import get_tracing_info
    
    try:
        info = get_tracing_info(ap_package_id)
        return info.to_dict()
    except Exception as e:
        # Return minimal info if tracing data not available
        return {
            "ap_package_id": ap_package_id,
            "invoice_number": None,
            "workflow": None,
            "temporal_url": None,
            "activities": [],
            "stages": [],
            "error": str(e),
        }


@router.get(
    "/tracing/invoice/{ap_package_id}/{invoice_number}",
    summary="Get Invoice Tracing Info",
    description="Get workflow execution info for tracing a specific invoice."
)
async def get_invoice_tracing(
    ap_package_id: str = Path(..., description="AP Package ID"),
    invoice_number: str = Path(..., description="Invoice number"),
) -> dict:
    """
    Get tracing information for a specific invoice.
    
    Returns:
        Workflow execution info, activity history, and Temporal Cloud UI link
    """
    from core.observability.tracing import get_tracing_info
    
    try:
        info = get_tracing_info(ap_package_id, invoice_number)
        return info.to_dict()
    except Exception as e:
        return {
            "ap_package_id": ap_package_id,
            "invoice_number": invoice_number,
            "workflow": None,
            "temporal_url": None,
            "activities": [],
            "stages": [],
            "error": str(e),
        }


@router.get(
    "/metrics",
    summary="Get Pipeline Metrics",
    description="Get metrics for workflows, activities, and processing times."
)
async def get_pipeline_metrics() -> dict:
    """
    Get pipeline metrics summary.
    
    Returns:
        Workflow counts, activity counts, timing stats, queue backlogs
    """
    from core.observability.metrics import get_metrics
    
    try:
        metrics = get_metrics()
        return metrics.get_summary()
    except Exception as e:
        return {
            "error": str(e),
            "workflows": {"started": 0, "completed": 0, "failed": 0},
            "activities": {"started": 0, "completed": 0, "failed": 0, "retries": 0},
            "timings": {},
            "queues": {},
        }


@router.get(
    "/metrics/timings/{stage}",
    summary="Get Stage Timing Stats",
    description="Get timing statistics for a specific processing stage."
)
async def get_stage_timings(
    stage: str = Path(..., description="Stage name (e.g., 'activity.extract_invoice')"),
) -> dict:
    """
    Get timing statistics for a stage.
    
    Returns:
        Average and p95 processing times
    """
    from core.observability.metrics import get_metrics
    
    try:
        metrics = get_metrics()
        return {
            "stage": stage,
            **metrics.get_timing_stats(stage),
        }
    except Exception as e:
        return {
            "stage": stage,
            "average_ms": 0,
            "p95_ms": 0,
            "sample_count": 0,
            "error": str(e),
        }

