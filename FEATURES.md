# AP Automation Pipeline - Complete Feature Reference

**System Name:** Temporal Invoice  
**Version:** 2.0 (Steps 0-9 Complete)  
**Last Updated:** January 7, 2026

---

## Table of Contents

1. [Feature Overview](#1-feature-overview)
2. [Core Extraction Features](#2-core-extraction-features)
3. [Validation Engine](#3-validation-engine)
4. [Reconciliation Engine](#4-reconciliation-engine)
5. [Entity Resolution](#5-entity-resolution)
6. [Vendor Resolution](#6-vendor-resolution)
7. [Coding Engine (GL Mapping)](#7-coding-engine-gl-mapping)
8. [Temporal Orchestration](#8-temporal-orchestration)
9. [Persistence & Audit Trail](#9-persistence--audit-trail)
10. [Data Models](#10-data-models)
11. [Artifact Storage](#11-artifact-storage)
12. [Worker & Activities](#12-worker--activities)
13. [Configuration & Deployment](#13-configuration--deployment)
14. [Mission Control Dashboard](#14-mission-control-dashboard)
15. [Stakeholder Views & Insights](#15-stakeholder-views--insights)
16. [Discrepancy Detection](#16-discrepancy-detection)

---

# 1. Feature Overview

## Summary Dashboard

| Feature | Module | Status | Description |
|---------|--------|--------|-------------|
| **PDF Extraction** | `extraction/` | ✅ Production | GPT-4o Vision extracts statements & invoices |
| **Invoice Validation** | `activities/validate.py` | ✅ Production | B1/B2 math validation checks |
| **Statement Reconciliation** | `reconciliation/engine.py` | ✅ Production | A1-A7, D1 reconciliation checks |
| **Entity Resolution** | `entity_resolver/` | ✅ Production | Auto-assign BC company from signals |
| **Vendor Resolution** | `vendor_resolver/` | ✅ Production | Alias table + fuzzy matching |
| **GL Coding Engine** | `coding_engine/` | ✅ Production | Hierarchical GL mapping + dimensions |
| **Temporal Workflows** | `workflows/` | ✅ Production | Durable execution with retry |
| **Audit Trail** | `activities/integrate.py` | ✅ Production | Per-stage audit logging |
| **ERP Payload Builder** | `activities/integrate.py` | ✅ Production | BC-ready purchase invoice format |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AP AUTOMATION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────┐     ┌──────────────────┐     ┌──────────────────────┐        │
│   │   PDF   │────▶│  Temporal Cloud  │────▶│  Business Central    │        │
│   │ Package │     │  (Orchestration) │     │  (ERP Integration)   │        │
│   └─────────┘     └────────┬─────────┘     └──────────────────────┘        │
│                            │                                                 │
│                            ▼                                                 │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                        PROCESSING PIPELINE                            │  │
│   │                                                                        │  │
│   │  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────────────┐  │  │
│   │  │EXTRACT  │─▶│VALIDATE  │─▶│ RECONCILE  │─▶│ RESOLVE & CODE     │  │  │
│   │  │GPT-4o   │  │B1/B2     │  │ A1-A7/D1   │  │ Entity/Vendor/GL   │  │  │
│   │  └─────────┘  └──────────┘  └────────────┘  └─────────────────────┘  │  │
│   │                                                                        │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                        STORAGE LAYER                                  │  │
│   │                                                                        │  │
│   │  ┌─────────────┐  ┌────────────────┐  ┌──────────────────────────┐   │  │
│   │  │   SQLite    │  │ JSON Artifacts │  │     Audit Events        │   │  │
│   │  │ (Tracking)  │  │ (Documents)    │  │     (Compliance)        │   │  │
│   │  └─────────────┘  └────────────────┘  └──────────────────────────┘   │  │
│   │                                                                        │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 2. Core Extraction Features

## Module: `extraction/runner.py`

### 2.1 PDF Page Classification

**Function:** `categorize_pages(doc, statement_keyword, invoice_keyword)`

| Feature | Description |
|---------|-------------|
| **Keyword Detection** | Scans each PDF page for statement/invoice keywords |
| **Multi-Feedlot Support** | Different keywords per feedlot type |
| **Page Index Output** | Returns lists of page indices for processing |

**Supported Feedlots:**

| Feedlot | Statement Keyword | Invoice Keyword |
|---------|------------------|-----------------|
| Bovina | `"statement of notes"` | `"feed invoice"` |
| Mesquite | `"statement of account"` | `"invoice"` |

### 2.2 Statement Extraction

**Function:** `extract_statement(pdf_path, prompt_name, statement_pages, api_key)`

| Feature | Description |
|---------|-------------|
| **GPT-4o Vision** | Uses latest vision model for document understanding |
| **Prompt Templates** | Feedlot-specific prompts in `prompts/` folder |
| **Structured Output** | Parses JSON response to `StatementDocument` |
| **Artifact Persistence** | Saves to `artifacts/{feedlot}/statement.json` |

**Extracted Fields:**
- Feedlot name and address
- Owner number and name
- Statement period (start/end dates)
- Total balance due
- Lot references (invoice number, lot number, charge, balance)

### 2.3 Invoice Extraction

**Function:** `extract_invoice(pdf_path, prompt_name, page_index, api_key)`

| Feature | Description |
|---------|-------------|
| **Page-by-Page** | Processes each invoice page individually |
| **Image Rendering** | Converts PDF pages to high-res images (300 DPI) |
| **Retry Logic** | 5 attempts with exponential backoff |
| **Canonical Model** | Outputs `InvoiceDocument` with normalized fields |

**Extracted Fields:**
- Invoice number, date, lot number
- Feedlot and owner information
- Line items (description, quantity, rate, amount)
- Subtotal, adjustments, total

### 2.4 Caching

| Feature | Description |
|---------|-------------|
| **Skip Existing** | If artifact exists, skips re-extraction |
| **Cache Control** | `use_cache=True/False` parameter |
| **Hash Verification** | `DataReference` includes content hash |

---

# 3. Validation Engine

## Module: `activities/validate.py`

### 3.1 Invoice Validation Checks

| Check ID | Name | Severity | Description |
|----------|------|----------|-------------|
| **B1** | Required Fields | BLOCK | Verifies mandatory fields present |
| **B2** | Line Item Sum | BLOCK | Sum of line items equals invoice total |

### 3.2 B1: Required Fields Check

**Required Fields:**
- `invoice_number` - Unique invoice identifier
- `lot.lot_number` - Lot reference
- `statement_date` OR `invoice_date` - Date reference
- `totals` - At least one total field
- `line_items[]` - At least one line item

### 3.3 B2: Line Item Sum Check

**Features:**
- Sum all `line_items[].amount` values
- Compare to invoice `total_amount_due` or `total_period_charges`
- **Tolerance:** ±$0.05 for rounding differences
- Fallback chain for total field selection

### 3.4 Validation Output

**Artifact:** `artifacts/{feedlot}/validations/{invoice_number}_validation.json`

```json
{
  "invoice_number": "13330",
  "validated_at": "2026-01-07T16:38:55Z",
  "status": "VALIDATED_PASS",
  "checks": [
    {"check_id": "B1_REQUIRED_FIELDS", "passed": true, "severity": "BLOCK"},
    {"check_id": "B2_LINE_SUM", "passed": true, "severity": "BLOCK"}
  ]
}
```

---

# 4. Reconciliation Engine

## Module: `reconciliation/engine.py`

### 4.1 Reconciliation Checks

| Check ID | Category | Severity | Description |
|----------|----------|----------|-------------|
| **A1** | Package | WARN/BLOCK | All statement-referenced invoices exist |
| **A2** | Package | WARN | No extra invoices beyond statement |
| **A3** | Package | WARN | Invoice dates within statement period |
| **A4** | Package | WARN | Feedlot/owner consistent across documents |
| **A5** | Package | WARN | Invoice amounts match statement lines |
| **A6** | Package | WARN | Sum of invoices matches statement total |
| **A7** | Package | INFO | All lots referenced are accounted for |
| **D1** | Duplicate | BLOCK | No duplicate invoice numbers |

### 4.2 Known Missing Invoice Registry

**Purpose:** Distinguish extraction failures from source PDF issues

```python
KNOWN_MISSING_FROM_SOURCE_PDF = {
    "bovina": {
        "13304": "Invoice for lot 20-3927 - listed on statement but invoice page not in PDF",
    },
    "mesquite": {},
}
```

- **Known Missing:** Severity = WARN (documented issue)
- **Unknown Missing:** Severity = BLOCK (possible extraction failure)

### 4.3 Tolerance Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| `AMOUNT_TOLERANCE` | $0.05 | Rounding tolerance for comparisons |

### 4.4 Reconciliation Status

| Status | Description |
|--------|-------------|
| `RECONCILED_PASS` | All checks passed |
| `RECONCILED_WARN` | Non-blocking issues found |
| `RECONCILED_FAIL` | Blocking issues found |

### 4.5 Reconciliation Output

**Artifact:** `artifacts/{feedlot}/_reconciliation_report.json`

```json
{
  "feedlot_key": "bovina",
  "status": "WARN",
  "checks": [...],
  "summary": {
    "total_checks": 76,
    "passed_checks": 75,
    "blocking_issues": 0,
    "warnings": 1
  },
  "metrics": {
    "matched_invoices": 23,
    "expected_invoices": 24,
    "total_invoice_sum": 165099.79,
    "statement_total": 164833.15
  }
}
```

---

# 5. Entity Resolution

## Module: `entity_resolver/`

### 5.1 Purpose

Automatically determine which BC company (entity) should receive an invoice based on document signals.

### 5.2 Scoring Algorithm

| Signal | Weight | Description |
|--------|--------|-------------|
| **Owner Number** | 25-40 pts | Strong signal - unique owner routing |
| **Vendor Existence** | 30 pts | Strong signal - vendor exists in entity |
| **Remit-to State** | 15 pts | Medium signal - state match |
| **Feedlot Name** | 15 pts | Medium signal - name pattern match |
| **Lot Number Prefix** | 10 pts | Weak signal - lot pattern match |

### 5.3 Decision Logic

```
IF top_score >= 70 AND margin_over_second >= 15:
    → Auto-assign entity (high confidence)
ELSE:
    → Return top 3 candidates for user confirmation
```

### 5.4 Routing Key Types

| Key Type | Description | Confidence |
|----------|-------------|------------|
| `OWNER_NUMBER` | Owner/customer number from invoice | HARD |
| `REMIT_STATE` | State from remit-to address | SOFT |
| `LOT_PREFIX` | Lot number prefix pattern | SOFT |
| `FEEDLOT_NAME` | Feedlot name pattern | SOFT |
| `VENDOR_NAME` | Vendor name for matching | HARD |

### 5.5 Entity Profile Model

```python
class EntityProfile:
    customer_id: str       # Tenant identifier
    entity_id: str         # BC company GUID
    entity_name: str       # Human-readable name
    entity_code: str       # Short code (BF2, MESQ)
    aliases: List[str]     # Alternative names for fuzzy matching
    routing_rules: Dict    # Complex routing logic
    default_dimensions: Dict  # Default dimension values
    is_active: bool
```

### 5.6 Resolution Output

```python
class EntityResolution:
    is_auto_assigned: bool     # True if confident match
    entity_id: str             # BC company GUID
    entity_name: str           # Company name
    bc_company_id: str         # For API calls
    confidence: Decimal        # Score percentage
    match_method: str          # How it was matched
    reasons: List[str]         # Explanation
    candidates: List[EntityCandidate]  # If not auto-assigned
```

---

# 6. Vendor Resolution

## Module: `vendor_resolver/`

### 6.1 Purpose

Match extracted vendor/feedlot names to BC vendor records using alias table and fuzzy matching.

### 6.2 Resolution Strategy

```
1. Normalize extracted name (lowercase, remove punctuation)
2. Check alias table for exact match (instant return)
3. If no alias → Fuzzy match against BC vendor list
4. Score candidates and decide auto-match or return options
5. On user confirmation → Create alias for future instant match
```

### 6.3 Normalization Rules

| Transformation | Example |
|----------------|---------|
| Lowercase | `"BOVINA FEEDERS"` → `"bovina feeders"` |
| Remove punctuation | `"Inc., LLC"` → `"inc llc"` |
| Collapse whitespace | `"  DBA  "` → `" dba "` |
| Remove common suffixes | `"feeders inc"` → `"feeders"` |

### 6.4 Match Types

| Match Type | Description | Speed |
|------------|-------------|-------|
| `EXACT_ALIAS` | Found in alias table | Instant |
| `FUZZY_NAME` | Fuzzy name matching | Moderate |
| `ADDRESS_MATCH` | Address helped disambiguate | Moderate |
| `MANUAL` | User manually selected | N/A |
| `NO_MATCH` | No match found | N/A |

### 6.5 Fuzzy Matching Algorithm

| Metric | Weight | Description |
|--------|--------|-------------|
| **Token Similarity** | 60% | Jaccard similarity of word tokens |
| **String Similarity** | 25% | Levenshtein ratio |
| **Address Score** | 15% | City/state match bonus |

### 6.6 Alias Model

```python
class VendorAlias:
    customer_id: str        # Tenant identifier
    entity_id: str          # BC company GUID
    alias_normalized: str   # Normalized name (lookup key)
    alias_original: str     # Original extracted name
    vendor_id: str          # BC vendor GUID
    vendor_number: str      # Human-readable code (V00010)
    vendor_name: str        # Display name
    created_by: str         # User or system
```

### 6.7 Resolution Output

```python
class VendorResolution:
    is_auto_matched: bool      # True if confident match
    vendor_id: str             # BC vendor GUID
    vendor_number: str         # Vendor code
    vendor_name: str           # Display name
    match_type: MatchType      # How matched
    confidence_score: Decimal  # 0-100
    candidates: List[VendorCandidate]  # If not auto-matched
    resolved_at: datetime
    resolution_time_ms: int
```

---

# 7. Coding Engine (GL Mapping)

## Module: `coding_engine/`

### 7.1 Purpose

Generate GL account coding and dimension values for invoice lines using hierarchical mapping rules.

### 7.2 Mapping Hierarchy

```
┌─────────────────────────────────────────────────┐
│  VENDOR LEVEL (Most Specific)                   │
│  Entity + Vendor + Category → GL Account        │
├─────────────────────────────────────────────────┤
│  ENTITY LEVEL                                   │
│  Entity + Category → GL Account                 │
├─────────────────────────────────────────────────┤
│  GLOBAL LEVEL                                   │
│  Category → GL Account                          │
├─────────────────────────────────────────────────┤
│  SUSPENSE (Fallback)                            │
│  Unmapped → 9999-00 (Suspense Account)          │
└─────────────────────────────────────────────────┘
```

### 7.3 Line Item Categories

| Category | Description | Keywords |
|----------|-------------|----------|
| `FEED` | Feed & rations | feed, ration, grain, hay |
| `YARDAGE` | Daily yardage charges | yardage, daily, pen |
| `VET` | Veterinary services | vet, medicine, health |
| `PROCESSING` | Processing charges | processing, working |
| `INSURANCE` | Cattle insurance | insurance, mortality |
| `INTEREST` | Interest charges | interest, finance |
| `FREIGHT` | Freight/trucking | freight, trucking, haul |
| `COMMISSION` | Sales commission | commission, selling |
| `UNCATEGORIZED` | Unknown category | (fallback) |

### 7.4 Dimension System

| Dimension Code | Source | Transform | Example |
|----------------|--------|-----------|---------|
| `LOT` | `invoice.lot_number` | UPPERCASE | `20-3883` |
| `FEEDLOT` | `feedlot.name` | NORMALIZE | `BF2` |
| `OWNER` | `owner.number` | NONE | `531` |
| `PERIOD` | `invoice.invoice_date` | YYYY_MM | `2025-11` |
| `ENTITY` | `entity.code` | NONE | `BF2` |

### 7.5 GL Mapping Model

```python
class GLMapping:
    category: str           # Line item category
    gl_account_ref: str     # GL account number
    level: MappingLevel     # vendor/entity/global
    entity_id: str          # For entity/vendor level
    vendor_id: str          # For vendor level
    description: str        # Human-readable
    is_active: bool
```

### 7.6 Dimension Rule Model

```python
class DimensionRule:
    dimension_code: str      # Dimension identifier
    source_field: str        # Data source
    transform: TransformType # Transformation to apply
    entity_id: str           # Entity scope (None = global)
    default_value: str       # If source is empty
    is_required: bool        # Mandatory dimension
```

### 7.7 Coding Output

```python
class InvoiceCoding:
    invoice_number: str
    entity_id: str
    vendor_ref: str
    invoice_date: str
    total_amount: Decimal
    is_complete: bool              # All required dimensions present
    missing_mappings: List[str]    # Categories without GL mapping
    missing_dimensions: List[str]  # Required dimensions not resolved
    warnings: List[str]            # Non-blocking issues
    line_codings: List[LineCoding] # Per-line coding
```

### 7.8 Line Coding Output

```python
class LineCoding:
    line_index: int
    description: str
    amount: Decimal
    category: str              # Resolved category
    gl_ref: str                # GL account reference
    mapping_level: MappingLevel  # Which level matched
    dimensions: List[DimensionValue]
    is_complete: bool
    missing_dimensions: List[str]
```

---

# 8. Temporal Orchestration

## Module: `workflows/`

### 8.1 Registered Workflows

| Workflow | Purpose | Stages |
|----------|---------|--------|
| `PingWorkflow` | Health check | 1 (echo) |
| `APPackageWorkflow` | Package processing | 7 (full pipeline) |
| `InvoiceWorkflow` | Per-invoice integration | 5 (resolution → payload) |

### 8.2 APPackageWorkflow Stages

```
1. PERSIST_PACKAGE     → Create package record (STARTED)
2. SPLIT_PDF           → Identify statement/invoice pages
3. EXTRACT_STATEMENT   → GPT-4o Vision extraction
4. EXTRACT_INVOICES    → Extract each invoice (loop)
5. VALIDATE_INVOICES   → B1/B2 checks (loop)
6. RECONCILE_PACKAGE   → A1-A7/D1 checks
7. UPDATE_STATUS       → Final status (PASS/WARN/FAIL)
```

### 8.3 InvoiceWorkflow Stages

```
1. RESOLVE_ENTITY      → Determine BC company
2. RESOLVE_VENDOR      → Match vendor to BC vendor
3. APPLY_MAPPING       → Generate GL coding
4. BUILD_PAYLOAD       → Create BC-ready JSON
5. PAYLOAD_GENERATED   → Stop (v1)
6. CREATE_UNPOSTED     → Post to BC (v1.5)
```

### 8.4 InvoiceWorkflowInput

```python
class InvoiceWorkflowInput:
    ap_package_id: str
    invoice_number: str
    feedlot_type: str
    customer_id: str
    invoice_data: Dict[str, Any]     # Already extracted invoice
    statement_data: Dict[str, Any]   # Optional for dimensions
    entity_id: str                   # Pre-resolved (optional)
    vendor_id: str                   # Pre-resolved (optional)
    skip_entity_resolution: bool
    skip_vendor_resolution: bool
    stop_at_stage: str               # Default: PAYLOAD_GENERATED
```

### 8.5 InvoiceWorkflowOutput

```python
class InvoiceWorkflowOutput:
    ap_package_id: str
    invoice_number: str
    status: str                      # COMPLETED/FAILED/NEEDS_REVIEW
    current_stage: str
    entity_id: str
    entity_name: str
    bc_company_id: str
    vendor_id: str
    vendor_number: str
    vendor_name: str
    is_fully_coded: bool
    missing_mappings: List[str]
    payload_ref: Dict[str, Any]      # DataReference to payload
    is_payload_ready: bool
    stage_results: List[Dict]        # Per-stage audit
    needs_review: bool
    review_reasons: List[str]
```

### 8.6 Activity Timeouts & Retry

| Activity Type | Timeout | Retries | Backoff |
|---------------|---------|---------|---------|
| Extraction | 5 minutes | 3 | Exponential |
| Validation | 30 seconds | 3 | Fixed |
| Reconciliation | 2 minutes | 3 | Exponential |
| Integration | 2 minutes | 3 | Exponential |
| Persistence | 30 seconds | 3 | Fixed |

---

# 9. Persistence & Audit Trail

## Module: `activities/persist.py` & `activities/integrate.py`

### 9.1 Database Tables

#### `ap_packages`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `ap_package_id` | TEXT | Unique package identifier |
| `feedlot_type` | TEXT | BOVINA or MESQUITE |
| `status` | TEXT | Current processing status |
| `statement_ref` | TEXT | JSON DataReference to statement |
| `total_invoices` | INTEGER | Expected invoice count |
| `extracted_invoices` | INTEGER | Successfully extracted count |
| `created_at` | TIMESTAMP | Package creation time |
| `updated_at` | TIMESTAMP | Last update time |

#### `ap_invoices`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `ap_package_id` | TEXT | Parent package reference |
| `invoice_number` | TEXT | Invoice identifier |
| `lot_number` | TEXT | Lot reference |
| `invoice_date` | TEXT | Invoice date |
| `total_amount` | REAL | Invoice total |
| `invoice_ref` | TEXT | JSON DataReference to invoice |
| `validation_ref` | TEXT | JSON DataReference to validation |
| `status` | TEXT | EXTRACTED/VALIDATED_PASS/VALIDATED_FAIL |
| `created_at` | TIMESTAMP | Record creation time |

#### `audit_events`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `ap_package_id` | TEXT | Package reference |
| `invoice_number` | TEXT | Invoice reference |
| `stage` | TEXT | Processing stage (InvoiceStage enum) |
| `status` | TEXT | SUCCESS/FAILED/SKIPPED/NEEDS_REVIEW |
| `details` | TEXT | JSON details |
| `created_at` | TIMESTAMP | Event timestamp |

### 9.2 Audit Event Activity

**Activity:** `persist_audit_event(input: AuditEventInput) -> AuditEventOutput`

```python
@dataclass
class AuditEventInput:
    ap_package_id: str
    invoice_number: str
    stage: str                # InvoiceStage value
    status: str               # SUCCESS/FAILED/SKIPPED
    details: Dict[str, Any]   # Stage-specific data

@dataclass
class AuditEventOutput:
    event_id: int
    timestamp: str
    success: bool
```

### 9.3 Invoice Stages (Audit Points)

| Stage | Description | Logged Data |
|-------|-------------|-------------|
| `EXTRACT` | Document extraction | extraction_ref, feedlot, time |
| `VALIDATE` | B1/B2 validation | checks, status, issues |
| `RECONCILE_LINK` | Statement linking | match_status, discrepancies |
| `RESOLVE_ENTITY` | Entity resolution | entity_id, confidence, method |
| `RESOLVE_VENDOR` | Vendor matching | vendor_id, match_type |
| `APPLY_MAPPING_OVERLAY` | GL coding | gl_accounts, dimensions |
| `BUILD_ERP_PAYLOAD` | Payload creation | payload_ref, line_count |
| `PAYLOAD_GENERATED` | Ready for posting | final_status |
| `CREATE_UNPOSTED` | Posted to BC | bc_response, posted_id |

---

# 10. Data Models

## Module: `models/canonical.py`

### 10.1 StatementDocument

```python
class StatementDocument:
    feedlot: Feedlot                   # Feedlot info
    owner: Owner                       # Owner/customer info
    period_start: date                 # Statement period start
    period_end: date                   # Statement period end
    total_balance: Decimal             # Total amount due
    lot_references: List[StatementLotReference]  # Invoice lines
    transactions: List[StatementTransaction]     # Transaction detail
    summary_rows: List[StatementSummaryRow]      # Summary by category
    metadata: DocumentMetadata
```

### 10.2 InvoiceDocument

```python
class InvoiceDocument:
    feedlot: Feedlot                   # Feedlot info
    owner: Owner                       # Owner/customer info
    lot: LotInfo                       # Lot details
    invoice_number: str                # Unique identifier
    invoice_date: date                 # Invoice date
    statement_date: date               # Statement period date
    line_items: List[InvoiceLineItem]  # Charge lines
    totals: InvoiceTotals              # Total amounts
    metadata: DocumentMetadata
```

### 10.3 Supporting Models

```python
class Feedlot:
    name: str
    address_line1: str
    city: str
    state: str
    postal_code: str
    phone: str

class Owner:
    owner_number: str
    name: str
    address_line1: str
    city: str
    state: str
    postal_code: str

class InvoiceLineItem:
    description: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    category: str        # Optional category hint
```

## Module: `models/refs.py`

### 10.4 DataReference

```python
class DataReference:
    storage_uri: str      # Absolute file path
    content_hash: str     # SHA256 for integrity
    content_type: str     # MIME type (application/json)
    size_bytes: int       # File size
    stored_at: datetime   # Storage timestamp
```

### 10.5 ReconciliationReport

```python
class ReconciliationReport:
    feedlot_key: str
    status: str           # PASS, WARN, FAIL
    checks: List[dict]    # Individual check results
    summary: dict         # Aggregated summary
    metrics: dict         # Processing metrics
    report_ref: DataReference
```

---

# 11. Artifact Storage

## Module: `storage/artifacts.py`

### 11.1 Directory Structure

```
artifacts/
├── bovina/
│   ├── statement.json           # Extracted statement
│   ├── _reconciliation_report.json  # Reconciliation result
│   ├── invoices/
│   │   ├── 13330.json           # Invoice documents
│   │   ├── 13334.json
│   │   └── ...
│   ├── validations/
│   │   ├── 13330_validation.json
│   │   └── ...
│   ├── codings/
│   │   ├── 13330_coding.json    # GL coding results
│   │   └── ...
│   └── payloads/
│       ├── 13330_payload.json   # BC-ready payloads
│       └── ...
│
└── mesquite/
    ├── statement.json
    ├── invoices/
    ├── validations/
    ├── codings/
    └── payloads/
```

### 11.2 Storage Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `put_json(feedlot, filename, data)` | Save JSON artifact | DataReference |
| `get_json(feedlot, filename)` | Load JSON artifact | dict |
| `artifact_exists(feedlot, filename)` | Check existence | bool |

### 11.3 BC Payload Format

**Artifact:** `payloads/{invoice_number}_payload.json`

```json
{
  "purchaseInvoice": {
    "vendorNumber": "V-BF2",
    "vendorName": "Bovina Feeders Inc.",
    "invoiceDate": "2025-11-30",
    "vendorInvoiceNumber": "13330",
    "status": "Draft"
  },
  "purchaseInvoiceLines": [
    {
      "lineNumber": 10000,
      "description": "Feed & Rations",
      "accountId": "5100-01",
      "unitPrice": 8487.61,
      "dimensions": {
        "FEEDLOT": "BF2",
        "LOT": "20-3883",
        "OWNER": "531",
        "PERIOD": "2025-11",
        "ENTITY": "BF2"
      }
    }
  ]
}
```

---

# 12. Worker & Activities

## Module: `workers/worker.py`

### 12.1 Worker Configuration

| Setting | Value |
|---------|-------|
| **Task Queue** | `ap-default` |
| **Namespace** | `skalable.ocfwk` |
| **Endpoint** | `us-central1.gcp.api.temporal.io:7233` |
| **Registered Workflows** | 3 |
| **Registered Activities** | 14 |

### 12.2 Registered Workflows

| Workflow | Description |
|----------|-------------|
| `PingWorkflow` | Health check workflow |
| `APPackageWorkflow` | Full package processing |
| `InvoiceWorkflow` | Per-invoice integration |

### 12.3 Registered Activities (14 Total)

#### Persistence Activities (4)

| Activity | Purpose |
|----------|---------|
| `persist_package_started` | Create package record |
| `persist_invoice` | Create invoice record |
| `update_package_status` | Update package status |
| `update_invoice_status` | Update invoice status + validation ref |

#### Extraction Activities (3)

| Activity | Purpose |
|----------|---------|
| `split_pdf` | Identify page types |
| `extract_statement` | LLM extract statement |
| `extract_invoice` | LLM extract invoice |

#### Validation Activity (1)

| Activity | Purpose |
|----------|---------|
| `validate_invoice` | B1/B2 math checks |

#### Reconciliation Activity (1)

| Activity | Purpose |
|----------|---------|
| `reconcile_package` | A1-A7/D1 statement checks |

#### Integration Activities (5)

| Activity | Purpose |
|----------|---------|
| `resolve_entity` | EntityResolver → BC company |
| `resolve_vendor` | VendorResolver → BC vendor |
| `apply_mapping_overlay` | CodingEngine → GL coding |
| `build_bc_payload` | Transform → BC purchase invoice |
| `persist_audit_event` | Log audit event to database |

---

# 13. Configuration & Deployment

### 13.1 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `TEMPORAL_ENDPOINT` | Temporal Cloud endpoint | Yes |
| `TEMPORAL_NAMESPACE` | Temporal namespace | Yes |
| `TEMPORAL_API_KEY` | Temporal API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o | Yes |

### 13.2 Database Files

| File | Purpose |
|------|---------|
| `ap_automation.db` | Main SQLite database (packages, invoices, audit) |
| `entity_resolver/resolver.db` | Entity resolution tables |
| `vendor_resolver/resolver.db` | Vendor alias tables |
| `coding_engine/coding.db` | GL mapping tables |

### 13.3 Prompt Templates

| Template | Purpose |
|----------|---------|
| `prompts/bovina_statement_prompt.txt` | Bovina statement extraction |
| `prompts/bovina_invoice_prompt.txt` | Bovina invoice extraction |
| `prompts/mesquite_statement_prompt.txt` | Mesquite statement extraction |
| `prompts/mesquite_invoice_prompt.txt` | Mesquite invoice extraction |
| `prompts/system.txt` | System prompt for all extractions |

### 13.4 Starting the Worker

```powershell
# Set environment variables
$env:OPENAI_API_KEY = "sk-..."

# Start worker
.venv\Scripts\python.exe workers\worker.py
```

### 13.5 Starting a Workflow

```python
from temporal_client import get_temporal_client
from workflows.ap_package_workflow import APPackageWorkflow, APPackageInput

async def run_package():
    client = await get_temporal_client()
    
    result = await client.execute_workflow(
        APPackageWorkflow.run,
        APPackageInput(
            ap_package_id="pkg_bovina_20251107",
            feedlot_type="BOVINA",
            pdf_path="C:/path/to/bovina.pdf",
        ),
        id="pkg_bovina_20251107",
        task_queue="ap-default",
    )
    
    return result
```

---

## Appendix A: Step Completion Summary

| Step | Description | Files Created/Modified | Lines of Code |
|------|-------------|------------------------|---------------|
| **Step 0** | Module Interfaces | `extraction/runner.py`, `reconciliation/engine.py`, `models/`, `storage/` | ~1,500 |
| **Step 1** | Temporal Connectivity | `temporal_client.py`, `workers/worker.py`, `workflows/ping_workflow.py` | ~200 |
| **Step 2** | AP Package Workflow | `workflows/ap_package_workflow.py`, `activities/persist.py` | ~500 |
| **Step 3** | Extraction Activities | `activities/extract.py` | ~480 |
| **Step 4** | Validation Activities | `activities/validate.py` | ~340 |
| **Step 5** | Reconciliation Activity | `activities/reconcile.py` | ~180 |
| **Step 6** | Entity Resolver | `entity_resolver/` module | ~900 |
| **Step 7** | Vendor Resolver | `vendor_resolver/` module | ~750 |
| **Step 8** | Coding Engine | `coding_engine/` module | ~700 |
| **Step 9** | Temporal Integration | `activities/integrate.py`, `workflows/invoice_workflow.py` | ~1,100 |

**Total Lines of Code:** ~6,650+

---

# 14. Mission Control Dashboard

## UI Design: `ap-mission-control-v3.jsx`

### 14.1 Dashboard Philosophy

The Mission Control dashboard is designed around the core insight that **different stakeholders hunt for different discrepancies**:

| Stakeholder | Primary Concern | Dashboard Focus |
|-------------|-----------------|-----------------|
| **Operations** | "Did the system catch what my team would normally catch?" | Completeness, problem lots |
| **CFO** | "Can I trust the numbers? Where is financial risk hiding?" | Dollar risk, trends, drift |
| **Accounting** | "Is this auditable and defensible six months from now?" | Traceability, duplicates, credits |
| **IT/Controls** | "Is this safe, deterministic, and controllable?" | Audit trails, idempotency |

### 14.2 Invoice Pipeline Visualization

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INVOICE PIPELINE FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐   ┌───────────┐   ┌─────────────┐   ┌─────────────────────┐  │
│  │ RECEIVED │──▶│PROCESSING │──▶│AUTO-APPROVED│──▶│   READY TO POST     │  │
│  │   215    │   │     3     │   │    187      │   │       195           │  │
│  │ $892K    │   │   $12K    │   │   $693K     │   │      $759K          │  │
│  └──────────┘   └───────────┘   └─────────────┘   └─────────────────────┘  │
│                       │                                      │              │
│                       ▼                                      ▼              │
│              ┌─────────────────┐               ┌──────────────────────┐    │
│              │  HUMAN REVIEW   │               │   POSTED TO ERP      │    │
│              │      12         │               │       178            │    │
│              │    $89K         │               │      $687K           │    │
│              └─────────────────┘               └──────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 14.3 Pipeline Stage Metrics

| Stage | Count | Dollars | Icon | Status Color |
|-------|-------|---------|------|--------------|
| **Received** | 215 | $892,341.50 | FileText | Blue (info) |
| **Processing** | 3 | $12,450.00 | Loader | Purple (active) |
| **Auto-Approved** | 187 | $692,841.20 | Bot | Green (success) |
| **Human Review** | 12 | $89,234.50 | Hand | Amber (warn) |
| **Ready to Post** | 195 | $758,923.45 | CheckCheck | Green (success) |
| **Posted to ERP** | 178 | $687,234.20 | Send | Green (success) |

### 14.4 Human Review Panel

**Purpose:** Surface invoices requiring human intervention with clear reasons

| Reason | Count | Dollars | Urgency |
|--------|-------|---------|---------|
| Suspense GL Coding | 4 | $32,180.00 | Normal |
| Missing Source Document | 3 | $28,450.75 | **Urgent** |
| Amount Variance | 2 | $15,890.00 | Normal |
| Entity Resolution | 2 | $8,713.75 | Normal |
| Duplicate Detection | 1 | $4,000.00 | **Urgent** |

**Recent Items Display:**
```
┌────────────────────────────────────────────────────────────────────────────┐
│ INV-13304 │ 20-3927 │ Bovina  │ $301.36  │ Medicine only, zero head │ 5m │
│ INV-13508 │ 20-4263 │ Bovina  │ $7,427.87│ Contains credit adjustment│12m │
│ INV-M2901 │ M-2901  │ Mesquite│ $8,742.30│ Hospital feed >15%       │28m │
└────────────────────────────────────────────────────────────────────────────┘
```

### 14.5 Packages Panel

**Features:**
- Search by package ID, feedlot, or owner
- Filter by status: All / Ready / Review / Blocked
- Status breakdown per package (ready/review/blocked counts)

**Package Display Columns:**

| Column | Description |
|--------|-------------|
| Package ID | Unique identifier (e.g., `PKG-2025-1130-531`) |
| Feedlot | Feedlot name with code badge |
| Owner | Cattle owner name |
| Invoices | Total invoice count with lot count |
| Status | Ready / Review / Blocked with visual indicator |
| Amount | Total dollar value |
| Action | Open / Review Now buttons |

### 14.6 Today's Activity Stats

| Metric | Value | Description |
|--------|-------|-------------|
| Processed | 47 | Invoices processed today |
| Auto-Approved | 89% | Auto-approval rate |
| Avg Time | 4.2 sec | Average processing time |
| Value | $198K | Total dollars processed |

### 14.7 Theme System

**Dark Mode (Default):**
- Background: `bg-slate-900`
- Cards: `bg-slate-800`
- Text: `text-white` / `text-slate-400`

**Light Mode:**
- Background: `bg-gray-50`
- Cards: `bg-white`
- Text: `text-gray-900` / `text-gray-500`

**Status Colors:**
| Status | Dark Mode | Light Mode |
|--------|-----------|------------|
| Success | `text-emerald-400` | `text-emerald-600` |
| Warning | `text-amber-400` | `text-amber-600` |
| Error | `text-red-400` | `text-red-600` |
| Info | `text-blue-400` | `text-blue-600` |
| Purple | `text-purple-400` | `text-purple-600` |

---

# 15. Stakeholder Views & Insights

## 15.1 Role-Based Dashboard Insights

The dashboard provides tailored insights for each stakeholder role with:
- **Key Metrics** (4 role-specific KPIs)
- **Alerts** (Actionable items requiring attention)
- **Details** (Expandable sections with drill-down data)

---

## 15.2 CFO View: Financial Overview

**Mental Model:** "Can I trust the numbers, and where is financial risk hiding?"

### Key Metrics

| Metric | Value | Trend | Status |
|--------|-------|-------|--------|
| Total Pipeline | $847K | +12% | ↑ Up |
| Ready to Post | $759K | 89% | ✓ Good |
| Blocked Dollars | $65K | -23% | ↓ Down |
| Avg Cost/Head | $187.42 | +2.1% | Neutral |

### Alerts

| Type | Message | Actionable |
|------|---------|------------|
| ⚠️ Warn | $42K blocked due to missing source documents | Yes |
| ℹ️ Info | Feed costs trending 2.1% above 3-month average | No |
| 🔴 Error | $568 credit in suspense needs classification | Yes |

### Details Sections

**Reconciliation Status:**
| Status | Value |
|--------|-------|
| ✅ Perfect Match | 9 packages |
| ⚠️ Within Tolerance | 2 packages |
| ❌ Needs Attention | 1 package |

**Cost Outliers (>10% variance):**
| Lot | Cost/Head | Variance |
|-----|-----------|----------|
| 20-4353 (Bovina) | $218.59/head | +16.6% |
| M-2847 (Mesquite) | $224.87/head | +15.2% |
| 20-4260 (Bovina) | $203.14/head | +8.4% |

**Suspense Postings:**
| Item | Amount | GL |
|------|--------|-----|
| 20-3927 Medicine charge | $301.36 | 9999-00 |
| 20-4263 MIDWEST credit | -$568.00 | 9999-00 |

### CFO Questions Answered

1. **Do invoice totals reconcile to statements at scale?**
   - Dashboard shows: Statement total vs Sum of invoices
   - Delta explained by: Missing invoices, OCR variances
   - Example: Bovina $164,833.15 statement vs $165,099.79 invoices = $266.64 (missing invoice 13304)

2. **Where are dollars stuck?**
   - Blocked dollars by reason with dollar impact
   - CFO sees "$42K blocked" not "3 packages blocked"

3. **Are costs trending out of bounds?**
   - Cost outlier panel shows lots exceeding averages
   - Feed $/ton variability highlighted

---

## 15.3 COO View: Operations Overview

**Mental Model:** "Did the system catch what my team would normally catch?"

### Key Metrics

| Metric | Value | Trend | Status |
|--------|-------|-------|--------|
| Total Lots | 47 | +5 | ↑ Up |
| Lots Matched | 44 | 94% | ✓ Good |
| Problem Lots | 6 | -2 | ↓ Down |
| Death Loss | 23 | +9 | ⚠️ Bad |

### Alerts

| Type | Message | Actionable |
|------|---------|------------|
| 🔴 Error | Lot M-2901: 8 deaths (RESPIRATORY) - 4x above average | Yes |
| ⚠️ Warn | 3 lots with hospital feed >10% for 3+ months | Yes |
| ⚠️ Warn | 2 lots missing invoice documents | Yes |

### Details Sections

**Lot Accountability:**
| Status | Count |
|--------|-------|
| On Statements | 47 lots |
| Matched to Invoices | 44 lots |
| Missing Invoices | 2 lots |
| Explained Exceptions | 1 lot |

**Problem Lots (Repeated Warnings):**
| Lot | Feedlot | Warnings |
|-----|---------|----------|
| M-2901 | Mesquite | 6 warns: Death spike, Hospital feed |
| 20-3927 | Bovina | 5 warns: Missing inv, Zero head |
| 20-4033 | Bovina | 4 warns: Hospital 12%, High medicine |

**Death Loss by Feedlot:**
| Feedlot | Deaths | Cause |
|---------|--------|-------|
| Mesquite Cattle | 14 (4 lots) | RESPIRATORY |
| Bovina Feeders | 6 (3 lots) | MECHANICAL |
| Panhandle Feedyard | 3 (2 lots) | UNKNOWN |

### Operations Questions Answered

1. **Are all lots accounted for this month?**
   - Lot Accountability shows: On statement vs Matched vs Missing
   - Missing lots flagged with explanation (source issue vs extraction failure)

2. **Which lots are "problem lots"?**
   - Problem Lots panel shows repeated warnings
   - Tracks: Hospital feed, medicine, processing patterns

3. **Is death loss being reflected correctly?**
   - Death Loss by Feedlot with cause breakdown
   - Cross-references with invoice head counts

---

## 15.4 CIO View: System & Controls

**Mental Model:** "Is this safe, deterministic, and controllable?"

### Key Metrics

| Metric | Value | Trend | Status |
|--------|-------|-------|--------|
| Success Rate | 98.7% | +0.3% | ✓ Good |
| Avg Processing | 4.2 sec | -0.8s | ↓ Down |
| Auto-Approval | 89% | +3% | ↑ Up |
| Uptime | 99.9% | 30 days | ✓ Good |

### Alerts

| Type | Message | Actionable |
|------|---------|------------|
| ✅ Success | 12 duplicate posting attempts successfully blocked | No |
| ℹ️ Info | 2 manual overrides this period (both with approval) | No |
| ⚠️ Warn | P95 processing time at 12.8s (threshold: 15s) | No |

### Details Sections

**Processing Stats:**
| Metric | Value |
|--------|-------|
| Invoices Processed | 210 this period |
| Auto-Approved | 187 (89%) |
| Human Reviewed | 21 (10%) |
| Overridden | 2 (1%) |

**Idempotency & Safety:**
| Metric | Value |
|--------|-------|
| Duplicate Attempts | 12 blocked |
| Posting Registry | 4,287 entries |
| Last Failure | 3 days ago |

**Audit Log:**
| Metric | Value |
|--------|-------|
| Total Entries | 1,842 this period |
| Edits with Approval | 23 |
| Unauthorized Edits | 0 |

### IT/Controls Questions Answered

1. **What happens if the system crashes mid-process?**
   - Temporal guarantees exactly-once execution
   - Workflows resume from last checkpoint

2. **Can users override data without audit?**
   - All edits logged with before/after values
   - Override requires approval context

3. **Can the same invoice be posted twice?**
   - Posting registry prevents duplicates
   - Idempotency key: `{feedlot}_{invoice_number}_{lot}_{period}`

---

## 15.5 Accounting View: Audit & Compliance

**Mental Model:** "Is this auditable, consistent, and defensible six months from now?"

### Key Metrics

| Metric | Value | Trend | Status |
|--------|-------|-------|--------|
| Fully Traceable | 187 | 94% | ✓ Good |
| Credits Classified | 7/8 | 1 pending | ⚠️ Warn |
| Duplicates Blocked | 1 | $4,100 | ✓ Good |
| Period Consistency | 196/200 | 98% | ✓ Good |

### Alerts

| Type | Message | Actionable |
|------|---------|------------|
| 🔴 Error | INV-13304 duplicate: Already posted in October ($4,100) | Yes |
| ⚠️ Warn | 1 credit pending classification: -$568 MIDWEST transfer | Yes |
| ℹ️ Info | 4 cross-period invoices flagged and reviewed | No |

### Details Sections

**Traceability:**
| Status | Count |
|--------|-------|
| Fully Traceable | 187 invoices |
| Partial Trace | 12 invoices |
| No Trace | 1 invoice |

**Credit Handling:**
| Status | Count |
|--------|-------|
| Credits Identified | 8 total |
| Properly Classified | 7 credits |
| Pending Classification | 1 credit (-$568) |

**Duplicate Prevention:**
| Status | Count |
|--------|-------|
| Potential Duplicates | 2 detected |
| Confirmed & Blocked | 1 (INV-13304) |
| False Positives | 1 (released) |

### Accounting Questions Answered

1. **Is every posted amount traceable back to source documents?**
   - Statement → Invoice → Line Item → PDF region
   - Document Intelligence view with bounding boxes

2. **Are beginning balances, credits, and rolling balances handled correctly?**
   - Only current charges hit AP, not beginning balances
   - Credits flagged for classification

3. **Are invoice numbers and dates consistent?**
   - Duplicate detection across periods
   - Cross-period invoice flagging

---

# 16. Discrepancy Detection

## 16.1 What Discrepancies Each Stakeholder Hunts

### Operations Discrepancy Checklist

| Discrepancy Type | Example | System Detection |
|------------------|---------|------------------|
| **Missing Invoice** | Lot 20-3927 on statement, no invoice PDF | A1 check flags as WARN |
| **Repeated Hospital Feed** | Lot 20-4033 hospital feed 3+ months | Cross-period analysis |
| **Zero Head with Charges** | Medicine $301.36 on lot with 0 head | B1 validation warning |
| **Head Count Drift** | 847 head Nov, 823 Dec, no death/sale | Cross-period trend |

### CFO Discrepancy Checklist

| Discrepancy Type | Example | System Detection |
|------------------|---------|------------------|
| **Statement vs Invoice Drift** | $164,833 statement, $165,099 invoices | A6 reconciliation |
| **Accumulating Variances** | 12 invoices with $0.03 rounding = $0.36 | Tolerance tracking |
| **Cost Outliers** | Lot 20-4353 at $218/head vs $187 avg | Cost per head analysis |
| **Suspense Accumulation** | $4,500 in GL 9999-00 this period | Suspense tracking |

### Accounting Discrepancy Checklist

| Discrepancy Type | Example | System Detection |
|------------------|---------|------------------|
| **Duplicate Invoices** | INV-13304 posted Oct and Nov | D1 check + posting registry |
| **Unclassified Credits** | -$568 MIDWEST transfer | Credit classification queue |
| **Cross-Period Postings** | Nov invoice dated Oct 28 | Period consistency check |
| **Missing Audit Trail** | Invoice edited without approval | Audit log gaps |

### IT/Controls Discrepancy Checklist

| Discrepancy Type | Example | System Detection |
|------------------|---------|------------------|
| **Non-Deterministic Results** | Same invoice, different coding | Workflow replay verification |
| **Silent Corrections** | Amount changed without log | Before/after logging |
| **Duplicate Posting Attempts** | 12 blocked this period | Idempotency key check |
| **Unauthorized Overrides** | Edit without approval context | Permission audit |

---

## 16.2 Cross-Lot Discrepancies

| Check | Description | Detection Method |
|-------|-------------|------------------|
| **Feed Cost Variance** | Same feedlot, same month, wildly different $/head | Standard deviation analysis |
| **High Processing/Medicine** | Processing or medicine > 10% of total | Line item ratio analysis |
| **Repeated Hospital Feed** | Hospital feed > 10% for 3+ periods | Cross-period tracking |
| **Lot Appearance/Disappearance** | Lot on Oct statement, missing Nov | Cross-period lot tracking |

**Example Analysis:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TOP 5 LOTS BY FEED COST/HEAD (November 2025)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Lot        │ Feedlot   │ $/Head  │ vs Avg  │ Status                       │
├─────────────┼───────────┼─────────┼─────────┼──────────────────────────────┤
│  20-4353    │ Bovina    │ $218.59 │ +16.6%  │ 🔴 Outlier - Hospital Feed   │
│  M-2847     │ Mesquite  │ $224.87 │ +15.2%  │ 🔴 Outlier - Processing      │
│  20-4260    │ Bovina    │ $203.14 │ +8.4%   │ ⚠️ Above Threshold           │
│  20-3883    │ Bovina    │ $187.42 │ +0.1%   │ ✅ Normal                     │
│  M-2901     │ Mesquite  │ $178.30 │ -4.8%   │ ✅ Normal                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16.3 Cross-Document Discrepancies

| Check | Description | Example |
|-------|-------------|---------|
| **Statement Line No Invoice** | Lot on statement without invoice | Bovina 20-3927: $301.36 charge, no PDF |
| **Invoice No Statement Line** | Invoice extracted but not on statement | Extra invoice page in PDF |
| **Credits Without Context** | Credit on statement without payment doc | OCTOBER FEED BILL credit |

**Statement ↔ Invoice Reconciliation:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  BOVINA STATEMENT RECONCILIATION                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  Statement Total:        $164,833.15                                        │
│  Sum of Invoices:        $165,099.79                                        │
│  Difference:             $266.64                                            │
│                                                                              │
│  Explained By:                                                              │
│  ├── Missing Invoice 13304 (lot 20-3927):    $301.36                       │
│  ├── OCR rounding variances:                  -$34.72                       │
│  └── Net:                                     $266.64 ✅                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16.4 Cross-Period Discrepancies

| Check | Description | Impact |
|-------|-------------|--------|
| **Feed Cost Trend** | $/head up/down sharply month over month | CFO alert |
| **Death Loss Spike** | Deaths 4x above prior month | Operations alert |
| **Head Count Drift** | Unexplained head count changes | Inventory concern |
| **Invoice Date Mismatch** | Nov invoice dated October | Period accuracy |

**Trend Analysis Example:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LOT 20-3883 - 3 MONTH TREND                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Metric           │ Sep 2025  │ Oct 2025  │ Nov 2025  │ Trend              │
├───────────────────┼───────────┼───────────┼───────────┼────────────────────┤
│  Head Count       │    847    │    843    │    823    │ ↓ -2.8%            │
│  Total Charges    │ $158,432  │ $162,891  │ $164,833  │ ↑ +4.0%            │
│  Feed $/Head      │  $178.42  │  $182.91  │  $187.42  │ ↑ +5.0%            │
│  Hospital Feed %  │    4.2%   │    5.1%   │    6.8%   │ ⚠️ Trending Up    │
│  Medicine $/Head  │   $12.40  │   $14.20  │   $18.90  │ ⚠️ +52% (3 mo)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16.5 Cross-System Discrepancies (BC Integration)

| Check | Description | Resolution |
|-------|-------------|------------|
| **Invoice vs Posted Amount** | Amount extracted ≠ amount posted | Audit trail review |
| **Dimension Mismatch** | Lot coded to wrong dimension | Re-code and re-post |
| **Vendor Mismatch** | Vendor in BC ≠ resolved vendor | Vendor alias update |
| **Entity Mismatch** | Invoice posted to wrong BC company | Entity routing fix |

---

## 16.6 Cross-Lot Insights Panel (Read-Only)

**Purpose:** High-leverage insights for advanced users (CFO, Operations)

| Insight | Query | Stakeholder |
|---------|-------|-------------|
| **Top 5 lots by feed cost per head** | Highest $/head this period | CFO |
| **Lots with hospital feed > 10%** | Hospital feed ratio analysis | Operations |
| **Lots with repeated WARNs (3+ months)** | Problem lot identification | Operations |
| **Lots with death loss spikes** | Deaths > 2x average | COO |
| **Lots approaching close-out** | Head count < 50 remaining | Operations |

**Widget Design:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CROSS-LOT INSIGHTS                                          [Refresh] [▼]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  🔥 Problem Lots (3+ months repeated warnings)                              │
│  ├── M-2901 (Mesquite): Death spike, Hospital feed >15%                    │
│  ├── 20-3927 (Bovina): Missing invoice, Zero head charges                  │
│  └── 20-4033 (Bovina): Hospital 12%, High medicine trend                   │
│                                                                              │
│  💰 Cost Outliers (>10% above feedlot average)                              │
│  ├── 20-4353: $218.59/head (+16.6%)                                        │
│  └── M-2847: $224.87/head (+15.2%)                                         │
│                                                                              │
│  ☠️ Death Loss Spikes                                                       │
│  └── M-2901: 8 deaths (RESPIRATORY) - 4x above monthly average             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 16.7 Discrepancy Severity Classification

| Severity | Color | Description | Action |
|----------|-------|-------------|--------|
| **BLOCK** | 🔴 Red | Cannot proceed, requires resolution | Immediate review |
| **WARN** | ⚠️ Amber | Non-blocking but needs attention | Review queue |
| **INFO** | ℹ️ Blue | Informational, no action required | Logged only |
| **SUCCESS** | ✅ Green | Check passed or action succeeded | No action |

**Escalation Rules:**
```
IF discrepancy.dollars > $10,000 → Escalate to CFO
IF discrepancy.type == "duplicate" → Escalate to Accounting
IF discrepancy.type == "death_spike" → Escalate to Operations
IF discrepancy.consecutive_months >= 3 → Add to Problem Lots
```

---

## Appendix A: Step Completion Summary

| Step | Description | Files Created/Modified | Lines of Code |
|------|-------------|------------------------|---------------|
| **Step 0** | Module Interfaces | `extraction/runner.py`, `reconciliation/engine.py`, `models/`, `storage/` | ~1,500 |
| **Step 1** | Temporal Connectivity | `temporal_client.py`, `workers/worker.py`, `workflows/ping_workflow.py` | ~200 |
| **Step 2** | AP Package Workflow | `workflows/ap_package_workflow.py`, `activities/persist.py` | ~500 |
| **Step 3** | Extraction Activities | `activities/extract.py` | ~480 |
| **Step 4** | Validation Activities | `activities/validate.py` | ~340 |
| **Step 5** | Reconciliation Activity | `activities/reconcile.py` | ~180 |
| **Step 6** | Entity Resolver | `entity_resolver/` module | ~900 |
| **Step 7** | Vendor Resolver | `vendor_resolver/` module | ~750 |
| **Step 8** | Coding Engine | `coding_engine/` module | ~700 |
| **Step 9** | Temporal Integration | `activities/integrate.py`, `workflows/invoice_workflow.py` | ~1,100 |

**Total Backend Lines of Code:** ~6,650+

---

## Appendix B: Processing Metrics

### Bovina Test Package (24 invoices)

| Metric | Value |
|--------|-------|
| Statement Extraction | ~15 seconds |
| Invoice Extraction (each) | ~8-12 seconds |
| Total Extraction Time | ~5 minutes |
| Validation Time | ~0.5 seconds per invoice |
| Reconciliation Time | ~1 second |
| GL Coding Time | ~0.1 seconds per invoice |

### Expected Production Throughput

| Package Size | Estimated Time |
|--------------|----------------|
| 5 invoices | ~2 minutes |
| 20 invoices | ~5 minutes |
| 50 invoices | ~12 minutes |

---

## Appendix C: Dashboard KPIs by Role

### CFO Dashboard KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Auto-Approval Rate | Auto-approved / Total | >85% | <80% |
| Blocked Dollars | Sum of blocked invoice amounts | <$50K | >$100K |
| Statement Reconciliation | Matched packages / Total | 100% | <95% |
| Suspense Balance | Sum of 9999-00 postings | $0 | >$5K |
| Cost per Head Variance | (Actual - Avg) / Avg | ±5% | >10% |

### Operations Dashboard KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Lot Accountability | Matched lots / Statement lots | 100% | <98% |
| Problem Lot Count | Lots with 3+ consecutive warnings | 0 | >5 |
| Death Loss Rate | Deaths / Total head | <1% | >2% |
| Hospital Feed Rate | Hospital feed / Total feed | <5% | >10% |
| Invoice Completeness | Invoices extracted / Expected | 100% | <95% |

### IT/Controls Dashboard KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Processing Success Rate | Successful / Attempted | >99% | <98% |
| Avg Processing Time | Total time / Invoices | <5s | >15s |
| Duplicate Block Rate | Blocked / Detected | 100% | <100% |
| Audit Coverage | Logged actions / Total actions | 100% | <100% |
| Uptime | Available time / Total time | 99.9% | <99.5% |

### Accounting Dashboard KPIs

| KPI | Formula | Target | Alert Threshold |
|-----|---------|--------|-----------------|
| Traceability Rate | Fully traceable / Total | >95% | <90% |
| Credit Classification | Classified / Total credits | 100% | <90% |
| Period Consistency | Same-period / Total | >98% | <95% |
| Duplicate Detection | True positives / Flagged | >90% | <80% |
| Posting Accuracy | Correct postings / Total | 100% | <99% |

---

## Appendix D: Month-End Close Checklist

### Pre-Close (Day -3 to -1)

| Check | Owner | Status |
|-------|-------|--------|
| All packages received and extracted | Operations | ☐ |
| All invoices validated (B1/B2 pass) | System | ☐ |
| Statement reconciliation complete | System | ☐ |
| Human review queue empty | Accounting | ☐ |
| Suspense balance explained | CFO | ☐ |

### Close Day

| Check | Owner | Status |
|-------|-------|--------|
| All packages ready to post | Accounting | ☐ |
| Duplicate detection reviewed | Accounting | ☐ |
| Credits classified | Accounting | ☐ |
| CFO approval obtained | CFO | ☐ |
| Batch posted to BC | IT | ☐ |

### Post-Close (Day +1)

| Check | Owner | Status |
|-------|-------|--------|
| BC posting verified | IT | ☐ |
| Audit trail exported | Accounting | ☐ |
| Period locked | IT | ☐ |
| KPI report generated | CFO | ☐ |

---

## Appendix E: UI Component Reference

### Mission Control Header

| Element | Purpose |
|---------|---------|
| Logo + Title | "AP Agent - Mission Control" branding |
| Period Selector | Dropdown to select statement period (e.g., "November 2025") |
| Live Indicator | Green pulse showing real-time connection |
| Notification Bell | Badge showing pending human review count |
| Theme Toggle | Dark/light mode switch |
| Settings Gear | System configuration access |

### Pipeline Flow Component

| Stage | Icon | Color | Click Action |
|-------|------|-------|--------------|
| Received | FileText | Blue | Show received invoices |
| Processing | Loader (animated) | Purple | Show in-progress workflows |
| Auto-Approved | Bot | Green | Show auto-approved list |
| Human Review | Hand | Amber | Open review queue |
| Ready to Post | CheckCheck | Green | Show posting batch |
| Posted | Send | Green | Show posted confirmation |

### Packages Table Columns

| Column | Width | Sortable | Filterable |
|--------|-------|----------|------------|
| Package ID | 180px | Yes | Yes (search) |
| Feedlot | 150px | Yes | Yes (dropdown) |
| Owner | 180px | Yes | Yes (dropdown) |
| Invoices | 80px | Yes | No |
| Status | 120px | No | Yes (tabs) |
| Amount | 100px | Yes | No |
| Action | 100px | No | No |

### Insights Panel Roles

| Role | Icon | Primary Metrics | Alert Types |
|------|------|-----------------|-------------|
| CFO | DollarSign | Pipeline $, Blocked $, Avg Cost | Financial risk |
| COO | Building2 | Lots, Deaths, Problems | Operations issues |
| CIO | Shield | Success %, Processing, Uptime | System health |
| Accounting | FileCheck | Traceability, Credits, Duplicates | Compliance |

---

**Document Version:** 2.0  
**Last Updated:** January 7, 2026  
**Author:** Temporal Invoice Team  
**Classification:** Internal Technical Documentation
