"""Core data models - ERP-neutral canonical types.

This package contains all canonical data models that are intentionally
independent of any specific ERP system.
"""

from core.models.canonical import (
    # Base
    CanonicalBase,
    DecimalValue,
    IntValue,
    DateValue,
    
    # Common entities
    Feedlot,
    Owner,
    DocumentMetadata,
    
    # Statement
    StatementDocument,
    StatementLotReference,
    StatementTransaction,
    StatementSummaryRow,
    
    # Invoice
    InvoiceDocument,
    InvoiceLineItem,
    InvoiceTotals,
    LotInfo,
    CattleInventory,
    PerformanceMetric,
    FeedingExpenseLine,
    FinancialSummaryLine,
    CurrentPeriodTransaction,
    FeedingHistoryRow,
    
    # Death report
    DeadsReportDocument,
    DeathEvent,
)

from core.models.refs import (
    DataReference,
    ExtractedPackageRefs,
    ReconciliationReport,
    AuditEvent,
    AuditSeverity,
)

__all__ = [
    # Base
    "CanonicalBase",
    "DecimalValue",
    "IntValue",
    "DateValue",
    
    # Common entities
    "Feedlot",
    "Owner",
    "DocumentMetadata",
    
    # Statement
    "StatementDocument",
    "StatementLotReference",
    "StatementTransaction",
    "StatementSummaryRow",
    
    # Invoice
    "InvoiceDocument",
    "InvoiceLineItem",
    "InvoiceTotals",
    "LotInfo",
    "CattleInventory",
    "PerformanceMetric",
    "FeedingExpenseLine",
    "FinancialSummaryLine",
    "CurrentPeriodTransaction",
    "FeedingHistoryRow",
    
    # Death report
    "DeadsReportDocument",
    "DeathEvent",
    
    # References
    "DataReference",
    "ExtractedPackageRefs",
    "ReconciliationReport",
    "AuditEvent",
    "AuditSeverity",
]
