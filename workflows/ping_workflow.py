"""Workflows for AP automation pipeline.

Workflow definitions for extraction, reconciliation, and orchestration.
"""

from temporalio import workflow


@workflow.defn
class PingWorkflow:
    """Simple ping workflow to verify Temporal connectivity.
    
    Returns "ok" to confirm the workflow executed successfully.
    """
    
    @workflow.run
    async def run(self) -> str:
        """Execute ping workflow.
        
        Returns:
            "ok" - confirms workflow executed
        """
        return "ok"
