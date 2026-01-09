import { useNavigate } from 'react-router-dom'
import {
  FileText,
  Loader,
  Bot,
  Hand,
  CheckCheck,
  Send,
  ChevronRight,
} from 'lucide-react'
import { buildPackageUrl } from '../../utils'
import type { PipelineSnapshot, PipelineStageData, PackageSummary } from '../../types'

interface PipelineFlowProps {
  pipeline: PipelineSnapshot
  packages: PackageSummary[]           // Pass packages for deterministic navigation
  currentPeriod?: string
  onStageClick?: (stage: string, count: number, dollars: number) => void
}

const STAGE_ICONS: Record<string, React.ElementType> = {
  received: FileText,
  processing: Loader,
  auto_approved: Bot,
  human_review: Hand,
  ready_to_post: CheckCheck,
  posted: Send,
}

const COLOR_CLASSES: Record<string, string> = {
  info: 'bg-blue-500/10 border-blue-500/30 text-blue-400 hover:bg-blue-500/20',
  purple: 'bg-purple-500/10 border-purple-500/30 text-purple-400 hover:bg-purple-500/20',
  success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20',
  warn: 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20',
  error: 'bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20',
}

function PipelineStageCard({
  stage,
  isLast,
  onClick,
}: {
  stage: PipelineStageData
  isLast: boolean
  onClick: () => void
}) {
  const Icon = STAGE_ICONS[stage.stage] || FileText
  const colorClass = COLOR_CLASSES[stage.color] || COLOR_CLASSES.info

  return (
    <div className="flex items-center flex-1">
      <button
        onClick={onClick}
        className={`flex-1 p-4 rounded-xl border-2 transition-all cursor-pointer ${colorClass} ${
          stage.is_highlighted
            ? 'ring-2 ring-offset-2 ring-offset-slate-900 ring-amber-500'
            : ''
        }`}
      >
        <div className="flex items-center gap-2 mb-2">
          <Icon
            size={18}
            className={stage.is_active ? 'animate-spin' : ''}
          />
          <span className="text-sm font-medium">{stage.label}</span>
        </div>
        <div className="text-2xl font-bold">{stage.count}</div>
        <div className="text-sm opacity-75">
          ${stage.dollars.toLocaleString()}
        </div>
      </button>
      {!isLast && (
        <div className="px-2">
          <ChevronRight size={20} className="text-slate-600" />
        </div>
      )}
    </div>
  )
}

export function PipelineFlow({ pipeline, packages, currentPeriod, onStageClick }: PipelineFlowProps) {
  const navigate = useNavigate()

  const stages: PipelineStageData[] = [
    pipeline.received,
    pipeline.processing,
    pipeline.auto_approved,
    pipeline.human_review,
    pipeline.ready_to_post,
    pipeline.posted,
  ]

  /**
   * Find the top package for a given stage
   * - For human_review: find package with status='review', sorted by $ (impact)
   * - For other stages: find packages matching stage criteria
   */
  const findTopPackageForStage = (stageName: string): PackageSummary | undefined => {
    let filtered: PackageSummary[] = []
    
    switch (stageName) {
      case 'human_review':
        // Packages needing human review (status=review or review_count > 0)
        filtered = packages.filter(p => p.status === 'review' || p.review_count > 0)
        // Sort by total dollars (highest impact first)
        filtered.sort((a, b) => b.total_dollars - a.total_dollars)
        break
      
      case 'ready_to_post':
        // Packages that are ready (status=ready)
        filtered = packages.filter(p => p.status === 'ready')
        filtered.sort((a, b) => b.total_dollars - a.total_dollars)
        break
      
      case 'processing':
        // Currently processing (would need status field for this)
        // For now, just return undefined to scroll to section
        break
      
      case 'auto_approved':
        // Auto-approved packages (ready status, no review items)
        filtered = packages.filter(p => p.status === 'ready' && p.review_count === 0)
        filtered.sort((a, b) => b.total_dollars - a.total_dollars)
        break
      
      default:
        // For received/posted, we may not have direct package mapping
        break
    }
    
    return filtered[0]
  }

  const handleStageClick = (stage: PipelineStageData) => {
    // Call the callback if provided
    onStageClick?.(stage.stage, stage.count, stage.dollars)

    // Find the top package for this stage
    const topPackage = findTopPackageForStage(stage.stage)
    
    if (topPackage) {
      // Determine which tab to open based on stage
      const tabForStage = stage.stage === 'human_review' ? 'validation' : undefined
      
      navigate(buildPackageUrl(topPackage.package_id, {
        source: 'mission-control',
        filter: stage.stage === 'human_review' ? 'review' : 'ready',
        tab: tabForStage,
        period: currentPeriod,
      }))
      return
    }

    // Fallback: For human_review without a package, scroll to the human review panel
    if (stage.stage === 'human_review') {
      const element = document.getElementById('human-review-panel')
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' })
        return
      }
    }
  }

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white flex items-center gap-3">
          <FileText size={24} className="text-purple-400" />
          Invoice Pipeline
        </h2>
        <div className="text-sm text-slate-400">
          Click any stage to filter packages
        </div>
      </div>

      <div className="flex items-center">
        {stages.map((stage, i) => (
          <PipelineStageCard
            key={stage.stage}
            stage={stage}
            isLast={i === stages.length - 1}
            onClick={() => handleStageClick(stage)}
          />
        ))}
      </div>
    </div>
  )
}
