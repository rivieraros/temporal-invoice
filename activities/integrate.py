"""
Integration Activities for AP Automation Pipeline

Activities that integrate all components:
- resolve_entity: Determine BC company from document
- resolve_vendor: Match vendor using alias/fuzzy matching
- apply_mapping_overlay: Generate GL coding for invoice lines
- build_bc_payload: Create BC-ready purchase invoice payload
- persist_audit_event: Log audit trail events
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from temporalio import activity

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from entity_resolver import EntityResolver
from vendor_resolver import VendorResolver, init_vendor_resolver_db
from coding_engine import CodingEngine, code_invoice, init_coding_engine_db


# =============================================================================
# Paths
# =============================================================================

ARTIFACTS_PATH = Path(__file__).resolve().parents[1] / "artifacts"
DB_PATH = Path(__file__).resolve().parents[1] / "ap_automation.db"


# =============================================================================
# Activity Input/Output Models
# =============================================================================

class InvoiceStage(str, Enum):
    """Invoice processing stages"""
    EXTRACT = "EXTRACT"
    VALIDATE = "VALIDATE"
    RECONCILE_LINK = "RECONCILE_LINK"
    RESOLVE_ENTITY = "RESOLVE_ENTITY"
    RESOLVE_VENDOR = "RESOLVE_VENDOR"
    APPLY_MAPPING_OVERLAY = "APPLY_MAPPING_OVERLAY"
    BUILD_ERP_PAYLOAD = "BUILD_ERP_PAYLOAD"
    PAYLOAD_GENERATED = "PAYLOAD_GENERATED"
    CREATE_UNPOSTED = "CREATE_UNPOSTED"  # v1.5


@dataclass
class ResolveEntityInput:
    """Input for resolve_entity activity"""
    customer_id: str
    feedlot_name: str
    address_state: Optional[str] = None
    address_city: Optional[str] = None


@dataclass
class ResolveEntityOutput:
    """Output from resolve_entity activity"""
    entity_id: str
    entity_name: str
    bc_company_id: str
    confidence: float
    match_reasons: List[str] = field(default_factory=list)


@dataclass
class ResolveVendorInput:
    """Input for resolve_vendor activity"""
    customer_id: str
    entity_id: str
    vendor_name: str
    address_state: Optional[str] = None
    address_city: Optional[str] = None


@dataclass
class ResolveVendorOutput:
    """Output from resolve_vendor activity"""
    vendor_id: str
    vendor_number: str
    vendor_name: str
    is_auto_matched: bool
    match_type: str
    confidence: float
    needs_confirmation: bool = False
    candidates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ApplyMappingInput:
    """Input for apply_mapping_overlay activity"""
    invoice_data: Dict[str, Any]
    entity_id: str
    vendor_id: Optional[str] = None
    vendor_info: Optional[Dict[str, Any]] = None
    statement_data: Optional[Dict[str, Any]] = None


@dataclass
class ApplyMappingOutput:
    """Output from apply_mapping_overlay activity"""
    invoice_number: str
    entity_id: str
    is_complete: bool
    line_codings: List[Dict[str, Any]]
    missing_mappings: List[str]
    missing_dimensions: List[str]
    warnings: List[str]
    coding_ref: Dict[str, Any]  # DataReference to coding JSON


@dataclass
class BuildPayloadInput:
    """Input for build_bc_payload activity"""
    invoice_data: Dict[str, Any]
    entity_id: str
    vendor_info: Dict[str, Any]
    coding_result: Dict[str, Any]
    bc_company_id: str


@dataclass
class BuildPayloadOutput:
    """Output from build_bc_payload activity"""
    invoice_number: str
    payload: Dict[str, Any]
    payload_ref: Dict[str, Any]  # DataReference to payload JSON
    is_ready: bool
    validation_errors: List[str]


@dataclass
class AuditEventInput:
    """Input for persist_audit_event activity"""
    ap_package_id: str
    invoice_number: str
    stage: str
    status: str
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class AuditEventOutput:
    """Output from persist_audit_event activity"""
    event_id: int
    timestamp: str
    success: bool


# =============================================================================
# Helper Functions
# =============================================================================

def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def create_data_reference(artifact_path: str, content: str) -> Dict[str, Any]:
    """Create a DataReference dict for an artifact"""
    return {
        "path": artifact_path,
        "hash": compute_hash(content),
        "created_at": datetime.now().isoformat(),
    }


def save_artifact(feedlot_key: str, subdir: str, filename: str, data: Any) -> Dict[str, Any]:
    """Save artifact and return DataReference"""
    # Ensure directory exists
    artifact_dir = ARTIFACTS_PATH / feedlot_key / subdir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    artifact_path = artifact_dir / filename
    content = json.dumps(data, indent=2, default=str)
    artifact_path.write_text(content)
    
    # Return reference
    rel_path = f"{feedlot_key}/{subdir}/{filename}"
    return create_data_reference(rel_path, content)


# =============================================================================
# resolve_entity Activity
# =============================================================================

@activity.defn
async def resolve_entity(input: ResolveEntityInput) -> ResolveEntityOutput:
    """
    Resolve entity (BC company) from document content.
    
    Uses EntityResolver to determine which BC company this document belongs to.
    """
    activity.logger.info(f"Resolving entity for customer={input.customer_id}, feedlot={input.feedlot_name}")
    
    resolver = EntityResolver(customer_id=input.customer_id)
    
    # Build invoice dict for resolver API
    invoice = {
        "feedlot": {
            "name": input.feedlot_name,
            "state": input.address_state,
            "city": input.address_city,
        }
    }
    
    result = await resolver.resolve_entity(invoice=invoice)
    
    # Extract entity info from result
    if result.is_auto_assigned:
        entity_id = result.entity_id
        entity_name = result.entity_name or entity_id
        bc_company_id = result.bc_company_id or entity_id
        confidence = float(result.confidence or 0)
        match_reasons = result.reasons or []
    elif result.candidates:
        top = result.candidates[0]
        entity_id = top.entity_id
        entity_name = top.entity_name or entity_id
        bc_company_id = top.entity_id  # Simplified
        confidence = float(top.score or 0)
        match_reasons = [f"Top candidate: {top.match_type}"]
    else:
        entity_id = ""
        entity_name = ""
        bc_company_id = ""
        confidence = 0.0
        match_reasons = result.reasons or ["No entities matched"]
    
    activity.logger.info(f"Entity resolved: {entity_id} ({confidence}%)")
    
    return ResolveEntityOutput(
        entity_id=entity_id,
        entity_name=entity_name,
        bc_company_id=bc_company_id,
        confidence=confidence,
        match_reasons=match_reasons,
    )


# =============================================================================
# resolve_vendor Activity
# =============================================================================

@activity.defn
async def resolve_vendor(input: ResolveVendorInput) -> ResolveVendorOutput:
    """
    Resolve vendor from extracted vendor/feedlot name.
    
    Uses VendorResolver with alias table and fuzzy matching.
    """
    activity.logger.info(f"Resolving vendor for entity={input.entity_id}, name={input.vendor_name}")
    
    # Initialize DB if needed
    init_vendor_resolver_db()
    
    resolver = VendorResolver(customer_id=input.customer_id)
    
    # Get vendor list for this entity (in real impl, from BC connector)
    # For now, use sample data
    vendor_list = _get_vendor_list_for_entity(input.entity_id)
    
    result = await resolver.resolve_vendor(
        extracted_name=input.vendor_name,
        entity_id=input.entity_id,
        vendor_list=vendor_list,
        extracted_address={"state": input.address_state, "city": input.address_city} if input.address_state else None,
    )
    
    confidence = float(result.confidence_score or 0)
    activity.logger.info(f"Vendor resolved: {result.vendor_id} (auto={result.is_auto_matched}, {confidence}%)")
    
    return ResolveVendorOutput(
        vendor_id=result.vendor_id or "",
        vendor_number=result.vendor_number or "",
        vendor_name=result.vendor_name or "",
        is_auto_matched=result.is_auto_matched,
        match_type=result.match_type.value,
        confidence=confidence,
        needs_confirmation=not result.is_auto_matched,
        candidates=[
            {
                "vendor_id": c.vendor_id,
                "vendor_number": c.vendor_number,
                "vendor_name": c.vendor_name,
                "score": float(c.combined_score or 0),
            }
            for c in result.candidates[:3]
        ] if result.candidates else [],
    )


def _get_vendor_list_for_entity(entity_id: str) -> List[Dict[str, Any]]:
    """Get vendor list for an entity (placeholder - in real impl, from BC)"""
    # Sample vendor lists per entity
    vendor_lists = {
        "BF2": [
            {"vendor_id": "V-BF2", "number": "V-BF2", "name": "Bovina Feeders Inc.", "address": {"state": "TX", "city": "FRIONA"}},
        ],
        "MESQ": [
            {"vendor_id": "V-MCF", "number": "V-MCF", "name": "Mesquite Cattle Feeders", "address": {"state": "CA", "city": "BRAWLEY"}},
        ],
    }
    return vendor_lists.get(entity_id, [])


# =============================================================================
# apply_mapping_overlay Activity
# =============================================================================

@activity.defn
async def apply_mapping_overlay(input: ApplyMappingInput) -> ApplyMappingOutput:
    """
    Apply GL mapping and dimension rules to invoice.
    
    Uses CodingEngine to generate GL coding for each line item.
    """
    activity.logger.info(f"Applying mapping overlay for entity={input.entity_id}")
    
    # Initialize DB if needed
    init_coding_engine_db()
    
    # Code the invoice
    coding = code_invoice(
        invoice=input.invoice_data,
        entity_id=input.entity_id,
        vendor_id=input.vendor_id,
        vendor=input.vendor_info,
        statement=input.statement_data,
    )
    
    # Save coding result as artifact
    invoice_number = input.invoice_data.get("invoice_number", "unknown")
    feedlot_key = _get_feedlot_key(input.entity_id)
    
    coding_data = coding.to_dict()
    coding_ref = save_artifact(
        feedlot_key=feedlot_key,
        subdir="codings",
        filename=f"{invoice_number}_coding.json",
        data=coding_data,
    )
    
    activity.logger.info(f"Coding complete: {len(coding.line_codings)} lines, complete={coding.is_complete}")
    
    return ApplyMappingOutput(
        invoice_number=coding.invoice_number,
        entity_id=coding.entity_id,
        is_complete=coding.is_complete,
        line_codings=[
            {
                "line_index": lc.line_index,
                "description": lc.description,
                "amount": str(lc.amount),
                "category": lc.category,
                "gl_ref": lc.gl_ref,
                "mapping_level": lc.mapping_level.value,
                "dimensions": [{"code": d.code, "value": d.value} for d in lc.dimensions],
            }
            for lc in coding.line_codings
        ],
        missing_mappings=coding.missing_mappings,
        missing_dimensions=coding.missing_dimensions,
        warnings=coding.warnings,
        coding_ref=coding_ref,
    )


def _get_feedlot_key(entity_id: str) -> str:
    """Map entity ID to feedlot key for artifacts"""
    mapping = {
        "BF2": "bovina",
        "MESQ": "mesquite",
    }
    return mapping.get(entity_id, entity_id.lower())


# =============================================================================
# build_bc_payload Activity
# =============================================================================

@activity.defn
async def build_bc_payload(input: BuildPayloadInput) -> BuildPayloadOutput:
    """
    Build Business Central-ready purchase invoice payload.
    
    Transforms coding result into BC API format.
    """
    activity.logger.info(f"Building BC payload for company={input.bc_company_id}")
    
    invoice_number = input.invoice_data.get("invoice_number", "unknown")
    validation_errors = []
    
    # Extract invoice data
    invoice_date = input.invoice_data.get("invoice_date", "")
    total_amount = input.invoice_data.get("total", 0)
    
    # Build header
    payload = {
        "purchaseInvoice": {
            "@odata.type": "#Microsoft.Dynamics.BC.purchaseInvoice",
            "vendorNumber": input.vendor_info.get("vendor_number", ""),
            "vendorName": input.vendor_info.get("vendor_name", ""),
            "invoiceDate": invoice_date,
            "vendorInvoiceNumber": invoice_number,
            "status": "Draft",
            "currencyCode": "USD",
        },
        "purchaseInvoiceLines": [],
    }
    
    # Build lines from coding result
    coding_lines = input.coding_result.get("line_codings", [])
    
    for idx, line in enumerate(coding_lines):
        # Build dimension set
        dimensions = {}
        for dim in line.get("dimensions", []):
            dimensions[dim["code"]] = dim["value"]
        
        bc_line = {
            "lineNumber": (idx + 1) * 10000,
            "description": line.get("description", ""),
            "lineType": "G/L Account",
            "accountId": line.get("gl_ref", "9999-00"),
            "quantity": 1,
            "unitPrice": float(line.get("amount", 0)),
            "lineAmount": float(line.get("amount", 0)),
            "dimensionSetLines": [
                {"code": k, "valueCode": v}
                for k, v in dimensions.items()
            ],
        }
        payload["purchaseInvoiceLines"].append(bc_line)
    
    # Validate payload
    if not payload["purchaseInvoice"]["vendorNumber"]:
        validation_errors.append("Missing vendor number")
    
    if not payload["purchaseInvoice"]["invoiceDate"]:
        validation_errors.append("Missing invoice date")
    
    if not payload["purchaseInvoiceLines"]:
        validation_errors.append("No invoice lines")
    
    # Check for suspense accounts
    suspense_lines = [
        l for l in coding_lines 
        if l.get("mapping_level") == "suspense"
    ]
    if suspense_lines:
        validation_errors.append(f"{len(suspense_lines)} line(s) mapped to suspense account")
    
    # Add metadata
    payload["_metadata"] = {
        "source": "ap-automation",
        "generatedAt": datetime.now().isoformat(),
        "invoiceNumber": invoice_number,
        "bcCompanyId": input.bc_company_id,
        "isReady": len(validation_errors) == 0,
    }
    
    # Save payload artifact
    feedlot_key = _get_feedlot_key(input.entity_id)
    payload_ref = save_artifact(
        feedlot_key=feedlot_key,
        subdir="payloads",
        filename=f"{invoice_number}_payload.json",
        data=payload,
    )
    
    is_ready = len(validation_errors) == 0
    activity.logger.info(f"Payload built: ready={is_ready}, errors={validation_errors}")
    
    return BuildPayloadOutput(
        invoice_number=invoice_number,
        payload=payload,
        payload_ref=payload_ref,
        is_ready=is_ready,
        validation_errors=validation_errors,
    )


# =============================================================================
# persist_audit_event Activity
# =============================================================================

@activity.defn
async def persist_audit_event(input: AuditEventInput) -> AuditEventOutput:
    """
    Persist an audit event for an invoice processing stage.
    
    Creates audit trail in database.
    """
    import sqlite3
    
    timestamp = datetime.now().isoformat()
    
    # Ensure audit table exists
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ap_package_id TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_package 
        ON audit_events(ap_package_id, invoice_number)
    """)
    
    # Insert event
    details_json = json.dumps(input.details) if input.details else None
    
    cursor.execute("""
        INSERT INTO audit_events 
        (ap_package_id, invoice_number, stage, status, details, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        input.ap_package_id,
        input.invoice_number,
        input.stage,
        input.status,
        details_json,
        input.error_message,
        timestamp,
    ))
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    activity.logger.info(f"Audit event {event_id}: {input.invoice_number} @ {input.stage} = {input.status}")
    
    return AuditEventOutput(
        event_id=event_id,
        timestamp=timestamp,
        success=True,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Activities
    "resolve_entity",
    "resolve_vendor", 
    "apply_mapping_overlay",
    "build_bc_payload",
    "persist_audit_event",
    
    # Input/Output classes
    "ResolveEntityInput",
    "ResolveEntityOutput",
    "ResolveVendorInput",
    "ResolveVendorOutput",
    "ApplyMappingInput",
    "ApplyMappingOutput",
    "BuildPayloadInput",
    "BuildPayloadOutput",
    "AuditEventInput",
    "AuditEventOutput",
    
    # Enums
    "InvoiceStage",
]
