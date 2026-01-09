import type {
  MissionControlResponse,
  PackageSummary,
  PackageDetailResponse,
  InvoiceDetailResponse,
  DrilldownResponse,
  StakeholderRole,
  PackageStatus,
  TimelineResponse,
  ConfigurationResponse,
  ConnectorConfig,
  EntityMapping,
  VendorMapping,
  ConnectorTestResult,
} from '../types'

// API base points to the dashboard router
const API_BASE = '/dashboard'

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// Mission Control - main dashboard endpoint
export async function fetchMissionControl(period?: string): Promise<MissionControlResponse> {
  const params = period ? `?period=${encodeURIComponent(period)}` : ''
  return fetchJson<MissionControlResponse>(`${API_BASE}${params}`)
}

// Packages list
export async function fetchPackages(options?: {
  period?: string
  status?: PackageStatus
  search?: string
}): Promise<PackageSummary[]> {
  const params = new URLSearchParams()
  if (options?.period) params.append('period', options.period)
  if (options?.status) params.append('status', options.status)
  if (options?.search) params.append('search', options.search)
  const query = params.toString() ? `?${params.toString()}` : ''
  return fetchJson<PackageSummary[]>(`${API_BASE}/packages${query}`)
}

// Package detail
export async function fetchPackageDetail(packageId: string): Promise<PackageDetailResponse> {
  return fetchJson<PackageDetailResponse>(`${API_BASE}/packages/${packageId}`)
}

// Invoice detail within a package
export async function fetchInvoiceDetail(
  packageId: string,
  invoiceId: string
): Promise<InvoiceDetailResponse> {
  return fetchJson<InvoiceDetailResponse>(
    `${API_BASE}/packages/${packageId}/invoices/${invoiceId}`
  )
}

// Drilldown data
export async function fetchDrilldown(
  type: string,
  id?: string,
  period?: string
): Promise<DrilldownResponse> {
  const params = new URLSearchParams({ type })
  if (id) params.append('id', id)
  if (period) params.append('period', period)
  return fetchJson<DrilldownResponse>(`${API_BASE}/drilldown?${params.toString()}`)
}

// Role-based insights
export async function fetchInsights(role: StakeholderRole): Promise<DrilldownResponse> {
  return fetchJson<DrilldownResponse>(`${API_BASE}/insights/${role}`)
}

// Invoice timeline for agent commentary
export async function fetchInvoiceTimeline(
  packageId: string,
  invoiceId: string
): Promise<TimelineResponse> {
  return fetchJson<TimelineResponse>(
    `${API_BASE}/packages/${packageId}/invoices/${invoiceId}/timeline`
  )
}

// =============================================================================
// CONFIGURATION ENDPOINTS
// =============================================================================

// Get complete configuration
export async function fetchConfiguration(): Promise<ConfigurationResponse> {
  return fetchJson<ConfigurationResponse>(`${API_BASE}/configuration`)
}

// Get connectors only
export async function fetchConnectors(): Promise<ConnectorConfig[]> {
  return fetchJson<ConnectorConfig[]>(`${API_BASE}/configuration/connectors`)
}

// Get entity mappings only
export async function fetchEntityMappings(): Promise<EntityMapping[]> {
  return fetchJson<EntityMapping[]>(`${API_BASE}/configuration/entities`)
}

// Get vendor mappings (optionally filtered by entity)
export async function fetchVendorMappings(entityId?: string): Promise<VendorMapping[]> {
  const params = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : ''
  return fetchJson<VendorMapping[]>(`${API_BASE}/configuration/vendors${params}`)
}

// Test connector connectivity
export async function testConnector(connectorId: string): Promise<ConnectorTestResult> {
  const response = await fetch(`${API_BASE}/configuration/connectors/${connectorId}/test`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// =============================================================================
// TRACING / OBSERVABILITY
// =============================================================================

import type { TracingInfo, PipelineMetrics } from '../types/api'

// Get tracing info for a package
export async function fetchPackageTracing(apPackageId: string): Promise<TracingInfo> {
  return fetchJson<TracingInfo>(`${API_BASE}/tracing/package/${encodeURIComponent(apPackageId)}`)
}

// Get tracing info for a specific invoice
export async function fetchInvoiceTracing(apPackageId: string, invoiceNumber: string): Promise<TracingInfo> {
  return fetchJson<TracingInfo>(
    `${API_BASE}/tracing/invoice/${encodeURIComponent(apPackageId)}/${encodeURIComponent(invoiceNumber)}`
  )
}

// Get pipeline metrics
export async function fetchPipelineMetrics(): Promise<PipelineMetrics> {
  return fetchJson<PipelineMetrics>(`${API_BASE}/metrics`)
}

// Get timing stats for a stage
export async function fetchStageTimings(stage: string): Promise<{
  stage: string
  average_ms: number
  p95_ms: number
  sample_count: number
}> {
  return fetchJson(`${API_BASE}/metrics/timings/${encodeURIComponent(stage)}`)
}
