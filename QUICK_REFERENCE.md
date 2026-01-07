# Quick Reference: Module API

## One-Liner Examples

### Extract All Documents
```python
from extraction.runner import extract_package
from pathlib import Path

refs = extract_package(
    feedlot_key="bovina",
    pdf_path=Path("Bovina.pdf"),
    statement_keyword="statement of notes",
    statement_prompt="bovina_statement_prompt.txt",
    invoice_keyword="feed invoice",
    invoice_prompt="bovina_invoice_prompt.txt",
    api_key="sk-...",
    output_dir=Path("artifacts/bovina")
)
```

### Extract Just a Statement
```python
from extraction.runner import extract_statement
from models.canonical import StatementDocument

stmt: StatementDocument = extract_statement(
    pdf_path=Path("Bovina.pdf"),
    prompt_name="bovina_statement_prompt.txt",
    statement_pages=[0, 1, 2],
    api_key="sk-...",
)
```

### Extract Single Invoice
```python
from extraction.runner import extract_invoice
from models.canonical import InvoiceDocument

inv: InvoiceDocument = extract_invoice(
    pdf_path=Path("Bovina.pdf"),
    prompt_name="bovina_invoice_prompt.txt",
    page_index=3,
    api_key="sk-...",
)
```

### Reconcile Documents
```python
from reconciliation.engine import reconcile
from models.canonical import StatementDocument, InvoiceDocument
from models.refs import ReconciliationReport

report: ReconciliationReport = reconcile(
    statement=statement_doc,
    invoices=[invoice1, invoice2, ...],
    feedlot_key="bovina",
)

print(f"Status: {report.status}")  # PASS, WARN, or FAIL
print(f"Checks: {len(report.checks)}")
```

### Store Artifact
```python
from storage.artifacts import put_json
from models.refs import DataReference
from pathlib import Path

ref: DataReference = put_json(
    obj=my_dict_or_pydantic_model,
    path=Path("artifacts/my_file.json")
)

print(f"Hash: {ref.content_hash}")
print(f"Size: {ref.size_bytes} bytes")
```

### Retrieve Artifact
```python
from storage.artifacts import get_json

data: dict = get_json(ref, validate_hash=True)
```

### List Artifacts
```python
from storage.artifacts import list_artifacts
from pathlib import Path

refs = list_artifacts(Path("artifacts/bovina"))

for ref in refs:
    print(f"{ref.storage_uri}: {ref.size_bytes} bytes")
```

---

## Import Patterns

### Get Everything
```python
from models.canonical import StatementDocument, InvoiceDocument
from models.refs import DataReference, ExtractedPackageRefs, ReconciliationReport
from storage.artifacts import put_json, get_json, list_artifacts
from extraction.runner import extract_package, extract_statement, extract_invoice
from reconciliation.engine import reconcile
```

### Just Extraction
```python
from extraction.runner import extract_package, extract_statement, extract_invoice
from models.canonical import StatementDocument, InvoiceDocument
from storage.artifacts import put_json, get_json
```

### Just Reconciliation
```python
from reconciliation.engine import reconcile
from models.canonical import StatementDocument, InvoiceDocument
from models.refs import ReconciliationReport
```

### Just Storage
```python
from storage.artifacts import put_json, get_json, list_artifacts
from models.refs import DataReference
```

---

## Common Tasks

### Load Existing Extracted Data
```python
import json
from pathlib import Path
from models.canonical import StatementDocument, InvoiceDocument

# Load statement
stmt_path = Path("artifacts/bovina/statement.json")
stmt_data = json.loads(stmt_path.read_text())
stmt = StatementDocument.model_validate(stmt_data)

# Load all invoices
invoices = []
inv_dir = Path("artifacts/bovina/invoices")
for inv_file in inv_dir.glob("*.json"):
    inv_data = json.loads(inv_file.read_text())
    invoices.append(InvoiceDocument.model_validate(inv_data))
```

