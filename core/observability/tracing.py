"""
Tracing Support for AP Automation Pipeline

Links UI data to Temporal workflow executions, enabling:
- Invoice → Workflow ID → Temporal Cloud UI
- Activity execution history
- Processing timeline visualization

Stores workflow_id in database for later lookup.
"""

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


# =============================================================================
# Configuration
# =============================================================================

DB_PATH = Path(__file__).resolve().parents[2].parent / "ap_automation.db"

# Temporal Cloud UI base URL (configurable)
TEMPORAL_CLOUD_NAMESPACE = "your-namespace"  # Set via environment
TEMPORAL_CLOUD_URL = f"https://cloud.temporal.io/namespaces/{TEMPORAL_CLOUD_NAMESPACE}"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class WorkflowExecution:
    """Reference to a Temporal workflow execution."""
    workflow_id: str
    run_id: str
    workflow_type: str
    status: str  # RUNNING, COMPLETED, FAILED, CANCELLED, TERMINATED
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    
    def get_temporal_url(self) -> str:
        """Get URL to view in Temporal Cloud UI."""
        return f"{TEMPORAL_CLOUD_URL}/workflows/{self.workflow_id}/{self.run_id}"


@dataclass
class ActivityExecution:
    """Record of an activity execution."""
    activity_id: str
    activity_name: str
    status: str  # SCHEDULED, RUNNING, COMPLETED, FAILED, RETRYING
    attempt: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    
    # Correlation
    ap_package_id: Optional[str] = None
    invoice_number: Optional[str] = None


@dataclass
class TracingInfo:
    """
    Complete tracing information for an invoice/package.
    
    Allows UI to show:
    - Current workflow status
    - Link to Temporal Cloud UI
    - Activity execution timeline
    - Processing stage history
    """
    ap_package_id: str
    invoice_number: Optional[str] = None
    
    # Workflow info
    workflow: Optional[WorkflowExecution] = None
    child_workflows: List[WorkflowExecution] = field(default_factory=list)
    
    # Activity history
    activities: List[ActivityExecution] = field(default_factory=list)
    
    # Stage timeline (from audit_events)
    stages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Quick links
    temporal_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API response."""
        result = {
            "ap_package_id": self.ap_package_id,
            "invoice_number": self.invoice_number,
            "temporal_url": self.temporal_url,
            "stages": self.stages,
            "activities": [asdict(a) for a in self.activities],
            "workflow": None,
            "child_workflows": [],
        }
        
        if self.workflow:
            result["workflow"] = asdict(self.workflow)
            result["workflow"]["temporal_url"] = self.workflow.get_temporal_url()
        
        if self.child_workflows:
            result["child_workflows"] = [
                {**asdict(w), "temporal_url": w.get_temporal_url()}
                for w in self.child_workflows
            ]
        
        return result


# =============================================================================
# Database Schema
# =============================================================================

def init_tracing_tables():
    """Initialize tracing tables in the database."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Workflow executions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            workflow_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            ap_package_id TEXT,
            invoice_number TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms REAL,
            parent_workflow_id TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(workflow_id, run_id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wf_package 
        ON workflow_executions(ap_package_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_wf_invoice 
        ON workflow_executions(ap_package_id, invoice_number)
    """)
    
    # Activity executions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            activity_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SCHEDULED',
            attempt INTEGER DEFAULT 1,
            ap_package_id TEXT,
            invoice_number TEXT,
            started_at TEXT,
            completed_at TEXT,
            duration_ms REAL,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_act_workflow 
        ON activity_executions(workflow_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_act_package 
        ON activity_executions(ap_package_id, invoice_number)
    """)
    
    conn.commit()
    conn.close()


# =============================================================================
# Store Functions
# =============================================================================

def store_workflow_id(
    workflow_id: str,
    run_id: str,
    workflow_type: str,
    ap_package_id: str,
    invoice_number: str = None,
    parent_workflow_id: str = None,
):
    """
    Store workflow execution info for later tracing.
    
    Called when a workflow starts to link it to the package/invoice.
    """
    init_tracing_tables()
    
    now = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO workflow_executions 
        (workflow_id, run_id, workflow_type, status, ap_package_id, invoice_number,
         started_at, parent_workflow_id, created_at, updated_at)
        VALUES (?, ?, ?, 'RUNNING', ?, ?, ?, ?, ?, ?)
    """, (
        workflow_id,
        run_id,
        workflow_type,
        ap_package_id,
        invoice_number,
        now,
        parent_workflow_id,
        now,
        now,
    ))
    
    conn.commit()
    conn.close()


def update_workflow_status(
    workflow_id: str,
    run_id: str,
    status: str,
    duration_ms: float = None,
    error: str = None,
):
    """Update workflow execution status."""
    now = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE workflow_executions 
        SET status = ?, completed_at = ?, duration_ms = ?, error = ?, updated_at = ?
        WHERE workflow_id = ? AND run_id = ?
    """, (status, now, duration_ms, error, now, workflow_id, run_id))
    
    conn.commit()
    conn.close()


