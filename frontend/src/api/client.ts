import type {
  MissionControlResponse,
  PackageSummary,
  PackageDetailResponse,
  InvoiceDetailResponse,
  DrilldownResponse,
  StakeholderRole,
  PackageStatus,
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
