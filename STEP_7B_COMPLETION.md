# Step 7B Completion: Reason + Age in State Columns

**Status:** ✅ COMPLETE  
**Date:** 2026-01-09

## Summary

Added "Reason" and "Age in State" columns to the Packages table to reduce clicks and make bottlenecks immediately visible. The Reason column is clickable, triggering the deterministic drilldown behavior from Step 6.

## What Was Built

### 1. Backend Model Updates

**PackageSummary** (`models/api_responses.py`):
```python
primary_reason: Optional[str] = Field(default=None, description="Primary reason for review/blocked status")
reason_check_id: Optional[str] = Field(default=None, description="Check ID for drilldown targeting")
age_in_state: str = Field(default="0m", description="Time in current status (e.g., '4d', '12m')")
```

### 2. Mock Data Updates

**MOCK_PACKAGES** (`api/services/mock_data.py`):
Each package now includes:
- `primary_reason` - Human-readable reason (e.g., "Entity unresolved", "GL in Suspense", "B2 variance $4,100")
- `reason_check_id` - Machine ID for drilldown (e.g., "entity_unresolved", "gl_suspense", "recon_variance")
- `state_entered_at` - Timestamp when package entered current state

**New Helper Function**:
```python
def _age_in_state(dt: datetime) -> str:
    """Convert datetime to compact age string (e.g., '4d', '12h', '35m')."""
```

### 3. Frontend Type Updates

**PackageSummary** (`types/api.ts`):
```typescript
primary_reason?: string      // Primary reason for review/blocked
reason_check_id?: string     // Check ID for drilldown targeting
age_in_state: string         // Compact age string (e.g., "4d", "12h")
```

### 4. PackagesPanel Updates

**New Columns**:
| Column | Description |
|--------|-------------|
| Reason | Shows `primary_reason`, clickable to trigger drilldown |
| Age | Shows `age_in_state` with timer icon for non-ready packages |

**Removed Column**:
- "Last Activity" - Replaced with more actionable "Age" column

**New Sort Option**:
- Sort by "Age" - Parses compact age strings and sorts by duration

**Reason Click Handler**:
```typescript
const handleReasonClick = (pkg: PackageSummary, e: React.MouseEvent) => {
  e.stopPropagation() // Prevent row click
  
  // Infer the correct tab from reason/checkId
  const tab = inferTabFromContext({
    reason: pkg.primary_reason,
    checkId: pkg.reason_check_id,
  })
  
  navigate(buildPackageUrl(pkg.package_id, {
    source: 'mission-control',
    period: currentPeriod,
    reason: pkg.primary_reason,
    checkId: pkg.reason_check_id,
    tab,
    filter: 'review',
    sort: 'impact',
  }))
}
```

## Files Modified

| File | Changes |
|------|---------|
| `models/api_responses.py` | Added `primary_reason`, `reason_check_id`, `age_in_state` fields |
| `api/services/mock_data.py` | Added fields to MOCK_PACKAGES, `_age_in_state()` helper, updated `build_package_summary()` |
| `frontend/src/types/api.ts` | Added new fields to PackageSummary type |
| `frontend/src/components/mission-control/PackagesPanel.tsx` | Added Reason/Age columns, clickable reason handler, age sort |

## Visual Design

### Reason Column
- Shows primary reason text in amber/warning color
- Truncates long reasons with `max-w-[180px]`
- Hover shows full reason via title tooltip
- Click triggers deterministic drilldown
- Dash (`—`) shown for packages with no issues

### Age Column
- Shows compact duration (e.g., "4d", "12h", "35m")
- Timer icon for visual clarity
- Only shown for review/blocked packages
- Dash (`—`) for ready packages

## Example Table Row

| Feedlot | Owner | Invoices | Amount | Status | Reason | Age | Progress |
|---------|-------|----------|--------|--------|--------|-----|----------|
| Canyon Feed | High Plains | 12 (9 lots) | $90,211 | BLOCKED | B2 variance $4,100 | 1d | 8/12 |

## User Flow

1. User sees "B2 variance $4,100" in Reason column
2. Clicks on the reason text
3. Navigates to package with:
   - `reason=B2 variance $4,100`
   - `checkId=recon_variance`
   - `tab=reconciliation` (inferred from checkId)
   - `filter=review`
4. Package detail auto-selects first invoice with variance
5. Opens reconciliation tab with variance highlighted

## Build Status

```
✓ 1473 modules transformed
✓ built in 12.32s
```

## Acceptance Criteria ✓

| Criterion | Status |
|-----------|--------|
| Reason column displays primary reason | ✅ |
| Age column displays time in current state | ✅ |
| Reason is clickable | ✅ |
| Click triggers drilldown to correct tab | ✅ |
| Bottlenecks are immediately visible | ✅ |

## Next Steps

**Step 8**: Reconciliation drilldown with variance highlighting
