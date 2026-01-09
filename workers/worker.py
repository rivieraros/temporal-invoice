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
from workflows.ap_package_workflow import APPackageWorkflow
from workflows.invoice_workflow import InvoiceWorkflow
from activities.persist import persist_package_started, persist_invoice, update_package_status, update_invoice_status
from activities.extract import split_pdf, extract_statement, extract_invoice
from activities.validate import validate_invoice
from activities.reconcile import reconcile_package
from activities.integrate import (
    resolve_entity,
    resolve_vendor,
    apply_mapping_overlay,
    build_bc_payload,
    persist_audit_event,
)


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
            workflows=[PingWorkflow, APPackageWorkflow, InvoiceWorkflow],
            activities=[
                # Persistence activities
                persist_package_started,
                persist_invoice,
                update_package_status,
                update_invoice_status,
                
                # Extraction activities
                split_pdf,
                extract_statement,
                extract_invoice,
                
                # Validation activities
                validate_invoice,
                
                # Reconciliation activities
                reconcile_package,
                
                # Integration activities (new)
                resolve_entity,
                resolve_vendor,
                apply_mapping_overlay,
                build_bc_payload,
                persist_audit_event,
            ],
        )
        
        logger.info(f"Worker created with:")
        logger.info(f"  - Namespace: {client.namespace}")
        logger.info(f"  - Task queue: {TASK_QUEUE}")
        logger.info(f"  - Workflows: 3 (PingWorkflow, APPackageWorkflow, InvoiceWorkflow)")
        logger.info(f"  - Activities: 14 (persist, extract, validate, reconcile, integrate)")
        
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
