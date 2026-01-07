"""Test Temporal workflow without Cloud (mock test).

Tests that the workflow code structure is correct and can be imported/executed.
"""

import asyncio
from workflows.ping_workflow import PingWorkflow


async def test_ping_workflow_directly():
    """Test PingWorkflow directly without Temporal server.
    
    This verifies the workflow code is correct by executing it directly.
    In production, Temporal server orchestrates execution.
    """
    print("\n" + "="*70)
    print("TESTING PING WORKFLOW")
    print("="*70 + "\n")
    
    # Create workflow instance
    workflow = PingWorkflow()
    
    # Execute run method directly
    print("Executing workflow.run()...")
    result = await workflow.run()
    
    # Verify result
    print(f"Result: {result}")
    assert result == "ok", f"Expected 'ok', got {result}"
    
    print("\n✓ Workflow executed successfully")
    print("✓ Result matches expected value")
    print("\n" + "="*70 + "\n")


async def test_temporal_imports():
    """Test that Temporal libraries can be imported."""
    print("\n" + "="*70)
    print("TESTING TEMPORAL IMPORTS")
    print("="*70 + "\n")
    
    try:
        from temporalio import workflow
        from temporalio.worker import Worker
        from temporalio.client import Client
        
        print("✓ temporalio.workflow")
        print("✓ temporalio.worker.Worker")
        print("✓ temporalio.client.Client")
        
        print("\n✓ All imports successful")
        print("\n" + "="*70 + "\n")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("\nTEMPORAL CODE STRUCTURE TEST\n")
    
    # Test imports
    imports_ok = await test_temporal_imports()
    if not imports_ok:
        return 1
    
    # Test workflow
    try:
        await test_ping_workflow_directly()
    except AssertionError as e:
        print(f"✗ Workflow test failed: {e}")
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED")
    print("="*70)
    print("\nWorkflow code structure is correct.")
    print("Ready to connect to Temporal Cloud.")
    print("\nNext: Configure Temporal Cloud credentials:")
    print("  TEMPORAL_ENDPOINT")
    print("  TEMPORAL_NAMESPACE")
    print("  TEMPORAL_API_KEY")
    print("\nThen run:")
    print("  python workers/worker.py  # in one terminal")
    print("  python scripts/start_ping.py  # in another")
    print("\n" + "="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
