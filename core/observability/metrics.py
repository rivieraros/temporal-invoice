"""
Metrics Collection for AP Automation Pipeline

Collects and exposes metrics for:
- Workflow lifecycle (started, completed, failed)
- Activity execution (started, completed, retries)
- Processing times (average, p95)
- Task queue backlog

Metrics are stored in-memory with periodic DB persistence for durability.
"""

import json
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Any
import statistics


# =============================================================================
# Configuration
# =============================================================================

DB_PATH = Path(__file__).resolve().parents[2].parent / "ap_automation.db"


# =============================================================================
# Metric Data Classes
# =============================================================================

@dataclass
class WorkflowMetrics:
    """Metrics for workflow execution."""
    started: int = 0
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    
    # By workflow type
    by_type: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"started": 0, "completed": 0, "failed": 0}))


@dataclass
class ActivityMetrics:
    """Metrics for activity execution."""
    started: int = 0
    completed: int = 0
    failed: int = 0
    retries: int = 0
    
    # By activity name
    by_name: Dict[str, Dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"started": 0, "completed": 0, "failed": 0, "retries": 0}))


@dataclass
class TimingMetrics:
    """Processing time metrics."""
    # Raw timing samples (keep last N for percentile calculations)
    samples: List[float] = field(default_factory=list)
    max_samples: int = 1000
    
    # By stage
    by_stage: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    def add_sample(self, duration_ms: float, stage: str = None):
        """Add a timing sample."""
        self.samples.append(duration_ms)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]
        
        if stage:
            self.by_stage[stage].append(duration_ms)
            if len(self.by_stage[stage]) > self.max_samples:
                self.by_stage[stage] = self.by_stage[stage][-self.max_samples:]
    
    def get_average(self, stage: str = None) -> float:
        """Get average processing time."""
        samples = self.by_stage.get(stage, []) if stage else self.samples
        return statistics.mean(samples) if samples else 0.0
    
    def get_p95(self, stage: str = None) -> float:
        """Get 95th percentile processing time."""
        samples = self.by_stage.get(stage, []) if stage else self.samples
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]


@dataclass
class QueueMetrics:
    """Task queue metrics."""
    # Estimated backlog per queue (updated by workers)
    backlog: Dict[str, int] = field(default_factory=dict)
    
    # Last poll time per queue
    last_poll: Dict[str, datetime] = field(default_factory=dict)


# =============================================================================
# Metrics Collector (Singleton)
# =============================================================================

