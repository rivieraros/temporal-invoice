/**
 * TracingPanel Component
 * 
 * Shows workflow execution info for a package or invoice.
 * Allows tracing from UI → Temporal workflow.
 * 
 * Features:
 * - Workflow status with link to Temporal Cloud UI
 * - Activity execution timeline
 * - Stage progression with timestamps
 * - Processing time metrics
 */

import { useState, useEffect } from 'react'
import type { TracingInfo, WorkflowExecution, ActivityExecution, StageEvent } from '../types/api'
import { fetchPackageTracing, fetchInvoiceTracing } from '../api/client'

interface TracingPanelProps {
  apPackageId: string
  invoiceNumber?: string
  className?: string
}

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  RUNNING: 'bg-blue-100 text-blue-700 border-blue-200',
  COMPLETED: 'bg-green-100 text-green-700 border-green-200',
  FAILED: 'bg-red-100 text-red-700 border-red-200',
  CANCELLED: 'bg-gray-100 text-gray-700 border-gray-200',
  TERMINATED: 'bg-orange-100 text-orange-700 border-orange-200',
  SCHEDULED: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  RETRYING: 'bg-purple-100 text-purple-700 border-purple-200',
  SUCCESS: 'bg-green-100 text-green-700 border-green-200',
  PARTIAL: 'bg-yellow-100 text-yellow-700 border-yellow-200',
}

