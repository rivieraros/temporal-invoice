Prompt Pack Usage

1) Use system.txt as the system prompt for all document types.
2) Use the feedlot-specific prompt for the document you are extracting.
3) Run one prompt per document (statement or invoice). Do not mix statements and invoices.

How to customize later
- Update the context cues section if the feedlot changes.
- Keep the JSON schema unchanged so downstream code can reuse it.
- Add new fields only at the end of an object to keep compatibility.
- If a section is not present on a document, return an empty list or nulls.

Tip
- Always preserve lot numbers as strings so leading zeros are not lost.
