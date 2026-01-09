"""Abstract ERP Connector Interface.

This module defines the abstract interface that all ERP connectors must implement.
It is intentionally ERP-agnostic - no Business Central, SAP, or Oracle specifics here.

Connectors implement this interface to:
1. Connect and authenticate with their ERP
2. Transform canonical models to ERP-specific formats
3. Post documents (invoices, journals, etc.)
4. Query and lookup entities (vendors, GL accounts, etc.)

Key Design Principles:
- All methods return NORMALIZED objects (EntityRef, VendorRef, etc.) - not ERP-specific
- Temporal workflows and API routes depend ONLY on this interface
- ERP-specific implementations live in connector subfolders
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar, Generic

from pydantic import BaseModel, Field

# Note: We avoid importing from core.models here to prevent circular imports
# InvoiceDocument is imported only in methods that need it


# =============================================================================
# Enums
# =============================================================================

class ERPEntityType(str, Enum):
    """Types of entities in an ERP system."""
    VENDOR = "VENDOR"
    CUSTOMER = "CUSTOMER"
    GL_ACCOUNT = "GL_ACCOUNT"
    ITEM = "ITEM"
    LOCATION = "LOCATION"
    PROJECT = "PROJECT"
    DIMENSION = "DIMENSION"
    DIMENSION_VALUE = "DIMENSION_VALUE"
    COST_CENTER = "COST_CENTER"
    DEPARTMENT = "DEPARTMENT"
    TAX_GROUP = "TAX_GROUP"
    PAYMENT_TERMS = "PAYMENT_TERMS"
    COMPANY = "COMPANY"  # Entity/company within the ERP


class ERPConnectionStatus(str, Enum):
    """Connection status to ERP system."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    AUTHENTICATING = "AUTHENTICATING"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"


class ERPDocumentType(str, Enum):
    """Types of documents that can be posted to ERP."""
    PURCHASE_INVOICE = "PURCHASE_INVOICE"
    PURCHASE_CREDIT_MEMO = "PURCHASE_CREDIT_MEMO"
    GENERAL_JOURNAL = "GENERAL_JOURNAL"
    PAYMENT = "PAYMENT"


class ERPPostingStatus(str, Enum):
    """Status of a posting attempt."""
    SUCCESS = "SUCCESS"
    PENDING = "PENDING"
    DRAFT = "DRAFT"  # Document created but not posted
    VALIDATION_FAILED = "VALIDATION_FAILED"
    POSTING_FAILED = "POSTING_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    CONNECTION_ERROR = "CONNECTION_ERROR"


class InvoiceStatus(str, Enum):
    """Status of an invoice document in the ERP."""
    DRAFT = "DRAFT"           # Created but not posted
    OPEN = "OPEN"             # Posted, awaiting payment
    PAID = "PAID"             # Fully paid
    PARTIALLY_PAID = "PARTIALLY_PAID"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


# =============================================================================
# Normalized Reference Models (ERP-Agnostic)
# =============================================================================
# These models are what Temporal workflows and API routes see.
# They contain no ERP-specific fields - just normalized business data.

class EntityRef(BaseModel):
    """Reference to a company/entity within the ERP.
    
    In BC: this is a "company"
    In SAP: this is a "company code"
    In Oracle: this is a "legal entity"
    
    IMPORTANT: Both id (API identifier) and code (human number) are stored.
    - id: Use for API calls (e.g., BC GUID like "5d115e9a-...")
    - code: Display to users (e.g., "CRONUS USA, Inc.")
    """
    id: str = Field(..., description="ERP internal ID/GUID for API calls")
    code: str = Field(..., description="Human-readable code/number for display")
    name: str = Field(..., description="Display name")
    is_active: bool = Field(default=True)
    currency_code: Optional[str] = Field(default=None, description="Default currency")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional ERP-specific data")
    
    class Config:
        frozen = True  # Immutable


