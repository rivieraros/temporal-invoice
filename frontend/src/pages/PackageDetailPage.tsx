import { useState, useEffect, useMemo, useCallback } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { usePackageDetail, useInvoiceDetail } from '../hooks'
import {
  PDFViewer,
  InvoiceList,
  QuickSummary,
  DetailPanel,
} from '../components'
import {
  Loader,
  ArrowLeft,
  Package,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
  Send,
  DollarSign,
} from 'lucide-react'
import { parseNavigationContext, getReturnUrl, inferTabFromContext, type DetailTab } from '../utils'
import type { InvoiceSummary, PackageStatus } from '../types'

// Derive package status from counts
function getPackageStatus(header: { ready_count: number; review_count: number; blocked_count: number }): PackageStatus {
  if (header.blocked_count > 0) return 'blocked'
  if (header.review_count > 0) return 'review'
  return 'ready'
}

/**
 * Find the best invoice to focus based on navigation context
 */
function findFocusInvoice(
  invoices: InvoiceSummary[],
  context: ReturnType<typeof parseNavigationContext>
): InvoiceSummary | undefined {
  // Priority 1: Exact invoice ID match
  if (context.focusInvoice) {
    const exact = invoices.find(inv => inv.invoice_id === context.focusInvoice)
    if (exact) return exact
  }
  
  // Priority 2: Match by reason (filter to invoices with matching reason)
  if (context.reason) {
    const reasonLower = context.reason.toLowerCase()
    const reasonMatch = invoices.find(inv => 
      inv.reason?.toLowerCase().includes(reasonLower) ||
      reasonLower.includes(inv.reason?.toLowerCase() || '')
    )
    if (reasonMatch) return reasonMatch
  }
  
  // Priority 3: Match by filter status
  if (context.filter && context.filter !== 'all') {
    const statusMatch = invoices.find(inv => inv.status === context.filter)
    if (statusMatch) return statusMatch
  }
  
  // Priority 4: If sort=impact, find highest $ review invoice
  if (context.sort === 'impact') {
    const reviewInvoices = invoices.filter(inv => inv.status === 'review')
    if (reviewInvoices.length > 0) {
      return reviewInvoices.sort((a, b) => b.amount - a.amount)[0]
    }
  }
  
  // Priority 5: If sort=age or default for review, find first review invoice
  if (context.filter === 'review' || context.sort === 'age') {
    return invoices.find(inv => inv.status === 'review')
  }
  
  return undefined
}

