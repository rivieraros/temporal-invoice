import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Download,
  Maximize2,
  Eye,
  Hash,
  Calendar,
  Package,
  Target,
} from 'lucide-react'
import { fetchInvoiceDetail } from '../api/client'
import type { InvoiceDetailResponse, InvoiceStatus, ValidationStatus } from '../types'
import { parseNavigationContext, buildPackageUrl } from '../utils'

const STATUS_CONFIG: Record<InvoiceStatus, { icon: React.ElementType; color: string; bgColor: string; label: string }> = {
  ready: { icon: CheckCircle2, color: 'text-emerald-400', bgColor: 'bg-emerald-500/10', label: 'Ready' },
  review: { icon: AlertTriangle, color: 'text-amber-400', bgColor: 'bg-amber-500/10', label: 'Review' },
  blocked: { icon: XCircle, color: 'text-red-400', bgColor: 'bg-red-500/10', label: 'Blocked' },
  processing: { icon: Loader, color: 'text-blue-400', bgColor: 'bg-blue-500/10', label: 'Processing' },
}

const VALIDATION_COLORS: Record<ValidationStatus, { text: string; bg: string; border: string }> = {
  pass: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  warn: { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
  fail: { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' },
}

export function EvidencePage() {
  const { packageId, invoiceId } = useParams<{ packageId: string; invoiceId: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const navContext = parseNavigationContext(searchParams)
  
  const [detail, setDetail] = useState<InvoiceDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [zoom, setZoom] = useState(100)
  const [activeSection, setActiveSection] = useState<'fields' | 'line-items' | 'validation'>('fields')

  useEffect(() => {
    if (!packageId || !invoiceId) return

    setLoading(true)
    fetchInvoiceDetail(packageId, invoiceId)
      .then(setDetail)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [packageId, invoiceId])

  const handleBack = () => {
    navigate(buildPackageUrl(packageId!, {
      ...navContext,
      focusInvoice: invoiceId,
      tab: 'evidence',
    }))
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Loader className="animate-spin text-purple-500" size={48} />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="mx-auto mb-4 text-red-400" size={48} />
          <p className="text-red-400">{error || 'Invoice not found'}</p>
          <button
            onClick={handleBack}
            className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
          >
            Go Back
          </button>
        </div>
      </div>
    )
  }

  const statusConfig = STATUS_CONFIG[detail.status]
  const StatusIcon = statusConfig.icon

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={handleBack}
              className="p-2 rounded-lg hover:bg-slate-700 transition-colors"
            >
              <ArrowLeft size={20} className="text-slate-400" />
            </button>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold text-white">Document Evidence</h1>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${statusConfig.bgColor} ${statusConfig.color}`}>
                  <StatusIcon size={12} />
                  {statusConfig.label.toUpperCase()}
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5">
                Invoice {invoiceId} • Lot {detail.lot_number}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {detail.reason && (
              <div className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <span className="text-amber-400 text-sm font-medium">{detail.reason}</span>
              </div>
            )}
            <div className="text-right">
              <div className="text-2xl font-bold text-white">${detail.amount.toLocaleString()}</div>
              <div className="text-xs text-slate-400">Invoice Amount</div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - Split View */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: PDF Viewer */}
        <div className="w-1/2 border-r border-slate-700 flex flex-col">
          {/* PDF Toolbar */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-slate-400" />
              <span className="text-sm text-slate-300">Source Document</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setZoom(Math.max(50, zoom - 25))}
                className="p-1.5 rounded hover:bg-slate-700 transition-colors"
                title="Zoom Out"
              >
                <ZoomOut size={16} className="text-slate-400" />
              </button>
              <span className="text-xs text-slate-400 w-12 text-center">{zoom}%</span>
              <button
                onClick={() => setZoom(Math.min(200, zoom + 25))}
                className="p-1.5 rounded hover:bg-slate-700 transition-colors"
                title="Zoom In"
              >
                <ZoomIn size={16} className="text-slate-400" />
              </button>
              <div className="w-px h-4 bg-slate-600 mx-1" />
              <button className="p-1.5 rounded hover:bg-slate-700 transition-colors" title="Rotate">
                <RotateCw size={16} className="text-slate-400" />
              </button>
              <button className="p-1.5 rounded hover:bg-slate-700 transition-colors" title="Fullscreen">
                <Maximize2 size={16} className="text-slate-400" />
              </button>
              {detail.source_pdf_url && (
                <a
                  href={detail.source_pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-1.5 rounded hover:bg-slate-700 transition-colors"
                  title="Download"
                >
                  <Download size={16} className="text-slate-400" />
                </a>
              )}
            </div>
          </div>

          {/* PDF Placeholder */}
          <div className="flex-1 bg-slate-950 flex items-center justify-center p-8">
            <div 
              className="bg-white rounded-lg shadow-2xl flex items-center justify-center"
              style={{ 
                width: `${Math.min(600, 400 * zoom / 100)}px`, 
                height: `${Math.min(800, 520 * zoom / 100)}px`,
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'center center',
              }}
            >
              <div className="text-center p-8">
                <FileText size={64} className="mx-auto mb-4 text-slate-300" />
                <p className="text-slate-600 font-medium mb-2">PDF Viewer</p>
                <p className="text-sm text-slate-400 mb-4">
                  Document preview with bounding box overlays
                </p>
                <div className="space-y-2 text-left text-xs text-slate-500 bg-slate-100 p-3 rounded">
                  <p>• Highlight extracted fields on hover</p>
                  <p>• Click field to see extraction confidence</p>
                  <p>• Bounding boxes for visual verification</p>
                </div>
                {detail.source_pdf_url && (
                  <a
                    href={detail.source_pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    <Eye size={16} />
                    Open PDF
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel: Extracted Data */}
        <div className="w-1/2 flex flex-col overflow-hidden">
          {/* Section Tabs */}
          <div className="flex border-b border-slate-700 bg-slate-800">
            {[
              { key: 'fields', label: 'Extracted Fields', count: detail.extracted_fields.length },
              { key: 'line-items', label: 'Line Items', count: detail.line_items.length },
              { key: 'validation', label: 'Validation', count: detail.validation_checks.filter(c => c.status !== 'pass').length },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveSection(tab.key as typeof activeSection)}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors relative ${
                  activeSection === tab.key
                    ? 'text-purple-400 bg-slate-900'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                    activeSection === tab.key ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-700 text-slate-400'
                  }`}>
                    {tab.count}
                  </span>
                )}
                {activeSection === tab.key && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-500" />
                )}
              </button>
            ))}
          </div>

          {/* Section Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {/* Extracted Fields */}
            {activeSection === 'fields' && (
              <div className="space-y-3">
                {/* Summary Card */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                      <Hash size={12} />
                      Lot Number
                    </div>
                    <div className="text-white font-semibold">{detail.lot_number}</div>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                      <Package size={12} />
                      Head Count
                    </div>
                    <div className="text-white font-semibold">{detail.head_count.toLocaleString()}</div>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                    <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
                      <Calendar size={12} />
                      Days on Feed
                    </div>
                    <div className="text-white font-semibold">{detail.days_on_feed}</div>
                  </div>
                </div>

                {/* Field List */}
                {detail.extracted_fields.map((field, i) => (
                  <div
                    key={i}
                    className="bg-slate-800 rounded-lg p-3 border border-slate-700 hover:border-purple-500/50 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-slate-400">{field.field_name}</span>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          field.confidence >= 0.95 ? 'bg-emerald-500/20 text-emerald-400' :
                          field.confidence >= 0.8 ? 'bg-amber-500/20 text-amber-400' :
                          'bg-red-500/20 text-red-400'
                        }`}>
                          {Math.round(field.confidence * 100)}%
                        </span>
                        <Target size={14} className="text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </div>
                    <div className="text-white font-medium">{field.value}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Line Items */}
            {activeSection === 'line-items' && (
              <div className="space-y-3">
                {detail.line_items.map((item, i) => (
                  <div
                    key={i}
                    className="bg-slate-800 rounded-lg p-4 border border-slate-700"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="text-white font-medium">{item.description}</div>
                        <div className="text-sm text-slate-400">{item.category}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-white font-semibold">${item.amount.toLocaleString()}</div>
                        {item.quantity && item.rate && (
                          <div className="text-xs text-slate-500">
                            {item.quantity} × {item.rate}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500 mt-2 pt-2 border-t border-slate-700">
                      <span>GL: {item.gl_code || 'Pending'}</span>
                      {item.unit && <span>Unit: {item.unit}</span>}
                    </div>
                  </div>
                ))}

                {/* Totals */}
                <div className="bg-slate-800 rounded-lg p-4 border border-purple-500/30 mt-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Subtotal</span>
                      <span className="text-white">${detail.totals.subtotal.toLocaleString()}</span>
                    </div>
                    {detail.totals.adjustments !== 0 && (
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-400">Adjustments</span>
                        <span className="text-white">${detail.totals.adjustments.toLocaleString()}</span>
                      </div>
                    )}
                    <div className="flex justify-between text-lg font-bold pt-2 border-t border-slate-700">
                      <span className="text-white">Total</span>
                      <span className="text-purple-400">${detail.totals.total.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Validation Checks */}
            {activeSection === 'validation' && (
              <div className="space-y-3">
                {detail.validation_checks.map((check, i) => {
                  const colors = VALIDATION_COLORS[check.status]
                  return (
                    <div
                      key={i}
                      className={`rounded-lg p-4 border ${colors.bg} ${colors.border}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`font-medium ${colors.text}`}>{check.field}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${colors.bg} ${colors.text} border ${colors.border}`}>
                          {check.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="text-slate-500 text-xs mb-0.5">Extracted</div>
                          <div className="text-white">{check.extracted}</div>
                        </div>
                        <div>
                          <div className="text-slate-500 text-xs mb-0.5">Expected</div>
                          <div className="text-white">{check.matched}</div>
                        </div>
                      </div>
                      {check.note && (
                        <div className={`mt-2 pt-2 border-t ${colors.border} text-sm ${colors.text}`}>
                          {check.note}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
