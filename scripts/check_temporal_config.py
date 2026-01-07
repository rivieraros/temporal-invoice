"""Temporal Cloud setup verification and configuration guide."""

import os
import sys
from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)


def check_temporal_config():
    """Check Temporal Cloud configuration status.
    
    Verifies that required environment variables are set for Temporal Cloud
    connectivity.
    """
    print("\n" + "="*70)
    print("TEMPORAL CLOUD CONFIGURATION CHECK")
    print("="*70 + "\n")
    
    # Check environment variables
    endpoint = os.getenv("TEMPORAL_ENDPOINT")
    namespace = os.getenv("TEMPORAL_NAMESPACE")
    api_key = os.getenv("TEMPORAL_API_KEY")
    cert_path = os.getenv("TEMPORAL_CERT_PATH")
    
    # Status
    status = {
        "TEMPORAL_ENDPOINT": ("✓" if endpoint else "✗", endpoint or "NOT SET"),
        "TEMPORAL_NAMESPACE": ("✓" if namespace else "✓ (optional)", namespace or "default"),
        "TEMPORAL_API_KEY": ("✓" if api_key else "✗", "SET" if api_key else "NOT SET"),
        "TEMPORAL_CERT_PATH": ("✓" if cert_path else "~ (optional)", cert_path or "system certs"),
    }
    
    for var, (check, val) in status.items():
        print(f"{check} {var}")
        print(f"   Value: {val}")
    
    print("\n" + "="*70)
    
    # Check if configured
    if endpoint and api_key:
        print("✓ READY FOR TEMPORAL CLOUD")
        print(f"\n  Endpoint: {endpoint}")
        print(f"  Namespace: {namespace or 'default'}")
        return True
    else:
        print("✗ NOT CONFIGURED FOR TEMPORAL CLOUD")
        print("\nTo configure, add to your .env file or environment:")
        print("\n  TEMPORAL_ENDPOINT=<your-endpoint>.tmprl.cloud:7233")
        print("  TEMPORAL_NAMESPACE=<your-namespace>")
        print("  TEMPORAL_API_KEY=<your-api-key>")
        print("\nOr set environment variables:")
        print("  export TEMPORAL_ENDPOINT=...")
        print("  export TEMPORAL_NAMESPACE=...")
        print("  export TEMPORAL_API_KEY=...")
        return False


def show_next_steps():
    """Show next steps for Temporal Cloud setup."""
    print("\nNEXT STEPS:")
    print("-" * 70)
    print("\n1. Get Temporal Cloud Account:")
    print("   Visit: https://cloud.temporal.io/")
    print("   Create a namespace and get your endpoint + API key")
    print("\n2. Configure Credentials:")
    print("   Add to .env file:")
    print("   - TEMPORAL_ENDPOINT")
    print("   - TEMPORAL_NAMESPACE")
    print("   - TEMPORAL_API_KEY")
    print("\n3. Start Worker:")
    print("   python workers/worker.py")
    print("\n4. Start Workflow:")
    print("   python scripts/start_ping.py")
    print("\n5. View in UI:")
    print("   Visit: https://cloud.temporal.io/")
    print("   Check your namespace for workflow executions")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    is_ready = check_temporal_config()
    show_next_steps()
    
    sys.exit(0 if is_ready else 1)
