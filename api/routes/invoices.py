"""Invoice endpoints.

Handles individual invoice operations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


router = APIRouter()


class LineItemResponse(BaseModel):
    """Invoice line item response."""
    description: str
    quantity: Optional[float] = None
    rate: Optional[float] = None
    total: Optional[float] = None
    gl_account: Optional[str] = None
    dimension_values: Dict[str, str] = {}


class InvoiceResponse(BaseModel):
    """Invoice response."""
    id: UUID
    package_id: UUID
    invoice_number: str
    invoice_date: Optional[date] = None
    vendor_name: Optional[str] = None
    vendor_code: Optional[str] = None
    feedlot: Optional[str] = None
    owner: Optional[str] = None
    lot_number: Optional[str] = None
    head_count: Optional[int] = None
    total_amount: Optional[float] = None
    line_items: List[LineItemResponse] = []
    status: str = "extracted"
    validation_warnings: List[str] = []
    erp_document_id: Optional[str] = None


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices."""
    items: List[InvoiceResponse]
    total: int
    page: int
    page_size: int


class InvoiceUpdateRequest(BaseModel):
    """Request to update invoice fields."""
    vendor_code: Optional[str] = None
    gl_account_overrides: Optional[Dict[int, str]] = Field(
        None,
        description="Map of line index to GL account code"
    )
    dimension_overrides: Optional[Dict[str, str]] = None
    notes: Optional[str] = None


class InvoiceLineUpdateRequest(BaseModel):
    """Request to update a specific line item."""
    description: Optional[str] = None
    quantity: Optional[float] = None
    rate: Optional[float] = None
    total: Optional[float] = None
    gl_account: Optional[str] = None


# In-memory store for demo
_invoices: Dict[UUID, Dict[str, Any]] = {}


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    package_id: Optional[UUID] = None,
    vendor_code: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> InvoiceListResponse:
    """List invoices with optional filtering."""
    items = list(_invoices.values())
    
    # Apply filters
    if package_id:
        items = [i for i in items if i.get("package_id") == package_id]
    if vendor_code:
        items = [i for i in items if i.get("vendor_code") == vendor_code]
    if status:
        items = [i for i in items if i.get("status") == status]
    if from_date:
        items = [i for i in items if i.get("invoice_date") and i["invoice_date"] >= from_date]
    if to_date:
        items = [i for i in items if i.get("invoice_date") and i["invoice_date"] <= to_date]
    
    # Paginate
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    
    return InvoiceListResponse(
        items=[InvoiceResponse(**i) for i in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: UUID) -> InvoiceResponse:
    """Get a specific invoice by ID."""
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return InvoiceResponse(**_invoices[invoice_id])


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    request: InvoiceUpdateRequest,
) -> InvoiceResponse:
    """Update invoice fields.
    
    Use this to set or override GL accounts, dimensions, etc.
    """
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices[invoice_id]
    
    if request.vendor_code:
        invoice["vendor_code"] = request.vendor_code
    
    if request.gl_account_overrides:
        for line_idx, gl_account in request.gl_account_overrides.items():
            if line_idx < len(invoice.get("line_items", [])):
                invoice["line_items"][line_idx]["gl_account"] = gl_account
    
    if request.dimension_overrides:
        invoice.setdefault("dimensions", {}).update(request.dimension_overrides)
    
    if request.notes:
        invoice["notes"] = request.notes
    
    return InvoiceResponse(**invoice)


@router.patch("/{invoice_id}/lines/{line_index}", response_model=InvoiceResponse)
async def update_invoice_line(
    invoice_id: UUID,
    line_index: int,
    request: InvoiceLineUpdateRequest,
) -> InvoiceResponse:
    """Update a specific line item."""
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices[invoice_id]
    lines = invoice.get("line_items", [])
    
    if line_index < 0 or line_index >= len(lines):
        raise HTTPException(status_code=404, detail="Line item not found")
    
    line = lines[line_index]
    
    if request.description is not None:
        line["description"] = request.description
    if request.quantity is not None:
        line["quantity"] = request.quantity
    if request.rate is not None:
        line["rate"] = request.rate
    if request.total is not None:
        line["total"] = request.total
    if request.gl_account is not None:
        line["gl_account"] = request.gl_account
    
    return InvoiceResponse(**invoice)


@router.get("/{invoice_id}/suggested-mappings")
async def get_suggested_mappings(invoice_id: UUID) -> Dict[str, Any]:
    """Get AI-suggested GL account mappings for an invoice."""
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices[invoice_id]
    
    # Would use mapping engine to suggest
    suggestions = []
    for i, line in enumerate(invoice.get("line_items", [])):
        suggestions.append({
            "line_index": i,
            "description": line.get("description", ""),
            "suggested_gl_account": None,
            "confidence": 0.0,
            "alternatives": [],
        })
    
    return {
        "invoice_id": str(invoice_id),
        "suggestions": suggestions,
    }


@router.post("/{invoice_id}/validate")
async def validate_invoice(invoice_id: UUID) -> Dict[str, Any]:
    """Run validation on an invoice."""
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices[invoice_id]
    
    warnings = []
    errors = []
    
    # Basic validation
    if not invoice.get("vendor_code"):
        warnings.append("No vendor code assigned")
    
    if not invoice.get("invoice_number"):
        errors.append("Missing invoice number")
    
    # Check line items have GL accounts
    for i, line in enumerate(invoice.get("line_items", [])):
        if not line.get("gl_account"):
            warnings.append(f"Line {i+1} has no GL account assigned")
    
    invoice["validation_warnings"] = warnings
    
    return {
        "invoice_id": str(invoice_id),
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


@router.post("/{invoice_id}/post")
async def post_invoice(
    invoice_id: UUID,
    connector_type: str = "business_central",
) -> Dict[str, Any]:
    """Post a single invoice to ERP."""
    if invoice_id not in _invoices:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice = _invoices[invoice_id]
    
    # Would trigger posting via connector
    invoice["status"] = "posting"
    
    return {
        "message": "Invoice posting started",
        "invoice_id": str(invoice_id),
        "connector": connector_type,
    }
