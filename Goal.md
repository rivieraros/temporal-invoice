# Goal

## Objective
Build a minimal, working AP automation extraction pipeline for **Bovina** and **Mesquite** feedlots that:
- Ingests the sample PDFs.
- Extracts **complete** invoice and statement data into a canonical JSON schema.
- Validates the JSON against Pydantic models for consistency.
- Produces artifacts that can be reused by a developer or end user without changing the schema.

This is **v1** scope only: focus on accuracy and completeness of extraction, not enterprise workflows.

## What We Are Setting Up
1) **Prompt pack** for LLM-based extraction
   - Feedlot-specific prompts for:
     - Bovina Statement of Notes
     - Bovina Feed Invoice
     - Mesquite Statement of Account
     - Mesquite Invoice
   - Shared system prompt with strict JSON output rules

2) **Canonical schemas** for validation
   - Pydantic models capture all invoice/statement sections:
     - Header details, lot info, cattle inventory
     - Line items with rates/units/quantities
     - Performance metrics
     - Feeding expense summary
     - Financial summary
     - Current period transactions
     - Feeding history grid
   - Deads report schema included for future use

3) **Extraction runner** (LLM vision)
   - Convert PDF pages to images
   - Send prompts + images to the LLM
   - Validate JSON against the canonical schema
   - Save outputs to `artifacts/` folders

## References Used
- **Primary spec**: `ap_automation_temporal_spec_v1.3.md` (architecture and data model inspiration)
- **Sample PDFs**:
  - `C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Bovina.pdf`
  - `C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Mesquite.pdf`
- **Prompt pack files**:
  - `prompts/system.txt`
  - `prompts/bovina_statement_prompt.txt`
  - `prompts/bovina_invoice_prompt.txt`
  - `prompts/mesquite_statement_prompt.txt`
  - `prompts/mesquite_invoice_prompt.txt`
- **Canonical models**:
  - `models/canonical.py`
  - `models/refs.py`
- **Extraction runner**:
  - `scripts/run_extraction.py`

## Out of Scope (v1)
- Temporal workflows/activities
- Business Central posting
- GL/dimension mapping
- Review UI and human-in-the-loop flows
- Advanced retry/exception taxonomy

## Current Status
- Prompt pack: ready.
- Canonical models: ready.
- Extraction runner: ready.
- GPT-4o execution blocked by OpenAI quota (HTTP 429). Switching to Claude remains an option.

## Next Steps
1) Run extraction with a key that has active quota (GPT-4o or Claude).
2) Review the JSON outputs in `artifacts/` and spot-check against the PDFs.
3) Adjust prompts if any fields are missing or ambiguous.
