/**
 * Navigation Context Utilities
 * 
 * Provides a shared mechanism for passing context between pages via query params.
 * 
 * Query params:
 * - period: e.g., "2025-11"
 * - source: e.g., "mission-control", "packages"
 * - filter: e.g., "review", "ready", "blocked"
 * - focusInvoice: e.g., "INV-13304" - auto-select this invoice
 * - tab: "validation" | "reconciliation" | "evidence" | "commentary" - open this tab in detail panel
 * - reason: filter by review reason
 * - checkId: specific validation check ID to highlight
 * - sort: sort order for review items (impact|age)
 */

export type DetailTab = 'validation' | 'reconciliation' | 'evidence' | 'commentary' | 'line-items' | 'gl-coding' | 'tracing'

export type SortOrder = 'impact' | 'age'

/**
 * Shared drilldown payload shape for deterministic navigation
 * Every click from Mission Control should produce one of these
 */
export interface DrilldownPayload {
  targetRoute: string                     // e.g., "/packages/:id"
  focusInvoiceId?: string                 // Optional invoice to focus
  focusTab?: DetailTab                    // Which tab to open in detail panel
  reason?: string                         // Filter by review reason
  checkId?: string                        // Specific check to highlight
  sort?: SortOrder                        // Sort order (impact = highest $, age = oldest first)
}

export interface NavigationContext {
  period?: string
  source?: string
  filter?: 'all' | 'ready' | 'review' | 'blocked'
  focusInvoice?: string
  tab?: DetailTab
  reason?: string
  stage?: string
  checkId?: string
  sort?: SortOrder
}

/**
 * Build a URL with navigation context query params
 */
export function buildPackageUrl(
  packageId: string,
  context?: Partial<NavigationContext>
): string {
  const params = new URLSearchParams()
  
  if (context?.period) params.set('period', context.period)
  if (context?.source) params.set('source', context.source)
  if (context?.filter) params.set('filter', context.filter)
  if (context?.focusInvoice) params.set('focusInvoice', context.focusInvoice)
  if (context?.tab) params.set('tab', context.tab)
  if (context?.reason) params.set('reason', context.reason)
  if (context?.checkId) params.set('checkId', context.checkId)
  if (context?.sort) params.set('sort', context.sort)
  
  const queryString = params.toString()
  return `/packages/${packageId}${queryString ? `?${queryString}` : ''}`
}

/**
 * Build a drilldown URL from a DrilldownPayload
 * Converts the payload into a fully-qualified URL with all context
 */
export function buildDrilldownUrl(
  payload: DrilldownPayload,
  additionalContext?: Partial<NavigationContext>
): string {
  const params = new URLSearchParams()
  
  params.set('source', 'mission-control')
  
  if (payload.focusInvoiceId) params.set('focusInvoice', payload.focusInvoiceId)
  if (payload.focusTab) params.set('tab', payload.focusTab)
  if (payload.reason) params.set('reason', payload.reason)
  if (payload.checkId) params.set('checkId', payload.checkId)
  if (payload.sort) params.set('sort', payload.sort)
  
  if (additionalContext?.period) params.set('period', additionalContext.period)
  if (additionalContext?.filter) params.set('filter', additionalContext.filter)
  
  const queryString = params.toString()
  return `${payload.targetRoute}${queryString ? `?${queryString}` : ''}`
}

/**
 * Build evidence page URL for an invoice
 */
export function buildEvidenceUrl(
  packageId: string,
  invoiceId: string,
  context?: Partial<NavigationContext>
): string {
  const params = new URLSearchParams()
  
  if (context?.period) params.set('period', context.period)
  if (context?.source) params.set('source', context.source)
  if (context?.filter) params.set('filter', context.filter)
  
  const queryString = params.toString()
  return `/packages/${packageId}/invoices/${invoiceId}/evidence${queryString ? `?${queryString}` : ''}`
}

/**
 * Build a mission control URL with filter params
 */
export function buildMissionControlUrl(
  context?: Partial<NavigationContext>
): string {
  const params = new URLSearchParams()
  
  if (context?.period) params.set('period', context.period)
  if (context?.filter && context.filter !== 'all') params.set('status', context.filter)
  if (context?.stage) params.set('stage', context.stage)
  if (context?.reason) params.set('reason', context.reason)
  if (context?.focusInvoice) params.set('invoice', context.focusInvoice)
  
  const queryString = params.toString()
  return `/mission-control${queryString ? `?${queryString}` : ''}`
}

/**
 * Parse navigation context from URLSearchParams
 */
export function parseNavigationContext(searchParams: URLSearchParams): NavigationContext {
  return {
    period: searchParams.get('period') || undefined,
    source: searchParams.get('source') || undefined,
    filter: (searchParams.get('filter') || searchParams.get('status')) as NavigationContext['filter'] || undefined,
    focusInvoice: searchParams.get('focusInvoice') || searchParams.get('invoice') || undefined,
    tab: searchParams.get('tab') as DetailTab || undefined,
    reason: searchParams.get('reason') || undefined,
    stage: searchParams.get('stage') || undefined,
    checkId: searchParams.get('checkId') || undefined,
    sort: searchParams.get('sort') as SortOrder || undefined,
  }
}

/**
 * Determine which tab to auto-open based on reason/checkId
 */
export function inferTabFromContext(context: NavigationContext): DetailTab {
  const reason = context.reason?.toLowerCase() || ''
  const checkId = context.checkId?.toLowerCase() || ''
  
  // Reconciliation-related reasons
  if (
    reason.includes('variance') ||
    reason.includes('reconcil') ||
    reason.includes('mismatch') ||
    reason.includes('missing') ||
    checkId.startsWith('recon_') ||
    checkId.includes('statement')
  ) {
    return 'reconciliation'
  }
  
  // GL coding related
  if (
    reason.includes('suspense') ||
    reason.includes('gl') ||
    reason.includes('mapping') ||
    reason.includes('unmapped') ||
    checkId.startsWith('gl_') ||
    checkId.includes('coding')
  ) {
    return 'gl-coding'
  }
  
  // Evidence/document related
  if (
    reason.includes('document') ||
    reason.includes('source') ||
    reason.includes('evidence') ||
    reason.includes('attachment') ||
    checkId.startsWith('doc_')
  ) {
    return 'evidence'
  }
  
  // Default to validation tab
  return 'validation'
}

/**
 * Get the return URL for "Back" navigation
 */
export function getReturnUrl(searchParams: URLSearchParams): string {
  const source = searchParams.get('source')
  const context = parseNavigationContext(searchParams)
  
  if (source === 'mission-control' || !source) {
    return buildMissionControlUrl({
      period: context.period,
      filter: context.filter,
      reason: context.reason,
    })
  }
  
  return '/mission-control'
}