### Check Reconciliation Status
```python
from reconciliation.engine import reconcile

report = reconcile(stmt, invoices, feedlot_key="bovina")

if report.status == "PASS":
    print("✓ All checks passed")
elif report.status == "WARN":
    print("⚠ Warnings but no critical issues")
else:
    print("✗ Critical issues found")

# Print blocking issues
for check in report.checks:
    if check["severity"] == "BLOCK" and not check["passed"]:
        print(f"  - {check['check_id']}: {check['message']}")
```

### Export Report to JSON
```python
import json
from pathlib import Path
from storage.artifacts import put_json

# Store using storage layer (recommended)
report_ref = put_json(report, Path("artifacts/bovina/report.json"))

# Or manually (if not using storage layer)
report_dict = report.model_dump()
Path("report.json").write_text(json.dumps(report_dict, indent=2))
```

### Verify Artifact Integrity
```python
from storage.artifacts import get_json

try:
    data = get_json(ref, validate_hash=True)
    print("✓ Artifact integrity verified")
except ValueError:
    print("✗ Hash mismatch - artifact corrupted!")
```

### Handle Extraction Errors
```python
from extraction.runner import extract_statement

try:
    stmt = extract_statement(
        pdf_path=Path("Bovina.pdf"),
        prompt_name="bovina_statement_prompt.txt",
        statement_pages=[0, 1, 2],
        api_key="sk-...",
    )
except ValueError as e:
    print(f"Extraction failed: {e}")
except RuntimeError as e:
    print(f"API error after retries: {e}")
```

---

## Data Models

### StatementDocument
```python
{
    "feedlot": {"name": str, ...},
    "owner": {"owner_number": str, ...},
    "period_start": date,
    "period_end": date,
    "total_balance": Decimal,
    "lot_references": [{"lot_number": str, "invoice_number": str, ...}],
    "transactions": [...],
}
```

### InvoiceDocument
```python
{
    "feedlot": {"name": str, ...},
    "owner": {"owner_number": str, ...},
    "invoice_number": str,
    "lot": {"lot_number": str, ...},
    "invoice_date": date,
    "statement_date": date,
    "line_items": [{"description": str, "quantity": Decimal, "total": Decimal}],
    "totals": {"total_amount_due": Decimal, ...},
}
```

### ReconciliationReport
```python
{
    "feedlot_key": str,
    "status": "PASS" | "WARN" | "FAIL",
    "checks": [
        {
            "check_id": str,
            "severity": "BLOCK" | "WARN" | "INFO",
            "passed": bool,
            "message": str,
            "evidence": {...}
        }
    ],
    "summary": {
        "total_checks": int,
        "passed_checks": int,
        "blocking_issues": int,
        "warnings": int,
    },
    "metrics": {
        "matched_invoices": int,
        "expected_invoices": int,
        "total_invoice_sum": str,
        "statement_total": str,
    }
}
```

### DataReference
```python
{
    "storage_uri": str,        # Absolute path
    "content_hash": str,       # SHA256
    "content_type": str,       # "application/json"
    "size_bytes": int,
    "stored_at": datetime,
}
```

---

## Check Types Reference

| ID | Type | Severity | Description |
|----|------|----------|-------------|
| A1 | Package | BLOCK/WARN | All referenced invoices exist |
| A2 | Package | WARN | No extra invoices |
| A3 | Package | WARN | Invoice dates in period |
| A4 | Package | BLOCK | Feedlot/owner match |
| A5 | Package | WARN | Invoice totals match (trust invoice) |
| A6 | Package | WARN | Package totals align |
| A7 | Package | WARN/BLOCK | All lots have invoices |
| B1 | Invoice | BLOCK | Required fields present |
| B2 | Invoice | BLOCK | Line sum = total |
| D1 | Package | BLOCK | No duplicates |

---

## Severity Levels

- **BLOCK**: Critical - stops processing. Fix required.
- **WARN**: Issue detected but non-critical. Often informational.
- **INFO**: Successful check. No action needed.

---

## Status Values

- **PASS**: All checks passed, no warnings
- **WARN**: Some warnings but no blockers
- **FAIL**: One or more blocking issues

---

See `MODULE_INTERFACES.md` for complete documentation.
