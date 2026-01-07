# Methodology

## Overview

This document describes the AP automation extraction pipeline for **Bovina** and **Mesquite** feedlots. The system extracts structured invoice and statement data from PDF documents using GPT-4o vision capabilities.

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PDF Input     │────▶│  Image Convert  │────▶│   GPT-4o API    │
│ (Bovina.pdf,    │     │  (PyMuPDF)      │     │   (Vision)      │
│  Mesquite.pdf)  │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  JSON Output    │◀────│   Validation    │◀────│  JSON Response  │
│  (artifacts/)   │     │   (Pydantic)    │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Components

### 1. Prompt Pack (`prompts/`)

| File | Purpose |
|------|---------|
| `system.txt` | Shared system prompt with strict JSON output rules |
| `bovina_statement_prompt.txt` | Extraction instructions for Bovina Statement of Notes |
| `bovina_invoice_prompt.txt` | Extraction instructions for Bovina Feed Invoices |
| `mesquite_statement_prompt.txt` | Extraction instructions for Mesquite Statement of Account |
| `mesquite_invoice_prompt.txt` | Extraction instructions for Mesquite Invoices |

### 2. Canonical Schemas (`models/`)

**`canonical.py`** defines Pydantic models for:
- `StatementDocument` - Statement header, transactions, lot references
- `InvoiceDocument` - Invoice header, line items, totals, performance metrics
- `DeadsReportDocument` - Death event tracking (future use)

**Custom Validators:**
- `DecimalValue` - Parses currency strings (`$1,234.56`, `(500.00)`) to `Decimal`
- `IntValue` - Parses formatted integers (`1,000`) to `int`
- `DateValue` - Parses date strings (`2025-11-01`, `11/30/2025`) to `date`

### 3. Extraction Runner (`scripts/run_extraction.py`)

The extraction script performs:

1. **PDF Loading** - Opens source PDFs from disk
2. **Page Categorization** - Identifies statement vs invoice pages by keyword matching
3. **Image Conversion** - Converts each PDF page to PNG at 2x zoom (PyMuPDF)
4. **API Calls** - Sends images + prompts to OpenAI GPT-4o Chat Completions API
5. **JSON Parsing** - Extracts JSON from model response, handles markdown code blocks
6. **Validation** - Validates against Pydantic models
7. **Output** - Writes validated JSON to `artifacts/` directory

---

## Execution Flow

```bash
# Run extraction
python scripts/run_extraction.py \
  --bovina "C:\path\to\Bovina.pdf" \
  --mesquite "C:\path\to\Mesquite.pdf"
```

**Process:**
1. Load `OPENAI_API_KEY` from `.env` file
2. Open Bovina PDF → categorize pages → extract statement → extract invoices
3. Open Mesquite PDF → categorize pages → extract statement → extract invoices
4. Validate all outputs against canonical schema
5. Save to `artifacts/{feedlot}/statement.json` and `artifacts/{feedlot}/invoices/*.json`

---

## Technical Decisions

### API Choice: Chat Completions vs Responses API

Initially attempted the OpenAI Responses API (`/v1/responses`) but encountered timeout issues with large image payloads. Switched to the **Chat Completions API** using the official OpenAI Python SDK, which provides:
- Better timeout handling (600s configurable)
- Automatic retry logic
- More stable connection management

### Image Processing

- **Format:** PNG (lossless, good OCR quality)
- **Resolution:** 2x zoom factor for clear text extraction
- **Encoding:** Base64 inline data URLs

### Date Parsing

The LLM returns dates as strings (e.g., `"2025-11-01"`). Custom Pydantic validators parse these into proper `date` objects, supporting multiple formats:
- `YYYY-MM-DD`
- `MM/DD/YYYY`
- `MM-DD-YYYY`

---

## Output Structure

```
artifacts/
├── bovina/
│   ├── statement.json      # Statement of Notes
│   └── invoices/
│       ├── 13330.json      # Feed Invoice for Lot 20-3883
│       ├── 13334.json      # Feed Invoice for Lot 20-3917
│       └── ...
└── mesquite/
    ├── statement.json      # Statement of Account
    └── invoices/
        ├── 43953.json
        ├── 43954.json
        └── 43955.json
```

---

## Sample Output

**Statement (excerpt):**
```json
{
  "feedlot": {
    "name": "BOVINA FEEDERS INC. DBA BF2"
  },
  "owner": {
    "owner_number": "531",
    "name": "SUGAR MOUNTAIN LIVESTOCK",
    "city": "SEATTLE",
    "state": "WA"
  },
  "period_start": "2025-11-01",
  "period_end": "2025-11-30",
  "total_balance": 164833.15,
  "lot_references": [
    {
      "lot_number": "20-3883",
      "invoice_number": "13330",
      "statement_charge": 8517.37
    }
  ]
}
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | ≥1.0 | OpenAI API client |
| `pymupdf` (fitz) | ≥1.23 | PDF to image conversion |
| `pydantic` | ≥2.0 | Schema validation |
| `requests` | ≥2.28 | HTTP client (fallback) |

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key with GPT-4o access |

Store in `.env` file at repository root:
```
OPENAI_API_KEY=sk-proj-...
```

---

## Error Handling

- **Rate Limits (429):** Automatic retry with exponential backoff (up to 5 attempts)
- **Timeouts:** 600-second timeout per request, with retry on timeout
- **Validation Errors:** Pydantic raises detailed errors for schema mismatches
- **JSON Parse Errors:** Attempts to extract JSON from markdown code blocks

---

## Results Summary

| Feedlot | Statements | Invoices |
|---------|------------|----------|
| Bovina | 1 | 23 |
| Mesquite | 1 | 3 |

All outputs validated successfully against canonical Pydantic models.

---

## Future Enhancements (Out of Scope for v1)

- Temporal workflows for orchestration
- Business Central posting integration
- GL/dimension mapping
- Human-in-the-loop review UI
- Deads report extraction
- Multi-tenant support
