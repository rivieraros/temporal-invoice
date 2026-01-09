# Step 6 Completion: Deterministic Drilldowns + Focus

**Status:** ✅ COMPLETE  
**Date:** 2026-01-09 (Updated)

## Summary

Implemented deterministic navigation so every click on Mission Control lands the user exactly at the right package, invoice, and tab—eliminating guesswork and reducing clicks to reach actionable issues.

## What Was Built

### 1. Navigation Context Enhancement (`navigation.ts`)

**New Types:**
```typescript
export type SortOrder = 'impact' | 'age'

export interface DrilldownPayload {
  targetRoute: string
  focusInvoiceId?: string
  focusTab?: DetailTab
  reason?: string
  checkId?: string
  sort?: SortOrder
}
```

**New Functions:**
- `buildDrilldownUrl()` - Constructs URL with full drilldown context
- `inferTabFromContext()` - Maps reason/checkId to correct tab:
  - Suspense/GL/coding → `gl-coding`
  - Recon/variance/match → `reconciliation`
  - Document/evidence/support → `evidence`
  - Default → `validation`

**Extended URL Parameters:**
- `checkId` - Specific validation check to highlight
- `sort` - Sort order preference (impact vs age)

### 2. Pipeline Stage Click → Top Package (`PipelineFlow.tsx`)

Added `packages` prop and `findTopPackageForStage()` function:
- **Human Review stage**: Filters packages with `status='review'` or `review_count > 0`, sorts by total dollars (highest impact first)
- **Ready to Post stage**: Filters packages with `status='ready'`, sorts by total dollars
- Navigates directly to the top package with full context

### 3. Review Reason Click → Exact Issue (`HumanReviewPanel.tsx`)

**`findTopPackageForReason()`:**
1. Priority 1: Match recent_items by reason, return first match
2. Priority 2: Fall back to highest-dollar review package

**`findOldestReviewItem()`:**
- Returns oldest item in recent_items (last in sorted list)
- Used by "Review Now" button for age-based prioritization

**Click Handlers Updated:**
- Reason card click → Routes to top package with `reason` and `focusTab` inferred
- Recent item click → Routes with `checkId`, `focusInvoice`, and correct tab
- "Review Now" → Routes to oldest item with full context

### 4. Package Detail Auto-Focus (`PackageDetailPage.tsx`)

**`findFocusInvoice()` Priority Logic:**
1. Exact `focusInvoice` ID match from URL
2. Match by `reason` (invoice with matching flag text)
3. Match by `filter` (invoice with matching status)
4. If `sort=impact`, highest-dollar review invoice
5. First invoice needing review
6. First invoice overall

**Auto-Focus State:**
- `hasAutoFocused` state prevents re-triggering on every render
- Auto-selects invoice, opens detail panel, sets correct tab
- Resets when package changes

### 5. Validation Check Highlighting (`DetailPanel.tsx`)

**New Props:**
```typescript
highlightCheckId?: string
highlightReason?: string
```

**`shouldHighlightCheck()` Logic:**
- Matches by checkId (prefix or contains)
- Matches by reason text in check name/result
- Also highlights non-passing checks when reason is provided

**Visual Feedback:**
- Highlighted check: Amber background, 2px amber ring, "FOCUS" badge
- Draws immediate attention to the specific issue

### 6. Backend Model Updates

**`ReviewReasonSummary`:**
```python
check_id: Optional[str] = None
top_package_id: Optional[str] = None
top_invoice_id: Optional[str] = None
```

**`ReviewQueueItem`:**
```python
check_id: Optional[str] = None
```

**Mock Data Updated:**
- All reason summaries have check_ids: `gl_suspense`, `doc_missing`, `recon_variance`, `val_zero_head`
- All queue items have check_ids for precise highlighting

## Files Modified

| File | Changes |
|------|---------|
| `frontend/src/utils/navigation.ts` | DrilldownPayload, SortOrder, buildDrilldownUrl, inferTabFromContext |
| `frontend/src/types/api.ts` | check_id, top_package_id, top_invoice_id fields |
| `frontend/src/components/mission-control/PipelineFlow.tsx` | packages prop, findTopPackageForStage |
| `frontend/src/components/mission-control/HumanReviewPanel.tsx` | findTopPackageForReason, findOldestReviewItem, updated handlers |
| `frontend/src/pages/MissionControlPage.tsx` | Pass packages to PipelineFlow |
| `frontend/src/pages/PackageDetailPage.tsx` | findFocusInvoice, hasAutoFocused, highlight prop wiring |
| `frontend/src/components/package-detail/DetailPanel.tsx` | highlightCheckId/Reason props, shouldHighlightCheck, visual highlighting |
| `models/api_responses.py` | New fields on review models |
| `api/routes/dashboard.py` | Mock data with check_id values |

## User Flows Now Supported

### Flow 1: Pipeline Stage → Issue
```
Click "Human Review" stage (45 items)
→ Navigate to PKG-001 (highest dollar package in review)
→ Auto-select INV-001 (highest dollar review invoice)
→ Open Detail Panel with Validation tab
```

### Flow 2: Review Reason → Specific Check
```
Click "GL Account in Suspense" reason card
→ Navigate to PKG with top impacted invoice
→ Auto-select invoice with GL issue
→ Open GL Coding tab
→ Highlight the suspense coding entry
```

### Flow 3: Recent Item → Exact Issue
```
Click "Missing PO Number" item for INV-456
→ Navigate to that package
→ Auto-select INV-456
→ Open Validation tab
→ Highlight "Missing PO Number" check with FOCUS badge
```

### Flow 4: Review Now → Oldest Item
```
Click "Review Now" button
→ Navigate to oldest review item (age-prioritized)
→ Auto-focus the specific invoice and check
```

## Query Parameter Usage

| From | To | Params |
|------|----|--------|
| HumanReviewPanel "Review Now" | Package Detail | `focusInvoice&tab&reason&checkId&sort=age` |
| HumanReviewPanel recent item | Package Detail | `focusInvoice&tab&reason&checkId` |
| HumanReviewPanel by reason | Package Detail | `focusInvoice&tab&reason&checkId&sort=impact` |
| PipelineFlow "Human Review" | Package Detail | `filter=review&tab=validation&sort=impact` |
| PipelineFlow "Ready to Post" | Package Detail | `filter=ready` |
| Package Detail Back link | Mission Control | Preserves `period`, `filter`, `reason` |

## Acceptance Criteria ✓

| Criterion | Status |
|-----------|--------|
| Every click leads to right package | ✅ |
| Every click leads to right invoice | ✅ |
| Every click leads to right tab | ✅ |
| Specific check is highlighted | ✅ |
| 1 click always lands at exact issue | ✅ |

## Build Status

```
✓ 1473 modules transformed
✓ built in 4.83s
```

## Next Steps

**Step 7**: Inline editing for GL coding and approvals  
**Step 8**: Reconciliation drilldown with variance highlighting
