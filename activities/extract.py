"""Extraction activities for AP automation pipeline.

Temporal activities that wrap the extraction pipeline for document processing.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from temporalio import activity

# Import extraction utilities - these run in activity context (not workflow)
import fitz

from extraction.runner import (
    extract_statement as _extract_statement,
    extract_invoice as _extract_invoice,
    categorize_pages,
    load_env_var,
    ARTIFACTS_DIR,
)
from models.refs import DataReference
from models.canonical import StatementDocument, InvoiceDocument
from storage.artifacts import put_json, get_json
from activities.persist import log_progress, update_extraction_counts


@dataclass
class ExtractStatementInput:
    """Input for extract_statement activity.
    
    Attributes:
        feedlot_type: BOVINA or MESQUITE
        pdf_path: Absolute path to source PDF
        page_indices: List of page indices to extract (0-based)
        ap_package_id: Package ID for progress tracking
        use_cache: If True, skip extraction if artifact exists (default: True)
    """
    feedlot_type: str
    pdf_path: str
    page_indices: List[int]
    ap_package_id: str = ""
    use_cache: bool = True


@dataclass
class ExtractStatementOutput:
    """Output from extract_statement activity.
    
    Attributes:
        statement_ref: DataReference to saved statement JSON
        feedlot_name: Extracted feedlot name
        owner_name: Extracted owner name
        period_start: Statement period start date
        period_end: Statement period end date
    """
    statement_ref: dict  # Serialized DataReference
    feedlot_name: Optional[str]
    owner_name: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]


@dataclass
class ExtractInvoiceInput:
    """Input for extract_invoice activity.
    
    Attributes:
        feedlot_type: BOVINA or MESQUITE
        pdf_path: Absolute path to source PDF
        page_index: Page index to extract (0-based)
        ap_package_id: Parent package ID for reference
        invoice_index: Current invoice index (1-based) for progress tracking
        total_invoices: Total number of invoices for progress tracking
        use_cache: If True, skip extraction if artifact exists (default: True)
    """
    feedlot_type: str
    pdf_path: str
    page_index: int
    ap_package_id: str
    invoice_index: int = 0
    total_invoices: int = 0
    use_cache: bool = True


@dataclass
class ExtractInvoiceOutput:
    """Output from extract_invoice activity.
    
    Attributes:
        invoice_ref: DataReference to saved invoice JSON
        invoice_number: Extracted invoice number
        lot_number: Extracted lot number
        invoice_date: Invoice date
        total_amount: Invoice total amount
    """
    invoice_ref: dict  # Serialized DataReference
    invoice_number: Optional[str]
    lot_number: Optional[str]
    invoice_date: Optional[str]
    total_amount: Optional[str]


@dataclass
class SplitPdfInput:
    """Input for split_pdf activity.
    
    Attributes:
        feedlot_type: BOVINA or MESQUITE
        pdf_path: Absolute path to source PDF
        ap_package_id: Package ID for progress tracking
    """
    feedlot_type: str
    pdf_path: str
    ap_package_id: str = ""


@dataclass
class SplitPdfOutput:
    """Output from split_pdf activity.
    
    Attributes:
        statement_pages: List of page indices for statement
        invoice_pages: List of page indices for invoices
        total_pages: Total pages in PDF
    """
    statement_pages: List[int]
    invoice_pages: List[int]
    total_pages: int


def _get_prompt_name(feedlot_type: str, doc_type: str) -> str:
    """Get prompt template name for feedlot and document type."""
    feedlot = feedlot_type.lower()
    return f"{feedlot}_{doc_type}_prompt.txt"


def _get_keywords(feedlot_type: str) -> Tuple[str, str]:
    """Get statement and invoice keywords for feedlot type."""
    if feedlot_type.upper() == "BOVINA":
        return "statement of notes", "feed invoice"
    elif feedlot_type.upper() == "MESQUITE":
        return "statement of account", "invoice"
    else:
        raise ValueError(f"Unknown feedlot type: {feedlot_type}")


def _get_api_key() -> str:
    """Get OpenAI API key from environment."""
    api_key = load_env_var("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return api_key


@activity.defn
async def split_pdf(input: SplitPdfInput) -> SplitPdfOutput:
    """Split PDF into statement and invoice pages.
    
    Analyzes PDF to identify which pages contain statements vs invoices
    based on keyword matching.
    
    Args:
        input: SplitPdfInput with feedlot_type and pdf_path
        
    Returns:
        SplitPdfOutput with page indices for statement and invoices
    """
    activity.logger.info(f"Splitting PDF for {input.feedlot_type}: {input.pdf_path}")
    
    pdf_path = Path(input.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    statement_kw, invoice_kw = _get_keywords(input.feedlot_type)
    
    with fitz.open(pdf_path) as doc:
        statement_pages, invoice_pages = categorize_pages(
            doc,
            statement_keyword=statement_kw,
            invoice_keyword=invoice_kw,
        )
        total_pages = doc.page_count
    
    msg = f"PDF split: {len(statement_pages)} statement pages, {len(invoice_pages)} invoices to extract"
    activity.logger.info(msg)
    
    # Log progress
    if input.ap_package_id:
        log_progress(input.ap_package_id, "split_pdf", msg)
        update_extraction_counts(input.ap_package_id, total=len(invoice_pages))
    
    return SplitPdfOutput(
        statement_pages=statement_pages,
        invoice_pages=invoice_pages,
        total_pages=total_pages,
    )


@activity.defn
async def extract_statement(input: ExtractStatementInput) -> ExtractStatementOutput:
    """Extract statement document from PDF pages.
    
    Uses GPT-4o vision to extract structured data from statement pages.
    Supports caching to skip extraction if artifact already exists.
    
    Args:
        input: ExtractStatementInput with feedlot_type, pdf_path, and page_indices
        
    Returns:
        ExtractStatementOutput with DataReference and extracted metadata
    """
    feedlot_key = input.feedlot_type.lower()
    output_dir = ARTIFACTS_DIR / feedlot_key
    statement_path = output_dir / "statement.json"
    
    # Check cache first
    if input.use_cache and statement_path.exists():
        activity.logger.info(f"Using cached statement from {statement_path}")
        try:
            with open(statement_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            statement = StatementDocument.model_validate(data)
            
            # Build DataReference for existing file
            import hashlib
            content = statement_path.read_bytes()
            statement_ref = DataReference(
                storage_uri=str(statement_path),
                content_hash=hashlib.sha256(content).hexdigest(),
                content_type="application/json",
                size_bytes=len(content),
            )
            
            # Extract metadata
            period_start = None
            period_end = None
            if statement.period_start:
                period_start = str(statement.period_start)
            if statement.period_end:
                period_end = str(statement.period_end)
            
            feedlot_name = statement.feedlot.name if statement.feedlot else None
            owner_name = statement.owner.name if statement.owner else None
            
            activity.logger.info(f"✓ Loaded statement from cache (feedlot: {feedlot_name})")
            
            # Log progress
            if input.ap_package_id:
                log_progress(input.ap_package_id, "extract_statement", f"Statement loaded from cache (feedlot: {feedlot_name})")
            
            return ExtractStatementOutput(
                statement_ref=statement_ref.model_dump(),
                feedlot_name=feedlot_name,
                owner_name=owner_name,
                period_start=period_start,
                period_end=period_end,
            )
        except Exception as e:
            activity.logger.warning(f"Cache load failed, extracting fresh: {e}")
    
    activity.logger.info(f"Extracting statement for {input.feedlot_type} from pages {input.page_indices}")
    
    pdf_path = Path(input.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    api_key = _get_api_key()
    prompt_name = _get_prompt_name(input.feedlot_type, "statement")
    
    activity.logger.info(f"Calling GPT-4o for statement extraction ({len(input.page_indices)} pages)...")
    
    # Heartbeat before LLM call to signal we're still alive
    activity.heartbeat("Starting GPT-4o extraction...")
    
    # Extract statement using existing function
    statement = _extract_statement(
        pdf_path=pdf_path,
        prompt_name=prompt_name,
        statement_pages=input.page_indices,
        api_key=api_key,
    )
    
    # Heartbeat after LLM call
    activity.heartbeat("GPT-4o extraction complete, saving...")
    
    # Save to artifacts
    output_dir.mkdir(parents=True, exist_ok=True)
    statement_ref = put_json(statement, statement_path)
    
    activity.logger.info(f"✓ Statement saved to {statement_path}")
    
    # Extract metadata for return
    period_start = None
    period_end = None
    if statement.period_start:
        period_start = str(statement.period_start)
    if statement.period_end:
        period_end = str(statement.period_end)
    
    feedlot_name = None
    if statement.feedlot:
        feedlot_name = statement.feedlot.name
    
    owner_name = None
    if statement.owner:
        owner_name = statement.owner.name
    
    # Log progress
    if input.ap_package_id:
        log_progress(input.ap_package_id, "extract_statement", f"Statement extracted successfully (feedlot: {feedlot_name})")
    
    return ExtractStatementOutput(
        statement_ref=statement_ref.model_dump(),
        feedlot_name=feedlot_name,
        owner_name=owner_name,
        period_start=period_start,
        period_end=period_end,
    )


@activity.defn
async def extract_invoice(input: ExtractInvoiceInput) -> ExtractInvoiceOutput:
    """Extract single invoice from PDF page.
    
    Uses GPT-4o vision to extract structured data from an invoice page.
    Supports caching to skip extraction if artifact already exists.
    
    Args:
        input: ExtractInvoiceInput with feedlot_type, pdf_path, page_index, ap_package_id
        
    Returns:
        ExtractInvoiceOutput with DataReference and extracted metadata
    """
    feedlot_key = input.feedlot_type.lower()
    output_dir = ARTIFACTS_DIR / feedlot_key / "invoices"
    
    # Check cache - look for any invoice file that matches this page
    # For existing caches without page_index, we try to find by invoice_index order
    if input.use_cache and output_dir.exists():
        # Try to find existing invoice files
        existing_files = sorted(output_dir.glob("*.json"))
        
        # First try: match by page_index in metadata
        for invoice_path in existing_files:
            try:
                with open(invoice_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Check if this invoice matches our page
                doc_meta = data.get("document_metadata", {})
                if doc_meta.get("page_index") == input.page_index:
                    invoice = InvoiceDocument.model_validate(data)
                    
                    # Build DataReference
                    import hashlib
                    content = invoice_path.read_bytes()
                    invoice_ref = DataReference(
                        storage_uri=str(invoice_path),
                        content_hash=hashlib.sha256(content).hexdigest(),
                        content_type="application/json",
                        size_bytes=len(content),
                    )
                    
                    invoice_date = str(invoice.invoice_date) if invoice.invoice_date else None
                    total_amount = str(invoice.totals.total_amount_due) if invoice.totals and invoice.totals.total_amount_due is not None else None
                    lot_number = invoice.lot.lot_number if invoice.lot else None
                    
                    activity.logger.info(f"✓ Loaded invoice {invoice.invoice_number} from cache (page {input.page_index})")
                    
                    # Log progress
                    if input.ap_package_id:
                        progress_msg = f"Invoice {invoice.invoice_number} loaded from cache ({input.invoice_index}/{input.total_invoices})"
                        log_progress(input.ap_package_id, "extract_invoice", progress_msg)
                        update_extraction_counts(input.ap_package_id, extracted_increment=1)
                    
                    return ExtractInvoiceOutput(
                        invoice_ref=invoice_ref.model_dump(),
                        invoice_number=invoice.invoice_number,
                        lot_number=lot_number,
                        invoice_date=invoice_date,
                        total_amount=total_amount,
                    )
            except Exception:
                continue  # Try next file
        
        # Second try: if we have the same number of invoices as expected, use index order
        if input.invoice_index > 0 and len(existing_files) >= input.total_invoices:
            try:
                # Use the invoice at the matching index (1-based to 0-based)
                invoice_path = existing_files[input.invoice_index - 1]
                with open(invoice_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                invoice = InvoiceDocument.model_validate(data)
                
                # Build DataReference
                import hashlib
                content = invoice_path.read_bytes()
                invoice_ref = DataReference(
                    storage_uri=str(invoice_path),
                    content_hash=hashlib.sha256(content).hexdigest(),
                    content_type="application/json",
                    size_bytes=len(content),
                )
                
                invoice_date = str(invoice.invoice_date) if invoice.invoice_date else None
                total_amount = str(invoice.totals.total_amount_due) if invoice.totals and invoice.totals.total_amount_due is not None else None
                lot_number = invoice.lot.lot_number if invoice.lot else None
                
                activity.logger.info(f"✓ Loaded invoice {invoice.invoice_number} from cache by index ({input.invoice_index}/{input.total_invoices})")
                
                # Log progress
                if input.ap_package_id:
                    progress_msg = f"Invoice {invoice.invoice_number} loaded from cache ({input.invoice_index}/{input.total_invoices})"
                    log_progress(input.ap_package_id, "extract_invoice", progress_msg)
                    update_extraction_counts(input.ap_package_id, extracted_increment=1)
                
                return ExtractInvoiceOutput(
                    invoice_ref=invoice_ref.model_dump(),
                    invoice_number=invoice.invoice_number,
                    lot_number=lot_number,
                    invoice_date=invoice_date,
                    total_amount=total_amount,
                )
            except Exception as e:
                activity.logger.warning(f"Cache lookup by index failed: {e}")
    
    activity.logger.info(f"Extracting invoice for {input.feedlot_type} from page {input.page_index}")
    
    pdf_path = Path(input.pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    api_key = _get_api_key()
    prompt_name = _get_prompt_name(input.feedlot_type, "invoice")
    
    activity.logger.info(f"Calling GPT-4o for invoice extraction (page {input.page_index})...")
    
    # Heartbeat before LLM call to signal we're still alive
    activity.heartbeat(f"Starting GPT-4o extraction for page {input.page_index}...")
    
    # Extract invoice using existing function
    invoice = _extract_invoice(
        pdf_path=pdf_path,
        prompt_name=prompt_name,
        page_index=input.page_index,
        api_key=api_key,
    )
    
    # Heartbeat after LLM call
    activity.heartbeat(f"GPT-4o extraction complete for invoice {invoice.invoice_number or 'unknown'}...")
    
    # Save to artifacts
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Use invoice number as filename
    invoice_num = invoice.invoice_number or f"page_{input.page_index + 1}"
    safe_name = "".join(ch for ch in str(invoice_num) if ch.isalnum() or ch in ("-", "_"))
    invoice_path = output_dir / f"{safe_name}.json"
    invoice_ref = put_json(invoice, invoice_path)
    
    activity.logger.info(f"✓ Invoice {invoice_num} saved to {invoice_path}")
    
    # Extract metadata for return
    invoice_date = None
    if invoice.invoice_date:
        invoice_date = str(invoice.invoice_date)
    
    total_amount = None
    if invoice.totals and invoice.totals.total_amount_due is not None:
        total_amount = str(invoice.totals.total_amount_due)
    
    lot_number = None
    if invoice.lot:
        lot_number = invoice.lot.lot_number
    
    # Log progress
    if input.ap_package_id:
        progress_msg = f"Invoice {invoice.invoice_number} extracted ({input.invoice_index}/{input.total_invoices})"
        log_progress(input.ap_package_id, "extract_invoice", progress_msg)
        update_extraction_counts(input.ap_package_id, extracted_increment=1)
    
    return ExtractInvoiceOutput(
        invoice_ref=invoice_ref.model_dump(),
        invoice_number=invoice.invoice_number,
        lot_number=lot_number,
        invoice_date=invoice_date,
        total_amount=total_amount,
    )
