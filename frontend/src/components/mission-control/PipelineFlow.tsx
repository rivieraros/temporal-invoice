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
import { buildMissionControlUrl } from '../../utils'
import type { PipelineSnapshot, PipelineStageData } from '../../types'

interface PipelineFlowProps {
  pipeline: PipelineSnapshot
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

// Map stage names to filter parameters
const STAGE_TO_FILTER: Record<string, { status?: string; stage?: string }> = {
  received: { stage: 'received' },
  processing: { stage: 'processing' },
  auto_approved: { status: 'ready', stage: 'auto_approved' },
  human_review: { status: 'review' },
  ready_to_post: { status: 'ready', stage: 'ready_to_post' },
  posted: { stage: 'posted' },
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

export function PipelineFlow({ pipeline, currentPeriod, onStageClick }: PipelineFlowProps) {
  const navigate = useNavigate()

  const stages: PipelineStageData[] = [
    pipeline.received,
    pipeline.processing,
    pipeline.auto_approved,
    pipeline.human_review,
    pipeline.ready_to_post,
    pipeline.posted,
  ]

  const handleStageClick = (stage: PipelineStageData) => {
    // Call the callback if provided
    onStageClick?.(stage.stage, stage.count, stage.dollars)

    // For human_review, scroll to the human review panel
    if (stage.stage === 'human_review') {
      const element = document.getElementById('human-review-panel')
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' })
        return
      }
    }

    // Build navigation context based on stage
    const filter = STAGE_TO_FILTER[stage.stage]
    if (filter) {
      navigate(buildMissionControlUrl({
        filter: filter.status as 'ready' | 'review' | 'blocked' | undefined,
        stage: filter.stage,
        period: currentPeriod,
      }))
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
