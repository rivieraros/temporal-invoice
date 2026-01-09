"""Start AP Package workflow on Temporal Cloud.

This script connects to Temporal Cloud, starts an APPackageWorkflow,
and prints the result.
"""

import asyncio
import sys
from pathlib import Path
import logging
import uuid

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from temporal_client import get_temporal_client
from workflows.ap_package_workflow import APPackageWorkflow, APPackageInput


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TASK_QUEUE = "ap-default"

# Default PDF paths for testing
DEFAULT_PDF_PATHS = {
    "BOVINA": r"C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Bovina.pdf",
    "MESQUITE": r"C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Mesquite.pdf",
}


async def start_ap_package_workflow(
    feedlot_type: str = "BOVINA",
    pdf_path: str = None,
):
    """Start AP package workflow and return result.
    
    Args:
        feedlot_type: BOVINA or MESQUITE
        pdf_path: Path to the source PDF file
        
    Returns:
        dict: Result from workflow
    """
    # Use default path if not provided
    if pdf_path is None:
        pdf_path = DEFAULT_PDF_PATHS.get(feedlot_type)
        if not pdf_path:
            raise ValueError(f"No default PDF path for feedlot type: {feedlot_type}")
    
    # Validate PDF exists
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    # Generate unique package ID
    ap_package_id = f"pkg-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"Starting AP Package workflow for {ap_package_id}...")
    logger.info(f"PDF: {pdf_path}")
    
    try:
        # Connect to Temporal Cloud
        client = await get_temporal_client()
        logger.info(f"Connected to Temporal Cloud: {client.namespace}")
        
        # Prepare input
        input_data = APPackageInput(
            ap_package_id=ap_package_id,
            feedlot_type=feedlot_type,
            pdf_path=str(pdf_file.resolve()),
        )
        
        # Start workflow
        logger.info(f"Starting APPackageWorkflow on task queue '{TASK_QUEUE}'...")
        handle = await client.start_workflow(
            APPackageWorkflow.run,
            input_data,
            task_queue=TASK_QUEUE,
            id=ap_package_id,
        )
        
        logger.info(f"Workflow started: {handle.id}")
        logger.info("Waiting for result (this may take several minutes for LLM extraction)...")
        
        # Wait for result
        result = await handle.result()
        
        logger.info(f"✓ Workflow completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}", exc_info=True)
        raise


def main():
    """Entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start AP Package workflow")
    parser.add_argument(
        "--feedlot", 
        choices=["BOVINA", "MESQUITE"], 
        default="BOVINA",
        help="Feedlot type (default: BOVINA)"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        default=None,
        help="Path to source PDF file (uses default if not provided)"
    )
    args = parser.parse_args()
    
    try:
        result = asyncio.run(start_ap_package_workflow(
            feedlot_type=args.feedlot,
            pdf_path=args.pdf,
        ))
        print("\n=== WORKFLOW RESULT ===")
        for key, value in result.items():
            print(f"  {key}: {value}")
        print("=======================\n")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
