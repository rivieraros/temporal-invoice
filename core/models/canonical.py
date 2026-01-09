"""Core canonical data models - ERP-neutral extraction models.

These models represent the extracted data in a standardized format
that is independent of any specific ERP system (Business Central, SAP, etc.).

ERP-specific field mappings are handled in /connectors/ and /core/mapping/.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated


# =============================================================================
# Value Parsers (handle various input formats from LLM extraction)
# =============================================================================

def _parse_decimal(value):
    """Parse decimal from various formats (string with $ or commas, floats, etc.)."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        s = s.replace("$", "").replace(",", "")
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        return Decimal(s)
    return value


def _parse_int(value):
    """Parse integer from various formats."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if s == "":
            return None
        return int(float(s))
    return value


def _parse_date(value):
    """Parse date from various string formats."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {s}")
    return value


# Annotated types for automatic parsing
DecimalValue = Annotated[Decimal, BeforeValidator(_parse_decimal)]
IntValue = Annotated[int, BeforeValidator(_parse_int)]
DateValue = Annotated[date, BeforeValidator(_parse_date)]


# =============================================================================
# Base Model
# =============================================================================

class CanonicalBase(BaseModel):
    """Base model for all canonical data structures."""
    model_config = ConfigDict(populate_by_name=True)


# =============================================================================
# Common Entities (ERP-Neutral)
# =============================================================================

class Feedlot(CanonicalBase):
    """Feedlot information extracted from documents."""
    name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None


class Owner(CanonicalBase):
    """Cattle owner information extracted from documents."""
    owner_number: Optional[str] = None
    name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None


class DocumentMetadata(CanonicalBase):
    """Metadata about document extraction."""
    source_file: Optional[str] = None
    page_count: Optional[int] = None
    extracted_at: Optional[datetime] = None


# =============================================================================
# Statement Models
# =============================================================================

class StatementLotReference(CanonicalBase):
    """A lot/invoice reference line on a statement."""
    lot_number: Optional[str] = None
    invoice_number: Optional[str] = None
    statement_charge: Optional[DecimalValue] = None
    ending_balance: Optional[DecimalValue] = None
    description: Optional[str] = None


class StatementTransaction(CanonicalBase):
    """A transaction line on a statement."""
    lot_number: Optional[str] = None
    date: Optional[DateValue] = None
    ref_number: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    principal: Optional[DecimalValue] = None
    interest: Optional[DecimalValue] = None
    total: Optional[DecimalValue] = None
    charge: Optional[DecimalValue] = None
    credit: Optional[DecimalValue] = None


class StatementSummaryRow(CanonicalBase):
    """Summary row on a statement (category totals)."""
    category: Optional[str] = None
    beginning_balance: Optional[DecimalValue] = None
    statement_charges: Optional[DecimalValue] = None
    statement_credits: Optional[DecimalValue] = None
    amount_due: Optional[DecimalValue] = None


class StatementDocument(CanonicalBase):
    """Complete statement document - ERP neutral."""
    feedlot: Optional[Feedlot] = None
    owner: Optional[Owner] = None
    statement_date: Optional[DateValue] = None
    period_start: Optional[DateValue] = None
    period_end: Optional[DateValue] = None
    total_balance: Optional[DecimalValue] = None
    summary_rows: List[StatementSummaryRow] = Field(default_factory=list)
    transactions: List[StatementTransaction] = Field(default_factory=list)
    lot_references: List[StatementLotReference] = Field(default_factory=list)
    notes: Optional[str] = None
    document_metadata: Optional[DocumentMetadata] = None


# =============================================================================
# Invoice Models
# =============================================================================

class LotInfo(CanonicalBase):
    """Lot information on an invoice."""
    lot_number: Optional[str] = None
    pen: Optional[str] = None
    home_pen: Optional[str] = None
    sex: Optional[str] = None
    date_in: Optional[DateValue] = None
    ownership_pct: Optional[DecimalValue] = None


class CattleInventory(CanonicalBase):
    """Cattle inventory counts on an invoice."""
    head_received: Optional[IntValue] = None
    head_shipped: Optional[IntValue] = None
    head_out: Optional[IntValue] = None
    deaths: Optional[IntValue] = None
    current_head: Optional[IntValue] = None
    live_head: Optional[DecimalValue] = None
    death_loss_pct: Optional[DecimalValue] = None


