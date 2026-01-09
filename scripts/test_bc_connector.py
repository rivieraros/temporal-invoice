#!/usr/bin/env python
"""Test script for Business Central connector.

This script tests the BC connector's ability to:
1. List companies/entities
2. List vendors for a company
3. List GL accounts for a company
4. List dimensions and dimension values

Usage:
    # With real BC credentials (set environment variables):
    $env:BC_TENANT_ID = "your-tenant-id"
    $env:BC_CLIENT_ID = "your-client-id"
    $env:BC_CLIENT_SECRET = "your-secret"
    python scripts/test_bc_connector.py
    
    # Dry run (no API calls, just verify structure):
    python scripts/test_bc_connector.py --dry-run
"""

import asyncio
import os
import sys
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_bc_connector_structure():
    """Test that the BC connector structure is correct (no API calls)."""
    print("=" * 60)
    print("BC Connector Structure Test (Dry Run)")
    print("=" * 60)
    
    from connectors import (
        ERPConnector,
        EntityRef,
        VendorRef,
        GLAccountRef,
        DimensionRef,
        DimensionValueRef,
    )
    from connectors.business_central import BusinessCentralConnector
    from connectors.business_central.bc_client import (
        BCApiConfig,
        BCApiError,
        BCAuthenticationError,
        BCNotFoundError,
        BCRateLimitError,
        RetryConfig,
    )
    
    print("\n✓ All imports successful")
    
    # Check BC connector inherits from ERPConnector
    assert issubclass(BusinessCentralConnector, ERPConnector), \
        "BusinessCentralConnector should inherit from ERPConnector"
    print("✓ BusinessCentralConnector inherits from ERPConnector")
    
    # Check required methods exist
    required_methods = [
        'list_entities',
        'list_vendors',
        'list_gl_accounts',
        'list_dimensions',
        'list_dimension_values',
        'connect',
        'disconnect',
        'test_connection',
    ]
    
    for method in required_methods:
        assert hasattr(BusinessCentralConnector, method), \
            f"Missing method: {method}"
    print(f"✓ All {len(required_methods)} required methods present")
    
    # Check normalized types have both id and code
    print("\n--- Normalized Types ---")
    
    for type_class, type_name in [
        (EntityRef, "EntityRef"),
        (VendorRef, "VendorRef"),
        (GLAccountRef, "GLAccountRef"),
        (DimensionRef, "DimensionRef"),
        (DimensionValueRef, "DimensionValueRef"),
    ]:
        fields = list(type_class.model_fields.keys())
        assert 'id' in fields, f"{type_name} missing 'id' field"
        assert 'code' in fields, f"{type_name} missing 'code' field"
        print(f"  ✓ {type_name}: id (GUID) + code (number) present")
    
    # Check retry config
    print("\n--- Retry Configuration ---")
    config = RetryConfig()
    print(f"  Max retries: {config.max_retries}")
    print(f"  Base delay: {config.base_delay}s")
    print(f"  Exponential base: {config.exponential_base}")
    print(f"  Retry on status codes: {config.retry_on_status}")
    
    # Check error types
    print("\n--- Error Types ---")
    for error_type in [BCApiError, BCAuthenticationError, BCNotFoundError, BCRateLimitError]:
        print(f"  ✓ {error_type.__name__}")
    
    print("\n" + "=" * 60)
    print("All structure tests passed!")
    print("=" * 60)


