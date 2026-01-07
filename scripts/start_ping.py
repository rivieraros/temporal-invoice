"""Start ping workflow on Temporal Cloud.

This script connects to Temporal Cloud, starts a PingWorkflow,
and prints the result.
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from temporal_client import get_temporal_client
from workflows.ping_workflow import PingWorkflow


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TASK_QUEUE = "ap-default"


async def start_ping_workflow():
    """Start ping workflow and return result.
    
    Connects to Temporal Cloud, starts PingWorkflow, waits for
    completion, and returns the result.
    
    Returns:
        str: Result from workflow ("ok")
        
    Raises:
        Exception: If workflow execution fails
    """
    logger.info("Starting ping workflow...")
    
    try:
        # Connect to Temporal Cloud
        client = await get_temporal_client()
        logger.info(f"Connected to Temporal Cloud: {client.namespace}")
        
        # Start workflow
        logger.info(f"Starting PingWorkflow on task queue '{TASK_QUEUE}'...")
        handle = await client.start_workflow(
            PingWorkflow.run,
            task_queue=TASK_QUEUE,
            id=f"ping-{int(asyncio.get_event_loop().time() * 1000)}",
        )
        
        logger.info(f"Workflow started: {handle.id}")
        logger.info("Waiting for result...")
        
        # Wait for result
        result = await handle.result()
        
        logger.info(f"✓ Workflow completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise


def main():
    """Entry point."""
    try:
        result = asyncio.run(start_ping_workflow())
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
