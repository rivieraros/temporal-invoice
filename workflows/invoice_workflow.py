"""
Invoice Processing Workflow

Per-invoice child workflow that orchestrates:
EXTRACT → VALIDATE → RECONCILE_LINK → RESOLVE_ENTITY → RESOLVE_VENDOR → 
APPLY_MAPPING_OVERLAY → BUILD_ERP_PAYLOAD → PAYLOAD_GENERATED

This workflow is designed to be called as a child workflow from APPackageWorkflow,
or can be started independently for single invoice processing.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
with workflow.unsafe.imports_passed_through():
    from activities.integrate import (
        resolve_entity,
        resolve_vendor,
        apply_mapping_overlay,
        build_bc_payload,
        persist_audit_event,
        ResolveEntityInput,
        ResolveVendorInput,
        ApplyMappingInput,
        BuildPayloadInput,
        AuditEventInput,
        InvoiceStage,
    )


# =============================================================================
# Workflow Input/Output
# =============================================================================

class ProcessingStatus(str, Enum):
    """Overall processing status"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class InvoiceWorkflowInput:
    """Input for invoice processing workflow"""
    ap_package_id: str
    invoice_number: str
    feedlot_type: str
    customer_id: str
    
    # Invoice data (already extracted)
    invoice_data: Dict[str, Any]
    
    # Optional statement data for dimension resolution
    statement_data: Optional[Dict[str, Any]] = None
    
    # Pre-resolved values (optional, for optimization)
    entity_id: Optional[str] = None
    vendor_id: Optional[str] = None
    
    # Skip certain stages if already done
    skip_entity_resolution: bool = False
    skip_vendor_resolution: bool = False
    
    # Stop at specific stage (for v1, stop at PAYLOAD_GENERATED)
    stop_at_stage: str = "PAYLOAD_GENERATED"


@dataclass
class StageResult:
    """Result from a processing stage"""
    stage: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED", "NEEDS_REVIEW"
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class InvoiceWorkflowOutput:
    """Output from invoice processing workflow"""
    ap_package_id: str
    invoice_number: str
    status: str
    current_stage: str
    
    # Resolution results
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    bc_company_id: Optional[str] = None
    
    vendor_id: Optional[str] = None
    vendor_number: Optional[str] = None
    vendor_name: Optional[str] = None
    
    # Coding results
    is_fully_coded: bool = False
    missing_mappings: List[str] = field(default_factory=list)
    
    # Payload results
    payload_ref: Optional[Dict[str, Any]] = None
    is_payload_ready: bool = False
    
    # Stage results for audit
    stage_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Error info
    error_message: Optional[str] = None
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)


# =============================================================================
# Invoice Processing Workflow
# =============================================================================

