"""Extraction pipeline for AP invoices and statements.

Exposes high-level functions for extracting documents from PDFs:
- extract_package(manifest) -> ExtractedPackageRefs
- extract_statement(doc_ref) -> StatementDocument
- extract_invoice(doc_ref) -> InvoiceDocument
"""

import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import fitz
import openai

from models.canonical import StatementDocument, InvoiceDocument
from models.refs import DataReference, ExtractedPackageRefs
from storage.artifacts import put_json


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = REPO_ROOT / "prompts"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


# =============================================================================
# Configuration & Utilities
# =============================================================================

def load_env_var(name: str) -> Optional[str]:
    """Load environment variable from env file or system."""
    value = os.getenv(name)
    if value:
        return value
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        key, _, val = line.partition("=")
        if key.strip() == name:
            return val.strip()
    return None


def read_prompt(name: str) -> str:
    """Read a prompt template from the prompts directory."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def page_to_png_b64(page: fitz.Page, zoom: float = 2.0) -> str:
    """Convert a PDF page to base64-encoded PNG for vision API."""
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    return base64.b64encode(png_bytes).decode("ascii")


def call_openai_vision(prompt: str, images_b64: List[str], api_key: str) -> str:
    """Call GPT-4o vision API with images and return response text."""
    client = openai.OpenAI(api_key=api_key, timeout=600.0)
    
    content = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img}", "detail": "high"},
        })

    print(f"  Sending {len(images_b64)} image(s) to GPT-4o...")
    
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                temperature=0,
                max_tokens=16000,
            )
            return response.choices[0].message.content
        except openai.RateLimitError as e:
            retry_after = 60
            print(f"  Rate limited, waiting {retry_after}s (attempt {attempt + 1}/5)...")
            time.sleep(retry_after)
        except openai.APITimeoutError:
            print(f"  Timeout, retrying (attempt {attempt + 1}/5)...")
            time.sleep(10)
    
    raise RuntimeError("Failed to extract document after 5 attempts")


def parse_json_str(raw_text: str) -> dict:
    """Parse JSON from LLM response, extracting JSON block if needed."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw_text[start:end + 1])
        raise


def categorize_pages(
    doc: fitz.Document,
    statement_keyword: str,
    invoice_keyword: str,
) -> Tuple[List[int], List[int]]:
    """Categorize PDF pages as statement or invoice based on keywords."""
    statement_pages = []
    invoice_pages = []
    for i in range(doc.page_count):
        text = doc.load_page(i).get_text("text").lower()
        if statement_keyword in text:
            statement_pages.append(i)
        elif invoice_keyword in text:
            invoice_pages.append(i)
    return statement_pages, invoice_pages


# =============================================================================
# Document Extraction Functions
# =============================================================================

def extract_statement(
    pdf_path: Path,
    prompt_name: str,
    statement_pages: List[int],
    api_key: str,
) -> StatementDocument:
    """Extract a statement document from PDF pages.
    
    Args:
        pdf_path: Path to PDF file
        prompt_name: Name of prompt template file
        statement_pages: List of page indices to extract
        api_key: OpenAI API key
        
    Returns:
        Validated StatementDocument
        
    Raises:
        ValueError: If extraction or validation fails
    """
    prompt = read_prompt("system.txt") + "\n" + read_prompt(prompt_name)

    with fitz.open(pdf_path) as doc:
        images = [page_to_png_b64(doc.load_page(i)) for i in statement_pages]

    raw = call_openai_vision(prompt, images, api_key)
    parsed = parse_json_str(raw)

    parsed.setdefault("document_metadata", {})
    parsed["document_metadata"].update({
        "source_file": str(pdf_path),
        "page_count": len(statement_pages),
        "extracted_at": datetime.utcnow().isoformat(),
    })

    # Validate against schema
    statement = StatementDocument.model_validate(parsed)
    return statement