class MetricsCollector:
    """
    Thread-safe metrics collector for the AP automation pipeline.
    
    Usage:
        metrics = MetricsCollector.instance()
        metrics.record_workflow_started("APPackageWorkflow", workflow_id)
        metrics.record_activity_completed("extract_invoice", duration_ms=1500)
    """
    
    _instance: Optional["MetricsCollector"] = None
    _lock = Lock()
    
    def __init__(self):
        self.workflows = WorkflowMetrics()
        self.activities = ActivityMetrics()
        self.timings = TimingMetrics()
        self.queues = QueueMetrics()
        self._lock = Lock()
        
        # Initialize DB table
        self._init_db()
    
    @classmethod
    def instance(cls) -> "MetricsCollector":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _init_db(self):
        """Initialize metrics table in database."""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                labels TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_type_time 
            ON metrics_snapshots(metric_type, timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # Workflow Metrics
    # =========================================================================
    
    def record_workflow_started(self, workflow_type: str, workflow_id: str):
        """Record a workflow start."""
        with self._lock:
            self.workflows.started += 1
            self.workflows.in_progress += 1
            self.workflows.by_type[workflow_type]["started"] += 1
        
        self._persist_metric("workflow", "started", 1, {"type": workflow_type, "workflow_id": workflow_id})
    
    def record_workflow_completed(self, workflow_type: str, workflow_id: str, duration_ms: float = None):
        """Record a workflow completion."""
        with self._lock:
            self.workflows.completed += 1
            self.workflows.in_progress = max(0, self.workflows.in_progress - 1)
            self.workflows.by_type[workflow_type]["completed"] += 1
            
            if duration_ms:
                self.timings.add_sample(duration_ms, f"workflow.{workflow_type}")
        
        self._persist_metric("workflow", "completed", 1, {"type": workflow_type, "workflow_id": workflow_id})
    
    def record_workflow_failed(self, workflow_type: str, workflow_id: str, error: str = None):
        """Record a workflow failure."""
        with self._lock:
            self.workflows.failed += 1
            self.workflows.in_progress = max(0, self.workflows.in_progress - 1)
            self.workflows.by_type[workflow_type]["failed"] += 1
        
        self._persist_metric("workflow", "failed", 1, {"type": workflow_type, "workflow_id": workflow_id, "error": error})
    
    # =========================================================================
    # Activity Metrics
    # =========================================================================
    
    def record_activity_started(self, activity_name: str):
        """Record an activity start."""
        with self._lock:
            self.activities.started += 1
            self.activities.by_name[activity_name]["started"] += 1
    
    def record_activity_completed(self, activity_name: str, duration_ms: float = None):
        """Record an activity completion."""
        with self._lock:
            self.activities.completed += 1
            self.activities.by_name[activity_name]["completed"] += 1
            
            if duration_ms:
                self.timings.add_sample(duration_ms, f"activity.{activity_name}")
    
    def record_activity_failed(self, activity_name: str, error: str = None):
        """Record an activity failure."""
        with self._lock:
            self.activities.failed += 1
            self.activities.by_name[activity_name]["failed"] += 1
    
    def record_activity_retry(self, activity_name: str, attempt: int, error: str = None):
        """Record an activity retry."""
        with self._lock:
            self.activities.retries += 1
            self.activities.by_name[activity_name]["retries"] += 1
        
        self._persist_metric("activity", "retry", attempt, {"name": activity_name, "error": error})
    
    # =========================================================================
    # Timing Metrics
    # =========================================================================
    
    def record_processing_time(self, stage: str, duration_ms: float):
        """Record a processing time sample."""
        with self._lock:
            self.timings.add_sample(duration_ms, stage)
    
    def get_timing_stats(self, stage: str = None) -> Dict[str, float]:
        """Get timing statistics for a stage."""
        with self._lock:
            return {
                "average_ms": self.timings.get_average(stage),
                "p95_ms": self.timings.get_p95(stage),
                "sample_count": len(self.timings.by_stage.get(stage, []) if stage else self.timings.samples),
            }
    
    # =========================================================================
    # Queue Metrics
    # =========================================================================
    
    def update_queue_backlog(self, queue_name: str, backlog: int):
        """Update the backlog count for a queue."""
        with self._lock:
            self.queues.backlog[queue_name] = backlog
            self.queues.last_poll[queue_name] = datetime.utcnow()
    
    def get_queue_backlog(self, queue_name: str = None) -> Dict[str, int]:
        """Get backlog for queues."""
        with self._lock:
            if queue_name:
                return {queue_name: self.queues.backlog.get(queue_name, 0)}
            return dict(self.queues.backlog)
    
    # =========================================================================
    # Summary
    # =========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self._lock:
            return {
                "workflows": {
                    "started": self.workflows.started,
                    "completed": self.workflows.completed,
                    "failed": self.workflows.failed,
                    "in_progress": self.workflows.in_progress,
                    "by_type": dict(self.workflows.by_type),
                },
                "activities": {
                    "started": self.activities.started,
                    "completed": self.activities.completed,
                    "failed": self.activities.failed,
                    "retries": self.activities.retries,
                    "by_name": dict(self.activities.by_name),
                },
                "timings": {
                    "overall": {
                        "average_ms": self.timings.get_average(),
                        "p95_ms": self.timings.get_p95(),
                    },
                    "by_stage": {
                        stage: {
                            "average_ms": self.timings.get_average(stage),
                            "p95_ms": self.timings.get_p95(stage),
                        }
                        for stage in self.timings.by_stage.keys()
                    },
                },
                "queues": {
                    "backlog": dict(self.queues.backlog),
                    "last_poll": {k: v.isoformat() for k, v in self.queues.last_poll.items()},
                },
            }
    
    # =========================================================================
    # Persistence
    # =========================================================================
    
    def _persist_metric(self, metric_type: str, metric_name: str, value: float, labels: Dict = None):
        """Persist a metric to the database."""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO metrics_snapshots (timestamp, metric_type, metric_name, metric_value, labels)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                metric_type,
                metric_name,
                value,
                json.dumps(labels) if labels else None,
            ))
            
            conn.commit()
            conn.close()
        except Exception:
            pass  # Don't fail on metrics persistence errors


# =============================================================================
# Module-level convenience functions
# =============================================================================

def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return MetricsCollector.instance()


def record_workflow_started(workflow_type: str, workflow_id: str):
    """Record a workflow start."""
    get_metrics().record_workflow_started(workflow_type, workflow_id)


def record_workflow_completed(workflow_type: str, workflow_id: str, duration_ms: float = None):
    """Record a workflow completion."""
    get_metrics().record_workflow_completed(workflow_type, workflow_id, duration_ms)


def record_workflow_failed(workflow_type: str, workflow_id: str, error: str = None):
    """Record a workflow failure."""
    get_metrics().record_workflow_failed(workflow_type, workflow_id, error)


def record_activity_started(activity_name: str):
    """Record an activity start."""
    get_metrics().record_activity_started(activity_name)


def record_activity_completed(activity_name: str, duration_ms: float = None):
    """Record an activity completion."""
    get_metrics().record_activity_completed(activity_name, duration_ms)


def record_activity_retry(activity_name: str, attempt: int, error: str = None):
    """Record an activity retry."""
    get_metrics().record_activity_retry(activity_name, attempt, error)


def record_processing_time(stage: str, duration_ms: float):
    """Record a processing time sample."""
    get_metrics().record_processing_time(stage, duration_ms)
