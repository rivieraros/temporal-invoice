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
