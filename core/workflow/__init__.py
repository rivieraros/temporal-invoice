"""Core workflow module - Temporal workflow definitions.

This module contains Temporal workflows for the AP automation pipeline.
Workflows are ERP-neutral and use activities to perform actual work.
"""

# Workflows are defined in the main workflows/ folder
# This module provides re-exports and utilities

from core.workflow.base import (
    WorkflowStatus,
    WorkflowResult,
)

__all__ = [
    "WorkflowStatus",
    "WorkflowResult",
]
