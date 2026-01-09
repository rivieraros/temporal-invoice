import { useState } from 'react'
import {
  Zap,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle,
  AlertTriangle,
  Info,
  XCircle,
  ChevronDown,
  ChevronUp,
  User,
  BarChart3,
  Shield,
  Calculator,
} from 'lucide-react'
import type {
  TodayStats,
  StakeholderRole,
  DrilldownResponse,
  TrendDirection,
  AlertType,
} from '../../types'

interface TodayStatsPanelProps {
  stats: TodayStats
}

interface InsightsPanelProps {
  insights: DrilldownResponse | null
  isLoading: boolean
  availableRoles: StakeholderRole[]
  selectedRole: StakeholderRole
  onRoleChange: (role: StakeholderRole) => void
}

// Role icons
const ROLE_ICONS: Record<StakeholderRole, React.ElementType> = {
  CFO: Calculator,
  COO: BarChart3,
  CIO: Shield,
  Accounting: User,
}

// Alert icons
const ALERT_ICONS: Record<AlertType, React.ElementType> = {
  success: CheckCircle,
  info: Info,
  warn: AlertTriangle,
  error: XCircle,
}

const ALERT_COLORS: Record<AlertType, string> = {
  success: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
  info: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
  warn: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  error: 'bg-red-500/10 border-red-500/30 text-red-400',
}

// Trend icon helper
function TrendIcon({ direction }: { direction?: TrendDirection }) {
  if (!direction) return null
  
  const isUp = direction === 'up' || direction === 'good'
  const isGood = direction === 'good' || (direction === 'up')
  
  return isUp ? (
    <TrendingUp size={14} className={isGood ? 'text-emerald-400' : 'text-red-400'} />
  ) : (
    <TrendingDown size={14} className={isGood ? 'text-emerald-400' : 'text-red-400'} />
  )
}

export function TodayStatsPanel({ stats }: TodayStatsPanelProps) {
  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6">
      <h2 className="text-lg font-bold text-white flex items-center gap-2 mb-4">
        <Zap size={20} className="text-purple-400" />
        Today's Performance
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Invoices Processed */}
        <div className="bg-slate-900 rounded-xl p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Processed</div>
          <div className="text-2xl font-bold text-white">
            {stats.invoices_processed}
          </div>
          <div className="text-xs text-slate-500">invoices</div>
        </div>

        {/* Avg Processing Time */}
        <div className="bg-slate-900 rounded-xl p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1 flex items-center gap-1">
            <Clock size={12} />
            Avg Time
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {stats.avg_processing_time}
          </div>
          <div className="text-xs text-slate-500">per invoice</div>
        </div>

        {/* Auto-Approval Rate */}
        <div className="bg-slate-900 rounded-xl p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Auto-Approved</div>
          <div className="text-2xl font-bold text-purple-400">
            {Math.round(stats.auto_approval_rate * 100)}%
          </div>
          <div className="text-xs text-slate-500">no human touch</div>
        </div>

        {/* Dollars Processed */}
        <div className="bg-slate-900 rounded-xl p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Total Value</div>
          <div className="text-2xl font-bold text-white">
            ${(stats.dollars_processed / 1000).toFixed(0)}K
          </div>
          <div className="text-xs text-slate-500">processed today</div>
        </div>
      </div>
    </div>
  )
}

export function InsightsPanel({
  insights,
  isLoading,
  availableRoles,
  selectedRole,
  onRoleChange,
}: InsightsPanelProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())

  const toggleSection = (title: string) => {
    const next = new Set(expandedSections)
    if (next.has(title)) {
      next.delete(title)
    } else {
      next.add(title)
    }
    setExpandedSections(next)
  }

  const RoleIcon = ROLE_ICONS[selectedRole] || User

  return (
    <div className="bg-slate-800 rounded-2xl border border-slate-700 p-6">
      {/* Header with Role Selector */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <RoleIcon size={20} className="text-purple-400" />
          Role Insights
        </h2>

        {/* Role Selector */}
        <div className="flex items-center gap-2">
          {availableRoles.map((role) => {
            const Icon = ROLE_ICONS[role]
            return (
              <button
                key={role}
                onClick={() => onRoleChange(role)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                  selectedRole === role
                    ? 'bg-purple-500 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Icon size={14} />
                {role}
              </button>
            )
          })}
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-purple-500 border-t-transparent" />
        </div>
      ) : insights ? (
        <div className="space-y-4">
          {/* Metrics Row */}
          {insights.metrics.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {insights.metrics.map((metric, i) => (
                <div
                  key={i}
                  className="bg-slate-900 rounded-lg p-3 border border-slate-700"
                >
                  <div className="text-xs text-slate-400 mb-1">{metric.label}</div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-white">{metric.value}</span>
                    {metric.trend && (
                      <div className="flex items-center gap-1 text-xs">
                        <TrendIcon direction={metric.trend_direction} />
                        <span className="text-slate-400">{metric.trend}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Alerts */}
          {insights.alerts.length > 0 && (
            <div className="space-y-2">
              {insights.alerts.map((alert, i) => {
                const Icon = ALERT_ICONS[alert.alert_type]
                const colorClass = ALERT_COLORS[alert.alert_type]
                return (
                  <div
                    key={i}
                    className={`flex items-center justify-between p-3 rounded-xl border ${colorClass}`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon size={18} />
                      <span>{alert.message}</span>
                    </div>
                    {alert.is_actionable && alert.action_url && (
                      <a
                        href={alert.action_url}
                        className="text-sm underline hover:no-underline"
                      >
                        Take Action →
                      </a>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Collapsible Detail Sections */}
          {insights.details.length > 0 && (
            <div className="space-y-2">
              {insights.details.map((section, i) => {
                const isExpanded = expandedSections.has(section.title)
                return (
                  <div
                    key={i}
                    className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden"
                  >
                    <button
                      onClick={() => toggleSection(section.title)}
                      className="w-full flex items-center justify-between p-3 hover:bg-slate-800 transition-colors"
                    >
                      <span className="font-medium text-white">{section.title}</span>
                      {isExpanded ? (
                        <ChevronUp size={18} className="text-slate-400" />
                      ) : (
                        <ChevronDown size={18} className="text-slate-400" />
                      )}
                    </button>
                    {isExpanded && (
                      <div className="px-3 pb-3 space-y-2">
                        {section.items.map((item, j) => (
                          <div
                            key={j}
                            className="flex items-center justify-between py-2 border-t border-slate-700"
                          >
                            <span className="text-slate-400">{item.label}</span>
                            <span
                              className={`font-medium ${
                                item.status === 'success'
                                  ? 'text-emerald-400'
                                  : item.status === 'warn'
                                  ? 'text-amber-400'
                                  : item.status === 'error'
                                  ? 'text-red-400'
                                  : 'text-white'
                              }`}
                            >
                              {item.value}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Timestamp */}
          <div className="text-xs text-slate-500 text-right">
            As of {insights.as_of}
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-slate-400">
          Select a role to view insights
        </div>
      )}
    </div>
  )
}
