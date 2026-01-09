"""AP Package Workflow for orchestrating document processing.

Main workflow that accepts a package input and coordinates extraction,
reconciliation, and persistence activities.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.persist import (
        persist_package_started, 
        persist_invoice,
        update_package_status,
        update_invoice_status,
        PersistPackageInput,
        PersistInvoiceInput,
        UpdatePackageStatusInput,
        UpdateInvoiceStatusInput,
    )
    from activities.extract import (
        split_pdf,
        extract_statement,
        extract_invoice,
        SplitPdfInput,
        ExtractStatementInput,
        ExtractInvoiceInput,
    )
    from activities.validate import (
        validate_invoice,
        ValidateInvoiceInput,
    )
    from activities.reconcile import (
        reconcile_package,
        ReconcilePackageInput,
    )


@dataclass
class APPackageInput:
    """Input for AP Package Workflow.
    
    Attributes:
        ap_package_id: Unique identifier for the AP package
        feedlot_type: Type of feedlot (BOVINA or MESQUITE)
        pdf_path: Absolute path to the source PDF file
        document_refs: List of document references (serialized as dicts) - optional
    """
    ap_package_id: str
    feedlot_type: str
    pdf_path: str
    document_refs: Optional[List[dict]] = None


@workflow.defn
class APPackageWorkflow:
    """Workflow for processing an AP (Accounts Payable) package.
    
    Orchestrates the full lifecycle of an AP package:
    1. Persist package with STARTED status
    2. Split PDF into statement and invoice pages
    3. Extract statement document
    4. Extract each invoice sequentially
    5. Persist invoice records
    6. Update status to EXTRACTED
    """
    
    @workflow.run
    async def run(self, input: APPackageInput) -> dict:
        """Execute AP package workflow.
        
        Args:
            input: APPackageInput with package details
            
        Returns:
            dict with workflow result including ap_package_id, status, and extraction results
        """
        workflow.logger.info(f"Starting AP Package Workflow for {input.ap_package_id}")
        workflow.logger.info(f"Feedlot type: {input.feedlot_type}")
        workflow.logger.info(f"PDF path: {input.pdf_path}")
        
        # Step 1: Persist package with STARTED status
        persist_input = PersistPackageInput(
            ap_package_id=input.ap_package_id,
            feedlot_type=input.feedlot_type,
            document_refs=input.document_refs or []
        )
        
        await workflow.execute_activity(
            persist_package_started,
            persist_input,
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        workflow.logger.info(f"Package {input.ap_package_id} persisted with status: STARTED")
        
        # Step 2: Split PDF into statement and invoice pages
        split_input = SplitPdfInput(
            feedlot_type=input.feedlot_type,
            pdf_path=input.pdf_path,
            ap_package_id=input.ap_package_id,
        )
        
        split_result = await workflow.execute_activity(
            split_pdf,
            split_input,
            start_to_close_timeout=timedelta(seconds=60),
        )
        
        workflow.logger.info(f"PDF split: {len(split_result.statement_pages)} statement pages, {len(split_result.invoice_pages)} invoice pages")
        
        # Step 3: Extract statement
        statement_ref = None
        if split_result.statement_pages:
            workflow.logger.info("Extracting statement...")
            
            statement_input = ExtractStatementInput(
                feedlot_type=input.feedlot_type,
                pdf_path=input.pdf_path,
                page_indices=split_result.statement_pages,
                ap_package_id=input.ap_package_id,
            )
            
            statement_result = await workflow.execute_activity(
                extract_statement,
                statement_input,
                start_to_close_timeout=timedelta(minutes=5),  # LLM calls can be slow
            )
            
            statement_ref = statement_result.statement_ref
            workflow.logger.info(f"Statement extracted: {statement_result.feedlot_name} / {statement_result.owner_name}")
        
        # Step 4: Extract each invoice sequentially
        invoice_results = []
        validation_results = []
        total_invoices = len(split_result.invoice_pages)
        for i, page_idx in enumerate(split_result.invoice_pages):
            workflow.logger.info(f"Extracting invoice {i + 1}/{total_invoices} from page {page_idx}...")
            
            invoice_input = ExtractInvoiceInput(
                feedlot_type=input.feedlot_type,
                pdf_path=input.pdf_path,
                page_index=page_idx,
                ap_package_id=input.ap_package_id,
                invoice_index=i + 1,
                total_invoices=total_invoices,
            )
            
            invoice_result = await workflow.execute_activity(
                extract_invoice,
                invoice_input,
                start_to_close_timeout=timedelta(minutes=5),  # LLM calls can be slow
            )
            
            invoice_results.append(invoice_result)
            workflow.logger.info(f"Invoice {invoice_result.invoice_number} extracted (lot: {invoice_result.lot_number})")
            
            # Step 5: Persist invoice record
            persist_invoice_input = PersistInvoiceInput(
                ap_package_id=input.ap_package_id,
                invoice_number=invoice_result.invoice_number or f"page_{page_idx + 1}",
                lot_number=invoice_result.lot_number,
                invoice_date=invoice_result.invoice_date,
                total_amount=invoice_result.total_amount,
                invoice_ref=invoice_result.invoice_ref,
            )
            
            await workflow.execute_activity(
                persist_invoice,
                persist_invoice_input,
                start_to_close_timeout=timedelta(seconds=30),
            )
            
            # Step 5b: Validate invoice (B1/B2 checks)
            validate_input = ValidateInvoiceInput(
                invoice_ref=invoice_result.invoice_ref,
                ap_package_id=input.ap_package_id,
                invoice_number=invoice_result.invoice_number or f"page_{page_idx + 1}",
            )
            
            validation_result = await workflow.execute_activity(
                validate_invoice,
                validate_input,
                start_to_close_timeout=timedelta(seconds=30),
            )
            
            validation_results.append(validation_result)
            
            # Step 5c: Update invoice status based on validation
            update_status_input = UpdateInvoiceStatusInput(
                ap_package_id=input.ap_package_id,
                invoice_number=invoice_result.invoice_number or f"page_{page_idx + 1}",
                status=validation_result.status,
                validation_ref=validation_result.validation_ref,
            )
            
            await workflow.execute_activity(
                update_invoice_status,
                update_status_input,
                start_to_close_timeout=timedelta(seconds=30),
            )
            
            workflow.logger.info(f"Invoice {invoice_result.invoice_number} validation: {validation_result.status}")
        
        # Step 6: Reconcile statement with invoices
        reconciliation_result = None
        if statement_ref and invoice_results:
            workflow.logger.info(f"Running reconciliation for package {input.ap_package_id}...")
            
            # Collect all invoice refs
            invoice_refs = [r.invoice_ref for r in invoice_results]
            
            reconcile_input = ReconcilePackageInput(
                statement_ref=statement_ref,
                invoice_refs=invoice_refs,
                feedlot_type=input.feedlot_type,
                ap_package_id=input.ap_package_id,
            )
            
            reconciliation_result = await workflow.execute_activity(
                reconcile_package,
                reconcile_input,
                start_to_close_timeout=timedelta(minutes=2),
            )
            
            workflow.logger.info(f"Reconciliation complete: {reconciliation_result.status}")
        
        # Step 7: Update package status based on reconciliation
        # Count validation results
        passed_count = sum(1 for v in validation_results if v.passed)
        failed_count = len(validation_results) - passed_count
        
        # Determine final status
        if reconciliation_result:
            final_status = reconciliation_result.status  # RECONCILED_PASS/WARN/FAIL
        else:
            final_status = "EXTRACTED"
        
        update_input = UpdatePackageStatusInput(
            ap_package_id=input.ap_package_id,
            status=final_status,
            statement_ref=statement_ref,
        )
        
        await workflow.execute_activity(
            update_package_status,
            update_input,
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        workflow.logger.info(f"Package {input.ap_package_id} complete with status: {final_status}")
        workflow.logger.info(f"Validation summary: {passed_count} passed, {failed_count} failed")
        
        result = {
            "ap_package_id": input.ap_package_id,
            "feedlot_type": input.feedlot_type,
            "status": final_status,
            "statement_extracted": statement_ref is not None,
            "invoices_extracted": len(invoice_results),
            "invoices_validated_pass": passed_count,
            "invoices_validated_fail": failed_count,
            "invoice_numbers": [r.invoice_number for r in invoice_results],
        }
        
        # Add reconciliation info if available
        if reconciliation_result:
            result["reconciliation"] = {
                "status": reconciliation_result.status,
                "passed_checks": reconciliation_result.passed_checks,
                "total_checks": reconciliation_result.total_checks,
                "blocking_issues": reconciliation_result.blocking_issues,
                "warnings": reconciliation_result.warnings,
            }
        
        return result