def extract_invoice(
    pdf_path: Path,
    prompt_name: str,
    page_index: int,
    api_key: str,
) -> InvoiceDocument:
    """Extract a single invoice from a PDF page.
    
    Args:
        pdf_path: Path to PDF file
        prompt_name: Name of prompt template file
        page_index: Page index to extract
        api_key: OpenAI API key
        
    Returns:
        Validated InvoiceDocument
        
    Raises:
        ValueError: If extraction or validation fails
    """
    prompt = read_prompt("system.txt") + "\n" + read_prompt(prompt_name)

    with fitz.open(pdf_path) as doc:
        images = [page_to_png_b64(doc.load_page(page_index))]

    raw = call_openai_vision(prompt, images, api_key)
    parsed = parse_json_str(raw)

    parsed.setdefault("document_metadata", {})
    parsed["document_metadata"].update({
        "source_file": str(pdf_path),
        "page_index": page_index,
        "page_count": 1,
        "extracted_at": datetime.utcnow().isoformat(),
    })

    # Validate against schema
    invoice = InvoiceDocument.model_validate(parsed)
    return invoice


# =============================================================================
# Package Extraction
# =============================================================================

def extract_package(
    feedlot_key: str,
    pdf_path: Path,
    statement_keyword: str,
    statement_prompt: str,
    invoice_keyword: str,
    invoice_prompt: str,
    api_key: str,
    output_dir: Optional[Path] = None,
) -> ExtractedPackageRefs:
    """Extract all documents from a feedlot PDF and store artifacts.
    
    Args:
        feedlot_key: Identifier for feedlot (e.g., "bovina", "mesquite")
        pdf_path: Path to PDF file
        statement_keyword: Keyword to identify statement pages
        statement_prompt: Prompt template name for statement extraction
        invoice_keyword: Keyword to identify invoice pages
        invoice_prompt: Prompt template name for invoice extraction
        api_key: OpenAI API key
        output_dir: Directory to store artifacts (default: artifacts/{feedlot_key})
        
    Returns:
        ExtractedPackageRefs with references to all stored artifacts
    """
    if output_dir is None:
        output_dir = ARTIFACTS_DIR / feedlot_key
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"Extracting {feedlot_key.upper()} package from {pdf_path.name}")
    print(f"{'='*70}")
    
    # Categorize pages
    print(f"\nCategorizing PDF pages...")
    with fitz.open(pdf_path) as doc:
        statement_pages, invoice_pages = categorize_pages(
            doc,
            statement_keyword=statement_keyword,
            invoice_keyword=invoice_keyword,
        )
    
    print(f"  Found {len(statement_pages)} statement page(s)")
    print(f"  Found {len(invoice_pages)} invoice page(s)")
    
    # Extract statement
    statement_ref = None
    if statement_pages:
        print(f"\nExtracting statement...")
        try:
            statement = extract_statement(
                pdf_path,
                statement_prompt,
                statement_pages,
                api_key,
            )
            statement_path = output_dir / "statement.json"
            statement_ref = put_json(statement, statement_path)
            print(f"  ✓ Statement saved to {statement_path.name}")
        except Exception as e:
            print(f"  ✗ Statement extraction failed: {e}")
    
    # Extract invoices
    invoice_refs = []
    if invoice_pages:
        print(f"\nExtracting invoices...")
        for i, page_idx in enumerate(invoice_pages, 1):
            try:
                invoice = extract_invoice(
                    pdf_path,
                    invoice_prompt,
                    page_idx,
                    api_key,
                )
                invoice_num = invoice.invoice_number or f"page_{page_idx + 1}"
                safe_name = "".join(ch for ch in invoice_num if ch.isalnum() or ch in ("-", "_"))
                invoice_path = output_dir / f"{safe_name}.json"
                invoice_ref = put_json(invoice, invoice_path)
                invoice_refs.append(invoice_ref)
                print(f"  ✓ [{i}/{len(invoice_pages)}] Invoice {invoice_num} saved")
            except Exception as e:
                print(f"  ✗ [{i}/{len(invoice_pages)}] Invoice extraction failed: {e}")
    
    # Create package reference
    package_refs = ExtractedPackageRefs(
        feedlot_key=feedlot_key,
        statement_ref=statement_ref,
        invoice_refs=invoice_refs,
        extraction_metadata={
            "pdf_path": str(pdf_path),
            "statement_pages": statement_pages,
            "invoice_pages": invoice_pages,
            "extracted_at": datetime.utcnow().isoformat(),
            "api_model": "gpt-4o",
        },
    )
    
    # Save package manifest
    manifest_path = output_dir / "_manifest.json"
    put_json(package_refs, manifest_path)
    print(f"\nPackage manifest saved to {manifest_path.name}")
    
    return package_refs