// Activity icons
const ACTIVITY_ICONS: Record<string, string> = {
  persist_package_started: '💾',
  split_pdf: '📄',
  extract_statement: '📋',
  extract_invoice: '📝',
  persist_invoice: '💾',
  validate_invoice: '✅',
  reconcile_package: '🔄',
  persist_audit_event: '📊',
  resolve_entity: '🏢',
  resolve_vendor: '👤',
  apply_mapping_overlay: '🗂️',
  build_bc_payload: '📦',
  update_package_status: '🔄',
  update_invoice_status: '🔄',
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] || 'bg-gray-100 text-gray-600 border-gray-200'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${colors}`}>
      {status}
    </span>
  )
}

function formatDuration(ms?: number): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function formatTime(isoString?: string): string {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// Workflow Card
function WorkflowCard({ workflow }: { workflow: WorkflowExecution }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900">{workflow.workflow_type}</h4>
          <p className="mt-1 text-xs text-gray-500 font-mono">{workflow.workflow_id}</p>
        </div>
        <StatusBadge status={workflow.status} />
      </div>
      
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-gray-500">Started:</span>
          <span className="ml-1 text-gray-900">{formatTime(workflow.started_at)}</span>
        </div>
        {workflow.completed_at && (
          <div>
            <span className="text-gray-500">Completed:</span>
            <span className="ml-1 text-gray-900">{formatTime(workflow.completed_at)}</span>
          </div>
        )}
        {workflow.duration_ms && (
          <div>
            <span className="text-gray-500">Duration:</span>
            <span className="ml-1 text-gray-900">{formatDuration(workflow.duration_ms)}</span>
          </div>
        )}
      </div>
      
      {workflow.temporal_url && (
        <a
          href={workflow.temporal_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          View in Temporal Cloud
        </a>
      )}
    </div>
  )
}

// Activity Timeline
function ActivityTimeline({ activities }: { activities: ActivityExecution[] }) {
  if (activities.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic">No activity executions recorded</div>
    )
  }
  
  return (
    <div className="space-y-2">
      {activities.map((activity, idx) => (
        <div
          key={`${activity.activity_id}-${idx}`}
          className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg"
        >
          <span className="text-lg">{ACTIVITY_ICONS[activity.activity_name] || '⚡'}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900 truncate">
                {activity.activity_name}
              </span>
              <StatusBadge status={activity.status} />
              {activity.attempt > 1 && (
                <span className="text-xs text-orange-600">Attempt {activity.attempt}</span>
              )}
            </div>
            {activity.error && (
              <p className="mt-0.5 text-xs text-red-600 truncate">{activity.error}</p>
            )}
          </div>
          <div className="text-xs text-gray-500 whitespace-nowrap">
            {formatDuration(activity.duration_ms)}
          </div>
        </div>
      ))}
    </div>
  )
}

// Stage Timeline
function StageTimeline({ stages }: { stages: StageEvent[] }) {
  if (stages.length === 0) {
    return (
      <div className="text-sm text-gray-500 italic">No stage events recorded</div>
    )
  }
  
  return (
    <div className="relative">
      <div className="absolute left-4 top-2 bottom-2 w-0.5 bg-gray-200" />
      <div className="space-y-3">
        {stages.map((stage, idx) => (
          <div key={`${stage.stage}-${idx}`} className="relative flex items-start gap-3 pl-8">
            <div className={`absolute left-2.5 w-3 h-3 rounded-full border-2 
              ${stage.status === 'SUCCESS' ? 'bg-green-500 border-green-500' :
                stage.status === 'FAILED' ? 'bg-red-500 border-red-500' :
                stage.status === 'PARTIAL' ? 'bg-yellow-500 border-yellow-500' :
                'bg-gray-300 border-gray-300'}`}
            />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">{stage.stage}</span>
                <StatusBadge status={stage.status} />
              </div>
              <div className="text-xs text-gray-500">{formatTime(stage.timestamp)}</div>
              {stage.invoice_number && stage.invoice_number !== '*' && (
                <div className="text-xs text-gray-600">Invoice: {stage.invoice_number}</div>
              )}
              {stage.error && (
                <div className="mt-1 text-xs text-red-600">{stage.error}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Main Component
export default function TracingPanel({ apPackageId, invoiceNumber, className = '' }: TracingPanelProps) {
  const [tracing, setTracing] = useState<TracingInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'workflow' | 'activities' | 'stages'>('workflow')
  
  useEffect(() => {
    async function loadTracing() {
      setLoading(true)
      setError(null)
      
      try {
        const info = invoiceNumber
          ? await fetchInvoiceTracing(apPackageId, invoiceNumber)
          : await fetchPackageTracing(apPackageId)
        setTracing(info)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load tracing info')
      } finally {
        setLoading(false)
      }
    }
    
    loadTracing()
    
    // Poll every 5 seconds if workflow is running
    const interval = setInterval(() => {
      if (tracing?.workflow?.status === 'RUNNING') {
        loadTracing()
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [apPackageId, invoiceNumber])
  
  if (loading) {
    return (
      <div className={`bg-white border border-gray-200 rounded-lg p-4 ${className}`}>
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className={`bg-white border border-gray-200 rounded-lg p-4 ${className}`}>
        <div className="text-sm text-red-600">
          <span className="font-medium">Error:</span> {error}
        </div>
      </div>
    )
  }
  
  if (!tracing) {
    return null
  }
  
  return (
    <div className={`bg-white border border-gray-200 rounded-lg ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">
            🔍 Workflow Tracing
          </h3>
          {tracing.temporal_url && (
            <a
              href={tracing.temporal_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Temporal Cloud
            </a>
          )}
        </div>
        
        {/* Tabs */}
        <div className="mt-3 flex gap-4 text-xs">
          <button
            onClick={() => setActiveTab('workflow')}
            className={`pb-1 border-b-2 ${activeTab === 'workflow' 
              ? 'border-blue-500 text-blue-600 font-medium' 
              : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Workflow
          </button>
          <button
            onClick={() => setActiveTab('activities')}
            className={`pb-1 border-b-2 ${activeTab === 'activities' 
              ? 'border-blue-500 text-blue-600 font-medium' 
              : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Activities ({tracing.activities.length})
          </button>
          <button
            onClick={() => setActiveTab('stages')}
            className={`pb-1 border-b-2 ${activeTab === 'stages' 
              ? 'border-blue-500 text-blue-600 font-medium' 
              : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Stages ({tracing.stages.length})
          </button>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 max-h-96 overflow-y-auto">
        {activeTab === 'workflow' && (
          <div className="space-y-3">
            {tracing.workflow ? (
              <>
                <WorkflowCard workflow={tracing.workflow} />
                {tracing.child_workflows && tracing.child_workflows.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-xs font-medium text-gray-700 mb-2">
                      Child Workflows ({tracing.child_workflows.length})
                    </h4>
                    <div className="space-y-2">
                      {tracing.child_workflows.map((child, idx) => (
                        <WorkflowCard key={`${child.workflow_id}-${idx}`} workflow={child} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-gray-500 italic">
                No workflow execution found for this package.
                <br />
                <span className="text-xs">The workflow may not have been started yet.</span>
              </div>
            )}
          </div>
        )}
        
        {activeTab === 'activities' && (
          <ActivityTimeline activities={tracing.activities} />
        )}
        
        {activeTab === 'stages' && (
          <StageTimeline stages={tracing.stages} />
        )}
      </div>
      
      {/* Footer with IDs */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex gap-4">
          <span>Package: <code className="font-mono">{tracing.ap_package_id}</code></span>
          {tracing.invoice_number && (
            <span>Invoice: <code className="font-mono">{tracing.invoice_number}</code></span>
          )}
        </div>
      </div>
    </div>
  )
}
