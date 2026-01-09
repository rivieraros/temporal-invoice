import {
  X,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader,
  FileText,
  DollarSign,
  Hash,
  MessageSquare,
  List,
  ShieldCheck,
  Calculator,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import type { InvoiceDetailResponse, InvoiceStatus, ValidationStatus, GLMappingStatus } from '../../types'
import type { DetailTab } from '../../utils'

interface DetailPanelProps {
  detail: InvoiceDetailResponse
  isLoading: boolean
  onClose: () => void
  onApprove?: (invoiceId: string) => void
  onReject?: (invoiceId: string) => void
  initialTab?: DetailTab
  onTabChange?: (tab: DetailTab) => void
}

const STATUS_CONFIG: Record<InvoiceStatus, { icon: React.ElementType; color: string; bgColor: string; label: string }> = {
  ready: { icon: CheckCircle2, color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', label: 'Ready' },
  review: { icon: AlertTriangle, color: 'text-amber-400', bgColor: 'bg-amber-500/10', label: 'Review' },
  blocked: { icon: XCircle, color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Blocked' },
  processing: { icon: Loader, color: 'text-blue-400', bgColor: 'bg-blue-500/10', label: 'Processing' },
}

const VALIDATION_COLORS: Record<ValidationStatus, string> = {
  pass: 'text-emerald-400',
  warn: 'text-amber-400',
  fail: 'text-red-400',
}

const GL_STATUS_COLORS: Record<GLMappingStatus, { color: string; bgColor: string }> = {
  mapped: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/10' },
  suspense: { color: 'text-amber-400', bgColor: 'bg-amber-500/10' },
  unmapped: { color: 'text-red-400', bgColor: 'bg-red-500/10' },
}

export function DetailPanel({ detail, isLoading, onClose, onApprove, onReject, initialTab, onTabChange }: DetailPanelProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>(initialTab || 'validation')

  // Update tab when initialTab changes
  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab)
    }
  }, [initialTab])

  const handleTabChange = (tab: DetailTab) => {
    setActiveTab(tab)
    onTabChange?.(tab)
  }

  if (isLoading) {
    return (
      <div className="h-full flex flex-col bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="flex-1 flex items-center justify-center">
          <Loader className="animate-spin text-purple-500" size={32} />
        </div>
      </div>
    )
  }

  const config = STATUS_CONFIG[detail.status] || STATUS_CONFIG.ready
  const StatusIcon = config.icon

  // Tab definitions
  const tabs: { key: DetailTab; label: string; icon: React.ElementType }[] = [
    { key: 'validation', label: 'Validation', icon: ShieldCheck },
    { key: 'reconciliation', label: 'Reconcile', icon: Calculator },
    { key: 'line-items', label: 'Line Items', icon: List },
    { key: 'gl-coding', label: 'GL Coding', icon: Hash },
    { key: 'evidence', label: 'Evidence', icon: FileText },
    { key: 'commentary', label: 'Commentary', icon: MessageSquare },
  ]

  return (
    <div className="h-full flex flex-col bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700 bg-slate-800">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${config.bgColor}`}>
            <StatusIcon size={18} className={config.color} />
          </div>
          <div>
            <h3 className="font-mono font-bold text-white">{detail.invoice_id}</h3>
            <p className="text-sm text-slate-400">Lot: {detail.lot_number}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
        >
          <X size={18} />
        </button>
      </div>

      {/* Content - Scrollable */}
      <div className="flex-1 overflow-y-auto flex flex-col min-h-0">
        {/* Quick Stats - Always visible */}
        <div className="p-4 pb-0">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="bg-slate-900 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Amount</div>
              <div className="text-lg font-bold text-white flex items-center justify-center gap-1">
                <DollarSign size={14} />
                {detail.amount.toLocaleString()}
              </div>
            </div>
            <div className="bg-slate-900 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Head Count</div>
              <div className="text-lg font-bold text-white">{detail.head_count}</div>
            </div>
            <div className="bg-slate-900 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-400 mb-1">Confidence</div>
              <div className={`text-lg font-bold ${
                detail.confidence >= 0.9 ? 'text-emerald-400' : 'text-amber-400'
              }`}>
                {Math.round(detail.confidence * 100)}%
              </div>
            </div>
          </div>

          {/* Reason (if review/blocked) */}
          {detail.reason && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 mb-3">
              <div className="flex items-center gap-2 text-amber-400 text-sm font-medium mb-1">
                <AlertTriangle size={14} />
                Review Reason
              </div>
              <p className="text-sm text-slate-300">{detail.reason}</p>
            </div>
          )}

          {/* Tab Navigation */}
          <div className="flex gap-1 overflow-x-auto pb-3 border-b border-slate-700">
            {tabs.map((tab) => {
              const TabIcon = tab.icon
              const isActive = activeTab === tab.key
              return (
                <button
                  key={tab.key}
                  onClick={() => handleTabChange(tab.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? 'bg-purple-500 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  <TabIcon size={12} />
                  {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4 pt-3 space-y-3">
          {/* Validation Tab */}
          {activeTab === 'validation' && (
            <div className="space-y-2">
              {detail.validation_checks.map((check, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-slate-900 rounded-lg"
                >
                  <div className="flex items-center gap-2">
                    {check.status === 'pass' && <CheckCircle2 size={14} className="text-emerald-400" />}
                    {check.status === 'warn' && <AlertTriangle size={14} className="text-amber-400" />}
                    {check.status === 'fail' && <XCircle size={14} className="text-red-400" />}
                    <span className="text-sm text-slate-300">{check.field}</span>
                  </div>
                  <span className={`text-xs font-medium ${VALIDATION_COLORS[check.status]}`}>
                    {check.status.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Reconciliation Tab */}
          {activeTab === 'reconciliation' && (
            <div className="space-y-3">
              <div className="bg-slate-900 rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-slate-400">Statement Amount</span>
                  <span className="font-mono text-white">
                    ${detail.reconciliation.statement_amount.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-slate-400">Invoice Amount</span>
                  <span className="font-mono text-white">
                    ${detail.reconciliation.invoice_amount.toLocaleString()}
                  </span>
                </div>
                <div className="flex items-center justify-between py-1 border-t border-slate-700 pt-2">
                  <span className="text-sm text-slate-400">Variance</span>
                  <span className={`font-mono font-bold ${
                    detail.reconciliation.status === 'matched'
                      ? 'text-emerald-400'
                      : detail.reconciliation.status === 'variance'
                      ? 'text-amber-400'
                      : 'text-red-400'
                  }`}>
                    ${detail.reconciliation.variance.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Line Items Tab */}
          {activeTab === 'line-items' && (
            <div className="space-y-2">
              {detail.line_items.map((item) => (
                <div key={item.line_id} className="p-3 bg-slate-900 rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-white">{item.description}</span>
                    <span className="font-mono text-white">
                      ${item.amount.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    <span>GL: {item.gl_code}</span>
                    <span>{item.category}</span>
                    {item.warning && (
                      <span className="text-amber-400 flex items-center gap-1">
                        <AlertTriangle size={10} />
                        {item.warning}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {/* Totals */}
              <div className="pt-3 border-t border-slate-700 space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Subtotal</span>
                  <span className="font-mono text-white">${detail.totals.subtotal.toLocaleString()}</span>
                </div>
                {detail.totals.adjustments !== 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Adjustments</span>
                    <span className="font-mono text-white">${detail.totals.adjustments.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm font-bold">
                  <span className="text-white">Total</span>
                  <span className="font-mono text-white">${detail.totals.total.toLocaleString()}</span>
                </div>
              </div>
            </div>
          )}

          {/* GL Coding Tab */}
          {activeTab === 'gl-coding' && (
            <div className="space-y-2">
              {detail.gl_coding.map((entry, i) => {
                const glConfig = GL_STATUS_COLORS[entry.status]
                return (
                  <div key={i} className="flex items-center justify-between p-3 bg-slate-900 rounded-lg">
                    <div>
                      <div className="text-sm text-white">{entry.description}</div>
                      <div className="text-xs text-slate-400">{entry.category}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm text-white">{entry.gl_code}</div>
                      <span className={`text-xs ${glConfig.color}`}>
                        {entry.status}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Evidence Tab (Extracted Fields) */}
          {activeTab === 'evidence' && (
            <div className="space-y-2">
              {detail.extracted_fields.map((field, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-slate-900 rounded-lg">
                  <span className="text-sm text-slate-400">{field.field_name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white">{field.value}</span>
                    <span className={`text-xs ${
                      field.confidence >= 0.9 ? 'text-emerald-400' : 'text-amber-400'
                    }`}>
                      {Math.round(field.confidence * 100)}%
                    </span>
                  </div>
                </div>
              ))}
              {/* Source PDF Link */}
              {detail.source_pdf_url && (
                <a
                  href={detail.source_pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 p-3 bg-slate-900 rounded-lg text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <ExternalLink size={16} />
                  <span>View Source PDF</span>
                </a>
              )}
            </div>
          )}

          {/* Commentary Tab */}
          {activeTab === 'commentary' && (
            <div className="space-y-3">
              {detail.agent_commentary.length > 0 ? (
                detail.agent_commentary.map((comment, i) => (
                  <div key={i} className="flex gap-3 p-3 bg-slate-900 rounded-lg">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
                      <MessageSquare size={14} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-white">{comment.title}</span>
                        <span className="text-xs text-slate-500">{comment.time_display}</span>
                      </div>
                      <p className="text-sm text-slate-400">{comment.description}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-slate-400 py-8">
                  <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
                  <p>No agent commentary available</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Actions (for review items) */}
      {detail.status === 'review' && (onApprove || onReject) && (
        <div className="p-4 border-t border-slate-700 bg-slate-800">
          <div className="flex items-center gap-3">
            {onReject && (
              <button
                onClick={() => onReject(detail.invoice_id)}
                className="flex-1 py-2.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-semibold flex items-center justify-center gap-2 transition-colors"
              >
                <ThumbsDown size={16} />
                Reject
              </button>
            )}
            {onApprove && (
              <button
                onClick={() => onApprove(detail.invoice_id)}
                className="flex-1 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-semibold flex items-center justify-center gap-2 transition-colors"
              >
                <ThumbsUp size={16} />
                Approve
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
