# Frontend Architecture - Mission Control Dashboard

**Project:** AP Automation Mission Control  
**Last Updated:** 2026-01-09  
**Status:** Steps 3-8 Complete

---

## 1. Overview

The Mission Control dashboard is a React-based single-page application that provides:
- Real-time visibility into the AP automation pipeline
- Human review workflow for invoices requiring attention
- Package-level drill-down with PDF viewer integration
- Navigation context preservation across views

### Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| UI Framework | React | 18.x |
| Language | TypeScript | 5.x |
| Build Tool | Vite | 5.4.21 |
| Styling | TailwindCSS | 3.x |
| Routing | React Router DOM | 6.x |
| Data Fetching | TanStack Query | 5.x |
| Icons | Lucide React | 0.x |

### Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── mission-control/          # Mission Control page components
│   │   │   ├── Header.tsx            # Period selector, stats banner
│   │   │   ├── PipelineFlow.tsx      # 6-stage pipeline visualization
│   │   │   ├── HumanReviewPanel.tsx  # Review queue with drill-down
│   │   │   ├── PackagesPanel.tsx     # Tabbed package table
│   │   │   ├── TodayStats.tsx        # Throughput metrics
│   │   │   └── InsightsPanel.tsx     # AI-generated insights
│   │   ├── package-detail/           # Package Detail page components
│   │   │   ├── PDFViewer.tsx         # PDF.js integration
│   │   │   ├── InvoiceList.tsx       # Invoice sidebar
│   │   │   ├── QuickSummary.tsx      # Package overview card
│   │   │   └── DetailPanel.tsx       # 6-tab invoice detail view
│   │   └── index.ts                  # Barrel exports
│   ├── pages/
│   │   ├── MissionControlPage.tsx    # Main dashboard
│   │   └── PackageDetailPage.tsx     # Package drill-down
│   ├── hooks/
│   │   └── useApi.ts                 # TanStack Query hooks
│   ├── types/
│   │   └── api.ts                    # TypeScript interfaces
│   ├── utils/
│   │   ├── navigation.ts             # URL context utilities
│   │   └── index.ts                  # Barrel exports
│   ├── App.tsx                       # Router configuration
│   └── main.tsx                      # Entry point
├── vite.config.ts                    # Vite + proxy config
├── tailwind.config.js                # Tailwind theme
└── package.json
```

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           BROWSER                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    MISSION CONTROL PAGE                          │    │
│  │                    /mission-control                              │    │
│  │  ┌─────────────────────────────────────────────────────────────┐│    │
│  │  │ Header: Period Selector + Stats Banner                      ││    │
│  │  └─────────────────────────────────────────────────────────────┘│    │
│  │  ┌─────────────────────────────────────────────────────────────┐│    │
│  │  │ PipelineFlow: 6 Stages (click → filter/scroll)              ││    │
│  │  └─────────────────────────────────────────────────────────────┘│    │
│  │  ┌────────────────────────┐ ┌──────────────────────────────────┐│    │
│  │  │ HumanReviewPanel       │ │ TodayStats + InsightsPanel       ││    │
│  │  │ - Review Now button    │ │ - Throughput metrics             ││    │
│  │  │ - By Reason (filter)   │ │ - AI insights                    ││    │
│  │  │ - Recent Items (focus) │ │                                  ││    │
│  │  └────────────────────────┘ └──────────────────────────────────┘│    │
│  │  ┌─────────────────────────────────────────────────────────────┐│    │
│  │  │ PackagesPanel: Tabbed Table (All/Ready/Review/Blocked)      ││    │
│  │  │ Click row → Package Detail                                  ││    │
│  │  └─────────────────────────────────────────────────────────────┘│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              │ Navigate with context                     │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PACKAGE DETAIL PAGE                           │    │
│  │  /packages/:packageId?source=mission-control&filter=review&tab=validation
│  │  ┌───────────┬─────────────────────┬─────────────────────────┐  │    │
│  │  │ PDF       │ Invoice List        │ Quick Summary /         │  │    │
│  │  │ Viewer    │ (status badges,     │ Detail Panel            │  │    │
│  │  │ (4 cols)  │  click to select)   │ (6 tabs)                │  │    │
│  │  │           │ (4 cols)            │ (4 cols)                │  │    │
│  │  └───────────┴─────────────────────┴─────────────────────────┘  │    │
│  │  ← Back to Mission Control (preserves filter/period)            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ Vite Dev Server Proxy
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                  │
│                         :8001 (or :8000)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  GET /dashboard                    → DashboardResponse                   │
│  GET /dashboard/packages/:id       → PackageDetailResponse               │
│  GET /dashboard/packages/:id/invoices/:id → InvoiceDetailResponse        │
│  GET /health                       → HealthStatus                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Navigation Context System

### Problem Statement

When drilling down from Mission Control to Package Detail and back:
1. User filters by "review" status on Mission Control
2. Clicks a package row → Package Detail
3. Clicks "Back" → Should return to Mission Control with "review" filter preserved
4. Clicking "Human Review Required" panel → Should auto-select first review invoice and open validation tab

### Solution: Query Parameter Context

All navigation context is encoded in URL query parameters, enabling:
- **Stateless navigation**: No global state management needed
- **Deep linking**: Direct links to filtered/focused views
- **Browser history**: Back/forward buttons work correctly

### Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `period` | Billing period | `2025-11` |
| `source` | Return destination | `mission-control` |
| `filter` | Status filter | `review`, `ready`, `blocked` |
| `focusInvoice` | Auto-select invoice | `INV-13304` |
| `tab` | Active detail tab | `validation`, `reconciliation` |
| `reason` | Filter by review reason | `Entity Resolution` |
| `stage` | Pipeline stage filter | `human_review` |

### Navigation Utilities (`utils/navigation.ts`)

```typescript
// Types
type DetailTab = 'validation' | 'reconciliation' | 'evidence' | 'commentary' | 'line-items' | 'gl-coding'

