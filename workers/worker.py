"""Worker for AP automation pipeline.

Runs on Temporal Cloud, listens for tasks and executes workflows/activities.
"""

import asyncio
import logging
import sys
from pathlib import Path

from temporalio.worker import Worker

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


async def run_worker():
    """Start worker listening on task queue.
    
    Connects to Temporal Cloud and registers workflows/activities,
    then blocks listening for work.
    
    Raises:
        Exception: If connection to Temporal Cloud fails
    """
    logger.info(f"Starting worker on task queue '{TASK_QUEUE}'...")
    
    client = None
    worker = None
    
    try:
        # Connect to Temporal Cloud
        client = await get_temporal_client()
        logger.info(f"Connected to Temporal Cloud: {client.namespace}")
        
        # Create worker
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[PingWorkflow],
            activities=[],  # No activities yet
        )
        
        logger.info(f"Worker created with:")
        logger.info(f"  - Namespace: {client.namespace}")
        logger.info(f"  - Task queue: {TASK_QUEUE}")
        logger.info(f"  - Workflows: 1 (PingWorkflow)")
        
        # Run worker (blocks until interrupted)
        logger.info("Worker running... (Ctrl+C to stop)")
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        raise
    finally:
        # Ensure proper cleanup
        if worker:
            try:
                logger.info("Shutting down worker...")
            except:
                pass
        if client:
            try:
                await client.close()
                logger.info("Client closed")
            except:
                pass


def main():
    """Entry point for worker."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
