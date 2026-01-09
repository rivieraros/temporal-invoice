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
 */

export type DetailTab = 'validation' | 'reconciliation' | 'evidence' | 'commentary' | 'line-items' | 'gl-coding'

export interface NavigationContext {
  period?: string
  source?: string
  filter?: 'all' | 'ready' | 'review' | 'blocked'
  focusInvoice?: string
  tab?: DetailTab
  reason?: string
  stage?: string
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
  
  const queryString = params.toString()
  return `/packages/${packageId}${queryString ? `?${queryString}` : ''}`
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
  }
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
