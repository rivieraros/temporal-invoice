"""
Structured Logging with Correlation IDs

Provides logging utilities that automatically include:
- ap_package_id: Links logs to a specific package
- invoice_number: Links logs to a specific invoice  
- workflow_id: Links logs to Temporal workflow execution
- activity_id: Links logs to specific activity execution

Usage:
    from core.observability.logging import get_logger, with_correlation
    
    logger = get_logger(__name__)
    
    with with_correlation(ap_package_id="PKG-001", workflow_id="wf-123"):
        logger.info("Processing invoice")  # Automatically includes correlation IDs
"""

import json
import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager


# =============================================================================
# Correlation Context
# =============================================================================

@dataclass
class CorrelationContext:
    """Context for correlating logs across workflow execution."""
    ap_package_id: Optional[str] = None
    invoice_number: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    task_queue: Optional[str] = None
    
    # Additional context
    feedlot_type: Optional[str] = None
    stage: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def merge(self, **kwargs) -> "CorrelationContext":
        """Create a new context with merged values."""
        data = self.to_dict()
        data.update({k: v for k, v in kwargs.items() if v is not None})
        return CorrelationContext(**data)


# Context variable for async/thread-safe correlation
_correlation_context: ContextVar[CorrelationContext] = ContextVar(
    "correlation_context",
    default=CorrelationContext()
)


def get_correlation_context() -> CorrelationContext:
    """Get the current correlation context."""
    return _correlation_context.get()


def set_correlation_context(ctx: CorrelationContext) -> None:
    """Set the current correlation context."""
    _correlation_context.set(ctx)


@contextmanager
def with_correlation(**kwargs):
    """
    Context manager to set correlation IDs for logging.
    
    Usage:
        with with_correlation(ap_package_id="PKG-001", workflow_id="wf-123"):
            logger.info("Processing")  # Will include ap_package_id and workflow_id
    """
    old_ctx = get_correlation_context()
    new_ctx = old_ctx.merge(**kwargs)
    token = _correlation_context.set(new_ctx)
    try:
        yield new_ctx
    finally:
        _correlation_context.reset(token)


# =============================================================================
# Structured JSON Formatter
# =============================================================================

class StructuredFormatter(logging.Formatter):
    """
    JSON formatter that includes correlation context.
    
    Output format:
    {
        "timestamp": "2024-01-09T12:00:00.000Z",
        "level": "INFO",
        "logger": "activities.extract",
        "message": "Extracting invoice",
        "ap_package_id": "PKG-001",
        "workflow_id": "wf-123",
        "duration_ms": 1500
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Base log structure
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation context
        ctx = get_correlation_context()
        log_data.update(ctx.to_dict())
        
        # Add extra fields from log record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter that includes key correlation IDs.
    
    Output format:
    2024-01-09 12:00:00 [INFO] activities.extract [PKG-001/wf-123]: Extracting invoice
    """
    
    def format(self, record: logging.LogRecord) -> str:
        ctx = get_correlation_context()
        
        # Build correlation prefix
        correlation_parts = []
        if ctx.ap_package_id:
            correlation_parts.append(ctx.ap_package_id)
        if ctx.workflow_id:
            # Truncate workflow_id for readability
            wf_short = ctx.workflow_id[:12] if len(ctx.workflow_id) > 12 else ctx.workflow_id
            correlation_parts.append(wf_short)
        if ctx.invoice_number:
            correlation_parts.append(f"inv:{ctx.invoice_number}")
        
        correlation = "/".join(correlation_parts) if correlation_parts else "-"
        
        # Format timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Build message
        msg = f"{timestamp} [{record.levelname:5}] {record.name} [{correlation}]: {record.getMessage()}"
        
        # Add exception if present
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        
        return msg


# =============================================================================
# Logger with Correlation Support
# =============================================================================

class CorrelatedLogger:
    """
    Logger wrapper that automatically includes correlation context.
    
    Also supports adding extra fields to individual log calls.
    """
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Log with extra fields support."""
        extra_fields = kwargs.pop("extra_fields", {})
        
        # Create a custom record with extra fields
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown file)",
            0,
            msg,
            args,
            None,
        )
        record.extra_fields = extra_fields
        
        self._logger.handle(record)
    
    def debug(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        if self._logger.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        kwargs["exc_info"] = True
        self.error(msg, *args, **kwargs)
    
    # Delegate other methods
    def setLevel(self, level):
        self._logger.setLevel(level)
    
    def isEnabledFor(self, level):
        return self._logger.isEnabledFor(level)


# =============================================================================
# Logger Factory
# =============================================================================

_loggers: Dict[str, CorrelatedLogger] = {}
_configured = False


def configure_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    include_temporal: bool = True,
):
    """
    Configure logging for the application.
    
    Args:
        level: Logging level
        json_format: If True, use JSON format; otherwise human-readable
        include_temporal: If True, also configure Temporal SDK loggers
    """
    global _configured
    
    if _configured:
        return
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Set formatter
    if json_format:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(HumanReadableFormatter())
    
    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    
    # Configure specific loggers
    for logger_name in ["activities", "workflows", "api", "core"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    if include_temporal:
        # Temporal SDK logs - keep at INFO to see workflow events
        logging.getLogger("temporalio").setLevel(logging.INFO)
    
    _configured = True


def get_logger(name: str) -> CorrelatedLogger:
    """
    Get a correlated logger for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        CorrelatedLogger instance
    """
    if name not in _loggers:
        # Ensure logging is configured
        if not _configured:
            configure_logging()
        
        base_logger = logging.getLogger(name)
        _loggers[name] = CorrelatedLogger(base_logger)
    
    return _loggers[name]


# =============================================================================
# Convenience Functions for Activities/Workflows
# =============================================================================

def log_activity_start(activity_name: str, **kwargs):
    """Log activity start with correlation."""
    logger = get_logger(f"activities.{activity_name}")
    logger.info(f"Activity started: {activity_name}", extra_fields=kwargs)


def log_activity_complete(activity_name: str, duration_ms: float = None, **kwargs):
    """Log activity completion with correlation."""
    logger = get_logger(f"activities.{activity_name}")
    extra = {"duration_ms": duration_ms} if duration_ms else {}
    extra.update(kwargs)
    logger.info(f"Activity completed: {activity_name}", extra_fields=extra)


def log_activity_error(activity_name: str, error: str, **kwargs):
    """Log activity error with correlation."""
    logger = get_logger(f"activities.{activity_name}")
    logger.error(f"Activity failed: {activity_name} - {error}", extra_fields=kwargs)


def log_workflow_event(event: str, **kwargs):
    """Log a workflow event with correlation."""
    logger = get_logger("workflows")
    logger.info(event, extra_fields=kwargs)
