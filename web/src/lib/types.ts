export type Decision = "ALLOW" | "REVIEW" | "BLOCK";
export type Priority = "critical" | "high" | "normal";
export type CaseStatus = "open" | "confirmed_fraud" | "false_positive";

export interface Metrics {
  window_s: number;
  transactions: number;
  review: number;
  block: number;
  alert_rate: number;
  avg_score: number;
  blocked_amount: number;
  cases: Partial<Record<CaseStatus, number>>;
  analyst_precision: number | null;
  model_version: string;
}

export interface Thresholds {
  review: number;
  block: number;
}

export interface Overview {
  metrics: Metrics;
  thresholds: Thresholds;
  series: { minute: number; n: number; review: number; block: number; held: number }[];
  cities: { city: string; n: number; alerts: number; block: number; held: number; lat: number | null; lon: number | null }[];
  channels: { channel: string; n: number; alerts: number }[];
  score_histogram: number[];
  traffic: Traffic;
  server_time: number;
}

export interface Traffic {
  running: boolean;
  rate: number;
}

export interface FeedRow {
  txn_id: string;
  created_at: number;
  user_id: string;
  amount: number;
  merchant: string;
  category: string;
  city: string;
  channel: string;
  device_id: string;
  score: number;
  decision: Decision;
  reason: string | null;
  case_id: number | null;
}

export interface TraceStep {
  step: number;
  tool: string;
  input: unknown;
  output: unknown;
  ms: number | null;
}

export interface PolicyRef {
  id: string;
  text: string;
  document: string;
}

export interface CaseRow {
  case_id: number;
  txn_id: string;
  status: CaseStatus;
  priority: Priority;
  summary: { text: string; actions: string[] } | null;
  trace: TraceStep[] | null;
  policy_refs: PolicyRef[] | null;
  assignee: string | null;
  resolution_notes: string | null;
  created_at: number;
  updated_at: number;
  amount: number;
  user_id: string;
  city: string;
  merchant: string;
  score: number;
  decision: Decision;
}

export interface RiskReason {
  code: string;
  title: string;
  observed: string;
  normal: string;
  detail: string;
  weight: number;
}

export interface Reasons {
  risk: RiskReason[];
  reassuring: string[];
  strength: "none" | "single" | "multiple";
  policy_override?: string;
}

export interface Transaction {
  txn_id: string;
  user_id: string;
  ts: number;
  amount: number;
  merchant: string;
  payee?: string | null;
  category: string;
  city: string;
  device_id: string;
  channel: string;
  score: number;
  decision: Decision;
  model_version: string;
  features: Record<string, number>;
  contributions: Record<string, number>;
  reasons: Reasons;
  label: number | null;
  created_at: number;
}

export interface HistoryRow {
  txn_id: string;
  ts: number;
  amount: number;
  merchant: string;
  payee?: string | null;
  category: string;
  city: string;
  device_id: string;
  score: number;
  decision: Decision;
  label: number | null;
}

export interface CaseDetail extends Omit<CaseRow, "amount" | "user_id" | "city" | "merchant" | "score" | "decision"> {
  transaction: Transaction;
  customer_message: string;
  history: HistoryRow[];
  profile: {
    home_city: string | null;
    typical_amount: number;
    transactions: number;
    devices: number;
    cities: number;
    categories: string[];
  };
  thresholds: Thresholds;
  alerts: { audience: string; channel: string; body: string; created_at: number }[];
  audit: { ts: number; actor: string; action: string; detail: Record<string, unknown> }[];
}

export interface Investigation {
  case_id: number;
  txn_id: string;
  priority: Priority;
  status: CaseStatus;
  trace: TraceStep[];
  created_at: number;
  amount: number;
  user_id: string;
  city: string;
  merchant: string;
  channel: string;
  decision: Decision;
  score: number;
  actor: string | null;
  agent_ms: number;
  notified: string[];
}

export interface ScoreResult {
  txn_id: string;
  score: number;
  decision: Decision;
  model_decision: Decision;
  model_version: string;
  reasons: Reasons;
  latency_ms: number;
  case_id: number | null;
}

export interface PolicyAnswer {
  answer: string | null;
  abstained: boolean;
  confidence: "high" | "low" | "none";
  citations: { id: string; text: string; document: string; score: number }[];
  message?: string;
}

export interface OperatingPoint {
  threshold: number;
  precision: number;
  recall: number;
  alerts_per_10k?: number;
  tp?: number;
  fp?: number;
  fn?: number;
}

export interface ModelVersion {
  version: string;
  trained_at: number;
  notes: string;
  thresholds: Thresholds;
  features: string[];
  metrics: {
    pr_auc: number;
    roc_auc: number;
    review: OperatingPoint;
    block: OperatingPoint;
    n_train?: number;
    n_test?: number;
    test_frauds?: number;
    comparison?: { champion: string; decision: string; reason: string; feedback_labels: number };
  };
}

export interface ModelInfo {
  current: string;
  thresholds: Thresholds;
  features: string[];
  versions: ModelVersion[];
  labels: number;
  benchmark: {
    dataset: string;
    rows: number;
    frauds: number;
    split: string;
    test_rows: number;
    test_frauds: number;
    models: Record<string, { pr_auc: number; roc_auc: number; review: OperatingPoint; block: OperatingPoint }>;
  } | null;
}

export interface Drift {
  ready: boolean;
  rows: number;
  needed?: number;
  model_version?: string;
  features?: { feature: string; psi: number; status: "stable" | "warning" | "critical" }[];
  score_psi?: number;
  score_status?: string;
  critical_features?: number;
  retrain_recommended?: boolean;
}

export interface AuditRow {
  id: number;
  ts: number;
  actor: string;
  action: string;
  detail: Record<string, unknown>;
}