class VendorRef(BaseModel):
    """Normalized vendor reference.
    
    Contains only the fields needed for invoice processing.
    ERP-specific fields go in metadata if needed.
    
    IMPORTANT: Both id (API identifier) and code (human number) are stored.
    - id: Use for API calls (e.g., BC GUID like "a1b2c3d4-...")
    - code: Display to users (e.g., "V00010" or "ACME-001")
    """
    id: str = Field(..., description="ERP internal ID/GUID for API calls")
    code: str = Field(..., description="Vendor number/code for display (e.g., 'V00010')")
    name: str = Field(..., description="Vendor display name")
    is_active: bool = Field(default=True)
    
    # Common fields across ERPs
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    phone: Optional[str] = None
    email: Optional[str] = None
    
    tax_id: Optional[str] = Field(default=None, description="Tax registration number")
    currency_code: Optional[str] = Field(default=None, description="Default currency")
    payment_terms_code: Optional[str] = Field(default=None)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True


class GLAccountRef(BaseModel):
    """Normalized G/L Account reference.
    
    Standard chart of accounts reference used for invoice line coding.
    
    IMPORTANT: Both id (API identifier) and code (account number) are stored.
    - id: Use for API calls (e.g., BC GUID)
    - code: Display to users (e.g., "5100" or "6100-001")
    """
    id: str = Field(..., description="ERP internal ID/GUID for API calls")
    code: str = Field(..., description="Account number for display (e.g., '5100')")
    name: str = Field(..., description="Account name (e.g., 'Cost of Goods Sold')")
    is_active: bool = Field(default=True)
    
    # Common categorization
    category: Optional[str] = Field(default=None, description="Account category (Asset, Expense, etc.)")
    subcategory: Optional[str] = Field(default=None)
    account_type: Optional[str] = Field(default=None, description="Posting, Heading, Total, etc.")
    
    # Posting rules
    direct_posting: bool = Field(default=True, description="Can post directly to this account")
    blocked: bool = Field(default=False)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True


class DimensionRef(BaseModel):
    """Normalized dimension reference.
    
    Dimensions are analysis codes used for reporting (cost centers, projects, etc.)
    In BC: Dimensions
    In SAP: Cost elements, profit centers
    In Oracle: Segments
    
    IMPORTANT: Both id (API identifier) and code (dimension code) are stored.
    """
    id: str = Field(..., description="ERP internal ID/GUID for API calls")
    code: str = Field(..., description="Dimension code (e.g., 'COSTCENTER', 'PROJECT')")
    name: str = Field(..., description="Dimension name")
    is_active: bool = Field(default=True)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True


class DimensionValueRef(BaseModel):
    """Normalized dimension value reference.
    
    A specific value within a dimension (e.g., 'SALES' in DEPARTMENT dimension).
    """
    id: str = Field(..., description="ERP internal ID")
    code: str = Field(..., description="Value code")
    name: str = Field(..., description="Value display name")
    dimension_code: str = Field(..., description="Parent dimension code")
    is_active: bool = Field(default=True)
    
    # Hierarchy support
    parent_code: Optional[str] = Field(default=None, description="Parent value for hierarchical dimensions")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True


class PaymentTermsRef(BaseModel):
    """Normalized payment terms reference."""
    id: str = Field(..., description="ERP internal ID")
    code: str = Field(..., description="Terms code (e.g., 'NET30')")
    name: str = Field(..., description="Terms description")
    due_days: Optional[int] = Field(default=None, description="Days until due")
    discount_percent: Optional[Decimal] = Field(default=None)
    discount_days: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True


# =============================================================================
# Invoice Models (Normalized for ERP posting)
# =============================================================================

