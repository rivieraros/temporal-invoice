# Context Log

## 2026-01-07
- Collected sample PDFs: `C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Bovina.pdf` and `C:\Users\sunil\Downloads\Sunil Meetings\Prospects\Sugar Mountain\Mesquite.pdf`.
- Read Bovina/Mesquite PDF text locally to align prompts with actual layouts.
- Created prompt pack:
  - `prompts/system.txt`
  - `prompts/bovina_statement_prompt.txt`
  - `prompts/bovina_invoice_prompt.txt`
  - `prompts/mesquite_statement_prompt.txt`
  - `prompts/mesquite_invoice_prompt.txt`
  - `prompts/README.md`
- Created canonical Pydantic models:
  - `models/canonical.py`
  - `models/refs.py`
- Added `.env` placeholder with `OPENAI_API_KEY=`.
- Installed dependencies locally: `pymupdf`.
- Added extraction script: `scripts/run_extraction.py` (GPT-4o via OpenAI Responses API, PDF->image conversion, schema validation, output to `artifacts/`).
- Attempted GPT-4o extraction; OpenAI API returned `insufficient_quota` (HTTP 429). Extraction did not run.
- Re-attempted GPT-4o extraction after key update; still `insufficient_quota` (HTTP 429). Extraction did not run.

## Notes
- OpenAI quota still blocking GPT-4o runs.
- Claude key is available if you want to switch extraction provider.
