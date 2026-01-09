"""Worker for AP automation pipeline.

Runs on Temporal Cloud, listens for tasks and executes workflows/activities.

Supports multiple task queues for separation of concerns:
- ap-default: DB/persistence activities, validation, reconciliation
- ap-llm: LLM-heavy extraction activities (GPT-4o calls)
- ap-erp: ERP/Business Central integration activities

Run with --queue <name> to specify which queue to poll.
Run with --all to poll all queues (for local development).
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from temporalio.worker import Worker

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from temporal_client import get_temporal_client
from workflows.ping_workflow import PingWorkflow
from workflows.ap_package_workflow import (
    APPackageWorkflow,
    TASK_QUEUE_DEFAULT,
    TASK_QUEUE_LLM,
    TASK_QUEUE_ERP,
)
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

# =============================================================================
# Activity Groupings by Task Queue
# =============================================================================

# Default queue: DB, validation, reconciliation (fast, low-resource)
DEFAULT_QUEUE_ACTIVITIES = [
    persist_package_started,
    persist_invoice,
    update_package_status,
    update_invoice_status,
    validate_invoice,
    reconcile_package,
    persist_audit_event,
    split_pdf,  # PDF parsing, no LLM
]

# LLM queue: GPT-4o extraction (slow, high-cost, rate-limited)
LLM_QUEUE_ACTIVITIES = [
    extract_statement,
    extract_invoice,
]

# ERP queue: Business Central API calls (may be rate-limited)
ERP_QUEUE_ACTIVITIES = [
    resolve_entity,
    resolve_vendor,
    apply_mapping_overlay,
    build_bc_payload,
]

# For backwards compatibility: all activities (local dev mode)
ALL_ACTIVITIES = DEFAULT_QUEUE_ACTIVITIES + LLM_QUEUE_ACTIVITIES + ERP_QUEUE_ACTIVITIES


async def run_worker(queue: str = None, all_queues: bool = False):
    """Start worker listening on task queue(s).
    
    Args:
        queue: Specific queue to poll (ap-default, ap-llm, ap-erp)
        all_queues: If True, poll all queues with all activities (local dev mode)
    
    Raises:
        Exception: If connection to Temporal Cloud fails
    """
    workers = []
    client = None
    
    try:
        # Connect to Temporal Cloud
        client = await get_temporal_client()
        logger.info(f"Connected to Temporal Cloud: {client.namespace}")
        
        if all_queues:
            # Local dev mode: run all activities on all queues
            logger.info("Running in ALL-QUEUES mode (local development)")
            
            for task_queue in [TASK_QUEUE_DEFAULT, TASK_QUEUE_LLM, TASK_QUEUE_ERP]:
                worker = Worker(
                    client,
                    task_queue=task_queue,
                    workflows=[PingWorkflow, APPackageWorkflow, InvoiceWorkflow] if task_queue == TASK_QUEUE_DEFAULT else [],
                    activities=ALL_ACTIVITIES,
                )
                workers.append(worker)
                logger.info(f"  Created worker for queue: {task_queue}")
        else:
            # Production mode: specific queue with specific activities
            task_queue = queue or TASK_QUEUE_DEFAULT
            
            if task_queue == TASK_QUEUE_LLM:
                activities = LLM_QUEUE_ACTIVITIES
                workflows = []
            elif task_queue == TASK_QUEUE_ERP:
                activities = ERP_QUEUE_ACTIVITIES
                workflows = []
            else:
                activities = DEFAULT_QUEUE_ACTIVITIES
                workflows = [PingWorkflow, APPackageWorkflow, InvoiceWorkflow]
            
            worker = Worker(
                client,
                task_queue=task_queue,
                workflows=workflows,
                activities=activities,
            )
            workers.append(worker)
            
            logger.info(f"Worker created for queue '{task_queue}':")
            logger.info(f"  - Workflows: {len(workflows)}")
            logger.info(f"  - Activities: {len(activities)}")
        
        # Run all workers concurrently
        logger.info("Worker(s) running... (Ctrl+C to stop)")
        await asyncio.gather(*[w.run() for w in workers])
        
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}", exc_info=True)
        raise
    finally:
        if client:
            try:
                await client.close()
                logger.info("Client closed")
            except:
                pass


def main():
    """Entry point for worker with CLI args."""
    parser = argparse.ArgumentParser(description="AP Automation Temporal Worker")
    parser.add_argument(
        "--queue", "-q",
        choices=[TASK_QUEUE_DEFAULT, TASK_QUEUE_LLM, TASK_QUEUE_ERP],
        default=TASK_QUEUE_DEFAULT,
        help="Task queue to poll (default: ap-default)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        dest="all_queues",
        help="Poll all queues (local development mode)"
    )
    
    args = parser.parse_args()
    asyncio.run(run_worker(queue=args.queue, all_queues=args.all_queues))


if __name__ == "__main__":
    main()