class InvoiceLinePayload(BaseModel):
    """A single line item for invoice creation."""
    line_number: int
    description: str
    gl_account_code: str = Field(..., description="G/L account code to post to")
    
    quantity: Decimal = Field(default=Decimal("1"))
    unit_price: Decimal
    amount: Decimal = Field(..., description="Line total (qty * price)")
    
    # Optional dimension coding
    dimensions: Dict[str, str] = Field(
        default_factory=dict,
        description="Dimension code -> value code mapping"
    )
    
    # Tax handling
    tax_code: Optional[str] = None
    tax_amount: Optional[Decimal] = None


class InvoicePayload(BaseModel):
    """Normalized invoice payload for ERP posting.
    
    This is the input for create_purchase_invoice_unposted().
    It contains all data needed to create an invoice, but no ERP-specific IDs.
    """
    # Vendor
    vendor_code: str = Field(..., description="Vendor number/code")
    
    # Document info
    external_document_no: str = Field(..., description="Original invoice number from vendor")
    document_date: date = Field(..., description="Invoice date")
    due_date: Optional[date] = None
    posting_date: Optional[date] = Field(default=None, description="Date for GL posting")
    
    # Amounts
    currency_code: Optional[str] = Field(default=None, description="Currency (defaults to entity currency)")
    
    # Lines
    lines: List[InvoiceLinePayload] = Field(default_factory=list)
    
    # Header dimensions (applied to all lines if not overridden)
    dimensions: Dict[str, str] = Field(default_factory=dict)
    
    # Optional description/memo
    description: Optional[str] = None
    
    # Source tracking
    source_system: Optional[str] = Field(default=None, description="System that created this")
    source_reference: Optional[str] = Field(default=None, description="Reference in source system")
    
    @property
    def total_amount(self) -> Decimal:
        """Calculate total from lines."""
        return sum(line.amount for line in self.lines)


class CreatedInvoiceRef(BaseModel):
    """Reference to an invoice created in the ERP.
    
    Returned by create_purchase_invoice_unposted().
    """
    id: str = Field(..., description="ERP internal document ID")
    document_number: Optional[str] = Field(default=None, description="ERP document number (may be assigned on post)")
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    
    # Echo back the input
    vendor_code: str
    external_document_no: str
    total_amount: Decimal
    currency_code: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # For idempotency
    idempotency_key: Optional[str] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostedInvoiceRef(BaseModel):
    """Reference to a posted invoice.
    
    Returned by post_purchase_invoice().
    """
    id: str = Field(..., description="ERP internal document ID")
    document_number: str = Field(..., description="Posted document number")
    status: InvoiceStatus = Field(default=InvoiceStatus.OPEN)
    
    posted_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Ledger entries created
    ledger_entries: List[str] = Field(default_factory=list, description="G/L entry IDs")
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Legacy Data Classes (for backward compatibility)
# =============================================================================