interface NavigationContext {
  period?: string
  source?: string
  filter?: 'all' | 'ready' | 'review' | 'blocked'
  focusInvoice?: string
  tab?: DetailTab
  reason?: string
  stage?: string
}

// Functions
buildPackageUrl(packageId: string, context?: NavigationContext): string
buildMissionControlUrl(context?: NavigationContext): string
parseNavigationContext(searchParams: URLSearchParams): NavigationContext
getReturnUrl(searchParams: URLSearchParams): string
```

### Navigation Flow Example

```
Mission Control
│
├─► Click "Review Now" in HumanReviewPanel
│   └─► /packages/PKG-2025-11-BF2-001?source=mission-control&filter=review&tab=validation
│       │
│       ├─► Auto-selects first invoice with status=review
│       ├─► Opens DetailPanel to validation tab
│       │
│       └─► Click "Back to Mission Control"
│           └─► /mission-control (filter/period preserved if set)
│
├─► Click recent item "INV-13304" in HumanReviewPanel
│   └─► /packages/PKG-2025-11-BF2-001?source=mission-control&focusInvoice=INV-13304&tab=validation
│       │
│       └─► Auto-selects INV-13304, opens DetailPanel to validation tab
│
└─► Click pipeline stage "Human Review"
    └─► Scrolls to HumanReviewPanel (same page)