export function PackageDetailPage() {
  const { packageId } = useParams<{ packageId: string }>()
  const [searchParams] = useSearchParams()

  // Parse navigation context from query params
  const navContext = parseNavigationContext(searchParams)
  const returnTo = getReturnUrl(searchParams)
  
  // Determine which tab to open based on context
  const initialTab = useMemo<DetailTab>(() => {
    // Explicit tab in URL takes precedence
    if (navContext.tab) return navContext.tab
    // Otherwise infer from reason/checkId
    return inferTabFromContext(navContext)
  }, [navContext])

  // State
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceSummary | null>(null)
  const [showDetailPanel, setShowDetailPanel] = useState(false)
  const [detailInvoiceId, setDetailInvoiceId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<DetailTab>(initialTab)
  const [hasAutoFocused, setHasAutoFocused] = useState(false)

  // Data fetching
  const { data, isLoading, error } = usePackageDetail(packageId!)
  const {
    data: invoiceDetail,
    isLoading: detailLoading,
  } = useInvoiceDetail(packageId!, detailInvoiceId || '')

  // Derive package status
  const packageStatus = useMemo(() => {
    if (!data) return 'ready'
    return getPackageStatus(data.header)
  }, [data])

  // Auto-select invoice based on navigation context (runs once when data loads)
  useEffect(() => {
    if (!data || hasAutoFocused) return
    
    const focusInvoice = findFocusInvoice(data.invoices, navContext)
    
    if (focusInvoice) {
      setSelectedInvoice(focusInvoice)
      setDetailInvoiceId(focusInvoice.invoice_id)
      setShowDetailPanel(true)
      setActiveTab(initialTab)
      setHasAutoFocused(true)
    }
  }, [data, navContext, initialTab, hasAutoFocused])

  // Handlers
  const handleInvoiceSelect = useCallback((invoice: InvoiceSummary) => {
    setSelectedInvoice(invoice)
    // Close detail panel when selecting a different invoice
    if (showDetailPanel && detailInvoiceId !== invoice.invoice_id) {
      setShowDetailPanel(false)
      setDetailInvoiceId(null)
    }
  }, [showDetailPanel, detailInvoiceId])

  const handleDetailClick = useCallback((invoice: InvoiceSummary) => {
    setSelectedInvoice(invoice)
    setDetailInvoiceId(invoice.invoice_id)
    setShowDetailPanel(true)
  }, [])

  const handleCloseDetail = () => {
    setShowDetailPanel(false)
    setDetailInvoiceId(null)
  }

  const handleNeedReviewClick = () => {
    if (!data) return
    const reviewInvoice = data.invoices.find((inv) => inv.status === 'review')
    if (reviewInvoice) {
      handleDetailClick(reviewInvoice)
    }
  }

  const handleApprove = (invoiceId: string) => {
    console.log('Approve invoice:', invoiceId)
    // TODO: API call to approve
  }

  const handleReject = (invoiceId: string) => {
    console.log('Reject invoice:', invoiceId)
    // TODO: API call to reject
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-8rem)]">
        <Loader className="animate-spin text-purple-500" size={40} />
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-red-400">
        <h2 className="text-lg font-semibold mb-2">Error Loading Package</h2>
        <p>{error instanceof Error ? error.message : 'Unknown error'}</p>
        <Link
          to={returnTo}
          className="inline-flex items-center gap-2 mt-4 text-slate-400 hover:text-white"
        >
          <ArrowLeft size={16} />
          Back to Mission Control
        </Link>
      </div>
    )
  }

  if (!data) return null

  const statusStyles: Record<PackageStatus, { bg: string; text: string; icon: React.ElementType }> = {
    ready: { bg: 'bg-emerald-500', text: 'text-white', icon: CheckCircle2 },
    review: { bg: 'bg-amber-500', text: 'text-white', icon: AlertTriangle },
    blocked: { bg: 'bg-red-500', text: 'text-white', icon: XCircle },
  }

  const statusConfig = statusStyles[packageStatus]
  const StatusIcon = statusConfig.icon

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col">
      {/* Header Bar */}
      <div className="flex-shrink-0 mb-4">
        {/* Back Link */}
        <Link
          to={returnTo}
          className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-3"
        >
          <ArrowLeft size={16} />
          Back to Mission Control
        </Link>

        {/* Package Header */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
          <div className="flex items-center justify-between">
            {/* Left: Package Info */}
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                <Package size={24} className="text-purple-400" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">{data.header.feedlot_name}</h1>
                <div className="flex items-center gap-3 text-sm text-slate-400">
                  <span>{data.header.owner_name}</span>
                  <span>•</span>
                  <span>{data.header.period}</span>
                </div>
              </div>
            </div>

            {/* Center: Stats */}
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{data.header.total_invoices}</div>
                <div className="text-xs text-slate-400">Invoices</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-white flex items-center gap-1 justify-center">
                  <DollarSign size={18} />
                  {data.header.invoice_total.toLocaleString()}
                </div>
                <div className="text-xs text-slate-400">Total</div>
              </div>
              <div className="flex items-center gap-2 px-3 py-1 bg-slate-900 rounded-lg">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 size={14} className="text-emerald-400" />
                  <span className="text-emerald-400 font-semibold">{data.header.ready_count}</span>
                </div>
                <div className="w-px h-4 bg-slate-700" />
                <div className="flex items-center gap-1.5">
                  <AlertTriangle size={14} className="text-amber-400" />
                  <span className="text-amber-400 font-semibold">{data.header.review_count}</span>
                </div>
                <div className="w-px h-4 bg-slate-700" />
                <div className="flex items-center gap-1.5">
                  <XCircle size={14} className="text-red-400" />
                  <span className="text-red-400 font-semibold">{data.header.blocked_count}</span>
                </div>
              </div>
            </div>

            {/* Right: Status & Actions */}
            <div className="flex items-center gap-3">
              <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-full font-semibold ${statusConfig.bg} ${statusConfig.text}`}>
                <StatusIcon size={16} />
                {packageStatus.toUpperCase()}
              </span>

              {data.header.review_count > 0 && (
                <button
                  onClick={handleNeedReviewClick}
                  className="px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 font-medium flex items-center gap-2 transition-colors"
                >
                  <Eye size={16} />
                  Need Review ({data.header.review_count})
                </button>
              )}

              {packageStatus === 'ready' && (
                <button className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-semibold flex items-center gap-2 transition-colors">
                  <Send size={16} />
                  Post All
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Three-Panel Layout */}
      <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
        {/* Left Panel: PDF Viewer */}
        <div className="col-span-4 min-h-0">
          <PDFViewer
            packageId={packageId!}
            selectedInvoiceId={selectedInvoice?.invoice_id}
          />
        </div>

        {/* Middle Panel: Invoice List */}
        <div className="col-span-4 min-h-0">
          <InvoiceList
            invoices={data.invoices}
            selectedId={selectedInvoice?.invoice_id}
            onSelect={handleInvoiceSelect}
            onDetailClick={handleDetailClick}
          />
        </div>

        {/* Right Panel: Quick Summary or Detail Panel */}
        <div className="col-span-4 min-h-0">
          {showDetailPanel && invoiceDetail ? (
            <DetailPanel
              detail={invoiceDetail}
              isLoading={detailLoading}
              onClose={handleCloseDetail}
              onApprove={handleApprove}
              onReject={handleReject}
              initialTab={activeTab}
              onTabChange={setActiveTab}
              highlightCheckId={navContext.checkId}
              highlightReason={navContext.reason}
              packageId={packageId}
            />
          ) : (
            <QuickSummary
              header={data.header}
              selectedInvoice={selectedInvoice || undefined}
              onDetailClick={selectedInvoice ? () => handleDetailClick(selectedInvoice) : undefined}
            />
          )}
        </div>
      </div>
    </div>
  )
}
