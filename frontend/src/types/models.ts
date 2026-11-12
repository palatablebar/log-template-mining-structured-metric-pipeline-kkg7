export type Role = 'admin' | 'engineer' | 'viewer';
export type EventLevel = 'debug' | 'info' | 'warn' | 'error' | 'fatal';
export type TemplateStatus = 'mined' | 'tentative' | 'confirmed' | 'noise';
export type AlertStatus = 'firing' | 'acknowledged' | 'silenced' | 'resolved';
export type SlotType = 'num' | 'ip' | 'uuid' | 'path' | 'hex' | 'ts' | 'str' | 'unknown' | 'static';

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  last_login_at: string | null;
}

export interface Source {
  id: number;
  name: string;
  service: string;
  log_format: string;
  collect_status: string;
  rate_per_min: number;
  host_group: string;
  description: string;
  last_collected_at: string | null;
  rule_count: number;
  template_count: number;
  event_count: number;
  pending_count: number;
}

export interface ParseRule {
  id: number;
  source_id: number;
  source_name?: string;
  name: string;
  pattern: string;
  field_names: string[];
  priority: number;
  enabled: boolean;
  hit_count: number;
}

export interface Template {
  id: number;
  signature: string;
  template_str: string;
  token_count: number;
  slot_types: SlotType[];
  slot_names: string[];
  source_id: number | null;
  source_name: string;
  service: string;
  sample_line: string;
  level_hint: EventLevel;
  status: TemplateStatus;
  is_noise: boolean;
  frequency: number;
  event_count: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  origin: string;
  slot_count: number;
}

export interface LogEvent {
  id: number;
  source_id: number;
  source_name: string;
  template_id: number | null;
  template_str: string;
  service: string;
  level: EventLevel;
  raw_line: string;
  event_time: string;
  bucket_start: string | null;
  origin: string;
}

export interface EventPage {
  items: LogEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TrendSeries {
  template_id: number;
  template_str: string;
  service: string;
  counts: Record<string, number>;
  errors: Record<string, number>;
  total: number;
  peak: number;
  series: number[];
  error_series: number[];
}

export interface TrendPayload {
  anchor: string | null;
  bucket_minutes: number;
  buckets: string[];
  series: TrendSeries[];
}

export interface TemplateAggregate {
  template_id: number;
  template_str: string;
  service: string;
  event_count: number;
  error_count: number;
  error_ratio: number;
}

export interface AlertRule {
  id: number;
  name: string;
  template_id: number | null;
  template_str: string;
  metric: string;
  window_minutes: number;
  baseline_buckets: number;
  z_threshold: number;
  error_ratio_low: number;
  error_ratio_high: number;
  silence_minutes: number;
  enabled: boolean;
  description: string;
  created_by: string;
}

export interface AlertEvent {
  id: number;
  rule_id: number;
  template_id: number;
  template_str: string;
  service: string;
  bucket_start: string;
  triggered_at: string;
  count_in_bucket: number;
  baseline_median: number;
  baseline_mad: number;
  z_score: number;
  error_ratio: number;
  baseline_error_ratio: number;
  level: EventLevel;
  reason: string;
  status: AlertStatus;
  acknowledged_by: string;
  acknowledged_at: string | null;
  silenced_until: string | null;
  note: string;
  origin: string;
  recompute_count: number;
}

export type RecomputeAction = 'created' | 'updated' | 'resolved' | 'unchanged' | 'skipped';

export interface RecomputePreview {
  range_start: string | null;
  range_end: string | null;
  expanded_end?: string;
  auto: boolean;
  bucket_count: number;
  template_count: number;
  pair_count: number;
  buckets: string[];
  template_ids?: number[];
  message?: string;
}

export interface RecomputeDetail {
  id: number;
  job_id: number;
  template_id: number;
  template_str: string;
  service: string;
  bucket_start: string;
  action: RecomputeAction;
  alert_id: number | null;
  before_status: AlertStatus | null;
  after_status: AlertStatus | null;
  before_count: number | null;
  after_count: number | null;
  before_z_score: number | null;
  after_z_score: number | null;
  before_error_ratio: number | null;
  after_error_ratio: number | null;
  reason: string;
  note: string;
}

export interface RecomputeBucketSummary {
  bucket_start: string;
  total: number;
  created: number;
  updated: number;
  resolved: number;
  unchanged: number;
  skipped: number;
  before_firing: number;
  after_firing: number;
}

export interface RecomputeJob {
  id: number;
  idempotency_key: string;
  triggered_by: string;
  range_start: string | null;
  range_end: string | null;
  affected_bucket_count: number;
  affected_template_count: number;
  pair_count: number;
  created: number;
  updated: number;
  resolved: number;
  unchanged: number;
  skipped: number;
  status: string;
  elapsed_ms: number;
  note: string;
  finished_at: string | null;
  details?: RecomputeDetail[];
  buckets?: RecomputeBucketSummary[];
  deduplicated?: boolean;
  message?: string;
}

export interface MinedTemplatePreview {
  template_str: string;
  token_count: number;
  slot_types: SlotType[];
  slot_names: string[];
  sample_count: number;
  sample_line: string;
  signature: string;
  status: string;
  level_hint: EventLevel;
  is_new: boolean;
  suggested_source_id: number | null;
  suggested_source_name: string;
}

export interface MinePreview {
  lines_total: number;
  covered_lines: number;
  noise_lines: number;
  tentative_lines: number;
  coverage: number;
  coverage_percent: number;
  new_templates: number;
  templates: MinedTemplatePreview[];
  known_hits: number;
  known_templates_used: number;
  elapsed_ms: number;
  message?: string;
  created_templates?: number;
  assigned_events?: number;
  inserted_events?: number;
}

export interface Overview {
  sources: number;
  parse_rules: number;
  templates: number;
  noise_templates: number;
  tentative_templates: number;
  slots: number;
  events: number;
  pending_events: number;
  covered_events: number;
  coverage_percent: number;
  alerts: { total: number; firing: number; acknowledged: number; silenced: number; resolved: number };
  anchor: string | null;
}

export interface ScanResult {
  bucket: string | null;
  templates_scanned: number;
  alerts: unknown[];
  skipped: unknown[];
  insufficient_history: number;
  created: number;
  elapsed_ms: number;
  message: string;
}

export interface AuditEntry {
  id: number;
  actor_email: string;
  action: string;
  entity: string;
  entity_id: string;
  detail: Record<string, unknown>;
  client_ip: string;
  occurred_at: string;
}
