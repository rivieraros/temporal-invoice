"""ERP Connectors - Pluggable ERP system integrations.

This package contains the abstract ERP interface and concrete implementations
for specific ERP systems (Business Central, SAP, Oracle, etc.).

Core extraction models are ERP-neutral. This package handles:
- ERP-specific authentication
- Data transformation (canonical → ERP format)
- API communication
- Posting and status tracking

Key Design Principle:
- Temporal workflows and API routes depend ONLY on ERPConnector interface
- All methods return NORMALIZED types (VendorRef, GLAccountRef, etc.)
- No BC/SAP/Oracle-specific types should leak through the interface

To add a new ERP:
1. Create a new folder (e.g., sap/)
2. Implement ERPConnector interface
3. Register using @register_connector decorator
"""

from connectors.erp_base import (
    # Core interface
    ERPConnector,
    ERPConfig,
    ERPConnectionStatus,
    ERPEntityType,
    ERPPostingStatus,
    
    # Normalized reference types (ERP-agnostic)
    EntityRef,
    VendorRef,
    GLAccountRef,
    DimensionRef,
    DimensionValueRef,
    PaymentTermsRef,
    
    # Invoice types
    InvoicePayload,
    InvoiceLinePayload,
    CreatedInvoiceRef,
    PostedInvoiceRef,
    InvoiceStatus,
    
    # Legacy types (backward compatibility)
    ERPPostingRequest,
    ERPPostingResponse,
    ERPEntity,
    ERPLookupResult,
    
    # Factory functions
    create_connector,
    register_connector,
    list_available_connectors,
)

__all__ = [
    # Core interface
    "ERPConnector",
    "ERPConfig",
    "ERPConnectionStatus",
    "ERPEntityType",
    "ERPPostingStatus",
    
    # Normalized reference types
    "EntityRef",
    "VendorRef",
    "GLAccountRef",
    "DimensionRef",
    "DimensionValueRef",
    "PaymentTermsRef",
    
    # Invoice types
    "InvoicePayload",
    "InvoiceLinePayload",
    "CreatedInvoiceRef",
    "PostedInvoiceRef",
    "InvoiceStatus",
    
    # Legacy types
    "ERPPostingRequest",
    "ERPPostingResponse",
    "ERPEntity",
    "ERPLookupResult",
    
    # Factory
    "create_connector",
    "register_connector",
    "list_available_connectors",
]