```

---

## 4. Component Contracts

### MissionControlPage

**Data Source:** `GET /dashboard`

**Child Components:**
| Component | Props | Behavior |
|-----------|-------|----------|
| `Header` | `period`, `stats` | Period dropdown, stats banner |
| `PipelineFlow` | `pipeline`, `currentPeriod` | Click stage → filter/scroll |
| `HumanReviewPanel` | `review`, `packages`, `currentPeriod` | Click → drill-down with context |
| `TodayStats` | `stats` | Throughput metrics |
| `InsightsPanel` | `insights` | AI-generated cards |
| `PackagesPanel` | `packages`, `currentPeriod` | Tabbed table, row click → detail |

### PackageDetailPage

**Data Sources:**
- `GET /dashboard/packages/:packageId` → Package header + invoice list
- `GET /dashboard/packages/:packageId/invoices/:invoiceId` → Invoice detail (lazy)

**Layout:** 12-column grid (4 + 4 + 4)

**Auto-Selection Logic:**
1. If `focusInvoice` in URL → Select that invoice, open DetailPanel
2. Else if `filter=review` → Select first `status=review` invoice, open DetailPanel
3. Else → Show QuickSummary, no auto-selection

**Tab Initialization:**
- If `tab` in URL → Open DetailPanel to that tab
- If invoice has `status=review` → Default to validation tab

---

## 5. API Contract (TypeScript ↔ Pydantic)

### Alignment Checklist

| Interface | Backend Model | Status |
|-----------|--------------|--------|
| `DashboardResponse` | `DashboardResponse` | ✅ Aligned |
| `PackageSummary` | `PackageSummary` | ✅ Aligned |
| `PackageDetailResponse` | `PackageDetailResponse` | ✅ Aligned |
| `PackageDetailHeader.variance` | `Optional[Decimal]` → `number \| null` | ✅ Fixed Step 7 |
| `InvoiceSummary.cost_per_head` | `Optional[Decimal]` → `number \| null` | ✅ Fixed Step 7 |
| `ReviewQueueItem.package_id` | `str` | ✅ Added Step 8 |
| `InvoiceDetailResponse.statement_highlight_region` | `Optional[Dict]` | ✅ Added Step 7 |

### Key Type Fixes (Step 7-8)

```typescript
// frontend/src/types/api.ts

// Before (incorrect)
interface PackageDetailHeader {
  variance: number  // ❌ Backend can return null
}

// After (correct)
interface PackageDetailHeader {
  variance: number | null  // ✅ Matches Optional[Decimal]
}

// Before (missing)
interface ReviewQueueItem {
  invoice_id: string
  // no package_id
}

// After (added)
interface ReviewQueueItem {
  invoice_id: string
  package_id: string  // ✅ Added for direct navigation
}
```

---

## 6. Issues Encountered & Solutions

### Issue #1: HumanReviewPanel Wrong Package Selection (Step 8)

**Symptom:** Clicking "Review Now" navigated to `PKG-2025-11-CF4-001` (status=blocked), but that package had no invoices with `status=review`, causing the auto-selection to fail.

**Root Cause:** The package selection logic was:
```typescript
// WRONG: First match might be blocked with review_count > 0
const firstReviewPackage = packages.find(
  (pkg) => pkg.status === 'review' || pkg.review_count > 0
)
```

The first package matching `review_count > 0` was `PKG-2025-11-CF4-001` with `status=blocked`, but its invoices were also blocked, not review.

**Fix Applied:**
```typescript
// CORRECT: Prioritize status=review packages
const firstReviewPackage = 
  packages.find((pkg) => pkg.status === 'review') ||
  packages.find((pkg) => pkg.review_count > 0)
```

**File:** `frontend/src/components/mission-control/HumanReviewPanel.tsx`

---

### Issue #2: ReviewQueueItem Missing package_id (Step 8)

**Symptom:** Clicking a recent item in HumanReviewPanel couldn't navigate directly to the correct package because `ReviewQueueItem` didn't include `package_id`.

**Fix Applied:**
1. Added `package_id: str` to backend model (`models/api_responses.py`)
2. Added `package_id: string` to frontend type (`frontend/src/types/api.ts`)
3. Updated mock data with correct package IDs (`api/routes/dashboard.py`)
4. Updated `handleItemClick` to use `item.package_id` directly

---

### Issue #3: Nullable Types Mismatch (Step 7)

**Symptom:** TypeScript build errors due to backend returning `null` for optional fields.

**Fields Affected:**
- `PackageDetailHeader.variance` - Backend returns `null` when variance is unknown
- `InvoiceSummary.cost_per_head` - Backend returns `null` when no head count

**Fix Applied:**
```typescript
// Changed from
variance: number
cost_per_head?: number

