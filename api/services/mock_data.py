"""
Mock Data Service for Mission Control API.

Provides realistic mock data for development and testing.
This will be replaced with database queries in production.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import random

from models.api_responses import (
    # Enums
    PipelineStage,
    PackageStatus,
    InvoiceStatus,
    ValidationStatus,
    ReconciliationStatus,
    GLMappingStatus,
    StakeholderRole,
    AlertType,
    TrendDirection,
    
    # Models
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
    MetricItem,
    AlertItem,
    DetailSection,
    DetailListItem,
    ExtractedField,
    InvoiceLineItem,
    InvoiceTotals,
    AgentCommentary,
    GLCodingEntry,
    ValidationCheck,
    ReconciliationResult,
)


# =============================================================================
# MOCK PACKAGES DATA
# =============================================================================

MOCK_PACKAGES: Dict[str, dict] = {
    "PKG-2025-11-BF2-001": {
        "package_id": "PKG-2025-11-BF2-001",
        "feedlot_name": "Bovina Feeders Inc.",
        "feedlot_code": "BF2",
        "owner_name": "Sugar Mountain Livestock",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("164833.15"),
        "invoice_total": Decimal("164833.15"),
        "variance": Decimal("0.00"),
        "total_invoices": 24,
        "total_lots": 24,
        "ready_count": 22,
        "review_count": 2,
        "blocked_count": 0,
        "status": PackageStatus.REVIEW,
        "last_activity_at": datetime.now() - timedelta(minutes=5),
        "overall_confidence": 96,
        "primary_reason": "Entity unresolved",
        "reason_check_id": "entity_unresolved",
        "state_entered_at": datetime.now() - timedelta(hours=2),
    },
    "PKG-2025-11-MC1-001": {
        "package_id": "PKG-2025-11-MC1-001",
        "feedlot_name": "Mesquite Cattle Co.",
        "feedlot_code": "MC1",
        "owner_name": "Sugar Mountain Livestock",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("287341.18"),
        "invoice_total": Decimal("287341.18"),
        "variance": Decimal("0.00"),
        "total_invoices": 18,
        "total_lots": 15,
        "ready_count": 15,
        "review_count": 3,
        "blocked_count": 0,
        "status": PackageStatus.REVIEW,
        "last_activity_at": datetime.now() - timedelta(minutes=12),
        "overall_confidence": 94,
        "primary_reason": "GL in Suspense",
        "reason_check_id": "gl_suspense",
        "state_entered_at": datetime.now() - timedelta(hours=4),
    },
    "PKG-2025-11-PF3-001": {
        "package_id": "PKG-2025-11-PF3-001",
        "feedlot_name": "Panhandle Feedyard",
        "feedlot_code": "PF3",
        "owner_name": "Summit Cattle Co",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("156892.45"),
        "invoice_total": Decimal("156892.45"),
        "variance": Decimal("0.00"),
        "total_invoices": 15,
        "total_lots": 11,
        "ready_count": 15,
        "review_count": 0,
        "blocked_count": 0,
        "status": PackageStatus.READY,
        "last_activity_at": datetime.now() - timedelta(hours=1),
        "overall_confidence": 98,
        "primary_reason": None,
        "reason_check_id": None,
        "state_entered_at": datetime.now() - timedelta(hours=1),
    },
    "PKG-2025-11-CF4-001": {
        "package_id": "PKG-2025-11-CF4-001",
        "feedlot_name": "Canyon Feed",
        "feedlot_code": "CF4",
        "owner_name": "High Plains Ranch",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("90211.90"),
        "invoice_total": Decimal("86111.90"),
        "variance": Decimal("4100.00"),
        "total_invoices": 12,
        "total_lots": 9,
        "ready_count": 8,
        "review_count": 1,
        "blocked_count": 3,
        "status": PackageStatus.BLOCKED,
        "last_activity_at": datetime.now() - timedelta(hours=2),
        "overall_confidence": 87,
        "primary_reason": "B2 variance $4,100",
        "reason_check_id": "recon_variance",
        "state_entered_at": datetime.now() - timedelta(days=1, hours=4),
    },
    "PKG-2025-11-BF2-002": {
        "package_id": "PKG-2025-11-BF2-002",
        "feedlot_name": "Bovina Feeders Inc.",
        "feedlot_code": "BF2",
        "owner_name": "High Country Cattle",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("52340.00"),
        "invoice_total": Decimal("52340.00"),
        "variance": Decimal("0.00"),
        "total_invoices": 8,
        "total_lots": 8,
        "ready_count": 8,
        "review_count": 0,
        "blocked_count": 0,
        "status": PackageStatus.READY,
        "last_activity_at": datetime.now() - timedelta(hours=3),
        "primary_reason": None,
        "reason_check_id": None,
        "state_entered_at": datetime.now() - timedelta(hours=3),
        "overall_confidence": 99,
    },
    "PKG-2025-11-MC1-002": {
        "package_id": "PKG-2025-11-MC1-002",
        "feedlot_name": "Mesquite Cattle Co.",
        "feedlot_code": "MC1",
        "owner_name": "Valley View Ranch",
        "period": "November 2025",
        "statement_date": date(2025, 11, 30),
        "statement_total": Decimal("38921.50"),
        "invoice_total": Decimal("38921.50"),
        "variance": Decimal("0.00"),
        "total_invoices": 6,
        "total_lots": 6,
        "ready_count": 6,
        "review_count": 0,
        "blocked_count": 0,
        "status": PackageStatus.READY,
        "last_activity_at": datetime.now() - timedelta(hours=4),
        "overall_confidence": 98,
    },
}


# =============================================================================
# MOCK INVOICES DATA
# =============================================================================

MOCK_INVOICES: Dict[str, dict] = {
    # Bovina Package 1 invoices
    "INV-13304": {
        "invoice_id": "INV-13304",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-3927",
        "amount": Decimal("301.36"),
        "status": InvoiceStatus.REVIEW,
        "reason": "Medicine charge only, zero head count",
        "feed_type": "Medicine",
        "head_count": 0,
        "days_on_feed": 0,
        "cost_per_head": Decimal("0.00"),
        "confidence": 94,
        "invoice_date": date(2025, 11, 26),
    },
    "INV-13508": {
        "invoice_id": "INV-13508",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-4263",
        "amount": Decimal("7427.87"),
        "status": InvoiceStatus.REVIEW,
        "reason": "Contains credit adjustment (-$568.00)",
        "feed_type": "Finishing Ration",
        "head_count": 156,
        "days_on_feed": 31,
        "cost_per_head": Decimal("47.61"),
        "confidence": 94,
        "invoice_date": date(2025, 11, 26),
    },
    "INV-13287": {
        "invoice_id": "INV-13287",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-4033",
        "amount": Decimal("15518.02"),
        "status": InvoiceStatus.READY,
        "reason": None,
        "feed_type": "Hospital Feed",
        "head_count": 178,
        "days_on_feed": 67,
        "cost_per_head": Decimal("87.18"),
        "confidence": 98,
        "invoice_date": date(2025, 11, 26),
    },
    "INV-13288": {
        "invoice_id": "INV-13288",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-4034",
        "amount": Decimal("12847.50"),
        "status": InvoiceStatus.READY,
        "reason": None,
        "feed_type": "Finishing Ration",
        "head_count": 165,
        "days_on_feed": 52,
        "cost_per_head": Decimal("77.86"),
        "confidence": 97,
        "invoice_date": date(2025, 11, 26),
    },
    "INV-13289": {
        "invoice_id": "INV-13289",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-4035",
        "amount": Decimal("11234.00"),
        "status": InvoiceStatus.READY,
        "reason": None,
        "feed_type": "Starter Ration",
        "head_count": 142,
        "days_on_feed": 28,
        "cost_per_head": Decimal("79.11"),
        "confidence": 99,
        "invoice_date": date(2025, 11, 26),
    },
    "INV-13290": {
        "invoice_id": "INV-13290",
        "package_id": "PKG-2025-11-BF2-001",
        "lot_number": "20-4036",
        "amount": Decimal("9876.45"),
        "status": InvoiceStatus.READY,
        "reason": None,
        "feed_type": "Finishing Ration",
        "head_count": 134,
        "days_on_feed": 48,
        "cost_per_head": Decimal("73.70"),
        "confidence": 96,
        "invoice_date": date(2025, 11, 26),
    },
    # Mesquite Package invoices
    "INV-M2901": {
        "invoice_id": "INV-M2901",
        "package_id": "PKG-2025-11-MC1-001",
        "lot_number": "M-2901",
        "amount": Decimal("8742.30"),
        "status": InvoiceStatus.REVIEW,
        "reason": "Hospital feed >15%",
        "feed_type": "Hospital Feed",
        "head_count": 89,
        "days_on_feed": 45,
        "cost_per_head": Decimal("98.23"),
        "confidence": 92,
        "invoice_date": date(2025, 11, 28),
    },
    # Canyon Feed blocked invoices
    "INV-CF-4521": {
        "invoice_id": "INV-CF-4521",
        "package_id": "PKG-2025-11-CF4-001",
        "lot_number": "CF-2201",
        "amount": Decimal("4100.00"),
        "status": InvoiceStatus.BLOCKED,
        "reason": "Duplicate: Already posted in October",
        "feed_type": "Finishing Ration",
        "head_count": 67,
        "days_on_feed": 30,
        "cost_per_head": Decimal("61.19"),
        "confidence": 99,
        "invoice_date": date(2025, 10, 31),
    },
}


# =============================================================================
# MOCK INVOICE DETAILS
# =============================================================================

def get_mock_invoice_detail(invoice_id: str) -> Optional[InvoiceDetailResponse]:
    """Get detailed invoice data with line items, validation, etc."""
    inv = MOCK_INVOICES.get(invoice_id)
    if not inv:
        return None
    
    # Build detailed response based on invoice
    if invoice_id == "INV-13304":
        return InvoiceDetailResponse(
            invoice_id=inv["invoice_id"],
            lot_number=inv["lot_number"],
            amount=inv["amount"],
            status=inv["status"],
            reason=inv["reason"],
            feed_type=inv["feed_type"],
            head_count=inv["head_count"],
            days_on_feed=inv["days_on_feed"],
            cost_per_head=inv["cost_per_head"],
            confidence=inv["confidence"],
            extracted_fields=[
                ExtractedField(field_name="Invoice Number", value="INV-13304", confidence=99),
                ExtractedField(field_name="Invoice Date", value="2025-11-26", confidence=98),
                ExtractedField(field_name="Feedlot", value="Bovina", confidence=97),
                ExtractedField(field_name="Vendor Name", value="Bovina Feeders LLC", confidence=96),
                ExtractedField(field_name="Lot Number", value="20-3927", confidence=99),
                ExtractedField(field_name="Owner Number", value="2341", confidence=95),
                ExtractedField(field_name="Owner Name", value="Sugar Mountain Livestock", confidence=94),
                ExtractedField(field_name="Period", value="Nov 1-30, 2025", confidence=97),
                ExtractedField(field_name="Head Count", value="0", confidence=92),
                ExtractedField(field_name="Days on Feed", value="0", confidence=91),
            ],
            line_items=[
                InvoiceLineItem(
                    line_id=1,
                    description="Medicine - Individual",
                    gl_code="5300-01",
                    amount=Decimal("301.36"),
                    quantity=Decimal("1"),
                    unit="EA",
                    rate="301.36",
                    category="MEDICINE",
                    warning=None,
                ),
            ],
            totals=InvoiceTotals(
                subtotal=Decimal("301.36"),
                adjustments=Decimal("0.00"),
                total=Decimal("301.36"),
            ),
            agent_commentary=[
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=17),
                    time_display="10:43 AM",
                    icon="upload",
                    title="PDF uploaded",
                    description="via email integration",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="extract",
                    title="Extracted 1 line item",
                    description="GPT-4o Vision extraction completed in 2.3s",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="warn",
                    title="Zero head count detected",
                    description="Invoice shows medicine charge with 0 head",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=15),
                    time_display="10:44 AM",
                    icon="review",
                    title="Awaiting review",
                    description="Queued for human decision",
                ),
            ],
            gl_coding=[
                GLCodingEntry(
                    description="Medicine - Individual",
                    category="MEDICINE",
                    gl_code="5300-01",
                    status=GLMappingStatus.MAPPED,
                ),
            ],
            validation_checks=[
                ValidationCheck(field="Invoice Number", status=ValidationStatus.PASS, extracted="INV-13304", matched="INV-13304"),
                ValidationCheck(field="Total Amount", status=ValidationStatus.PASS, extracted="$301.36", matched="$301.36"),
                ValidationCheck(field="Lot Number", status=ValidationStatus.PASS, extracted="20-3927", matched="20-3927"),
                ValidationCheck(field="Head Count", status=ValidationStatus.WARN, extracted="0", matched="—", note="Zero head - verify lot status"),
            ],
            reconciliation=ReconciliationResult(
                statement_amount=Decimal("301.36"),
                invoice_amount=Decimal("301.36"),
                variance=Decimal("0.00"),
                status=ReconciliationStatus.MATCHED,
            ),
            source_pdf_url="/api/documents/INV-13304.pdf",
        )
    
    elif invoice_id == "INV-13508":
        return InvoiceDetailResponse(
            invoice_id=inv["invoice_id"],
            lot_number=inv["lot_number"],
            amount=inv["amount"],
            status=inv["status"],
            reason=inv["reason"],
            feed_type=inv["feed_type"],
            head_count=inv["head_count"],
            days_on_feed=inv["days_on_feed"],
            cost_per_head=inv["cost_per_head"],
            confidence=inv["confidence"],
            extracted_fields=[
                ExtractedField(field_name="Invoice Number", value="INV-13508", confidence=99),
                ExtractedField(field_name="Invoice Date", value="2025-11-26", confidence=98),
                ExtractedField(field_name="Feedlot", value="Bovina", confidence=97),
                ExtractedField(field_name="Lot Number", value="20-4263", confidence=99),
                ExtractedField(field_name="Head Count", value="156", confidence=98),
                ExtractedField(field_name="Days on Feed", value="31", confidence=97),
            ],
            line_items=[
                InvoiceLineItem(
                    line_id=1,
                    description="Feed & Rations",
                    gl_code="5100-01",
                    amount=Decimal("4481.25"),
                    quantity=Decimal("4836"),
                    unit="LBS",
                    rate="0.185/TON",
                    category="FEED",
                    warning="Unit mismatch: qty in LBS, rate in TON",
                ),
                InvoiceLineItem(
                    line_id=2,
                    description="Yardage (31 days)",
                    gl_code="5200-01",
                    amount=Decimal("2175.60"),
                    quantity=Decimal("156"),
                    unit="HD",
                    rate="0.45/HD/DAY",
                    category="YARDAGE",
                    warning=None,
                ),
                InvoiceLineItem(
                    line_id=3,
                    description="Veterinary - Processing",
                    gl_code="5300-01",
                    amount=Decimal("1950.00"),
                    quantity=Decimal("156"),
                    unit="HD",
                    rate="12.50/HD",
                    category="VET",
                    warning=None,
                ),
                InvoiceLineItem(
                    line_id=4,
                    description="Insurance",
                    gl_code="5400-01",
                    amount=Decimal("335.40"),
                    quantity=Decimal("156"),
                    unit="HD",
                    rate="2.15/HD",
                    category="INSURANCE",
                    warning=None,
                ),
                InvoiceLineItem(
                    line_id=5,
                    description="Misc Charge",
                    gl_code="9999-00",
                    amount=Decimal("524.00"),
                    quantity=Decimal("1"),
                    unit="EA",
                    rate="524.00",
                    category="UNCATEGORIZED",
                    warning=None,
                ),
                InvoiceLineItem(
                    line_id=6,
                    description="1HD MIDWEST Transfer Credit",
                    gl_code="9999-00",
                    amount=Decimal("-568.00"),
                    quantity=Decimal("1"),
                    unit="HD",
                    rate="-568.00",
                    category="CREDIT",
                    warning="Credit needs classification",
                ),
            ],
            totals=InvoiceTotals(
                subtotal=Decimal("9466.25"),
                adjustments=Decimal("-568.00"),
                total=Decimal("7427.87"),
            ),
            agent_commentary=[
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=17),
                    time_display="10:43 AM",
                    icon="upload",
                    title="PDF uploaded",
                    description="via email integration",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="extract",
                    title="Extracted 6 line items",
                    description="GPT-4o Vision extraction completed in 2.3s",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="warn",
                    title="Detected unit mismatch",
                    description="Line 1: qty in LBS, rate in TON",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="warn",
                    title="Credit adjustment found",
                    description="-$568.00 requires classification",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=16),
                    time_display="10:43 AM",
                    icon="info",
                    title="Line sum variance $0.12",
                    description="Above tolerance but within review threshold",
                ),
                AgentCommentary(
                    timestamp=datetime.now() - timedelta(hours=2, minutes=15),
                    time_display="10:44 AM",
                    icon="review",
                    title="Awaiting review",
                    description="Queued for human decision",
                ),
            ],
            gl_coding=[
                GLCodingEntry(description="Feed & Rations", category="FEED", gl_code="5100-01", status=GLMappingStatus.MAPPED),
                GLCodingEntry(description="Yardage (31 days)", category="YARDAGE", gl_code="5200-01", status=GLMappingStatus.MAPPED),
                GLCodingEntry(description="Veterinary - Processing", category="VET", gl_code="5300-01", status=GLMappingStatus.MAPPED),
                GLCodingEntry(description="Insurance", category="INSURANCE", gl_code="5400-01", status=GLMappingStatus.MAPPED),
                GLCodingEntry(description="Misc Charge", category="UNCATEGORIZED", gl_code="9999-00", status=GLMappingStatus.SUSPENSE),
                GLCodingEntry(description="1HD MIDWEST Transfer Credit", category="CREDIT", gl_code="9999-00", status=GLMappingStatus.SUSPENSE),
            ],
            validation_checks=[
                ValidationCheck(field="Invoice Number", status=ValidationStatus.PASS, extracted="INV-13508", matched="INV-13508"),
                ValidationCheck(field="Total Amount", status=ValidationStatus.PASS, extracted="$7,427.87", matched="$7,427.87"),
                ValidationCheck(field="Line Sum", status=ValidationStatus.WARN, extracted="$7,427.99", matched="$7,427.87", note="$0.12 variance"),
                ValidationCheck(field="Credit Amount", status=ValidationStatus.WARN, extracted="-$568.00", matched="—", note="Needs classification"),
            ],
            reconciliation=ReconciliationResult(
                statement_amount=Decimal("7427.87"),
                invoice_amount=Decimal("7427.87"),
                variance=Decimal("0.00"),
                status=ReconciliationStatus.MATCHED,
            ),
            source_pdf_url="/api/documents/INV-13508.pdf",
        )
    
    # Generic invoice detail for other invoices
    return InvoiceDetailResponse(
        invoice_id=inv["invoice_id"],
        lot_number=inv["lot_number"],
        amount=inv["amount"],
        status=inv["status"],
        reason=inv.get("reason"),
        feed_type=inv.get("feed_type"),
        head_count=inv.get("head_count", 0),
        days_on_feed=inv.get("days_on_feed", 0),
        cost_per_head=inv.get("cost_per_head", Decimal("0")),
        confidence=inv.get("confidence", 95),
        extracted_fields=[
            ExtractedField(field_name="Invoice Number", value=inv["invoice_id"], confidence=99),
            ExtractedField(field_name="Lot Number", value=inv["lot_number"], confidence=98),
            ExtractedField(field_name="Amount", value=str(inv["amount"]), confidence=97),
        ],
        line_items=[
            InvoiceLineItem(
                line_id=1,
                description=inv.get("feed_type", "Feed Charges"),
                gl_code="5100-01",
                amount=inv["amount"],
                quantity=Decimal(str(inv.get("head_count", 1))),
                unit="HD",
                rate=str(inv.get("cost_per_head", inv["amount"])),
                category="FEED",
                warning=None,
            ),
        ],
        totals=InvoiceTotals(
            subtotal=inv["amount"],
            adjustments=Decimal("0.00"),
            total=inv["amount"],
        ),
        agent_commentary=[
            AgentCommentary(
                timestamp=datetime.now() - timedelta(hours=1),
                time_display="11:00 AM",
                icon="extract",
                title="Extracted successfully",
                description="All fields extracted with high confidence",
            ),
        ],
        gl_coding=[
            GLCodingEntry(
                description=inv.get("feed_type", "Feed Charges"),
                category="FEED",
                gl_code="5100-01",
                status=GLMappingStatus.MAPPED,
            ),
        ],
        validation_checks=[
            ValidationCheck(field="Invoice Number", status=ValidationStatus.PASS, extracted=inv["invoice_id"], matched=inv["invoice_id"]),
            ValidationCheck(field="Total Amount", status=ValidationStatus.PASS, extracted=f"${inv['amount']}", matched=f"${inv['amount']}"),
        ],
        reconciliation=ReconciliationResult(
            statement_amount=inv["amount"],
            invoice_amount=inv["amount"],
            variance=Decimal("0.00"),
            status=ReconciliationStatus.MATCHED,
        ),
        source_pdf_url=f"/api/documents/{inv['invoice_id']}.pdf",
    )


# =============================================================================
# DRILLDOWN DATA
# =============================================================================

def get_mock_drilldown(role: StakeholderRole) -> DrilldownResponse:
    """Get role-based drilldown data."""
    
    if role == StakeholderRole.CFO:
        return DrilldownResponse(
            role=role,
            title="Financial Overview",
            icon="DollarSign",
            metrics=[
                MetricItem(label="Total Pipeline", value="$847K", raw_value=Decimal("847234.50"), trend="+12%", trend_direction=TrendDirection.UP),
                MetricItem(label="Ready to Post", value="$759K", raw_value=Decimal("758923.45"), trend="89%", trend_direction=TrendDirection.GOOD),
                MetricItem(label="Blocked Dollars", value="$65K", raw_value=Decimal("65432.10"), trend="-23%", trend_direction=TrendDirection.DOWN),
                MetricItem(label="Avg Cost/Head", value="$187.42", raw_value=Decimal("187.42"), trend="+2.1%", trend_direction=TrendDirection.NEUTRAL),
            ],
            alerts=[
                AlertItem(alert_type=AlertType.WARN, message="$42K blocked due to missing source documents", is_actionable=True, action_url="/dashboard/review-queue?reason=missing_doc"),
                AlertItem(alert_type=AlertType.INFO, message="Feed costs trending 2.1% above 3-month average", is_actionable=False),
                AlertItem(alert_type=AlertType.ERROR, message="$568 credit in suspense needs classification", is_actionable=True, action_url="/dashboard/invoices-v2/INV-13508"),
            ],
            details=[
                DetailSection(title="Reconciliation Status", items=[
                    DetailListItem(label="Perfect Match", value="9 packages", status="success"),
                    DetailListItem(label="Within Tolerance", value="2 packages", status="warn"),
                    DetailListItem(label="Needs Attention", value="1 package", status="error"),
                ]),
                DetailSection(title="Cost Outliers (>10% variance)", items=[
                    DetailListItem(label="Lot 20-4353 (Bovina)", value="$218.59/head (+16.6%)", status="error"),
                    DetailListItem(label="Lot M-2847 (Mesquite)", value="$224.87/head (+15.2%)", status="error"),
                    DetailListItem(label="Lot 20-4260 (Bovina)", value="$203.14/head (+8.4%)", status="warn"),
                ]),
                DetailSection(title="Suspense Postings", items=[
                    DetailListItem(label="20-3927 Medicine charge", value="$301.36 → GL 9999-00", status="warn"),
                    DetailListItem(label="20-4263 MIDWEST credit", value="-$568.00 → GL 9999-00", status="warn"),
                ]),
            ],
            as_of=datetime.now(),
        )
    
    elif role == StakeholderRole.COO:
        return DrilldownResponse(
            role=role,
            title="Operations Overview",
            icon="Building2",
            metrics=[
                MetricItem(label="Total Lots", value="47", raw_value=Decimal("47"), trend="+5", trend_direction=TrendDirection.UP),
                MetricItem(label="Lots Matched", value="44", raw_value=Decimal("44"), trend="94%", trend_direction=TrendDirection.GOOD),
                MetricItem(label="Problem Lots", value="6", raw_value=Decimal("6"), trend="-2", trend_direction=TrendDirection.DOWN),
                MetricItem(label="Death Loss", value="23", raw_value=Decimal("23"), trend="+9", trend_direction=TrendDirection.BAD),
            ],
            alerts=[
                AlertItem(alert_type=AlertType.ERROR, message="Lot M-2901: 8 deaths (RESPIRATORY) - 4x above average", is_actionable=True),
                AlertItem(alert_type=AlertType.WARN, message="3 lots with hospital feed >10% for 3+ months", is_actionable=True),
                AlertItem(alert_type=AlertType.WARN, message="2 lots missing invoice documents", is_actionable=True),
            ],
            details=[
                DetailSection(title="Lot Accountability", items=[
                    DetailListItem(label="On Statements", value="47 lots", status="neutral"),
                    DetailListItem(label="Matched to Invoices", value="44 lots", status="success"),
                    DetailListItem(label="Missing Invoices", value="2 lots", status="error"),
                    DetailListItem(label="Explained Exceptions", value="1 lot", status="warn"),
                ]),
                DetailSection(title="Problem Lots (Repeated Warnings)", items=[
                    DetailListItem(label="M-2901 (Mesquite)", value="6 warns: Death spike, Hospital feed", status="error"),
                    DetailListItem(label="20-3927 (Bovina)", value="5 warns: Missing inv, Zero head", status="error"),
                    DetailListItem(label="20-4033 (Bovina)", value="4 warns: Hospital 12%, High medicine", status="warn"),
                ]),
                DetailSection(title="Death Loss by Feedlot", items=[
                    DetailListItem(label="Mesquite Cattle", value="14 deaths (4 lots) - RESPIRATORY", status="error"),
                    DetailListItem(label="Bovina Feeders", value="6 deaths (3 lots) - MECHANICAL", status="warn"),
                    DetailListItem(label="Panhandle Feedyard", value="3 deaths (2 lots) - UNKNOWN", status="neutral"),
                ]),
            ],
            as_of=datetime.now(),
        )
    
    elif role == StakeholderRole.CIO:
        return DrilldownResponse(
            role=role,
            title="System & Controls",
            icon="Shield",
            metrics=[
                MetricItem(label="Success Rate", value="98.7%", raw_value=Decimal("98.7"), trend="+0.3%", trend_direction=TrendDirection.GOOD),
                MetricItem(label="Avg Processing", value="4.2 sec", raw_value=Decimal("4.2"), trend="-0.8s", trend_direction=TrendDirection.DOWN),
                MetricItem(label="Auto-Approval", value="89%", raw_value=Decimal("89"), trend="+3%", trend_direction=TrendDirection.UP),
                MetricItem(label="Uptime", value="99.9%", raw_value=Decimal("99.9"), trend="30 days", trend_direction=TrendDirection.GOOD),
            ],
            alerts=[
                AlertItem(alert_type=AlertType.SUCCESS, message="12 duplicate posting attempts successfully blocked", is_actionable=False),
                AlertItem(alert_type=AlertType.INFO, message="2 manual overrides this period (both with approval)", is_actionable=False),
                AlertItem(alert_type=AlertType.WARN, message="P95 processing time at 12.8s (threshold: 15s)", is_actionable=False),
            ],
            details=[
                DetailSection(title="Processing Stats", items=[
                    DetailListItem(label="Invoices Processed", value="210 this period", status="neutral"),
                    DetailListItem(label="Auto-Approved", value="187 (89%)", status="success"),
                    DetailListItem(label="Human Reviewed", value="21 (10%)", status="warn"),
                    DetailListItem(label="Overridden", value="2 (1%)", status="neutral"),
                ]),
                DetailSection(title="Idempotency & Safety", items=[
                    DetailListItem(label="Duplicate Attempts", value="12 blocked", status="success"),
                    DetailListItem(label="Posting Registry", value="4,287 entries", status="neutral"),
                    DetailListItem(label="Last Failure", value="3 days ago", status="success"),
                ]),
                DetailSection(title="Audit Log", items=[
                    DetailListItem(label="Total Entries", value="1,842 this period", status="neutral"),
                    DetailListItem(label="Edits with Approval", value="23", status="success"),
                    DetailListItem(label="Unauthorized Edits", value="0", status="success"),
                ]),
            ],
            as_of=datetime.now(),
        )
    
    else:  # Accounting
        return DrilldownResponse(
            role=role,
            title="Audit & Compliance",
            icon="FileCheck",
            metrics=[
                MetricItem(label="Fully Traceable", value="187", raw_value=Decimal("187"), trend="94%", trend_direction=TrendDirection.GOOD),
                MetricItem(label="Credits Classified", value="7/8", raw_value=Decimal("7"), trend="1 pending", trend_direction=TrendDirection.WARN),
                MetricItem(label="Duplicates Blocked", value="1", raw_value=Decimal("1"), trend="$4,100", trend_direction=TrendDirection.GOOD),
                MetricItem(label="Period Consistency", value="196/200", raw_value=Decimal("196"), trend="98%", trend_direction=TrendDirection.GOOD),
            ],
            alerts=[
                AlertItem(alert_type=AlertType.ERROR, message="INV-13304 duplicate: Already posted in October ($4,100)", is_actionable=True),
                AlertItem(alert_type=AlertType.WARN, message="1 credit pending classification: -$568 MIDWEST transfer", is_actionable=True),
                AlertItem(alert_type=AlertType.INFO, message="4 cross-period invoices flagged and reviewed", is_actionable=False),
            ],
            details=[
                DetailSection(title="Traceability", items=[
                    DetailListItem(label="Fully Traceable", value="187 invoices", status="success"),
                    DetailListItem(label="Partial Trace", value="12 invoices", status="warn"),
                    DetailListItem(label="No Trace", value="1 invoice", status="error"),
                ]),
                DetailSection(title="Credit Handling", items=[
                    DetailListItem(label="Credits Identified", value="8 total", status="neutral"),
                    DetailListItem(label="Properly Classified", value="7 credits", status="success"),
                    DetailListItem(label="Pending Classification", value="1 credit (-$568)", status="warn"),
                ]),
                DetailSection(title="Duplicate Prevention", items=[
                    DetailListItem(label="Potential Duplicates", value="2 detected", status="neutral"),
                    DetailListItem(label="Confirmed & Blocked", value="1 (INV-13304)", status="success"),
                    DetailListItem(label="False Positives", value="1 (released)", status="neutral"),
                ]),
            ],
            as_of=datetime.now(),
        )


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


def _age_in_state(dt: datetime) -> str:
    """Convert datetime to compact age string (e.g., '4d', '12h', '35m')."""
    delta = datetime.now() - dt
    if delta.days > 0:
        return f"{delta.days}d"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"{hours}h"
    minutes = delta.seconds // 60
    if minutes > 0:
        return f"{minutes}m"
    return "0m"


def build_package_summary(pkg: dict) -> PackageSummary:
    """Build PackageSummary from mock data dict."""
    # Calculate age in state
    state_entered = pkg.get("state_entered_at", pkg["last_activity_at"])
    age = _age_in_state(state_entered)
    
    return PackageSummary(
        package_id=pkg["package_id"],
        feedlot_name=pkg["feedlot_name"],
        feedlot_code=pkg["feedlot_code"],
        owner_name=pkg["owner_name"],
        total_invoices=pkg["total_invoices"],
        total_lots=pkg["total_lots"],
        ready_count=pkg["ready_count"],
        review_count=pkg["review_count"],
        blocked_count=pkg["blocked_count"],
        total_dollars=pkg["statement_total"],
        status=pkg["status"],
        statement_date=pkg["statement_date"],
        last_activity=_relative_time(pkg["last_activity_at"]),
        last_activity_at=pkg["last_activity_at"],
        primary_reason=pkg.get("primary_reason"),
        reason_check_id=pkg.get("reason_check_id"),
        age_in_state=age,
    )


def build_invoice_summary(inv: dict) -> InvoiceSummary:
    """Build InvoiceSummary from mock data dict."""
    return InvoiceSummary(
        invoice_id=inv["invoice_id"],
        lot_number=inv["lot_number"],
        amount=inv["amount"],
        status=inv["status"],
        reason=inv.get("reason"),
        feed_type=inv.get("feed_type"),
        head_count=inv.get("head_count"),
        days_on_feed=inv.get("days_on_feed"),
        cost_per_head=inv.get("cost_per_head"),
        confidence=inv.get("confidence"),
    )