@workflow.defn
class InvoiceWorkflow:
    """
    Per-invoice processing workflow.
    
    Orchestrates the full invoice processing pipeline:
    1. RESOLVE_ENTITY - Determine BC company
    2. RESOLVE_VENDOR - Match vendor to BC vendor
    3. APPLY_MAPPING_OVERLAY - Generate GL coding
    4. BUILD_ERP_PAYLOAD - Create BC-ready payload
    5. PAYLOAD_GENERATED - Stop (v1)
    
    Note: EXTRACT, VALIDATE, RECONCILE_LINK stages are assumed
    to be completed before this workflow is called (in APPackageWorkflow).
    """
    
    def __init__(self):
        self.current_stage = InvoiceStage.RESOLVE_ENTITY
        self.stage_results: List[StageResult] = []
        self.needs_review = False
        self.review_reasons: List[str] = []
    
    @workflow.run
    async def run(self, input: InvoiceWorkflowInput) -> InvoiceWorkflowOutput:
        """Execute the invoice processing workflow."""
        workflow.logger.info(f"Starting invoice workflow for {input.invoice_number}")
        
        # Initialize result
        result = InvoiceWorkflowOutput(
            ap_package_id=input.ap_package_id,
            invoice_number=input.invoice_number,
            status=ProcessingStatus.IN_PROGRESS.value,
            current_stage=InvoiceStage.RESOLVE_ENTITY.value,
        )
        
        # Activity options for ERP activities (resolve_entity, resolve_vendor, mapping, payload)
        # These may be rate-limited by Business Central API
        erp_activity_options = {
            "start_to_close_timeout": timedelta(minutes=2),
            "retry_policy": RetryPolicy(
                maximum_attempts=5,
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(minutes=1),
                backoff_coefficient=2.0,
                # Don't retry on validation/schema errors - these won't self-heal
                non_retryable_error_types=["ValidationError", "SchemaError", "AuthenticationError"],
            ),
            "task_queue": "ap-erp",  # Separate queue for ERP activities
        }
        
        # Activity options for DB activities (audit events)
        db_activity_options = {
            "start_to_close_timeout": timedelta(seconds=30),
            "retry_policy": RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                non_retryable_error_types=["IntegrityError", "ConstraintError"],
            ),
            "task_queue": "ap-default",
        }
        
        # Legacy activity_options for backwards compatibility
        activity_options = erp_activity_options
        
        try:
            # =================================================================
            # Stage: RESOLVE_ENTITY
            # =================================================================
            if not input.skip_entity_resolution and not input.entity_id:
                self.current_stage = InvoiceStage.RESOLVE_ENTITY
                
                # Extract feedlot info from invoice
                feedlot_info = input.invoice_data.get("feedlot", {})
                
                entity_result = await workflow.execute_activity(
                    resolve_entity,
                    ResolveEntityInput(
                        customer_id=input.customer_id,
                        feedlot_name=feedlot_info.get("name", input.feedlot_type),
                        address_state=feedlot_info.get("state"),
                        address_city=feedlot_info.get("city"),
                    ),
                    **activity_options,
                )
                
                result.entity_id = entity_result.entity_id
                result.entity_name = entity_result.entity_name
                result.bc_company_id = entity_result.bc_company_id
                
                self._record_stage_result(
                    InvoiceStage.RESOLVE_ENTITY, 
                    "SUCCESS",
                    {"entity_id": entity_result.entity_id, "confidence": entity_result.confidence},
                )
                
                # Audit event
                await self._audit_event(
                    input.ap_package_id,
                    input.invoice_number,
                    InvoiceStage.RESOLVE_ENTITY,
                    "SUCCESS",
                    {"entity_id": entity_result.entity_id},
                    activity_options,
                )
            else:
                # Use pre-resolved or skip
                result.entity_id = input.entity_id or self._infer_entity_id(input.feedlot_type)
                result.bc_company_id = result.entity_id  # Simplified mapping
                
                self._record_stage_result(
                    InvoiceStage.RESOLVE_ENTITY,
                    "SKIPPED",
                    {"entity_id": result.entity_id, "reason": "pre-resolved"},
                )
            
            # Check stop condition
            if input.stop_at_stage == InvoiceStage.RESOLVE_ENTITY.value:
                result.status = ProcessingStatus.COMPLETED.value
                result.current_stage = InvoiceStage.RESOLVE_ENTITY.value
                return self._finalize_result(result)
            
            # =================================================================
            # Stage: RESOLVE_VENDOR
            # =================================================================
            if not input.skip_vendor_resolution and not input.vendor_id:
                self.current_stage = InvoiceStage.RESOLVE_VENDOR
                
                feedlot_info = input.invoice_data.get("feedlot", {})
                
                vendor_result = await workflow.execute_activity(
                    resolve_vendor,
                    ResolveVendorInput(
                        customer_id=input.customer_id,
                        entity_id=result.entity_id,
                        vendor_name=feedlot_info.get("name", input.feedlot_type),
                        address_state=feedlot_info.get("state"),
                        address_city=feedlot_info.get("city"),
                    ),
                    **activity_options,
                )
                
                result.vendor_id = vendor_result.vendor_id
                result.vendor_number = vendor_result.vendor_number
                result.vendor_name = vendor_result.vendor_name
                
                if vendor_result.needs_confirmation:
                    self.needs_review = True
                    self.review_reasons.append(f"Vendor match needs confirmation: {vendor_result.match_type}")
                
                self._record_stage_result(
                    InvoiceStage.RESOLVE_VENDOR,
                    "SUCCESS" if vendor_result.is_auto_matched else "NEEDS_REVIEW",
                    {
                        "vendor_id": vendor_result.vendor_id,
                        "match_type": vendor_result.match_type,
                        "confidence": vendor_result.confidence,
                    },
                )
                
                await self._audit_event(
                    input.ap_package_id,
                    input.invoice_number,
                    InvoiceStage.RESOLVE_VENDOR,
                    "SUCCESS",
                    {"vendor_id": vendor_result.vendor_id, "auto_matched": vendor_result.is_auto_matched},
                    activity_options,
                )
            else:
                result.vendor_id = input.vendor_id
                self._record_stage_result(
                    InvoiceStage.RESOLVE_VENDOR,
                    "SKIPPED",
                    {"vendor_id": result.vendor_id, "reason": "pre-resolved"},
                )
            
            if input.stop_at_stage == InvoiceStage.RESOLVE_VENDOR.value:
                result.status = ProcessingStatus.COMPLETED.value
                result.current_stage = InvoiceStage.RESOLVE_VENDOR.value
                return self._finalize_result(result)
            
            # =================================================================
            # Stage: APPLY_MAPPING_OVERLAY
            # =================================================================
            self.current_stage = InvoiceStage.APPLY_MAPPING_OVERLAY
            
            mapping_result = await workflow.execute_activity(
                apply_mapping_overlay,
                ApplyMappingInput(
                    invoice_data=input.invoice_data,
                    entity_id=result.entity_id,
                    vendor_id=result.vendor_id,
                    vendor_info={
                        "vendor_id": result.vendor_id,
                        "vendor_number": result.vendor_number,
                        "vendor_name": result.vendor_name,
                    },
                    statement_data=input.statement_data,
                ),
                **activity_options,
            )
            
            result.is_fully_coded = mapping_result.is_complete
            result.missing_mappings = mapping_result.missing_mappings
            
            if not mapping_result.is_complete:
                self.needs_review = True
                if mapping_result.missing_mappings:
                    self.review_reasons.append(f"Missing mappings: {mapping_result.missing_mappings}")
                if mapping_result.missing_dimensions:
                    self.review_reasons.append(f"Missing dimensions: {mapping_result.missing_dimensions}")
            
            self._record_stage_result(
                InvoiceStage.APPLY_MAPPING_OVERLAY,
                "SUCCESS" if mapping_result.is_complete else "NEEDS_REVIEW",
                {
                    "lines_coded": len(mapping_result.line_codings),
                    "is_complete": mapping_result.is_complete,
                    "coding_ref": mapping_result.coding_ref,
                },
            )
            
            await self._audit_event(
                input.ap_package_id,
                input.invoice_number,
                InvoiceStage.APPLY_MAPPING_OVERLAY,
                "SUCCESS",
                {"lines": len(mapping_result.line_codings), "complete": mapping_result.is_complete},
                activity_options,
            )
            
            if input.stop_at_stage == InvoiceStage.APPLY_MAPPING_OVERLAY.value:
                result.status = ProcessingStatus.COMPLETED.value
                result.current_stage = InvoiceStage.APPLY_MAPPING_OVERLAY.value
                return self._finalize_result(result)
            
            # =================================================================
            # Stage: BUILD_ERP_PAYLOAD
            # =================================================================
            self.current_stage = InvoiceStage.BUILD_ERP_PAYLOAD
            
            payload_result = await workflow.execute_activity(
                build_bc_payload,
                BuildPayloadInput(
                    invoice_data=input.invoice_data,
                    entity_id=result.entity_id,
                    vendor_info={
                        "vendor_id": result.vendor_id,
                        "vendor_number": result.vendor_number,
                        "vendor_name": result.vendor_name,
                    },
                    coding_result={
                        "line_codings": mapping_result.line_codings,
                    },
                    bc_company_id=result.bc_company_id,
                ),
                **activity_options,
            )
            
            result.payload_ref = payload_result.payload_ref
            result.is_payload_ready = payload_result.is_ready
            
            if not payload_result.is_ready:
                self.needs_review = True
                self.review_reasons.extend(payload_result.validation_errors)
            
            self._record_stage_result(
                InvoiceStage.BUILD_ERP_PAYLOAD,
                "SUCCESS" if payload_result.is_ready else "NEEDS_REVIEW",
                {
                    "is_ready": payload_result.is_ready,
                    "payload_ref": payload_result.payload_ref,
                    "errors": payload_result.validation_errors,
                },
            )
            
            await self._audit_event(
                input.ap_package_id,
                input.invoice_number,
                InvoiceStage.BUILD_ERP_PAYLOAD,
                "SUCCESS" if payload_result.is_ready else "NEEDS_REVIEW",
                {"ready": payload_result.is_ready, "payload_ref": payload_result.payload_ref},
                activity_options,
            )
            
            # =================================================================
            # Stage: PAYLOAD_GENERATED (v1 stop point)
            # =================================================================
            self.current_stage = InvoiceStage.PAYLOAD_GENERATED
            
            await self._audit_event(
                input.ap_package_id,
                input.invoice_number,
                InvoiceStage.PAYLOAD_GENERATED,
                "SUCCESS",
                {"payload_ready": result.is_payload_ready},
                activity_options,
            )
            
            # Determine final status
            if self.needs_review:
                result.status = ProcessingStatus.NEEDS_REVIEW.value
            else:
                result.status = ProcessingStatus.COMPLETED.value
            
            result.current_stage = InvoiceStage.PAYLOAD_GENERATED.value
            
            workflow.logger.info(
                f"Invoice workflow completed: {input.invoice_number} "
                f"status={result.status}, payload_ready={result.is_payload_ready}"
            )
            
            return self._finalize_result(result)
            
        except Exception as e:
            workflow.logger.error(f"Invoice workflow failed: {e}")
            
            result.status = ProcessingStatus.FAILED.value
            result.error_message = str(e)
            
            # Audit the failure
            await self._audit_event(
                input.ap_package_id,
                input.invoice_number,
                self.current_stage,
                "FAILED",
                {},
                activity_options,
                error_message=str(e),
            )
            
            return self._finalize_result(result)
    
    def _record_stage_result(
        self,
        stage: InvoiceStage,
        status: str,
        data: Dict[str, Any],
    ) -> None:
        """Record a stage result for audit trail."""
        self.stage_results.append(StageResult(
            stage=stage.value,
            status=status,
            data=data,
        ))
    
    async def _audit_event(
        self,
        ap_package_id: str,
        invoice_number: str,
        stage: InvoiceStage,
        status: str,
        details: Dict[str, Any],
        activity_options: Dict,
        error_message: Optional[str] = None,
    ) -> None:
        """Persist an audit event."""
        await workflow.execute_activity(
            persist_audit_event,
            AuditEventInput(
                ap_package_id=ap_package_id,
                invoice_number=invoice_number,
                stage=stage.value,
                status=status,
                details=details,
                error_message=error_message,
            ),
            **activity_options,
        )
    
    def _finalize_result(self, result: InvoiceWorkflowOutput) -> InvoiceWorkflowOutput:
        """Finalize the result with stage data."""
        result.needs_review = self.needs_review
        result.review_reasons = self.review_reasons
        result.stage_results = [
            {
                "stage": sr.stage,
                "status": sr.status,
                "data": sr.data,
            }
            for sr in self.stage_results
        ]
        return result
    
    def _infer_entity_id(self, feedlot_type: str) -> str:
        """Infer entity ID from feedlot type."""
        mapping = {
            "BOVINA": "BF2",
            "MESQUITE": "MESQ",
        }
        return mapping.get(feedlot_type.upper(), feedlot_type)
