"""Module Interface Documentation

This document describes the stable function boundaries and interfaces for the
AP automation extraction and reconciliation pipeline.

## Overview

The codebase is organized into four main modules:

1. **models/** - Data structures and schemas
2. **storage/** - Artifact persistence layer
3. **extraction/** - PDF document extraction
4. **reconciliation/** - Validation and reconciliation logic

## Module Interfaces

### models.canonical

Pydantic models for extracted documents.

```python
from models.canonical import StatementDocument, InvoiceDocument

# Validate extracted data
statement: StatementDocument = StatementDocument.model_validate(data_dict)
invoice: InvoiceDocument = InvoiceDocument.model_validate(data_dict)

# Serialize to JSON
json_dict = statement.model_dump(mode="json", by_alias=True)
```

### models.refs

Reference and metadata models for artifacts and reports.

```python
from models.refs import (
    DataReference,           # Reference to a stored artifact
    ExtractedPackageRefs,   # References to all extraction results
    ReconciliationReport,   # Reconciliation results
)

# Create a reference
ref = DataReference(
    storage_uri="/path/to/file.json",
    content_hash="abc123...",
    content_type="application/json",
    size_bytes=1024,
    stored_at="2026-01-07T12:00:00"
)

# Serialize for storage
ref_dict = ref.model_dump()

# Package references
package_refs = ExtractedPackageRefs(
    feedlot_key="bovina",
    statement_ref=statement_ref,
    invoice_refs=[inv_ref1, inv_ref2],
    extraction_metadata={...}
)

# Reconciliation report
report = ReconciliationReport(
    feedlot_key="bovina",
    status="PASS",
    checks=[...],
    summary={...},
    metrics={...}
)
```

### storage.artifacts

Artifact persistence with integrity verification.

```python
from storage.artifacts import put_json, get_json, list_artifacts

# Store artifact with automatic hashing and metadata
ref = put_json(obj, Path("artifacts/my_artifact.json"))
# Returns: DataReference with SHA256 hash, size, timestamp

# Retrieve with optional hash verification
data = get_json(ref, validate_hash=True)
# Raises ValueError if hash doesn't match

# List all artifacts in directory
refs = list_artifacts(Path("artifacts/bovina"))
# Returns: List[DataReference] sorted by most recent first

# Check existence
exists = artifact_exists(ref)

# Delete artifact
deleted = delete_artifact(ref)
```

### extraction.runner

PDF document extraction with vision API.

#### Function 1: extract_package()

High-level function to extract all documents from a feedlot PDF.

```python
from extraction.runner import extract_package

package_refs = extract_package(
    feedlot_key="bovina",
    pdf_path=Path("Bovina.pdf"),
    statement_keyword="statement of notes",
    statement_prompt="bovina_statement_prompt.txt",
    invoice_keyword="feed invoice",
    invoice_prompt="bovina_invoice_prompt.txt",
    api_key="sk-...",
    output_dir=Path("artifacts/bovina"),  # optional
)

# Returns: ExtractedPackageRefs
#   - feedlot_key: str
#   - statement_ref: Optional[DataReference]
#   - invoice_refs: List[DataReference]
#   - extraction_metadata: dict with extraction details
```

#### Function 2: extract_statement()

Extract a statement document from PDF pages.

```python
from extraction.runner import extract_statement
from models.canonical import StatementDocument

statement: StatementDocument = extract_statement(
    pdf_path=Path("Bovina.pdf"),
    prompt_name="bovina_statement_prompt.txt",
    statement_pages=[0, 1, 2],
    api_key="sk-...",
)

# Returns: Validated StatementDocument
# Raises: ValueError if extraction or validation fails
```

#### Function 3: extract_invoice()

Extract a single invoice from a PDF page.

```python
from extraction.runner import extract_invoice
from models.canonical import InvoiceDocument

invoice: InvoiceDocument = extract_invoice(
    pdf_path=Path("Bovina.pdf"),
    prompt_name="bovina_invoice_prompt.txt",
    page_index=3,
    api_key="sk-...",
)

# Returns: Validated InvoiceDocument
# Raises: ValueError if extraction or validation fails
```

### reconciliation.engine

Finance-grade reconciliation and validation.

#### Main Function: reconcile()

Run all reconciliation checks on a package.

```python
from reconciliation.engine import reconcile
from models.refs import ReconciliationReport

report: ReconciliationReport = reconcile(
    statement=statement_doc,
    invoices=[invoice1, invoice2, ...],
    feedlot_key="bovina",
)

# Returns: ReconciliationReport
#   - feedlot_key: str
#   - status: str ("PASS", "WARN", "FAIL")
#   - checks: list[dict] - detailed check results
#   - summary: dict - human-readable summary
#   - metrics: dict - key metrics
```

#### Check Types

The reconciliation engine implements 10 check types:

| Check ID | Type | Severity | Description |
|----------|------|----------|-------------|
| A1 | Package | BLOCK/WARN | All referenced invoices exist |
| A2 | Package | WARN | No extra invoices beyond statement |
| A3 | Package | WARN | Invoice dates within period |
| A4 | Package | BLOCK | Feedlot/owner consistency |
| A5 | Package | WARN | Invoice totals match statement (trust invoice) |
| A6 | Package | WARN | Package totals align (trust invoice) |
| A7 | Package | WARN/BLOCK | All lots have invoices |
| B1 | Invoice | BLOCK | Required fields present |
| B2 | Invoice | BLOCK | Line item sum matches total |
| D1 | Package | BLOCK | No duplicate invoices |

#### Check Result Structure

```python
{
    "check_id": "A1_PACKAGE_COMPLETENESS",
    "severity": "WARN",
    "passed": true,
    "message": "1 invoices missing from source PDF (not extraction failure)",
    "evidence": {
        "source_pdf_missing": ["13304"],
        "source_pdf_missing_reasons": {
            "13304": "Invoice for lot 20-3927 - ..."
        },
        "expected_count": 24,
        "extracted_count": 23
    }
}
```

## Usage Examples

### Basic Extraction and Reconciliation

```python
from pathlib import Path
from extraction.runner import extract_package
from reconciliation.engine import reconcile
from storage.artifacts import put_json, get_json

# Extract documents
package_refs = extract_package(
    feedlot_key="bovina",
    pdf_path=Path("Bovina.pdf"),
    statement_keyword="statement of notes",
    statement_prompt="bovina_statement_prompt.txt",
    invoice_keyword="feed invoice",
    invoice_prompt="bovina_invoice_prompt.txt",
    api_key="sk-...",
)

# Retrieve extracted data
statement_data = get_json(package_refs.statement_ref)
statement = StatementDocument.model_validate(statement_data)

invoices = []
for inv_ref in package_refs.invoice_refs:
    inv_data = get_json(inv_ref)
    invoices.append(InvoiceDocument.model_validate(inv_data))

# Reconcile
report = reconcile(statement, invoices, feedlot_key="bovina")

# Save report
report_ref = put_json(report, Path("artifacts/bovina/reconciliation_report.json"))
```

### Loading Existing Artifacts

```python
from storage.artifacts import list_artifacts, get_json
from models.canonical import InvoiceDocument

# List all invoices
invoice_refs = list_artifacts(Path("artifacts/bovina/invoices"))

# Load each invoice
for ref in invoice_refs:
    data = get_json(ref)
    invoice = InvoiceDocument.model_validate(data)
    print(f"Invoice {invoice.invoice_number}: {data}")
```

### Error Handling

```python
from storage.artifacts import get_json

try:
    data = get_json(ref, validate_hash=True)
except FileNotFoundError:
    print(f"Artifact not found: {ref.storage_uri}")
except ValueError:
    print(f"Hash mismatch - artifact may be corrupted")
except json.JSONDecodeError:
    print(f"Invalid JSON in artifact")
```

## Configuration

### Known Missing Invoices

To register invoices that are on statements but missing from source PDFs:

```python
# In reconciliation/engine.py
KNOWN_MISSING_FROM_SOURCE_PDF = {
    "bovina": {
        "13304": "Invoice for lot 20-3927 - listed on statement but invoice page not in PDF",
    },
    "mesquite": {},
}
```

### API Configuration

```python
import os
from extraction.runner import load_env_var

api_key = load_env_var("OPENAI_API_KEY")
# Loads from:
# 1. OPENAI_API_KEY environment variable
# 2. .env file in repo root
```

## Architecture Notes

### Trust Model

The reconciliation engine trusts **invoice totals over statement amounts** because:
- Invoice line items sum correctly internally
- Statement amounts are susceptible to OCR errors
- Invoices have verifiable line-item details

### Severity Levels

- **BLOCK**: Critical issue - stops processing
- **WARN**: Issue detected but processing continues (e.g., OCR discrepancy)
- **INFO**: Informational - successful check

### Status Values

- **PASS**: All checks passed
- **WARN**: Some warnings but no blockers
- **FAIL**: One or more blocking issues

## File Structure

```
temporalinvoice/
├── models/
│   ├── canonical.py       # Pydantic schemas (documents)
│   └── refs.py           # Reference and metadata models
├── storage/
│   └── artifacts.py      # JSON storage abstraction
├── extraction/
│   └── runner.py         # PDF extraction pipeline
├── reconciliation/
│   └── engine.py         # Reconciliation checks
├── prompts/
│   ├── system.txt        # Shared system prompt
│   ├── bovina_*.txt      # Bovina prompts
│   └── mesquite_*.txt    # Mesquite prompts
├── artifacts/
│   ├── bovina/
│   │   ├── statement.json
│   │   ├── invoices/
│   │   │   ├── 13330.json
│   │   │   └── ...
│   │   └── _manifest.json
│   ├── mesquite/
│   │   └── ...
│   └── test_artifact.json
└── .env                  # API keys
```

## Dependencies

- pydantic>=2.0 - Data validation
- openai - GPT-4o API
- pymupdf (fitz) - PDF processing

## Version Information

- Created: 2026-01-07
- Status: Stable interface
- Last Updated: Step 0 (Module Refactoring)
"""
