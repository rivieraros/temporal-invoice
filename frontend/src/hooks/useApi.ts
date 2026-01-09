import { useQuery } from '@tanstack/react-query'
import {
  fetchMissionControl,
  fetchPackages,
  fetchPackageDetail,
  fetchInvoiceDetail,
  fetchInsights,
} from '../api'
import type { PackageStatus, StakeholderRole } from '../types'

export function useMissionControl(period?: string) {
  return useQuery({
    queryKey: ['mission-control', period],
    queryFn: () => fetchMissionControl(period),
  })
}

export function usePackages(options?: {
  period?: string
  status?: PackageStatus
  search?: string
}) {
  return useQuery({
    queryKey: ['packages', options],
    queryFn: () => fetchPackages(options),
  })
}

export function usePackageDetail(packageId: string) {
  return useQuery({
    queryKey: ['package', packageId],
    queryFn: () => fetchPackageDetail(packageId),
    enabled: !!packageId,
  })
}

export function useInvoiceDetail(packageId: string, invoiceId: string) {
  return useQuery({
    queryKey: ['invoice', packageId, invoiceId],
    queryFn: () => fetchInvoiceDetail(packageId, invoiceId),
    enabled: !!packageId && !!invoiceId,
  })
}

export function useInsights(role: StakeholderRole) {
  return useQuery({
    queryKey: ['insights', role],
    queryFn: () => fetchInsights(role),
  })
}
