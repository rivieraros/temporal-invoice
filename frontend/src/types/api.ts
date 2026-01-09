// API Types matching backend Pydantic models

export type PackageStatus = 'ready' | 'review' | 'blocked'
export type InvoiceStatus = 'ready' | 'review' | 'blocked' | 'processing'
export type StakeholderRole = 'CFO' | 'COO' | 'CIO' | 'Accounting'
export type AlertType = 'success' | 'info' | 'warn' | 'error'
export type TrendDirection = 'up' | 'down' | 'neutral' | 'good' | 'bad'
export type ValidationStatus = 'pass' | 'warn' | 'fail'
export type ReconciliationStatus = 'matched' | 'variance' | 'unmatched'
export type GLMappingStatus = 'mapped' | 'suspense' | 'unmapped'

export interface PipelineStageData {
  stage: string
  count: number
  dollars: number
  label: string
  color: string
  is_active: boolean
  is_highlighted: boolean
}

export interface PipelineSnapshot {
  received: PipelineStageData
  processing: PipelineStageData
  auto_approved: PipelineStageData
  human_review: PipelineStageData
  ready_to_post: PipelineStageData
  posted: PipelineStageData
}

export interface ReviewReasonSummary {
  reason: string
  count: number
  dollars: number
  is_urgent: boolean
  check_id?: string                // Validation check ID for deterministic drilldown
  top_package_id?: string          // Package with most/highest $ items for this reason
  top_invoice_id?: string          // First invoice to focus when drilling down
}

export interface ReviewQueueItem {
  invoice_id: string
  package_id: string
  lot_number: string
  feedlot: string
  amount: number
  reason: string
  time_ago: string
  queued_at: string
  check_id?: string                // Specific check that flagged this item
}

export interface HumanReviewSummary {
  total_count: number
  total_dollars: number
  by_reason: ReviewReasonSummary[]
  recent_items: ReviewQueueItem[]
}

export interface TodayStats {
  invoices_processed: number
  avg_processing_time: string
  avg_processing_seconds: number
  auto_approval_rate: number
  dollars_processed: number
}

export interface PackageSummary {
  package_id: string
  feedlot_name: string
  feedlot_code: string
  owner_name: string
  total_invoices: number
  total_lots: number
  ready_count: number
  review_count: number
  blocked_count: number
  total_dollars: number
  status: PackageStatus
  statement_date: string
  last_activity: string
  last_activity_at: string
  primary_reason?: string           // Primary reason for review/blocked (e.g., "Entity unresolved")
  reason_check_id?: string          // Check ID for drilldown targeting
  age_in_state: string              // Compact age string (e.g., "4d", "12h", "35m")
}

export interface MissionControlResponse {
  period: string
  period_start: string
  period_end: string
  last_sync: string
  last_sync_at: string
  pipeline: PipelineSnapshot
  human_review: HumanReviewSummary
  packages: PackageSummary[]
  today_stats: TodayStats
  insights_available: StakeholderRole[]
}

export interface PackageDetailHeader {
  package_id: string
  feedlot_name: string
  feedlot_code: string
  owner_name: string
  period: string
  statement_total: number
  invoice_total: number
  variance: number | null
  total_invoices: number
  ready_count: number
  review_count: number
  blocked_count: number
  overall_confidence: number
}

export interface InvoiceSummary {
  invoice_id: string
  lot_number: string
  amount: number
  status: InvoiceStatus
  reason?: string
  feed_type?: string
  head_count?: number
  days_on_feed?: number
  cost_per_head?: number | null
  confidence?: number
}

export interface PackageDetailResponse {
  header: PackageDetailHeader
  invoices: InvoiceSummary[]
  selected_invoice_detail?: InvoiceDetailResponse
}

export interface ExtractedField {
  field_name: string
  value: string
  confidence: number
}

export interface InvoiceLineItem {
  line_id: number
  description: string
  gl_code: string
  amount: number
  quantity?: number
  unit?: string
  rate?: string
  category: string
  warning?: string
}

export interface InvoiceTotals {
  subtotal: number
  adjustments: number
  total: number
}

export interface AgentCommentary {
  timestamp: string
  time_display: string
  icon: string
  title: string
  description: string
}

export interface TimelineEvent {
  id: string
  timestamp: string
  time_display: string
  relative_time: string
  
  // Event classification
  event_type: 'upload' | 'extract' | 'validate' | 'resolve' | 'code' | 'reconcile' | 'approve' | 'reject' | 'pause' | 'resume' | 'error'
  severity: 'info' | 'success' | 'warning' | 'error'
  
  // Display content
  title: string
  description: string
  
  // Agent state
  agent_state?: 'processing' | 'waiting' | 'paused' | 'complete'
  pause_reason?: string
  
  // Related entities
  related_check?: string
  related_field?: string
  
