"""AP Package endpoints.

Handles creation, status, and retrieval of AP packages (statement + invoices).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field


router = APIRouter()


class PackageStatus(str, Enum):
    """Status of an AP package."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    RECONCILING = "reconciling"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    POSTING = "posting"
    POSTED = "posted"
    FAILED = "failed"


class PackageCreateRequest(BaseModel):
    """Request to create a new AP package."""
    vendor_code: str = Field(..., description="Vendor code or identifier")
    feedlot: Optional[str] = Field(None, description="Feedlot identifier")
    notes: Optional[str] = None


class PackageResponse(BaseModel):
    """AP package response."""
    id: UUID
    vendor_code: str
    feedlot: Optional[str]
    status: PackageStatus
    created_at: datetime
    updated_at: datetime
    statement_count: int = 0
    invoice_count: int = 0
    warnings: List[str] = []
    errors: List[str] = []


class PackageListResponse(BaseModel):
    """Paginated list of packages."""
    items: List[PackageResponse]
    total: int
    page: int
    page_size: int


class PackageSummary(BaseModel):
    """Summary of package processing."""
    statement_total: Optional[float]
    invoice_total: Optional[float]
    variance: Optional[float]
    variance_percentage: Optional[float]
    line_item_count: int
    reconciliation_status: str


# In-memory store for demo (replace with database)
_packages: Dict[UUID, Dict[str, Any]] = {}


@router.post("", response_model=PackageResponse, status_code=201)
async def create_package(request: PackageCreateRequest) -> PackageResponse:
    """Create a new AP package.
    
    Creates an empty package ready to receive statement and invoice documents.
    """
    package_id = uuid4()
    now = datetime.utcnow()
    
    package = {
        "id": package_id,
        "vendor_code": request.vendor_code,
        "feedlot": request.feedlot,
        "status": PackageStatus.PENDING,
        "created_at": now,
        "updated_at": now,
        "statement_count": 0,
        "invoice_count": 0,
        "warnings": [],
        "errors": [],
        "notes": request.notes,
    }
    
    _packages[package_id] = package
    
    return PackageResponse(**package)


@router.get("", response_model=PackageListResponse)
async def list_packages(
    status: Optional[PackageStatus] = None,
    vendor_code: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> PackageListResponse:
    """List AP packages with optional filtering."""
    items = list(_packages.values())
    
    # Apply filters
    if status:
        items = [p for p in items if p["status"] == status]
    if vendor_code:
        items = [p for p in items if p["vendor_code"] == vendor_code]
    
    # Paginate
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    
    return PackageListResponse(
        items=[PackageResponse(**p) for p in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package(package_id: UUID) -> PackageResponse:
    """Get a specific AP package by ID."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    return PackageResponse(**_packages[package_id])


@router.get("/{package_id}/summary", response_model=PackageSummary)
async def get_package_summary(package_id: UUID) -> PackageSummary:
    """Get processing summary for a package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    # Would compute from actual data
    return PackageSummary(
        statement_total=None,
        invoice_total=None,
        variance=None,
        variance_percentage=None,
        line_item_count=0,
        reconciliation_status="pending",
    )


@router.post("/{package_id}/statement")
async def upload_statement(
    package_id: UUID,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Upload a statement document to the package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    # Read file content
    content = await file.read()
    
    # Would store and trigger extraction workflow
    _packages[package_id]["statement_count"] += 1
    _packages[package_id]["status"] = PackageStatus.EXTRACTING
    _packages[package_id]["updated_at"] = datetime.utcnow()
    
    return {
        "message": "Statement uploaded",
        "filename": file.filename,
        "size": len(content),
        "status": "processing",
    }


@router.post("/{package_id}/invoices")
async def upload_invoices(
    package_id: UUID,
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    """Upload invoice documents to the package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    results = []
    for file in files:
        content = await file.read()
        results.append({
            "filename": file.filename,
            "size": len(content),
            "status": "processing",
        })
    
    _packages[package_id]["invoice_count"] += len(files)
    _packages[package_id]["status"] = PackageStatus.EXTRACTING
    _packages[package_id]["updated_at"] = datetime.utcnow()
    
    return {
        "message": f"Uploaded {len(files)} invoice(s)",
        "invoices": results,
    }


@router.post("/{package_id}/extract")
async def trigger_extraction(package_id: UUID) -> Dict[str, Any]:
    """Trigger extraction workflow for a package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    _packages[package_id]["status"] = PackageStatus.EXTRACTING
    _packages[package_id]["updated_at"] = datetime.utcnow()
    
    # Would start Temporal workflow
    return {
        "message": "Extraction started",
        "workflow_id": f"extraction-{package_id}",
    }


@router.post("/{package_id}/reconcile")
async def trigger_reconciliation(package_id: UUID) -> Dict[str, Any]:
    """Trigger reconciliation for a package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    _packages[package_id]["status"] = PackageStatus.RECONCILING
    _packages[package_id]["updated_at"] = datetime.utcnow()
    
    # Would start Temporal workflow
    return {
        "message": "Reconciliation started",
        "workflow_id": f"reconciliation-{package_id}",
    }


@router.post("/{package_id}/post")
async def post_to_erp(
    package_id: UUID,
    connector_type: str = "business_central",
) -> Dict[str, Any]:
    """Post package to ERP system."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    package = _packages[package_id]
    
    if package["status"] not in [PackageStatus.READY, PackageStatus.NEEDS_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Package not ready for posting. Current status: {package['status']}"
        )
    
    _packages[package_id]["status"] = PackageStatus.POSTING
    _packages[package_id]["updated_at"] = datetime.utcnow()
    
    # Would start Temporal posting workflow
    return {
        "message": "Posting to ERP started",
        "workflow_id": f"posting-{package_id}",
        "connector": connector_type,
    }


@router.delete("/{package_id}")
async def delete_package(package_id: UUID) -> Dict[str, str]:
    """Delete an AP package."""
    if package_id not in _packages:
        raise HTTPException(status_code=404, detail="Package not found")
    
    del _packages[package_id]
    
    return {"message": "Package deleted"}
