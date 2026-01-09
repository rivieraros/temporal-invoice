import { useNavigate } from 'react-router-dom'
import { Hand, Eye, ChevronRight, AlertCircle, Clock } from 'lucide-react'
import { buildPackageUrl, buildMissionControlUrl } from '../../utils'
import type { HumanReviewSummary, ReviewReasonSummary, ReviewQueueItem } from '../../types'

interface HumanReviewPanelProps {
  review: HumanReviewSummary
  packages: Array<{ package_id: string; status: string; review_count: number }>
  currentPeriod?: string
}

export function HumanReviewPanel({ review, packages, currentPeriod }: HumanReviewPanelProps) {
  const navigate = useNavigate()

  // Find the first package with review items
  // Priority 1: packages with status 'review' (have review invoices)
  // Priority 2: packages with review_count > 0 (may be blocked but have items needing review)
  const firstReviewPackage = packages.find((pkg) => pkg.status === 'review') ||
    packages.find((pkg) => pkg.review_count > 0)

  const handleReviewNow = () => {
    if (firstReviewPackage) {
      // Navigate to package with review context and validation tab open
      navigate(buildPackageUrl(firstReviewPackage.package_id, {
        source: 'mission-control',
        filter: 'review',
        tab: 'validation',
        period: currentPeriod,
      }))
    }
  }

  const handleReasonClick = (reason: ReviewReasonSummary) => {
    // Filter packages by review reason, focus on highest-$ item
    navigate(buildMissionControlUrl({
      filter: 'review',
      reason: reason.reason,
      period: currentPeriod,
    }))
  }

  const handleItemClick = (item: ReviewQueueItem) => {
    // Navigate directly to the package containing this invoice
    // item.package_id gives us the exact package
    navigate(buildPackageUrl(item.package_id, {
      source: 'mission-control',
      focusInvoice: item.invoice_id,
      tab: 'validation',
      period: currentPeriod,
    }))
  }

  if (review.total_count === 0) {
    return null
  }

  return (
    <div
      id="human-review-panel"
      className="rounded-2xl border-2 border-amber-500 bg-gradient-to-br from-amber-500/10 to-orange-500/5 p-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-amber-500">
            <Hand size={24} className="text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Human Review Required</h2>
            <p className="text-slate-400">
              {review.total_count} invoices waiting •{' '}
              ${review.total_dollars.toLocaleString()}
            </p>
          </div>
        </div>
        <button
          onClick={handleReviewNow}
          className="px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-semibold flex items-center gap-2 transition-all"
        >
          <Eye size={18} />
          Review Now
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Two columns: By Reason + Recent Items */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Reason */}
        <div>
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            By Reason
          </h3>
          <div className="space-y-2">
            {review.by_reason.map((item, i) => (
              <button
                key={i}
                onClick={() => handleReasonClick(item)}
                className={`w-full flex items-center justify-between p-3 rounded-xl bg-slate-800 border transition-all hover:bg-slate-700 ${
                  item.is_urgent ? 'border-red-500/50' : 'border-slate-700'
                }`}
              >
                <div className="flex items-center gap-3">
                  {item.is_urgent && (
                    <AlertCircle size={16} className="text-red-400" />
                  )}
                  <span className="text-white text-left">{item.reason}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400">
                    {item.count}
                  </span>
                  <span className="font-mono text-white">
                    ${item.dollars.toLocaleString()}
                  </span>
                  <ChevronRight size={16} className="text-slate-500" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Recent Items */}
        <div>
          <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wide mb-3">
            Recent Items
          </h3>
          <div className="space-y-2">
            {review.recent_items.map((item, i) => (
              <button
                key={i}
                onClick={() => handleItemClick(item)}
                className="w-full text-left p-3 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-all"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-blue-400">
                      {item.invoice_id}
                    </span>
                    <span className="text-xs text-slate-400">{item.feedlot}</span>
                  </div>
                  <span className="font-mono font-semibold text-white">
                    ${item.amount.toLocaleString()}
                  </span>
                </div>
                <div className="text-sm text-slate-400 mb-1">{item.reason}</div>
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock size={12} />
                  {item.time_ago}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