def store_activity_execution(
    workflow_id: str,
    activity_id: str,
    activity_name: str,
    status: str,
    attempt: int = 1,
    ap_package_id: str = None,
    invoice_number: str = None,
    duration_ms: float = None,
    error: str = None,
):
    """Store activity execution info."""
    init_tracing_tables()
    
    now = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    started_at = now if status in ("RUNNING", "SCHEDULED") else None
    completed_at = now if status in ("COMPLETED", "FAILED") else None
    
    cursor.execute("""
        INSERT INTO activity_executions 
        (workflow_id, activity_id, activity_name, status, attempt, 
         ap_package_id, invoice_number, started_at, completed_at, 
         duration_ms, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        workflow_id,
        activity_id,
        activity_name,
        status,
        attempt,
        ap_package_id,
        invoice_number,
        started_at,
        completed_at,
        duration_ms,
        error,
        now,
        now,
    ))
    
    conn.commit()
    conn.close()


# =============================================================================
# Query Functions
# =============================================================================

def get_tracing_info(
    ap_package_id: str,
    invoice_number: str = None,
) -> TracingInfo:
    """
    Get complete tracing information for a package/invoice.
    
    Returns workflow execution info, activity history, and stage timeline.
    """
    init_tracing_tables()
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    result = TracingInfo(ap_package_id=ap_package_id, invoice_number=invoice_number)
    
    # Get workflow executions
    if invoice_number:
        cursor.execute("""
            SELECT * FROM workflow_executions 
            WHERE ap_package_id = ? AND (invoice_number = ? OR invoice_number IS NULL)
            ORDER BY started_at DESC
        """, (ap_package_id, invoice_number))
    else:
        cursor.execute("""
            SELECT * FROM workflow_executions 
            WHERE ap_package_id = ?
            ORDER BY started_at DESC
        """, (ap_package_id,))
    
    workflows = cursor.fetchall()
    
    for wf in workflows:
        execution = WorkflowExecution(
            workflow_id=wf["workflow_id"],
            run_id=wf["run_id"],
            workflow_type=wf["workflow_type"],
            status=wf["status"],
            started_at=wf["started_at"],
            completed_at=wf["completed_at"],
            duration_ms=wf["duration_ms"],
        )
        
        if wf["parent_workflow_id"] is None:
            # This is the main workflow
            if result.workflow is None:
                result.workflow = execution
                result.temporal_url = execution.get_temporal_url()
        else:
            # This is a child workflow
            result.child_workflows.append(execution)
    
    # Get activity executions
    if result.workflow:
        cursor.execute("""
            SELECT * FROM activity_executions 
            WHERE workflow_id = ?
            ORDER BY started_at ASC
        """, (result.workflow.workflow_id,))
        
        activities = cursor.fetchall()
        
        for act in activities:
            result.activities.append(ActivityExecution(
                activity_id=act["activity_id"],
                activity_name=act["activity_name"],
                status=act["status"],
                attempt=act["attempt"],
                started_at=act["started_at"],
                completed_at=act["completed_at"],
                duration_ms=act["duration_ms"],
                error=act["error"],
                ap_package_id=act["ap_package_id"],
                invoice_number=act["invoice_number"],
            ))
    
    # Get audit events for stage timeline (optional - table may not exist)
    try:
        cursor.execute("""
            SELECT * FROM audit_events 
            WHERE ap_package_id = ? 
            AND (invoice_number = ? OR invoice_number = '*' OR ? IS NULL)
            ORDER BY created_at ASC
        """, (ap_package_id, invoice_number, invoice_number))
        
        events = cursor.fetchall()
        
        for event in events:
            result.stages.append({
                "stage": event["stage"],
                "status": event["status"],
                "invoice_number": event["invoice_number"],
                "timestamp": event["created_at"],
                "details": json.loads(event["details"]) if event["details"] else None,
                "error": event["error_message"],
            })
    except sqlite3.OperationalError:
        # audit_events table may not exist in all environments
        pass
    
    conn.close()
    
    return result


def get_workflow_for_package(ap_package_id: str) -> Optional[Dict[str, Any]]:
    """Get the main workflow execution for a package."""
    info = get_tracing_info(ap_package_id)
    if info.workflow:
        return {
            "workflow_id": info.workflow.workflow_id,
            "run_id": info.workflow.run_id,
            "status": info.workflow.status,
            "temporal_url": info.workflow.get_temporal_url(),
        }
    return None


def get_workflow_for_invoice(ap_package_id: str, invoice_number: str) -> Optional[Dict[str, Any]]:
    """Get workflow execution for a specific invoice."""
    info = get_tracing_info(ap_package_id, invoice_number)
    
    # Check child workflows for invoice-specific workflow
    for child in info.child_workflows:
        if child.workflow_type == "InvoiceWorkflow":
            return {
                "workflow_id": child.workflow_id,
                "run_id": child.run_id,
                "status": child.status,
                "temporal_url": child.get_temporal_url(),
            }
    
    # Fall back to parent workflow
    if info.workflow:
        return {
            "workflow_id": info.workflow.workflow_id,
            "run_id": info.workflow.run_id,
            "status": info.workflow.status,
            "temporal_url": info.workflow.get_temporal_url(),
        }
    
    return None
