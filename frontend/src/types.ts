/**
 * RepoScore TypeScript API Interface Contracts.
 * Adheres strictly to docs/api/OPENAPI_SPEC.yaml and backend/api/schemas/contracts.py.
 */

export type EvaluationStatus =
  | 'QUEUED'
  | 'INGESTING'
  | 'ANALYZING'
  | 'BUILDING'
  | 'STARTING'
  | 'TESTING'
  | 'OBSERVING'
  | 'SCORING'
  | 'AI_INTERPRETATION'
  | 'COMPLETED'
  | 'PARTIALLY_COMPLETED'
  | 'BUILD_FAILED'
  | 'STARTUP_FAILED'
  | 'FAILED'
  | 'TIMEOUT'
  | 'CANCELLED'
  | 'UNSUPPORTED';

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type EvidenceCategory =
  | 'CORRECTNESS'
  | 'SECURITY'
  | 'RELIABILITY'
  | 'TESTING'
  | 'MAINTAINABILITY'
  | 'ARCHITECTURE'
  | 'PERFORMANCE'
  | 'DEPENDENCY_HEALTH'
  | 'DOCUMENTATION'
  | 'ENGINEERING_MATURITY';

export type LetterGrade = 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';

export interface RepositoryRegistrationRequest {
  url: string;
  provider?: string;
}

export interface RepositoryResponse {
  id: string;
  url: string;
  owner: string;
  name: string;
  default_branch: string;
  is_private: boolean;
  stars_count: number;
  primary_language?: string | null;
  created_at: string;
}

export interface EvaluationOptions {
  timeout_seconds?: number;
  enable_ai_reasoning?: boolean;
}

export interface EvaluationCreateRequest {
  repository_id: string;
  ref?: string;
  options?: EvaluationOptions;
}

export interface EvaluationAcceptedResponse {
  evaluation_id: string;
  status: EvaluationStatus;
  correlation_id: string;
  status_url: string;
  events_url: string;
}

export interface EvaluationRecordResponse {
  id: string;
  repository_id: string;
  snapshot_id: string;
  status: EvaluationStatus;
  correlation_id: string;
  trigger_source: string;
  worker_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  error_summary?: string | null;
  created_at: string;
}

export interface EvaluationStatusResponse {
  evaluation_id: string;
  status: EvaluationStatus;
  current_step?: string | null;
  elapsed_seconds: number;
  is_terminal: boolean;
}

export interface EvaluationCancelResponse {
  evaluation_id: string;
  status: string;
  message: string;
}

export interface ItemizedReceiptItem {
  type: 'DEDUCTION' | 'CREDIT';
  rule_code: string;
  evidence_id: string;
  description: string;
  points: number;
  confidence: number;
  calculated_delta: number;
}

export interface ScoreDimensionResponse {
  dimension_name: string;
  score: number;
  weight: number;
  base_score: number;
  itemized_receipt: ItemizedReceiptItem[];
}

export interface ScorecardResponse {
  evaluation_id: string;
  scoring_version: string;
  overall_score: number;
  grade: LetterGrade;
  dimensions: ScoreDimensionResponse[];
  ai_executive_summary?: string | null;
  created_at: string;
}

export interface EvidenceLocation {
  file_path: string;
  start_line?: number | null;
  end_line?: number | null;
  start_col?: number | null;
  end_col?: number | null;
  symbol_name?: string | null;
}

export interface EvidenceItemResponse {
  id: string;
  source: string;
  category: EvidenceCategory;
  severity: SeverityLevel;
  confidence: number;
  title: string;
  description: string;
  location?: EvidenceLocation | null;
  created_at: string;
}

export interface PaginatedEvidenceResponse {
  items: EvidenceItemResponse[];
  total_count: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface RuntimeTelemetryResponse {
  evaluation_id: string;
  evaluator_strategy: string;
  build_success?: boolean | null;
  build_exit_code?: number | null;
  startup_ready?: boolean | null;
  startup_port?: number | null;
  latency_p95_ms?: number | null;
  total_http_requests: number;
  error_5xx_requests: number;
  failure_code?: string | null;
  failure_reason?: string | null;
  observations: Record<string, unknown>[];
}

export interface AIRecommendationItem {
  title: string;
  category: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  explanation: string;
  actionable_steps: string[];
  related_evidence_ids: string[];
}

export interface AIInterpretationResponse {
  evaluation_id: string;
  provider: string;
  model_name: string;
  prompt_version: string;
  executive_summary: string;
  architectural_assessment: string;
  security_risk_narrative: string;
  runtime_failure_root_cause?: string | null;
  top_strengths: string[];
  critical_risks: string[];
  recommendations: AIRecommendationItem[];
  tokens_consumed?: number | null;
  duration_ms?: number | null;
  is_fallback: boolean;
}

export interface EvaluationHistoryItemResponse {
  id: string;
  repository_id: string;
  status: EvaluationStatus;
  commit_sha?: string | null;
  overall_score?: number | null;
  grade?: LetterGrade | null;
  created_at: string;
  duration_ms?: number | null;
}