class InvoiceLineItem(CanonicalBase):
    """A charge line item on an invoice."""
    description: str
    rate: Optional[DecimalValue] = None
    rate_unit: Optional[str] = None
    quantity: Optional[DecimalValue] = None
    quantity_unit: Optional[str] = None
    ownership_pct: Optional[DecimalValue] = None
    total: Optional[DecimalValue] = None


class InvoiceTotals(CanonicalBase):
    """Total amounts on an invoice."""
    total_period_charges: Optional[DecimalValue] = None
    total_amount_due: Optional[DecimalValue] = None


class PerformanceMetric(CanonicalBase):
    """Performance metric from an invoice."""
    metric_name: str
    ptd_value: Optional[DecimalValue] = None
    ltd_value: Optional[DecimalValue] = None
    unit: Optional[str] = None


class FeedingExpenseLine(CanonicalBase):
    """Feeding expense breakdown line."""
    category: str
    total_amount: Optional[DecimalValue] = None
    avg_per_head: Optional[DecimalValue] = None
    cog_per_cwt: Optional[DecimalValue] = None


class FinancialSummaryLine(CanonicalBase):
    """Financial summary line (current vs previous)."""
    label: str
    current: Optional[DecimalValue] = None
    previous: Optional[DecimalValue] = None
    total: Optional[DecimalValue] = None


class CurrentPeriodTransaction(CanonicalBase):
    """Transaction within the current period."""
    date: Optional[DateValue] = None
    head: Optional[DecimalValue] = None
    type: Optional[str] = None
    pay_weight: Optional[DecimalValue] = None
    amount: Optional[DecimalValue] = None
    note: Optional[str] = None


class FeedingHistoryRow(CanonicalBase):
    """Feeding history row (historical comparison)."""
    period_label: str
    live: Optional[DecimalValue] = None
    in_: Optional[DecimalValue] = Field(default=None, alias="in")
    ship: Optional[DecimalValue] = None
    trans: Optional[DecimalValue] = None
    dead: Optional[DecimalValue] = None
    avg: Optional[DecimalValue] = None
    hd_days_total: Optional[DecimalValue] = None
    hd_days_per_day: Optional[DecimalValue] = None
    total_pounds_fed: Optional[DecimalValue] = None
    avg_daily_consumption: Optional[DecimalValue] = None
    cog_feed: Optional[DecimalValue] = None
    cog_other: Optional[DecimalValue] = None
    cog_total: Optional[DecimalValue] = None


class InvoiceDocument(CanonicalBase):
    """Complete invoice document - ERP neutral."""
    feedlot: Optional[Feedlot] = None
    owner: Optional[Owner] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[DateValue] = None
    statement_date: Optional[DateValue] = None
    lot: Optional[LotInfo] = None
    cattle_inventory: Optional[CattleInventory] = None
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    totals: Optional[InvoiceTotals] = None
    performance_metrics: List[PerformanceMetric] = Field(default_factory=list)
    feeding_expense_summary: List[FeedingExpenseLine] = Field(default_factory=list)
    financial_summary: List[FinancialSummaryLine] = Field(default_factory=list)
    current_period_transactions: List[CurrentPeriodTransaction] = Field(default_factory=list)
    feeding_history: List[FeedingHistoryRow] = Field(default_factory=list)
    notes: Optional[str] = None
    document_metadata: Optional[DocumentMetadata] = None


# =============================================================================
# Death Report Models
# =============================================================================

class DeathEvent(CanonicalBase):
    """Individual death event record."""
    date_time: Optional[datetime] = None
    tag_number: Optional[str] = None
    lot_number: Optional[str] = None
    pen: Optional[str] = None
    owner_name: Optional[str] = None
    sex: Optional[str] = None
    rider: Optional[str] = None
    days_on_feed: Optional[DecimalValue] = None
    diagnosis: Optional[str] = None
    location: Optional[str] = None
    treatment_cost: Optional[DecimalValue] = None
    first_pull_dof: Optional[DecimalValue] = None
    pull_count: Optional[DecimalValue] = None
    days_between_death_treat: Optional[DecimalValue] = None


class DeadsReportDocument(CanonicalBase):
    """Death report document - ERP neutral."""
    feedlot: Optional[Feedlot] = None
    owner: Optional[Owner] = None
    report_date: Optional[DateValue] = None
    period_start: Optional[DateValue] = None
    period_end: Optional[DateValue] = None
    death_events: List[DeathEvent] = Field(default_factory=list)
    notes: Optional[str] = None
    document_metadata: Optional[DocumentMetadata] = None