// To
variance: number | null
cost_per_head?: number | null
```

**Runtime Fix in QuickSummary.tsx:**
```typescript
// Changed from
{header.variance !== 0 && ...}

// To
{header.variance != null && header.variance !== 0 && ...}
```

---

### Issue #4: Port Conflicts (Step 8)

**Symptom:** FastAPI server couldn't start on port 8000 due to orphaned processes.

**Fix Applied:**
1. Changed to port 8001 temporarily
2. Updated Vite proxy config (`vite.config.ts`) to point to 8001
3. Used `Start-Process powershell` to run servers in separate windows

**Permanent Solution:** Kill orphaned processes before starting:
```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { 
  Stop-Process -Id $_.OwningProcess -Force 
}
```

---

### Issue #5: Vite Server Killed by Terminal Commands

**Symptom:** Running `Invoke-RestMethod` in the same terminal as Vite killed the dev server.

**Cause:** VS Code terminal tool sends commands to the same terminal where Vite is running.

**Fix Applied:** Start servers in separate PowerShell windows using `Start-Process`.

---

## 7. Testing Checklist

### Acceptance Flow (Step 8)

| # | Action | Expected Result | Status |
|---|--------|-----------------|--------|
| 1 | Open `/mission-control` | Dashboard loads with all panels | ✅ |
| 2 | Click "Review Now" | Navigate to first review package with `filter=review&tab=validation` | ✅ |
| 3 | Verify auto-selection | First `status=review` invoice selected | ✅ |
| 4 | Verify DetailPanel | Validation tab active | ✅ |
| 5 | Click "Back" | Return to `/mission-control` | ✅ |
| 6 | Click recent item | Navigate with `focusInvoice` param | ✅ |
| 7 | Click package row | Navigate to package detail | ✅ |
| 8 | Click pipeline stage | Filter or scroll to panel | ✅ |

### Build Verification

```bash
cd frontend
npm run build

# Expected output:
✓ 1473 modules transformed
vite v5.4.21 building for production...
dist/index.html                  0.46 kB │ gzip:  0.30 kB
dist/assets/index-*.css         27.85 kB │ gzip:  5.77 kB
dist/assets/index-*.js         274.82 kB │ gzip: 89.07 kB
✓ built in 3.21s
```

---

## 8. Running the Application

### Prerequisites
- Node.js 18+
- Python 3.11+
- FastAPI backend running

### Start Backend (Port 8001)
```powershell
cd c:\Users\sunil\temporalinvoice
.\.venv\Scripts\activate
python -m uvicorn api.server:app --host 127.0.0.1 --port 8001
```

### Start Frontend (Port 5173)
```powershell
cd c:\Users\sunil\temporalinvoice\frontend
npm run dev
```

### Access Application
- **Mission Control:** http://localhost:5173/mission-control
- **Package Detail:** http://localhost:5173/packages/PKG-2025-11-BF2-001

### Proxy Configuration (`vite.config.ts`)
```typescript
proxy: {
  '/api': { target: 'http://127.0.0.1:8001' },
  '/dashboard': { target: 'http://127.0.0.1:8001' },
  '/health': { target: 'http://127.0.0.1:8001' },
}
```

---

## 9. Future Enhancements

| Feature | Description | Priority |
|---------|-------------|----------|
| WebSocket Updates | Real-time pipeline status updates | High |
| Keyboard Navigation | Arrow keys in invoice list, Escape to close panels | Medium |
| PDF Highlighting | Highlight statement line matching selected invoice | Medium |
| Approve/Reject API | Wire up approval buttons to backend | High |
| Bulk Actions | Multi-select invoices for batch approval | Low |
| Search | Global search across packages and invoices | Medium |
