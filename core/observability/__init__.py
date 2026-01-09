"""
Observability Module for AP Automation Pipeline

Provides:
- Structured logging with correlation IDs
- Metrics collection (workflows, activities, processing times)
- Tracing support for linking UI → Temporal workflows
"""

from core.observability.metrics import (
    MetricsCollector,
    get_metrics,
    record_workflow_started,
    record_workflow_completed,
    record_workflow_failed,
    record_activity_started,
    record_activity_completed,
    record_activity_retry,
    record_processing_time,
)

from core.observability.logging import (
    get_logger,
    CorrelationContext,
    with_correlation,
)

from core.observability.tracing import (
    TracingInfo,
    get_tracing_info,
    store_workflow_id,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "get_metrics",
    "record_workflow_started",
    "record_workflow_completed",
    "record_workflow_failed",
    "record_activity_started",
    "record_activity_completed",
    "record_activity_retry",
    "record_processing_time",
    # Logging
    "get_logger",
    "CorrelationContext",
    "with_correlation",
    # Tracing
    "TracingInfo",
    "get_tracing_info",
    "store_workflow_id",
]
