import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Hash,
  DollarSign,
  Calendar,
  Percent,
  Clock,
} from 'lucide-react'
import type { InvoiceSummary, InvoiceStatus, PackageDetailHeader } from '../../types'

interface QuickSummaryProps {
  header: PackageDetailHeader
  selectedInvoice?: InvoiceSummary
  onDetailClick?: () => void
}

const STATUS_CONFIG: Record<InvoiceStatus, { color: string; bgColor: string; label: string }> = {
  ready: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', label: 'Ready' },
  review: { color: 'text-amber-400', bgColor: 'bg-amber-500/10', label: 'Review' },
  blocked: { color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Blocked' },
  processing: { color: 'text-blue-400', bgColor: 'bg-blue-500/10', label: 'Processing' },
}

export function QuickSummary({ header, selectedInvoice, onDetailClick }: QuickSummaryProps) {
  return (
    <div className="h-full flex flex-col bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide">
          {selectedInvoice ? 'Invoice Summary' : 'Package Summary'}
        </h3>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {selectedInvoice ? (
          // Invoice Quick Summary
          <div className="space-y-4">
            {/* Invoice ID & Status */}
            <div className="text-center pb-4 border-b border-slate-700">
              <div className="font-mono text-xl font-bold text-white mb-2">
                {selectedInvoice.invoice_id}
              </div>
              {(() => {
                const config = STATUS_CONFIG[selectedInvoice.status]
                return (
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold ${config.color} ${config.bgColor}`}>
                    {selectedInvoice.status === 'ready' && <CheckCircle2 size={14} />}
                    {selectedInvoice.status === 'review' && <AlertTriangle size={14} />}
                    {selectedInvoice.status === 'blocked' && <XCircle size={14} />}
                    {config.label}
                  </span>
                )
              })()}
            </div>

            {/* Key Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                  <DollarSign size={12} />
                  Amount
                </div>
                <div className="text-lg font-bold text-white">
                  ${selectedInvoice.amount.toLocaleString()}
                </div>
              </div>
              <div className="bg-slate-900 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                  <Hash size={12} />
                  Lot
                </div>
                <div className="text-lg font-bold text-white font-mono">
                  {selectedInvoice.lot_number}
                </div>
              </div>
              {selectedInvoice.head_count && (
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                    <Hash size={12} />
                    Head Count
                  </div>
                  <div className="text-lg font-bold text-white">
                    {selectedInvoice.head_count}
                  </div>
                </div>
              )}
              {selectedInvoice.days_on_feed && (
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                    <Calendar size={12} />
                    Days on Feed
                  </div>
                  <div className="text-lg font-bold text-white">
                    {selectedInvoice.days_on_feed}
                  </div>
                </div>
              )}
              {selectedInvoice.cost_per_head && (
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                    <DollarSign size={12} />
                    Cost/Head
                  </div>
                  <div className="text-lg font-bold text-white">
                    ${selectedInvoice.cost_per_head.toFixed(2)}
                  </div>
                </div>
              )}
              {selectedInvoice.confidence !== undefined && (
                <div className="bg-slate-900 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 text-slate-400 text-xs mb-1">
                    <Percent size={12} />
                    Confidence
                  </div>
                  <div className={`text-lg font-bold ${
                    selectedInvoice.confidence >= 0.9 ? 'text-emerald-400' : 'text-amber-400'
                  }`}>
                    {Math.round(selectedInvoice.confidence * 100)}%
                  </div>
                </div>
              )}
            </div>

            {/* Reason (if review/blocked) */}
            {selectedInvoice.reason && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2 text-amber-400 text-sm font-medium mb-1">
                  <AlertTriangle size={14} />
                  Review Reason
                </div>
                <p className="text-sm text-slate-300">{selectedInvoice.reason}</p>
              </div>
            )}

            {/* View Details Button */}
            {onDetailClick && (
              <button
                onClick={onDetailClick}
                className="w-full py-3 rounded-lg bg-purple-500 hover:bg-purple-600 text-white font-semibold transition-colors"
              >
                View Full Details
              </button>
            )}
          </div>
        ) : (
          // Package Quick Summary
          <div className="space-y-4">
            {/* Package Totals */}
            <div className="text-center pb-4 border-b border-slate-700">
              <div className="text-2xl font-bold text-white mb-1">
                {header.feedlot_name}
              </div>
              <div className="text-sm text-slate-400">{header.owner_name}</div>
            </div>

            {/* Key Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">Statement Total</div>
                <div className="text-lg font-bold text-white">
                  ${header.statement_total.toLocaleString()}
                </div>
              </div>
              <div className="bg-slate-900 rounded-lg p-3">
                <div className="text-xs text-slate-400 mb-1">Invoice Total</div>
                <div className="text-lg font-bold text-white">
                  ${header.invoice_total.toLocaleString()}
                </div>
              </div>
            </div>

            {/* Variance */}
            {header.variance != null && header.variance !== 0 && (
              <div className={`rounded-lg p-3 ${
                Math.abs(header.variance) < 100
                  ? 'bg-emerald-500/10 border border-emerald-500/30'
                  : 'bg-amber-500/10 border border-amber-500/30'
              }`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-400">Variance</span>
                  <span className={`font-mono font-bold ${
                    Math.abs(header.variance) < 100 ? 'text-emerald-400' : 'text-amber-400'
                  }`}>
                    ${header.variance.toLocaleString()}
                  </span>
                </div>
              </div>
            )}

            {/* Status Breakdown */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                Invoice Status
              </h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-400" />
                    <span className="text-sm text-slate-300">Ready</span>
                  </div>
                  <span className="font-bold text-emerald-400">{header.ready_count}</span>
                </div>
                <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={14} className="text-amber-400" />
                    <span className="text-sm text-slate-300">Need Review</span>
                  </div>
                  <span className="font-bold text-amber-400">{header.review_count}</span>
                </div>
                <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg">
                  <div className="flex items-center gap-2">
                    <XCircle size={14} className="text-red-400" />
                    <span className="text-sm text-slate-300">Blocked</span>
                  </div>
                  <span className="font-bold text-red-400">{header.blocked_count}</span>
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Completion</span>
                <span className="text-slate-300">
                  {header.ready_count}/{header.total_invoices}
                </span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all"
                  style={{
                    width: `${(header.ready_count / header.total_invoices) * 100}%`,
                  }}
                />
              </div>
            </div>

            {/* Confidence */}
            <div className="bg-slate-900 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-400">Overall Confidence</span>
                <span className={`font-bold ${
                  header.overall_confidence >= 0.9 ? 'text-emerald-400' : 'text-amber-400'
                }`}>
                  {Math.round(header.overall_confidence * 100)}%
                </span>
              </div>
            </div>

            {/* Period */}
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Clock size={14} />
              <span>Period: {header.period}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