@dataclass
class ERPConfig:
    """Configuration for an ERP connector.
    
    Generic configuration that can be extended by specific connectors.
    """
    connector_type: str                     # "business_central", "sap", etc.
    environment: str = "production"         # "production", "sandbox"
    base_url: Optional[str] = None          # ERP API endpoint
    tenant_id: Optional[str] = None         # Multi-tenant identifier
    company_id: Optional[str] = None        # Company/entity within ERP
    
    # Authentication (connector-specific)
    auth_type: str = "oauth2"               # "oauth2", "api_key", "basic"
    auth_config: Dict[str, Any] = field(default_factory=dict)
    
    # Behavior
    auto_post: bool = False                 # Automatically post after validation
    require_approval: bool = True           # Require human approval before posting
    retry_on_failure: bool = True           # Retry failed postings
    max_retries: int = 3
    
    # Mapping configuration
    mapping_file: Optional[str] = None      # Path to mapping rules JSON
    
    # ERP-specific settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ERPEntity:
    """An entity retrieved from the ERP system."""
    entity_type: ERPEntityType
    erp_id: str                             # Primary key in ERP
    code: str                               # Display code
    name: str                               # Display name
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ERPPostingRequest:
    """Request to post a document to the ERP.
    
    Contains the canonical document plus mapping results.
    DEPRECATED: Use InvoicePayload with create_purchase_invoice_unposted instead.
    """
    request_id: str                         # Unique request identifier
    document_type: ERPDocumentType
    ap_package_id: str                      # Source AP package
    
    # Mapped values (from mapping engine)
    vendor_id: str                          # ERP vendor ID
    vendor_name: Optional[str] = None
    
    # Document details
    document_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    external_document_no: Optional[str] = None  # Original invoice number
    
    # Lines
    lines: List[Dict[str, Any]] = field(default_factory=list)
    
    # Totals
    total_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    
    # Dimensions/coding
    dimensions: Dict[str, str] = field(default_factory=dict)
    
    # Source reference (artifact path or reference)
    source_invoice_ref: Optional[str] = None
    
    # Posting options
    post_immediately: bool = False          # Post vs create as draft
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ERPPostingResponse:
    """Response from posting a document to the ERP."""
    request_id: str
    status: ERPPostingStatus
    
    # Success details
    erp_document_id: Optional[str] = None   # ERP internal ID
    erp_document_number: Optional[str] = None  # ERP document number
    posted_at: Optional[datetime] = None
    
    # Error details
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    
    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None
    
    def is_success(self) -> bool:
        return self.status == ERPPostingStatus.SUCCESS


@dataclass 
class ERPLookupResult:
    """Result of an entity lookup in the ERP."""
    found: bool
    entity: Optional[ERPEntity] = None
    suggestions: List[ERPEntity] = field(default_factory=list)
    error_message: Optional[str] = None


# =============================================================================
# Abstract Connector Interface
# =============================================================================

