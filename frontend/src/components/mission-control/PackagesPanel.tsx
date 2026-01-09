import { useState, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Search,
  Package,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Clock,
  ArrowUpDown,
} from 'lucide-react'
import { buildPackageUrl, parseNavigationContext } from '../../utils'
import type { PackageSummary, PackageStatus } from '../../types'

interface PackagesPanelProps {
  packages: PackageSummary[]
  currentPeriod?: string
}

type TabFilter = 'all' | 'ready' | 'review' | 'blocked'
type SortField = 'feedlot' | 'amount' | 'status' | 'activity'
type SortDir = 'asc' | 'desc'

const STATUS_CONFIG: Record<PackageStatus, { color: string; icon: React.ElementType }> = {
  ready: { color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30', icon: CheckCircle },
  review: { color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', icon: AlertCircle },
  blocked: { color: 'text-red-400 bg-red-500/10 border-red-500/30', icon: AlertCircle },
}

const TAB_FILTERS: { key: TabFilter; label: string }[] = [
  { key: 'all', label: 'All Packages' },
  { key: 'ready', label: 'Ready' },
  { key: 'review', label: 'Needs Review' },
  { key: 'blocked', label: 'Blocked' },
]

export function PackagesPanel({ packages, currentPeriod }: PackagesPanelProps) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  
  // Get initial tab and context from URL params
  const navContext = parseNavigationContext(searchParams)
  const initialTab = (navContext.filter as TabFilter) || 'all'
  
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<TabFilter>(initialTab)
  const [sortField, setSortField] = useState<SortField>('activity')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  // Filter and sort packages
  const filteredPackages = useMemo(() => {
    let result = [...packages]

    // Filter by search
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (pkg) =>
          pkg.feedlot_name.toLowerCase().includes(q) ||
          pkg.owner_name.toLowerCase().includes(q) ||
          pkg.package_id.toLowerCase().includes(q)
      )
    }

    // Filter by tab
    if (activeTab !== 'all') {
      result = result.filter((pkg) => pkg.status === activeTab)
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'feedlot':
          cmp = a.feedlot_name.localeCompare(b.feedlot_name)
          break
        case 'amount':
          cmp = a.total_dollars - b.total_dollars
          break
        case 'status':
          const order: Record<PackageStatus, number> = { blocked: 0, review: 1, ready: 2 }
          cmp = order[a.status] - order[b.status]
          break
        case 'activity':
          cmp = new Date(a.last_activity_at).getTime() - new Date(b.last_activity_at).getTime()
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return result
  }, [packages, search, activeTab, sortField, sortDir])

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const handlePackageClick = (pkg: PackageSummary) => {
    // Navigate with full context
    navigate(buildPackageUrl(pkg.package_id, {
      source: 'mission-control',
      filter: activeTab !== 'all' ? activeTab : undefined,
      period: currentPeriod,
      // If package needs review, default to validation tab
      tab: pkg.status === 'review' ? 'validation' : undefined,
    }))
  }

  // Count by status
  const counts = useMemo(() => {
    return {
      all: packages.length,
      ready: packages.filter((p) => p.status === 'ready').length,
      review: packages.filter((p) => p.status === 'review').length,
      blocked: packages.filter((p) => p.status === 'blocked').length,
    }
  }, [packages])

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden">
      {/* Header with Search and Filter Tabs */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-3">
            <Package size={24} className="text-purple-400" />
            Packages
          </h2>

          {/* Search */}
          <div className="relative w-72">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search feedlots, owners..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2">
          {TAB_FILTERS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-purple-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {tab.label}
              <span className="ml-2 text-xs opacity-75">({counts[tab.key]})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-slate-400 uppercase tracking-wide">
              <th className="p-4">
                <button
                  onClick={() => handleSort('feedlot')}
                  className="flex items-center gap-1 hover:text-white transition-colors"
                >
                  Feedlot
                  <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="p-4">Owner</th>
              <th className="p-4 text-center">Invoices</th>
              <th className="p-4 text-right">
                <button
                  onClick={() => handleSort('amount')}
                  className="flex items-center gap-1 ml-auto hover:text-white transition-colors"
                >
                  Amount
                  <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="p-4 text-center">
                <button
                  onClick={() => handleSort('status')}
                  className="flex items-center gap-1 mx-auto hover:text-white transition-colors"
                >
                  Status
                  <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="p-4 text-center">Progress</th>
              <th className="p-4">
                <button
                  onClick={() => handleSort('activity')}
                  className="flex items-center gap-1 hover:text-white transition-colors"
                >
                  Last Activity
                  <ArrowUpDown size={12} />
                </button>
              </th>
              <th className="p-4"></th>
            </tr>
          </thead>
          <tbody>
            {filteredPackages.map((pkg) => {
              const config = STATUS_CONFIG[pkg.status]
              const Icon = config.icon
              const progress = Math.round((pkg.ready_count / pkg.total_invoices) * 100)

              return (
                <tr
                  key={pkg.package_id}
                  onClick={() => handlePackageClick(pkg)}
                  className="border-t border-slate-700/50 hover:bg-slate-700/30 cursor-pointer transition-colors"
                >
                  <td className="p-4">
                    <div className="font-semibold text-white">{pkg.feedlot_name}</div>
                    <div className="text-xs text-slate-500">{pkg.feedlot_code}</div>
                  </td>
                  <td className="p-4 text-slate-300">{pkg.owner_name}</td>
                  <td className="p-4 text-center">
                    <span className="font-semibold text-white">{pkg.total_invoices}</span>
                    <span className="text-slate-400 text-sm ml-1">
                      ({pkg.total_lots} lots)
                    </span>
                  </td>
                  <td className="p-4 text-right font-mono font-semibold text-white">
                    ${pkg.total_dollars.toLocaleString()}
                  </td>
                  <td className="p-4">
                    <div className="flex justify-center">
                      <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${config.color}`}
                      >
                        <Icon size={12} />
                        {pkg.status.toUpperCase()}
                      </span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-20 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-400">
                        {pkg.ready_count}/{pkg.total_invoices}
                      </span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-1 text-sm text-slate-400">
                      <Clock size={14} />
                      {pkg.last_activity}
                    </div>
                  </td>
                  <td className="p-4">
                    <button className="p-2 rounded-lg hover:bg-slate-600 transition-colors">
                      <ChevronRight size={18} className="text-slate-400" />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filteredPackages.length === 0 && (
          <div className="p-12 text-center text-slate-400">
            <Package size={48} className="mx-auto mb-4 opacity-50" />
            <p>No packages found matching your criteria</p>
          </div>
        )}
      </div>
    </div>
  )
}
