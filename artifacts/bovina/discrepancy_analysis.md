# Bovina Extraction Discrepancy Analysis

## Summary

The reconciliation found **8 invoice amount mismatches** and **1 missing invoice** when comparing extracted invoice totals against statement charges.

---

## Discrepancy Details

| Invoice | Lot | Extracted Total | Statement Charge | Difference | Issue Type |
|---------|-----|-----------------|------------------|------------|------------|
| 13335 | 20-3918 | $5,448.03 | $5,446.03 | $2.00 | Digit error (8→6) |
| 13347 | 20-4009 | $3,492.23 | $3,452.23 | $40.00 | Digit error (9→5) |
| 13355 | 20-4033 | $15,518.02 | $15,182.02 | $336.00 | Multiple digit errors |
| 13490 | 20-4233 | $15,983.39 | $15,883.39 | $100.00 | Digit error (9→8) |
| 13491 | 20-4234 | $16,933.98 | $16,333.98 | $600.00 | Digit error (9→3) |
| 13496 | 20-4242 | $6,991.85 | $6,917.85 | $74.00 | Digit errors (91→17) |
| 13506 | 20-4260 | $6,498.04 | $6,458.04 | $40.00 | Digit error (9→5) |
| 13508 | 20-4263 | $7,995.87 | $7,427.87 | $568.00 | Multiple digit errors |

**Total Difference:** $1,760.00

---

## Missing Invoice

| Invoice | Lot | Statement Charge | Description |
|---------|-----|------------------|-------------|
| 13304 | 20-3927 | $301.36 | Feed Inv:Lot 20-3927 |

**Cause:** The PDF page for lot 20-3927 was likely not categorized as an invoice page during extraction, or the page was merged with another document.

---

## Root Cause Analysis

### Pattern Observed
The digit mismatches follow a pattern suggesting **the invoice extraction is correct but the statement extraction has OCR errors**:

1. **Invoice line items sum correctly** - e.g., Invoice 13335 line items: $5,426.59 + $8.71 + $12.73 = $5,448.03 ✓
2. **Invoice total matches line sum** - All invoices pass B2 check
3. **Statement charges are the mismatched values** - The statement extraction likely misread digits

### Evidence
Looking at the digit patterns:
- `9` often misread as `5`, `3`, `8`, or `1`
- This is a common OCR confusion pattern

---

## Which Source is Correct?

To determine whether the **invoice** or **statement** amount is correct:

| Test | Invoice | Statement |
|------|---------|-----------|
| Line items sum to total | ✅ Yes | N/A |
| Internal consistency | ✅ Yes | Not verifiable |
| Cross-reference possible | Use original PDF | Use original PDF |

**Recommendation:** The **invoice totals are more likely correct** because:
1. They are calculated from extracted line items
2. The line item sums match perfectly
3. Statement totals are single numbers susceptible to OCR errors

---

## Remediation Options

### Option 1: Re-extract with enhanced OCR settings
- Increase image resolution (3x instead of 2x zoom)
- Add explicit instruction to double-check numeric values
- Request structured output with confirmation

### Option 2: Add validation prompt
Add to the statement extraction prompt:
```
For each lot reference amount, verify by cross-checking with any visible subtotals.
If you are uncertain about a digit (especially 9 vs 5, 1 vs 7), flag it.
```

### Option 3: Trust invoice totals (recommended)
Since invoice line items sum correctly, **trust the invoice totals** and update the reconciliation to:
- Use invoice totals as the source of truth
- Flag statement discrepancies for review but don't block

### Option 4: Manual correction
Create a corrections file to override known bad values:
```json
{
  "statement_corrections": {
    "13335": {"extracted": 5446.03, "corrected": 5448.03},
    ...
  }
}
```

---

## Missing Invoice (13304) Resolution

The page for invoice 13304 (Lot 20-3927, $301.36) was not extracted. Possible causes:

1. **Page categorization failure** - The keyword "feed invoice" wasn't found
2. **Page merged with another** - Multiple invoices on same page
3. **PDF page order issue** - Page was skipped

**Resolution:** Manually check the PDF and either:
- Re-run extraction for that specific page
- Add the invoice manually to artifacts

---

## Conclusion

The reconciliation is working correctly and **detecting real extraction issues**. The primary problem is:

1. **Statement OCR errors** for 8 invoices (total $1,760 discrepancy)
2. **Missing invoice 13304** ($301.36)

Combined impact: $2,061.36 in unreconciled charges out of $164,833.15 total (**1.25% error rate**).