class ERPConnector(ABC):
    """Abstract base class for ERP connectors.
    
    All ERP-specific connectors must implement this interface.
    This keeps the core system ERP-agnostic.
    
    DESIGN PRINCIPLE:
    - Temporal workflows and API routes depend ONLY on this interface
    - All methods return NORMALIZED objects (VendorRef, GLAccountRef, etc.)
    - No BC/SAP/Oracle-specific types leak through this interface
    
    Implementations:
    - connectors/business_central/bc_connector.py
    - connectors/sap/ (future)
    - connectors/oracle/ (future)
    """
    
    def __init__(self, config: ERPConfig):
        """Initialize connector with configuration."""
        self.config = config
        self._connection_status = ERPConnectionStatus.DISCONNECTED
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the ERP system.
        
        Returns:
            True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the ERP system."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection is valid and authenticated.
        
        Returns:
            True if connection is healthy
        """
        pass
    
    @property
    def connection_status(self) -> ERPConnectionStatus:
        """Get current connection status."""
        return self._connection_status
    
    # =========================================================================
    # Entity Listing (Primary Interface - Returns Normalized Types)
    # =========================================================================
    
    @abstractmethod
    async def list_entities(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EntityRef]:
        """List companies/entities available in the ERP.
        
        In BC: Lists companies
        In SAP: Lists company codes
        In Oracle: Lists legal entities
        
        Args:
            active_only: Only return active entities
            limit: Maximum number to return
            offset: Pagination offset
            
        Returns:
            List of EntityRef (normalized company references)
        """
        pass
    
    @abstractmethod
    async def list_vendors(
        self,
        entity_id: str,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[VendorRef]:
        """List vendors in the specified entity.
        
        Args:
            entity_id: Company/entity ID
            active_only: Only return active/unblocked vendors
            limit: Maximum number to return
            offset: Pagination offset
            search: Optional search string (name or code)
            
        Returns:
            List of VendorRef (normalized vendor references)
        """
        pass
    
    @abstractmethod
    async def list_gl_accounts(
        self,
        entity_id: str,
        active_only: bool = True,
        direct_posting_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[GLAccountRef]:
        """List G/L accounts in the specified entity.
        
        Args:
            entity_id: Company/entity ID
            active_only: Only return unblocked accounts
            direct_posting_only: Only return accounts that allow direct posting
            limit: Maximum number to return
            offset: Pagination offset
            search: Optional search string (name or code)
            
        Returns:
            List of GLAccountRef (normalized G/L account references)
        """
        pass
    
    @abstractmethod
    async def list_dimensions(
        self,
        entity_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DimensionRef]:
        """List dimensions (analysis codes) in the specified entity.
        
        Args:
            entity_id: Company/entity ID
            limit: Maximum number to return
            offset: Pagination offset
            
        Returns:
            List of DimensionRef (normalized dimension references)
        """
        pass
    
    @abstractmethod
    async def list_dimension_values(
        self,
        entity_id: str,
        dimension_code: str,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DimensionValueRef]:
        """List values for a specific dimension.
        
        Args:
            entity_id: Company/entity ID
            dimension_code: The dimension code (e.g., 'DEPARTMENT', 'PROJECT')
            active_only: Only return active values
            limit: Maximum number to return
            offset: Pagination offset
            
        Returns:
            List of DimensionValueRef (normalized dimension value references)
        """
        pass
    
    # =========================================================================
    # Individual Entity Lookup
    # =========================================================================
    
    async def get_vendor(
        self,
        entity_id: str,
        vendor_code: str,
    ) -> Optional[VendorRef]:
        """Get a specific vendor by code.
        
        Args:
            entity_id: Company/entity ID
            vendor_code: Vendor number/code
            
        Returns:
            VendorRef if found, None otherwise
        """
        # Default implementation using list - connectors can override for efficiency
        vendors = await self.list_vendors(
            entity_id=entity_id,
            search=vendor_code,
            limit=10,
        )
        for v in vendors:
            if v.code == vendor_code:
                return v
        return None
    
    async def get_gl_account(
        self,
        entity_id: str,
        account_code: str,
    ) -> Optional[GLAccountRef]:
        """Get a specific G/L account by code.
        
        Args:
            entity_id: Company/entity ID
            account_code: Account number
            
        Returns:
            GLAccountRef if found, None otherwise
        """
        accounts = await self.list_gl_accounts(
            entity_id=entity_id,
            search=account_code,
            limit=10,
        )
        for a in accounts:
            if a.code == account_code:
                return a
        return None
    
    # =========================================================================
    # Invoice Operations (v1 - Optional, can raise NotImplementedError)
    # =========================================================================
    
    async def create_purchase_invoice_unposted(
        self,
        entity_id: str,
        payload: InvoicePayload,
        idempotency_key: Optional[str] = None,
    ) -> CreatedInvoiceRef:
        """Create a purchase invoice as a draft (unposted).
        
        This creates the invoice in the ERP but does NOT post it to the ledger.
        The invoice remains in draft status for review before posting.
        
        Args:
            entity_id: Company/entity ID
            payload: Normalized invoice payload
            idempotency_key: Unique key to prevent duplicate creation
            
        Returns:
            CreatedInvoiceRef with the ERP document ID
            
        Raises:
            NotImplementedError: If connector doesn't support invoice creation yet
        """
        raise NotImplementedError(
            f"{self.get_connector_name()} does not yet support invoice creation"
        )
    
    async def post_purchase_invoice(
        self,
        entity_id: str,
        invoice_id: str,
    ) -> PostedInvoiceRef:
        """Post a draft invoice to the ledger.
        
        This takes a previously created draft invoice and posts it,
        creating the actual G/L entries.
        
        Args:
            entity_id: Company/entity ID
            invoice_id: The ERP document ID from create_purchase_invoice_unposted
            
        Returns:
            PostedInvoiceRef with the posted document number
            
        Raises:
            NotImplementedError: If connector doesn't support posting yet
        """
        raise NotImplementedError(
            f"{self.get_connector_name()} does not yet support invoice posting"
        )
    
    async def get_invoice_status(
        self,
        entity_id: str,
        invoice_id: str,
    ) -> Optional[InvoiceStatus]:
        """Get the current status of an invoice.
        
        Args:
            entity_id: Company/entity ID
            invoice_id: The ERP document ID
            
        Returns:
            InvoiceStatus or None if not found
        """
        raise NotImplementedError(
            f"{self.get_connector_name()} does not yet support invoice status"
        )
    
    # =========================================================================
    # Legacy Interface (Backward Compatibility)
    # =========================================================================
    
    @abstractmethod
    async def lookup_entity(
        self, 
        entity_type: ERPEntityType, 
        code: Optional[str] = None,
        name: Optional[str] = None,
        erp_id: Optional[str] = None,
    ) -> ERPLookupResult:
        """Lookup an entity in the ERP by code, name, or ID.
        
        DEPRECATED: Use list_vendors, list_gl_accounts, etc. instead.
        Kept for backward compatibility.
        """
        pass
    
    @abstractmethod
    async def list_entities_legacy(
        self,
        entity_type: ERPEntityType,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ERPEntity]:
        """List entities of a given type.
        
        DEPRECATED: Use list_vendors, list_gl_accounts, etc. instead.
        Returns legacy ERPEntity objects.
        """
        pass
    
    # -------------------------------------------------------------------------
    # Document Posting (Legacy)
    # -------------------------------------------------------------------------
    
    @abstractmethod
    async def validate_posting(self, request: ERPPostingRequest) -> List[str]:
        """Validate a posting request before submitting.
        
        Args:
            request: The posting request to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        pass
    
    @abstractmethod
    async def post_document(self, request: ERPPostingRequest) -> ERPPostingResponse:
        """Post a document to the ERP system.
        
        DEPRECATED: Use create_purchase_invoice_unposted + post_purchase_invoice
        """
        pass
    
    @abstractmethod
    async def get_posting_status(self, erp_document_id: str) -> Optional[ERPPostingResponse]:
        """Get the status of a previously posted document.
        
        Args:
            erp_document_id: The ERP internal document ID
            
        Returns:
            Current status, or None if not found
        """
        pass
    
    # -------------------------------------------------------------------------
    # Data Transformation (Legacy)
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def transform_invoice(
        self, 
        invoice: "InvoiceDocument",
        vendor_id: str,
        line_mappings: List[Dict[str, str]],
    ) -> ERPPostingRequest:
        """Transform a canonical invoice to an ERP posting request.
        
        Args:
            invoice: Canonical invoice document
            vendor_id: Mapped ERP vendor ID
            line_mappings: GL account mappings for each line item
            
        Returns:
            ERPPostingRequest ready for posting
        """
        pass
    
    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    
    def get_connector_name(self) -> str:
        """Get the name of this connector."""
        return self.config.connector_type
    
    def get_environment(self) -> str:
        """Get the environment (production/sandbox)."""
        return self.config.environment


# =============================================================================
# Connector Factory
# =============================================================================

_connector_registry: Dict[str, type] = {}


def register_connector(connector_type: str):
    """Decorator to register a connector implementation."""
    def decorator(cls):
        _connector_registry[connector_type] = cls
        return cls
    return decorator


def create_connector(config: ERPConfig) -> ERPConnector:
    """Create a connector instance from configuration.
    
    Args:
        config: ERPConfig with connector_type specified
        
    Returns:
        Configured connector instance
        
    Raises:
        ValueError: If connector_type is not registered
    """
    connector_type = config.connector_type.lower()
    
    if connector_type not in _connector_registry:
        available = list(_connector_registry.keys())
        raise ValueError(
            f"Unknown connector type: {connector_type}. "
            f"Available: {available}"
        )
    
    connector_class = _connector_registry[connector_type]
    return connector_class(config)


def list_available_connectors() -> List[str]:
    """List all registered connector types."""
    return list(_connector_registry.keys())
