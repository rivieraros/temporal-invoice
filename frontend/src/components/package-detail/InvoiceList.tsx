import { useState, useMemo } from 'react'
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader,
  ChevronRight,
  Hash,
  DollarSign,
} from 'lucide-react'
import type { InvoiceSummary, InvoiceStatus } from '../../types'

interface InvoiceListProps {
  invoices: InvoiceSummary[]
  selectedId?: string
  onSelect: (invoice: InvoiceSummary) => void
  onDetailClick: (invoice: InvoiceSummary) => void
}

type TabFilter = 'all' | 'ready' | 'review' | 'blocked'

const STATUS_CONFIG: Record<InvoiceStatus, { icon: React.ElementType; color: string; bgColor: string; label: string }> = {
  ready: { icon: CheckCircle2, color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', label: 'Ready' },
  review: { icon: AlertTriangle, color: 'text-amber-400', bgColor: 'bg-amber-500/10', label: 'Review' },
  blocked: { icon: XCircle, color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Blocked' },
  processing: { icon: Loader, color: 'text-blue-400', bgColor: 'bg-blue-500/10', label: 'Processing' },
}

const TAB_FILTERS: { key: TabFilter; label: string; color: string }[] = [
  { key: 'all', label: 'All', color: 'text-white' },
  { key: 'ready', label: 'Ready', color: 'text-emerald-400' },
  { key: 'review', label: 'Review', color: 'text-amber-400' },
  { key: 'blocked', label: 'Blocked', color: 'text-red-400' },
]

export function InvoiceList({ invoices, selectedId, onSelect, onDetailClick }: InvoiceListProps) {
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<TabFilter>('all')

  // Filter invoices
  const filteredInvoices = useMemo(() => {
    let result = [...invoices]

    // Search filter
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (inv) =>
          inv.invoice_id.toLowerCase().includes(q) ||
          inv.lot_number.toLowerCase().includes(q) ||
          (inv.reason?.toLowerCase().includes(q) ?? false)
      )
    }

    // Tab filter
    if (activeTab !== 'all') {
      result = result.filter((inv) => inv.status === activeTab)
    }

    return result
  }, [invoices, search, activeTab])

  // Count by status
  const counts = useMemo(() => ({
    all: invoices.length,
    ready: invoices.filter((i) => i.status === 'ready').length,
    review: invoices.filter((i) => i.status === 'review').length,
    blocked: invoices.filter((i) => i.status === 'blocked').length,
  }), [invoices])

  return (
    <div className="h-full flex flex-col bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header with Search */}
      <div className="p-3 border-b border-slate-700">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search invoices..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-700 bg-slate-800/50">
        {TAB_FILTERS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
            }`}
          >
            <span className={activeTab === tab.key ? tab.color : ''}>
              {tab.label}
            </span>
            <span className="ml-1 opacity-60">({counts[tab.key]})</span>
          </button>
        ))}
      </div>

      {/* Invoice List */}
      <div className="flex-1 overflow-y-auto">
        {filteredInvoices.length === 0 ? (
          <div className="p-8 text-center text-slate-400">
            <Hash size={32} className="mx-auto mb-2 opacity-50" />
            <p>No invoices found</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {filteredInvoices.map((invoice) => {
              const config = STATUS_CONFIG[invoice.status] || STATUS_CONFIG.ready
              const Icon = config.icon
              const isSelected = invoice.invoice_id === selectedId

              return (
                <div
                  key={invoice.invoice_id}
                  onClick={() => onSelect(invoice)}
                  className={`p-3 cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-purple-500/10 border-l-2 border-l-purple-500'
                      : 'hover:bg-slate-700/30 border-l-2 border-l-transparent'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Status Icon */}
                    <div className={`p-1.5 rounded-lg ${config.bgColor} ${config.color}`}>
                      <Icon size={14} className={invoice.status === 'processing' ? 'animate-spin' : ''} />
                    </div>

                    {/* Invoice Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono font-semibold text-white text-sm truncate">
                          {invoice.invoice_id}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${config.color} ${config.bgColor}`}>
                          {config.label}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 mb-1">
                        Lot: {invoice.lot_number}
                      </div>
                      {invoice.reason && (
                        <div className="text-xs text-amber-400/80 truncate">
                          {invoice.reason}
                        </div>
                      )}
                    </div>

                    {/* Amount & Actions */}
                    <div className="text-right flex-shrink-0">
                      <div className="font-mono font-semibold text-white text-sm flex items-center gap-1">
                        <DollarSign size={12} />
                        {invoice.amount.toLocaleString()}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDetailClick(invoice)
                        }}
                        className="mt-1 text-xs text-purple-400 hover:text-purple-300 flex items-center gap-0.5"
                      >
                        Details
                        <ChevronRight size={12} />
                      </button>
                    </div>
                  </div>

                  {/* Quick Stats Row */}
                  {(invoice.head_count || invoice.days_on_feed) && (
                    <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                      {invoice.head_count && (
                        <span>{invoice.head_count} head</span>
                      )}
                      {invoice.days_on_feed && (
                        <span>{invoice.days_on_feed} DOF</span>
                      )}
                      {invoice.confidence !== undefined && (
                        <span className={invoice.confidence >= 0.9 ? 'text-emerald-400' : 'text-amber-400'}>
                          {Math.round(invoice.confidence * 100)}% conf
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Footer Summary */}
      <div className="p-3 border-t border-slate-700 bg-slate-800/50 text-xs text-slate-400">
        Showing {filteredInvoices.length} of {invoices.length} invoices
      </div>
    </div>
  )
}
