"""Business Central ERP Connector.

Implements the ERPConnector interface for Microsoft Dynamics 365 Business Central.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from connectors.erp_base import (
    ERPConnector,
    ERPConfig,
    ERPConnectionStatus,
    ERPEntityType,
    ERPEntity,
    ERPPostingRequest,
    ERPPostingResponse,
    ERPPostingStatus,
    ERPLookupResult,
    ERPDocumentType,
    register_connector,
    # Normalized types
    EntityRef,
    VendorRef,
    GLAccountRef,
    DimensionRef,
    DimensionValueRef,
    InvoicePayload,
    CreatedInvoiceRef,
    PostedInvoiceRef,
    InvoiceStatus,
)
from connectors.business_central.bc_auth import BCAuthProvider, BCAuthConfig
from connectors.business_central.bc_client import BCApiClient, BCApiConfig
from connectors.business_central.bc_models import (
    BCVendor,
    BCGLAccount,
    BCDimension,
    BCDimensionValue,
    BCPurchaseInvoice,
    BCPurchaseInvoiceLine,
)
from core.models import InvoiceDocument


@register_connector("business_central")
class BusinessCentralConnector(ERPConnector):
    """Business Central connector implementation.
    
    Connects to Microsoft Dynamics 365 Business Central via REST API.
    
    Required configuration:
    - auth_config.tenant_id: Azure AD tenant ID
    - auth_config.client_id: Application client ID
    - auth_config.client_secret: Client secret
    - company_id: BC company ID (GUID)
    
    Optional configuration:
    - custom_settings.environment: BC environment (default: "production")
    - custom_settings.api_version: API version (default: "v2.0")
    """
    
    def __init__(self, config: ERPConfig):
        super().__init__(config)
        
        # Initialize auth provider
        auth_config = BCAuthConfig(
            tenant_id=config.auth_config.get("tenant_id", ""),
            client_id=config.auth_config.get("client_id", ""),
            client_secret=config.auth_config.get("client_secret", ""),
            environment=config.custom_settings.get("environment", "production"),
        )
        self._auth_provider = BCAuthProvider(auth_config)
        
        # Initialize API client configuration
        api_config = BCApiConfig(
            api_version=config.custom_settings.get("api_version", "v2.0"),
            environment=config.custom_settings.get("environment", "production"),
            company_id=config.company_id,
        )
        
        self._api_client = BCApiClient(
            self._auth_provider,
            api_config,
            auth_config.tenant_id,
        )
        
        # Entity caches
        self._vendor_cache: Dict[str, BCVendor] = {}
        self._gl_account_cache: Dict[str, BCGLAccount] = {}
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    async def connect(self) -> bool:
        """Establish connection to Business Central."""
        self._connection_status = ERPConnectionStatus.AUTHENTICATING
        
        try:
            success = await self._api_client.connect()
            
            if success:
                self._connection_status = ERPConnectionStatus.CONNECTED
                return True
            else:
                self._connection_status = ERPConnectionStatus.FAILED
                return False
                
        except Exception as e:
            print(f"BC connection failed: {e}")
            self._connection_status = ERPConnectionStatus.FAILED
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Business Central."""
        await self._api_client.disconnect()
        self._connection_status = ERPConnectionStatus.DISCONNECTED
    
    async def test_connection(self) -> bool:
        """Test if the connection is valid."""
        try:
            # Try to list companies as a health check
            vendors = await self._api_client.list("vendors", top=1)
            return True
        except Exception as e:
            print(f"BC connection test failed: {e}")
            return False
    
    # =========================================================================
    # Entity Lookup
    # =========================================================================
    
    async def lookup_entity(
        self,
        entity_type: ERPEntityType,
        code: Optional[str] = None,
        name: Optional[str] = None,
        erp_id: Optional[str] = None,
    ) -> ERPLookupResult:
        """Lookup an entity in Business Central."""
        
        if entity_type == ERPEntityType.VENDOR:
            return await self._lookup_vendor(code, name, erp_id)
        elif entity_type == ERPEntityType.GL_ACCOUNT:
            return await self._lookup_gl_account(code, name, erp_id)
        else:
            return ERPLookupResult(
                found=False,
                error_message=f"Entity type {entity_type} not supported"
            )
    
    async def _lookup_vendor(
        self,
        code: Optional[str],
        name: Optional[str],
        erp_id: Optional[str],
    ) -> ERPLookupResult:
        """Lookup a vendor in BC."""
        try:
            if erp_id:
                # Direct lookup by ID
                vendor_data = await self._api_client.get("vendors", erp_id)
                vendor = BCVendor.model_validate(vendor_data)
                return ERPLookupResult(
                    found=True,
                    entity=ERPEntity(
                        entity_type=ERPEntityType.VENDOR,
                        erp_id=vendor.id or "",
                        code=vendor.number or "",
                        name=vendor.displayName or "",
                        is_active=vendor.blocked != "All",
                    )
                )
            
            # Search by number or name
            filter_expr = None
            if code:
                filter_expr = f"number eq '{code}'"
            elif name:
                filter_expr = f"contains(displayName, '{name}')"
            
            if not filter_expr:
                return ERPLookupResult(found=False, error_message="No search criteria provided")
            
            vendors = await self._api_client.list("vendors", filter=filter_expr, top=5)
            
            if not vendors:
                return ERPLookupResult(found=False)
            
            # Return first match, rest as suggestions
            first = BCVendor.model_validate(vendors[0])
            entity = ERPEntity(
                entity_type=ERPEntityType.VENDOR,
                erp_id=first.id or "",
                code=first.number or "",
                name=first.displayName or "",
                is_active=first.blocked != "All",
            )
            
            suggestions = []
            for v_data in vendors[1:]:
                v = BCVendor.model_validate(v_data)
                suggestions.append(ERPEntity(
                    entity_type=ERPEntityType.VENDOR,
                    erp_id=v.id or "",
                    code=v.number or "",
                    name=v.displayName or "",
                ))
            
            return ERPLookupResult(found=True, entity=entity, suggestions=suggestions)
            
        except Exception as e:
            return ERPLookupResult(found=False, error_message=str(e))
    
    async def _lookup_gl_account(
        self,
        code: Optional[str],
        name: Optional[str],
        erp_id: Optional[str],
    ) -> ERPLookupResult:
        """Lookup a GL account in BC."""
        try:
            if erp_id:
                account_data = await self._api_client.get("accounts", erp_id)
                account = BCGLAccount.model_validate(account_data)
                return ERPLookupResult(
                    found=True,
                    entity=ERPEntity(
                        entity_type=ERPEntityType.GL_ACCOUNT,
                        erp_id=account.id or "",
                        code=account.number or "",
                        name=account.displayName or "",
                        is_active=not account.blocked,
                    )
                )
            
            filter_expr = None
            if code:
                filter_expr = f"number eq '{code}'"
            elif name:
                filter_expr = f"contains(displayName, '{name}')"
            
            if not filter_expr:
                return ERPLookupResult(found=False, error_message="No search criteria provided")
            
            accounts = await self._api_client.list("accounts", filter=filter_expr, top=5)
            
            if not accounts:
                return ERPLookupResult(found=False)
            
            first = BCGLAccount.model_validate(accounts[0])
            entity = ERPEntity(
                entity_type=ERPEntityType.GL_ACCOUNT,
                erp_id=first.id or "",
                code=first.number or "",
                name=first.displayName or "",
                is_active=not first.blocked,
            )
            
            return ERPLookupResult(found=True, entity=entity)
            
        except Exception as e:
            return ERPLookupResult(found=False, error_message=str(e))
    
    # =========================================================================
    # Normalized Entity Listing (Primary Interface)
    # =========================================================================
    
    async def list_entities(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EntityRef]:
        """List companies available in Business Central."""
        try:
            # BC API: /companies
            companies = await self._api_client.list_companies()
            
            result = []
            for company in companies[offset:offset + limit]:
                result.append(EntityRef(
                    id=company.get("id", ""),
                    code=company.get("name", ""),  # BC uses name as code
                    name=company.get("displayName", company.get("name", "")),
                    is_active=True,  # BC companies don't have active flag
                    metadata={"systemVersion": company.get("systemVersion")},
                ))
            
            return result
            
        except Exception as e:
            print(f"Failed to list companies: {e}")
            return []
    
    async def list_vendors(
        self,
        entity_id: str,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[VendorRef]:
        """List vendors in the specified company."""
        try:
            # Build filter
            filters = []
            if active_only:
                filters.append("blocked eq 'None' or blocked eq ''")
            if search:
                filters.append(f"(contains(number, '{search}') or contains(displayName, '{search}'))")
            
            filter_expr = " and ".join(filters) if filters else None
            
            results = await self._api_client.list(
                "vendors",
                filter=filter_expr,
                top=limit,
                skip=offset,
                company_id=entity_id,
            )
            
            vendors = []
            for data in results:
                v = BCVendor.model_validate(data)
                vendors.append(VendorRef(
                    id=v.id or "",
                    code=v.number or "",
                    name=v.displayName or "",
                    is_active=v.blocked in (None, "", "None"),
                    address_line1=v.addressLine1,
                    address_line2=v.addressLine2,
                    city=v.city,
                    state=v.state,
                    postal_code=v.postalCode,
                    country=v.country,
                    phone=v.phoneNumber,
                    email=v.email,
                    tax_id=v.taxRegistrationNumber,
                    currency_code=v.currencyCode,
                    metadata={"paymentTermsId": v.paymentTermsId},
                ))
            
            return vendors
            
        except Exception as e:
            print(f"Failed to list vendors: {e}")
            return []
    
    async def list_gl_accounts(
        self,
        entity_id: str,
        active_only: bool = True,
        direct_posting_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> List[GLAccountRef]:
        """List G/L accounts in the specified company."""
        try:
            # Build filter
            filters = []
            if active_only:
                filters.append("blocked eq false")
            if direct_posting_only:
                filters.append("directPosting eq true")
            if search:
                filters.append(f"(contains(number, '{search}') or contains(displayName, '{search}'))")
            
            filter_expr = " and ".join(filters) if filters else None
            
            results = await self._api_client.list(
                "accounts",
                filter=filter_expr,
                top=limit,
                skip=offset,
                company_id=entity_id,
            )
            
            accounts = []
            for data in results:
                a = BCGLAccount.model_validate(data)
                accounts.append(GLAccountRef(
                    id=a.id or "",
                    code=a.number or "",
                    name=a.displayName or "",
                    is_active=not a.blocked,
                    category=a.category,
                    subcategory=a.subCategory,
                    account_type=a.accountType,
                    direct_posting=a.directPosting or False,
                    blocked=a.blocked or False,
                    metadata={},
                ))
            
            return accounts
            
        except Exception as e:
            print(f"Failed to list GL accounts: {e}")
            return []
    
    async def list_dimensions(
        self,
        entity_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DimensionRef]:
        """List dimensions in the specified company."""
        try:
            results = await self._api_client.list(
                "dimensions",
                top=limit,
                skip=offset,
                company_id=entity_id,
            )
            
            dimensions = []
            for data in results:
                d = BCDimension.model_validate(data)
                dimensions.append(DimensionRef(
                    id=d.id or "",
                    code=d.code or "",
                    name=d.displayName or "",
                    is_active=True,  # BC dimensions don't have active flag
                    metadata={},
                ))
            
            return dimensions
            
        except Exception as e:
            print(f"Failed to list dimensions: {e}")
            return []
    
    async def list_dimension_values(
        self,
        entity_id: str,
        dimension_code: str,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DimensionValueRef]:
        """List values for a specific dimension."""
        try:
            # First get the dimension ID
            dimensions = await self.list_dimensions(entity_id)
            dimension_id = None
            for d in dimensions:
                if d.code == dimension_code:
                    dimension_id = d.id
                    break
            
            if not dimension_id:
                return []
            
            # BC API: dimensionValues filtered by dimensionId
            results = await self._api_client.list(
                "dimensionValues",
                filter=f"dimensionId eq {dimension_id}",
                top=limit,
                skip=offset,
                company_id=entity_id,
            )
            
            values = []
            for data in results:
                v = BCDimensionValue.model_validate(data)
                values.append(DimensionValueRef(
                    id=v.id or "",
                    code=v.code or "",
                    name=v.displayName or "",
                    dimension_code=dimension_code,
                    is_active=True,
                    metadata={},
                ))
            
            return values
            
        except Exception as e:
            print(f"Failed to list dimension values: {e}")
            return []
    
    # =========================================================================
    # Legacy Entity Listing (Backward Compatibility)
    # =========================================================================
    
    async def list_entities_legacy(
        self,
        entity_type: ERPEntityType,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ERPEntity]:
        """List entities of a given type from BC."""
        endpoint_map = {
            ERPEntityType.VENDOR: "vendors",
            ERPEntityType.GL_ACCOUNT: "accounts",
            ERPEntityType.LOCATION: "locations",
            ERPEntityType.DIMENSION: "dimensions",
        }
        
        endpoint = endpoint_map.get(entity_type)
        if not endpoint:
            return []
        
        try:
            filter_expr = None
            if active_only:
                if entity_type == ERPEntityType.VENDOR:
                    filter_expr = "blocked eq 'None'"
                elif entity_type == ERPEntityType.GL_ACCOUNT:
                    filter_expr = "blocked eq false"
            
            results = await self._api_client.list(
                endpoint,
                filter=filter_expr,
                top=limit,
                skip=offset,
            )
            
            entities = []
            for data in results:
                if entity_type == ERPEntityType.VENDOR:
                    v = BCVendor.model_validate(data)
                    entities.append(ERPEntity(
                        entity_type=entity_type,
                        erp_id=v.id or "",
                        code=v.number or "",
                        name=v.displayName or "",
                    ))
                elif entity_type == ERPEntityType.GL_ACCOUNT:
                    a = BCGLAccount.model_validate(data)
                    entities.append(ERPEntity(
                        entity_type=entity_type,
                        erp_id=a.id or "",
                        code=a.number or "",
                        name=a.displayName or "",
                    ))
            
            return entities
            
        except Exception as e:
            print(f"Failed to list entities: {e}")
            return []
    
    # =========================================================================
    # Invoice Operations (Normalized Interface)
    # =========================================================================
    
    async def create_purchase_invoice_unposted(
        self,
        entity_id: str,
        payload: InvoicePayload,
        idempotency_key: Optional[str] = None,
    ) -> CreatedInvoiceRef:
        """Create a purchase invoice as a draft in Business Central.
        
        The invoice is created but NOT posted to the ledger.
        """
        try:
            # First, look up the vendor by code
            vendors = await self.list_vendors(entity_id, search=payload.vendor_code, limit=1)
            if not vendors:
                raise ValueError(f"Vendor not found: {payload.vendor_code}")
            vendor = vendors[0]
            
            # Build BC purchase invoice payload
            invoice_data = {
                "vendorId": vendor.id,
                "invoiceDate": payload.document_date.isoformat() if payload.document_date else None,
                "vendorInvoiceNumber": payload.external_document_no,
            }
            
            if payload.due_date:
                invoice_data["dueDate"] = payload.due_date.isoformat()
            if payload.posting_date:
                invoice_data["postingDate"] = payload.posting_date.isoformat()
            if payload.currency_code:
                invoice_data["currencyCode"] = payload.currency_code
            
            # Create invoice header
            created = await self._api_client.create(
                "purchaseInvoices",
                invoice_data,
                company_id=entity_id,
            )
            invoice_id = created.get("id")
            invoice_number = created.get("number")
            
            # Add lines
            for line in payload.lines:
                # Look up G/L account
                accounts = await self.list_gl_accounts(
                    entity_id, 
                    search=line.gl_account_code, 
                    limit=1,
                    direct_posting_only=True,
                )
                if not accounts:
                    raise ValueError(f"G/L account not found: {line.gl_account_code}")
                
                line_data = {
                    "lineType": "Account",  # G/L Account line
                    "lineObjectNumber": accounts[0].code,
                    "description": line.description[:50] if line.description else "",
                    "quantity": float(line.quantity),
                    "directUnitCost": float(line.unit_price),
                }
                
                # Add dimension values if present
                if line.dimensions:
                    # BC uses dimensionSetLines for dimensions on lines
                    # This is a simplified version - full implementation would create dimension set
                    line_data["dimensionSetLines"] = [
                        {"code": dim_code, "valueCode": dim_value}
                        for dim_code, dim_value in line.dimensions.items()
                    ]
                
                await self._api_client.create(
                    f"purchaseInvoices({invoice_id})/purchaseInvoiceLines",
                    line_data,
                    company_id=entity_id,
                )
            
            return CreatedInvoiceRef(
                id=invoice_id,
                document_number=invoice_number,
                status=InvoiceStatus.DRAFT,
                vendor_code=payload.vendor_code,
                external_document_no=payload.external_document_no,
                total_amount=payload.total_amount,
                currency_code=payload.currency_code,
                idempotency_key=idempotency_key,
                created_at=datetime.utcnow(),
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to create invoice: {e}") from e
    
    async def post_purchase_invoice(
        self,
        entity_id: str,
        invoice_id: str,
    ) -> PostedInvoiceRef:
        """Post a draft invoice to the ledger."""
        try:
            # Post the invoice using BC action
            await self._api_client.post_action(
                "purchaseInvoices",
                invoice_id,
                "post",
                company_id=entity_id,
            )
            
            # Get the updated invoice to get the posted document number
            invoice_data = await self._api_client.get(
                "purchaseInvoices",
                invoice_id,
                company_id=entity_id,
            )
            
            return PostedInvoiceRef(
                id=invoice_id,
                document_number=invoice_data.get("number", ""),
                status=InvoiceStatus.OPEN,
                posted_at=datetime.utcnow(),
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to post invoice: {e}") from e
    
    async def get_invoice_status(
        self,
        entity_id: str,
        invoice_id: str,
    ) -> Optional[InvoiceStatus]:
        """Get the current status of an invoice."""
        try:
            invoice_data = await self._api_client.get(
                "purchaseInvoices",
                invoice_id,
                company_id=entity_id,
            )
            
            status = invoice_data.get("status", "")
            status_map = {
                "Draft": InvoiceStatus.DRAFT,
                "Open": InvoiceStatus.OPEN,
                "Paid": InvoiceStatus.PAID,
                "Canceled": InvoiceStatus.CANCELLED,
            }
            return status_map.get(status, InvoiceStatus.UNKNOWN)
            
        except Exception as e:
            return None
    
    # =========================================================================
    # Document Posting (Legacy)
    # =========================================================================
    
    async def validate_posting(self, request: ERPPostingRequest) -> List[str]:
        """Validate a posting request before submitting to BC."""
        errors = []
        
        # Validate vendor exists
        vendor_result = await self.lookup_entity(
            ERPEntityType.VENDOR,
            erp_id=request.vendor_id
        )
        if not vendor_result.found:
            errors.append(f"Vendor not found: {request.vendor_id}")
        elif vendor_result.entity and not vendor_result.entity.is_active:
            errors.append(f"Vendor is blocked: {request.vendor_id}")
        
        # Validate GL accounts for all lines
        for i, line in enumerate(request.lines):
            gl_account = line.get("gl_account")
            if gl_account:
                account_result = await self.lookup_entity(
                    ERPEntityType.GL_ACCOUNT,
                    code=gl_account
                )
                if not account_result.found:
                    errors.append(f"Line {i+1}: GL account not found: {gl_account}")
        
        # Validate required fields
        if not request.document_date:
            errors.append("Document date is required")
        
        if request.total_amount is None or request.total_amount <= 0:
            errors.append("Total amount must be positive")
        
        if not request.lines:
            errors.append("At least one line is required")
        
        return errors
    
    async def post_document(self, request: ERPPostingRequest) -> ERPPostingResponse:
        """Post a purchase invoice to Business Central."""
        try:
            # Validate first
            errors = await self.validate_posting(request)
            if errors:
                return ERPPostingResponse(
                    request_id=request.request_id,
                    status=ERPPostingStatus.VALIDATION_FAILED,
                    validation_errors=errors,
                )
            
            # Build BC purchase invoice
            invoice_data = {
                "vendorId": request.vendor_id,
                "invoiceDate": request.document_date.strftime("%Y-%m-%d") if request.document_date else None,
                "vendorInvoiceNumber": request.external_document_no,
            }
            
            if request.due_date:
                invoice_data["dueDate"] = request.due_date.strftime("%Y-%m-%d")
            
            # Create invoice header
            created = await self._api_client.create("purchaseInvoices", invoice_data)
            invoice_id = created.get("id")
            invoice_number = created.get("number")
            
            # Add lines
            for line in request.lines:
                line_data = {
                    "lineType": "Account",  # G/L Account line
                    "lineObjectNumber": line.get("gl_account"),
                    "description": line.get("description", "")[:50],
                    "quantity": float(line.get("quantity", 1)),
                    "directUnitCost": float(line.get("unit_cost", line.get("amount", 0))),
                }
                
                await self._api_client.create(
                    f"purchaseInvoices({invoice_id})/purchaseInvoiceLines",
                    line_data
                )
            
            # Post if requested
            if request.post_immediately:
                await self._api_client.post_action("purchaseInvoices", invoice_id, "post")
            
            return ERPPostingResponse(
                request_id=request.request_id,
                status=ERPPostingStatus.SUCCESS,
                erp_document_id=invoice_id,
                erp_document_number=invoice_number,
                posted_at=datetime.utcnow() if request.post_immediately else None,
            )
            
        except Exception as e:
            return ERPPostingResponse(
                request_id=request.request_id,
                status=ERPPostingStatus.POSTING_FAILED,
                error_message=str(e),
            )
    
    async def get_posting_status(self, erp_document_id: str) -> Optional[ERPPostingResponse]:
        """Get status of a posted document."""
        try:
            invoice_data = await self._api_client.get("purchaseInvoices", erp_document_id)
            invoice = BCPurchaseInvoice.model_validate(invoice_data)
            
            return ERPPostingResponse(
                request_id="",  # Not tracked
                status=ERPPostingStatus.SUCCESS if invoice.status == "Open" else ERPPostingStatus.PENDING,
                erp_document_id=invoice.id,
                erp_document_number=invoice.number,
            )
            
        except Exception as e:
            return None
    
    # =========================================================================
    # Data Transformation
    # =========================================================================
    
    def transform_invoice(
        self,
        invoice: InvoiceDocument,
        vendor_id: str,
        line_mappings: List[Dict[str, str]],
    ) -> ERPPostingRequest:
        """Transform a canonical invoice to a BC posting request."""
        
        # Build lines
        lines = []
        for i, line_item in enumerate(invoice.line_items):
            mapping = line_mappings[i] if i < len(line_mappings) else {}
            
            lines.append({
                "description": line_item.description[:50],
                "quantity": float(line_item.quantity or 1),
                "unit_cost": float(line_item.rate or line_item.total or 0),
                "amount": float(line_item.total or 0),
                "gl_account": mapping.get("gl_account"),
            })
        
        # Calculate total
        total = Decimal("0")
        if invoice.totals and invoice.totals.total_amount_due:
            total = invoice.totals.total_amount_due
        else:
            for line in invoice.line_items:
                if line.total:
                    total += line.total
        
        return ERPPostingRequest(
            request_id=str(uuid.uuid4()),
            document_type=ERPDocumentType.PURCHASE_INVOICE,
            ap_package_id="",  # Set by caller
            vendor_id=vendor_id,
            vendor_name=invoice.feedlot.name if invoice.feedlot else None,
            document_date=invoice.invoice_date,
            external_document_no=invoice.invoice_number,
            lines=lines,
            total_amount=total,
            dimensions={
                "lot": invoice.lot.lot_number if invoice.lot else None,
            },
        )
