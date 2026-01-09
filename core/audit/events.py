"""Audit event logging and persistence.

Provides structured audit logging for all system actions, from extraction
through ERP posting. Supports multiple persistence backends.
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models.refs import AuditEvent, AuditSeverity, DataReference


class AuditEventType(str, Enum):
    """Standard audit event types."""
    # Workflow events
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    
    # Extraction events
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    
    # Validation events
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_WARNING = "VALIDATION_WARNING"
    
    # Reconciliation events
    RECONCILIATION_STARTED = "RECONCILIATION_STARTED"
    RECONCILIATION_COMPLETED = "RECONCILIATION_COMPLETED"
    RECONCILIATION_FAILED = "RECONCILIATION_FAILED"
    
    # Mapping events
    MAPPING_APPLIED = "MAPPING_APPLIED"
    MAPPING_MISSING = "MAPPING_MISSING"
    MAPPING_DEFAULT_USED = "MAPPING_DEFAULT_USED"
    
    # ERP posting events
    ERP_POSTING_STARTED = "ERP_POSTING_STARTED"
    ERP_POSTING_COMPLETED = "ERP_POSTING_COMPLETED"
    ERP_POSTING_FAILED = "ERP_POSTING_FAILED"
    
    # User actions
    USER_APPROVED = "USER_APPROVED"
    USER_REJECTED = "USER_REJECTED"
    USER_MODIFIED = "USER_MODIFIED"
    
    # System events
    SYSTEM_ERROR = "SYSTEM_ERROR"
    CONFIGURATION_CHANGED = "CONFIGURATION_CHANGED"


def create_audit_event(
    event_type: AuditEventType,
    message: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    ap_package_id: Optional[str] = None,
    invoice_number: Optional[str] = None,
    workflow_id: Optional[str] = None,
    activity_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    actor: str = "system",
    artifact_refs: Optional[List[DataReference]] = None,
) -> AuditEvent:
    """Create a new audit event with auto-generated ID and timestamp.
    
    Args:
        event_type: Type of event
        message: Human-readable message
        severity: Event severity level
        ap_package_id: Associated AP package ID
        invoice_number: Associated invoice number
        workflow_id: Temporal workflow ID
        activity_name: Activity that generated the event
        details: Additional structured details
        actor: Who/what performed the action
        artifact_refs: Related artifact references
        
    Returns:
        Configured AuditEvent ready for logging
    """
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        event_type=event_type.value,
        severity=severity,
        ap_package_id=ap_package_id,
        invoice_number=invoice_number,
        workflow_id=workflow_id,
        activity_name=activity_name,
        message=message,
        details=details or {},
        actor=actor,
        artifact_refs=artifact_refs or [],
    )


class AuditBackend(ABC):
    """Abstract base class for audit persistence backends."""
    
    @abstractmethod
    def log(self, event: AuditEvent) -> None:
        """Persist an audit event."""
        pass
    
    @abstractmethod
    def query(
        self,
        event_type: Optional[str] = None,
        ap_package_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        pass


class JSONFileAuditBackend(AuditBackend):
    """Audit backend that stores events in JSON files.
    
    Stores one file per day in YYYY-MM-DD.json format.
    """
    
    def __init__(self, base_path: Path):
        """Initialize with base directory for audit files."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, date: datetime) -> Path:
        """Get file path for a given date."""
        return self.base_path / f"{date.strftime('%Y-%m-%d')}.json"
    
    def log(self, event: AuditEvent) -> None:
        """Append event to daily file."""
        file_path = self._get_file_path(event.timestamp)
        
        # Load existing events
        events = []
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                events = json.load(f)
        
        # Append new event
        events.append(event.model_dump(mode="json"))
        
        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
    
    def query(
        self,
        event_type: Optional[str] = None,
        ap_package_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query events from JSON files."""
        results = []
        
        # Determine date range
        if start_time is None:
            start_time = datetime(2020, 1, 1)
        if end_time is None:
            end_time = datetime.utcnow()
        
        # Iterate through relevant files
        current = start_time
        while current <= end_time and len(results) < limit:
            file_path = self._get_file_path(current)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    events = json.load(f)
                
                for event_data in events:
                    event = AuditEvent.model_validate(event_data)
                    
                    # Apply filters
                    if event_type and event.event_type != event_type:
                        continue
                    if ap_package_id and event.ap_package_id != ap_package_id:
                        continue
                    if start_time and event.timestamp < start_time:
                        continue
                    if end_time and event.timestamp > end_time:
                        continue
                    
                    results.append(event)
                    if len(results) >= limit:
                        break
            
            current = datetime(current.year, current.month, current.day + 1)
        
        return results


class InMemoryAuditBackend(AuditBackend):
    """In-memory audit backend for testing."""
    
    def __init__(self):
        self._events: List[AuditEvent] = []
    
    def log(self, event: AuditEvent) -> None:
        self._events.append(event)
    
    def query(
        self,
        event_type: Optional[str] = None,
        ap_package_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        results = []
        for event in self._events:
            if event_type and event.event_type != event_type:
                continue
            if ap_package_id and event.ap_package_id != ap_package_id:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return results
    
    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events.clear()


class AuditLogger:
    """Main audit logger that supports multiple backends.
    
    Usage:
        logger = AuditLogger()
        logger.add_backend(JSONFileAuditBackend(Path("./audit")))
        
        event = create_audit_event(
            AuditEventType.EXTRACTION_COMPLETED,
            "Invoice 13330 extracted successfully",
            ap_package_id="pkg_123"
        )
        logger.log(event)
    """
    
    def __init__(self):
        self._backends: List[AuditBackend] = []
    
    def add_backend(self, backend: AuditBackend) -> None:
        """Add an audit backend."""
        self._backends.append(backend)
    
    def log(self, event: AuditEvent) -> None:
        """Log event to all backends."""
        for backend in self._backends:
            try:
                backend.log(event)
            except Exception as e:
                # Don't let audit failures break the system
                print(f"Audit logging failed for backend {type(backend).__name__}: {e}")
    
    def log_info(
        self,
        event_type: AuditEventType,
        message: str,
        **kwargs,
    ) -> None:
        """Log an INFO level event."""
        event = create_audit_event(event_type, message, AuditSeverity.INFO, **kwargs)
        self.log(event)
    
    def log_warning(
        self,
        event_type: AuditEventType,
        message: str,
        **kwargs,
    ) -> None:
        """Log a WARN level event."""
        event = create_audit_event(event_type, message, AuditSeverity.WARN, **kwargs)
        self.log(event)
    
    def log_error(
        self,
        event_type: AuditEventType,
        message: str,
        **kwargs,
    ) -> None:
        """Log an ERROR level event."""
        event = create_audit_event(event_type, message, AuditSeverity.ERROR, **kwargs)
        self.log(event)
    
    def query(
        self,
        event_type: Optional[str] = None,
        ap_package_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query events from all backends (returns first backend's results)."""
        if not self._backends:
            return []
        return self._backends[0].query(event_type, ap_package_id, start_time, end_time, limit)