async def test_bc_connector_live(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    environment: str = "production",
):
    """Test the BC connector with real API calls."""
    print("=" * 60)
    print("BC Connector Live API Test")
    print("=" * 60)
    
    from connectors import ERPConfig, create_connector
    from connectors.business_central.bc_client import BCApiError, BCAuthenticationError
    
    # Create connector via factory
    config = ERPConfig(
        connector_type="business_central",
        tenant_id=tenant_id,
        environment=environment,
        auth_config={
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "environment": environment,
        },
        custom_settings={
            "environment": environment,
            "api_version": "v2.0",
        }
    )
    
    connector = create_connector(config)
    print(f"\n✓ Created connector: {connector.get_connector_name()}")
    
    try:
        # Connect
        print("\n--- Connecting ---")
        connected = await connector.connect()
        if not connected:
            print("✗ Failed to connect (check credentials)")
            return False
        print("✓ Connected to Business Central")
        
        # Test connection
        healthy = await connector.test_connection()
        print(f"✓ Connection healthy: {healthy}")
        
        # List companies/entities
        print("\n--- List Companies ---")
        entities = await connector.list_entities()
        print(f"Found {len(entities)} companies:")
        
        if not entities:
            print("  (No companies found - check permissions)")
            return False
        
        for entity in entities[:5]:  # Show first 5
            print(f"  • id={entity.id[:8]}... code='{entity.code}' name='{entity.name}'")
        
        # Use first company for remaining tests
        company = entities[0]
        company_id = company.id
        print(f"\nUsing company: {company.name} (id={company_id[:8]}...)")
        
        # List vendors
        print("\n--- List Vendors ---")
        vendors = await connector.list_vendors(company_id, limit=10)
        print(f"Found {len(vendors)} vendors (showing first 10):")
        for v in vendors[:5]:
            print(f"  • id={v.id[:8]}... code='{v.code}' name='{v.name}'")
            print(f"    └─ active={v.is_active}, city={v.city or 'N/A'}")
        
        # List GL accounts
        print("\n--- List G/L Accounts ---")
        accounts = await connector.list_gl_accounts(company_id, limit=10)
        print(f"Found {len(accounts)} accounts (showing first 10):")
        for a in accounts[:5]:
            print(f"  • id={a.id[:8]}... code='{a.code}' name='{a.name}'")
            print(f"    └─ category={a.category or 'N/A'}, direct_posting={a.direct_posting}")
        
        # List dimensions
        print("\n--- List Dimensions ---")
        dimensions = await connector.list_dimensions(company_id)
        print(f"Found {len(dimensions)} dimensions:")
        for d in dimensions[:5]:
            print(f"  • id={d.id[:8]}... code='{d.code}' name='{d.name}'")
        
        # List dimension values for first dimension
        if dimensions:
            dim = dimensions[0]
            print(f"\n--- Dimension Values for '{dim.code}' ---")
            values = await connector.list_dimension_values(company_id, dim.code, limit=10)
            print(f"Found {len(values)} values:")
            for v in values[:5]:
                print(f"  • id={v.id[:8]}... code='{v.code}' name='{v.name}'")
        
        print("\n" + "=" * 60)
        print("All live tests passed!")
        print("=" * 60)
        return True
        
    except BCAuthenticationError as e:
        print(f"\n✗ Authentication failed: {e}")
        print("  Check your BC_CLIENT_ID and BC_CLIENT_SECRET")
        return False
    except BCApiError as e:
        print(f"\n✗ API error: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await connector.disconnect()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test BC Connector")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only test structure, don't make API calls"
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("BC_TENANT_ID"),
        help="Azure AD tenant ID"
    )
    parser.add_argument(
        "--client-id",
        default=os.environ.get("BC_CLIENT_ID"),
        help="Application client ID"
    )
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("BC_CLIENT_SECRET"),
        help="Client secret"
    )
    parser.add_argument(
        "--environment",
        default=os.environ.get("BC_ENVIRONMENT", "production"),
        help="BC environment (default: production)"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        asyncio.run(test_bc_connector_structure())
    else:
        # Check required credentials
        if not all([args.tenant_id, args.client_id, args.client_secret]):
            print("Missing BC credentials. Set environment variables:")
            print("  $env:BC_TENANT_ID = 'your-tenant-id'")
            print("  $env:BC_CLIENT_ID = 'your-client-id'")
            print("  $env:BC_CLIENT_SECRET = 'your-secret'")
            print("\nOr run with --dry-run for structure tests only.")
            sys.exit(1)
        
        success = asyncio.run(test_bc_connector_live(
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            environment=args.environment,
        ))
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