  // Progress
  progress_current?: number
  progress_total?: number
}

export interface TimelineResponse {
  invoice_id: string
  events: TimelineEvent[]
  current_state: 'processing' | 'waiting_for_human' | 'paused' | 'complete'
  last_updated: string
  polling_interval_ms: number
}

export interface GLCodingEntry {
  description: string
  category: string
  gl_code: string
  status: GLMappingStatus
}

export interface ValidationCheck {
  field: string
  status: ValidationStatus
  extracted: string
  matched: string
  note?: string
}

export interface ReconciliationResult {
  statement_amount: number
  invoice_amount: number
  variance: number
  status: ReconciliationStatus
}

export interface InvoiceDetailResponse {
  invoice_id: string
  lot_number: string
  amount: number
  status: InvoiceStatus
  reason?: string
  feed_type?: string
  head_count: number
  days_on_feed: number
  cost_per_head: number | null
  confidence: number
  extracted_fields: ExtractedField[]
  line_items: InvoiceLineItem[]
  totals: InvoiceTotals
  agent_commentary: AgentCommentary[]
  gl_coding: GLCodingEntry[]
  validation_checks: ValidationCheck[]
  reconciliation: ReconciliationResult
  source_pdf_url?: string
  statement_highlight_region?: Record<string, unknown>
}

export interface MetricItem {
  label: string
  value: string
  raw_value?: number
  trend?: string
  trend_direction?: TrendDirection
}

export interface AlertItem {
  alert_type: AlertType
  message: string
  is_actionable: boolean
  action_url?: string
}

export interface DetailListItem {
  label: string
  value: string
  status?: 'success' | 'warn' | 'error' | 'neutral'
}

export interface DetailSection {
  title: string
  items: DetailListItem[]
}

export interface DrilldownResponse {
  role: StakeholderRole
  title: string
  icon: string
  metrics: MetricItem[]
  alerts: AlertItem[]
  details: DetailSection[]
  as_of: string
}

// =============================================================================
// CONFIGURATION TYPES
// =============================================================================

export type ConnectorStatusType = 'connected' | 'configured' | 'not_configured' | 'error'

export interface ConnectorConfig {
  id: string
  name: string
  connector_type: string
  status: ConnectorStatusType
  tenant_id?: string
  client_id?: string
  company_id?: string
  environment: string
  last_connected?: string
  last_sync?: string
  error_message?: string
}

export interface EntityMapping {
  id: string
  entity_name: string
  entity_code: string
  bc_company_id: string
  aliases: string[]
  routing_keys: string[]
  default_dimensions: Record<string, string>
  is_active: boolean
  invoice_count: number
  last_used?: string
}

export interface VendorMapping {
  id: string
  entity_id: string
  entity_name: string
  alias_normalized: string
  alias_original: string
  vendor_id: string
  vendor_number: string
  vendor_name: string
  match_count: number
  created_by: string
  created_at?: string
}

export interface ConfigurationResponse {
  connectors: ConnectorConfig[]
  entities: EntityMapping[]
  vendors: VendorMapping[]
  stats: Record<string, number>
}

export interface ConnectorTestResult {
  success: boolean
  connector_id: string
  latency_ms: number
  message: string
  details: Record<string, unknown>
}

// =============================================================================
// OBSERVABILITY / TRACING TYPES
// =============================================================================

export interface WorkflowExecution {
  workflow_id: string
  run_id: string
  workflow_type: string
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'TERMINATED'
  started_at: string
  completed_at?: string
  duration_ms?: number
  temporal_url: string
}

export interface ActivityExecution {
  activity_id: string
  activity_name: string
  status: 'SCHEDULED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'RETRYING'
  attempt: number
  started_at?: string
  completed_at?: string
  duration_ms?: number
  error?: string
  ap_package_id?: string
  invoice_number?: string
}

export interface StageEvent {
  stage: string
  status: string
  invoice_number?: string
  timestamp: string
  details?: Record<string, unknown>
  error?: string
}

export interface TracingInfo {
  ap_package_id: string
  invoice_number?: string
  workflow?: WorkflowExecution
  child_workflows?: WorkflowExecution[]
  activities: ActivityExecution[]
  stages: StageEvent[]
  temporal_url?: string
  error?: string
}

export interface PipelineMetrics {
  workflows: {
    started: number
    completed: number
    failed: number
    in_progress: number
    by_type: Record<string, { started: number; completed: number; failed: number }>
  }
  activities: {
    started: number
    completed: number
    failed: number
    retries: number
    by_name: Record<string, { started: number; completed: number; failed: number; retries: number }>
  }
  timings: {
    overall: { average_ms: number; p95_ms: number }
    by_stage: Record<string, { average_ms: number; p95_ms: number }>
  }
  queues: {
    backlog: Record<string, number>
    last_poll: Record<string, string>
  }
}
