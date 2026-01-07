"""Temporal Cloud client factory.

Creates and manages connections to Temporal Cloud using credentials from environment.
"""

import os
from typing import Optional
import ssl
from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from temporalio.client import Client


async def get_temporal_client() -> Client:
    """Create and return a Temporal Cloud client.
    
    Reads configuration from environment variables:
    - TEMPORAL_ENDPOINT: Temporal Cloud endpoint (e.g., "temporal.example.com:7233")
    - TEMPORAL_NAMESPACE: Namespace (e.g., "default")
    - TEMPORAL_API_KEY: mTLS API key for Cloud
    - TEMPORAL_CERT_PATH: Path to client certificate (optional, for mTLS)
    
    Returns:
        Configured Temporal client connected to Cloud
        
    Raises:
        ValueError: If required environment variables are missing
    """
    endpoint = os.getenv("TEMPORAL_ENDPOINT")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    api_key = os.getenv("TEMPORAL_API_KEY")
    cert_path = os.getenv("TEMPORAL_CERT_PATH")
    
    if not endpoint:
        raise ValueError(
            "TEMPORAL_ENDPOINT environment variable not set. "
            "Set to your Temporal Cloud endpoint (e.g., 'temporal.example.com:7233')"
        )
    
    if not api_key:
        raise ValueError(
            "TEMPORAL_API_KEY environment variable not set. "
            "Set to your Temporal Cloud mTLS API key"
        )
    
    # Build TLS config for Temporal Cloud
    tls_config: Optional[ssl.SSLContext] = None
    
    if cert_path:
        # Use client certificate if provided
        tls_config = ssl.create_default_context()
        tls_config.load_cert_chain(cert_path)
    else:
        # Default: use system certificates for Temporal Cloud
        tls_config = ssl.create_default_context()
    
    # Create client with Temporal Cloud credentials
    # For Temporal Cloud, pass the API key as an authorization header
    client = await Client.connect(
        target_host=endpoint,
        namespace=namespace,
        tls=tls_config,
        api_key=api_key,
    )
    
    return client
