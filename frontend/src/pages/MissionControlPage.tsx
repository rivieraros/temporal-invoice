import { useState } from 'react'
import { Loader } from 'lucide-react'
import { useMissionControl, useInsights } from '../hooks'
import {
  Header,
  PipelineFlow,
  HumanReviewPanel,
  PackagesPanel,
  TodayStatsPanel,
  InsightsPanel,
} from '../components'
import type { StakeholderRole } from '../types'

export function MissionControlPage() {
  const [period, setPeriod] = useState<string | undefined>()
  const [selectedRole, setSelectedRole] = useState<StakeholderRole>('CFO')
  
  const { data, isLoading, error } = useMissionControl(period)
  const { data: insights, isLoading: insightsLoading } = useInsights(selectedRole)

  // Handle period change
  const handlePeriodChange = (newPeriod: string) => {
    setPeriod(newPeriod)
  }

  // Handle pipeline stage click for analytics
  const handleStageClick = (stage: string, count: number, dollars: number) => {
    console.log(`Stage clicked: ${stage}, count: ${count}, dollars: $${dollars}`)
    // Could send analytics event here
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="animate-spin text-purple-500" size={40} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-red-400">
        <h2 className="text-lg font-semibold mb-2">Error Loading Dashboard</h2>
        <p>{error instanceof Error ? error.message : 'Unknown error'}</p>
        <p className="mt-2 text-sm text-slate-400">
          Make sure the API server is running on port 8000
        </p>
      </div>
    )
  }

  if (!data) return null

  // Current period for navigation context
  const currentPeriod = period || data.period

  return (
    <div className="space-y-6">
      {/* 1. Header - Period selector, live badge, notifications, theme/settings */}
      <Header
        period={data.period}
        lastSync={data.last_sync}
        onPeriodChange={handlePeriodChange}
      />

      {/* 2. Pipeline Flow - Stage cards with click handlers */}
      <PipelineFlow
        pipeline={data.pipeline}
        packages={data.packages}
        currentPeriod={currentPeriod}
        onStageClick={handleStageClick}
      />

      {/* 3. Human Review Panel - By Reason + Recent Items */}
      <HumanReviewPanel
        review={data.human_review}
        packages={data.packages}
        currentPeriod={currentPeriod}
      />

      {/* 4. Packages Panel - Search + filter tabs + table */}
      <PackagesPanel packages={data.packages} currentPeriod={currentPeriod} />

      {/* 5. Today Stats + Insights Panel - Role selector + alerts + collapsible details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TodayStatsPanel stats={data.today_stats} />
        <InsightsPanel
          insights={insights || null}
          isLoading={insightsLoading}
          availableRoles={data.insights_available}
          selectedRole={selectedRole}
          onRoleChange={setSelectedRole}
        />
      </div>
    </div>
  )
}

