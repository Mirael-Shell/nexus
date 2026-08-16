export const API_BASE = '/api/v1'

// ─── Types ─────────────────────────────────────────────

export interface PredictionResult {
  label: string
  probability: number
}

export interface PredictResponse {
  prediction_id: string
  label: string
  confidence: number
  all_probabilities: PredictionResult[]
  model_version: string
  processing_time_ms: number
  created_at: string
}

export interface PredictRequest {
  text: string
  model_version?: string
}

export interface FeedbackRequest {
  prediction_id: string
  feedback: 'up' | 'down'
  comment?: string
}

export interface FeedbackResponse {
  id: string
  prediction_id: string
  feedback: 'up' | 'down'
  comment: string | null
  created_at: string
}

export interface HealthResponse {
  status: string
  version: string
  model_loaded: boolean
  database_connected: boolean
}

export interface ModelVersion {
  version: string
  stage: string
  run_id: string
  status: string
  metrics: Record<string, number>
  params: Record<string, string>
  created_at: number | null
  updated_at: number | null
}

export interface ModelListResponse {
  model_name: string
  versions: ModelVersion[]
}

export interface PromoteResponse {
  model_name: string
  version: string
  new_stage: string
  success: boolean
}

// ─── A/B Experiments ───────────────────────────────────

export interface Experiment {
  id: string
  name: string
  description: string | null
  control_model: string
  treatment_model: string
  traffic_split: number
  strategy: string
  status: string
  min_samples: number
  created_at: string
  updated_at: string
  control_total: number
  control_up: number
  control_down: number
  treatment_total: number
  treatment_up: number
  treatment_down: number
}

export interface ExperimentListResponse {
  experiments: Experiment[]
}

export interface CreateExperimentData {
  name: string
  description?: string
  control_model: string
  treatment_model: string
  traffic_split?: number
  strategy?: string
  min_samples?: number
}

export interface BayesianAnalysis {
  experiment_id: string
  experiment_name: string
  control: {
    model: string
    total: number
    successes: number
    failures: number
    rate: number
    posterior_mean: number
    ci_95: [number, number]
  }
  treatment: {
    model: string
    total: number
    successes: number
    failures: number
    rate: number
    posterior_mean: number
    ci_95: [number, number]
  }
  prob_treatment_better: number
  expected_loss_control: number
  expected_loss_treatment: number
  recommendation: string
  should_stop: boolean
  reason: string
}

// ─── API calls ─────────────────────────────────────────

export async function predict(text: string): Promise<PredictResponse> {
  const res = await fetch(`${API_BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text } satisfies PredictRequest),
  })
  if (!res.ok) throw new Error(`Predict failed: ${res.status}`)
  return res.json()
}

export async function sendFeedback(
  predictionId: string,
  feedback: 'up' | 'down',
  comment?: string,
): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prediction_id: predictionId,
      feedback,
      comment,
    } satisfies FeedbackRequest),
  })
  if (!res.ok) throw new Error(`Feedback failed: ${res.status}`)
  return res.json()
}

export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}

export async function listModels(): Promise<ModelListResponse> {
  const res = await fetch(`${API_BASE}/models`)
  if (!res.ok) throw new Error(`List models failed: ${res.status}`)
  return res.json()
}

export async function promoteModel(version: string, stage: string): Promise<PromoteResponse> {
  const res = await fetch(`${API_BASE}/models/${version}/promote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ stage }),
  })
  if (!res.ok) throw new Error(`Promote failed: ${res.status}`)
  return res.json()
}

export async function listExperiments(): Promise<ExperimentListResponse> {
  const res = await fetch(`${API_BASE}/experiments`)
  if (!res.ok) throw new Error(`List experiments failed: ${res.status}`)
  return res.json()
}

export async function createExperiment(data: CreateExperimentData): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/experiments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Create experiment failed: ${res.status}`)
  return res.json()
}

export async function startExperiment(id: string): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/experiments/${id}/start`, { method: 'POST' })
  if (!res.ok) throw new Error(`Start experiment failed: ${res.status}`)
  return res.json()
}

export async function stopExperiment(id: string): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/experiments/${id}/stop`, { method: 'POST' })
  if (!res.ok) throw new Error(`Stop experiment failed: ${res.status}`)
  return res.json()
}

export async function analyzeExperiment(id: string): Promise<BayesianAnalysis> {
  const res = await fetch(`${API_BASE}/experiments/${id}/analyze`)
  if (!res.ok) throw new Error(`Analyze experiment failed: ${res.status}`)
  return res.json()
}

// ─── Drift & Cost ───────────────────────────────────────

export interface DriftMetric {
  name: string
  value: number
  threshold: number
  p_value: number
  is_drifted: boolean
  description: string
}

export interface DriftReport {
  window_size: number
  reference_size: number
  overall_drift_score: number
  drift_detected: boolean
  severity: string
  recommendation: string
  metrics: DriftMetric[]
}

export interface CostDaily {
  date: string
  total_predictions: number
  total_feedback: number
  negative_feedback: number
  inference_cost_usd: number
  review_cost_usd: number
  total_cost_usd: number
  revenue_usd: number
  profit_usd: number
  margin_pct: number
}

export interface CostSummary {
  period_days: number
  total_predictions: number
  total_cost_usd: number
  total_revenue_usd: number
  total_profit_usd: number
  avg_daily_cost_usd: number
  avg_margin_pct: number
  cost_per_1k_predictions_usd: number
  daily: CostDaily[]
}

export async function analyzeDrift(
  referenceDays: number = 7,
  currentHours: number = 24,
): Promise<DriftReport> {
  const res = await fetch(`${API_BASE}/drift/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reference_days: referenceDays,
      current_hours: currentHours,
    }),
  })
  if (!res.ok) throw new Error(`Drift analysis failed: ${res.status}`)
  return res.json()
}

export async function getCostSummary(days: number = 7): Promise<CostSummary> {
  const res = await fetch(`${API_BASE}/cost/summary?days=${days}`)
  if (!res.ok) throw new Error(`Cost summary failed: ${res.status}`)
  return res.json()
}

// ─── Multi-Modal ────────────────────────────────────────

export interface ImageModerationResult {
  label: string
  confidence: number
  model_version: string
  processing_time_ms: number
  file_size_bytes: number
  detected_issues: string[]
}

export async function moderateImage(file: File): Promise<ImageModerationResult> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/moderate/image`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`Image moderation failed: ${res.status}`)
  return res.json()
}

// ─── Filter API ────────────────────────────────────────

export interface FilterRules {
  block_labels: string[]
  flag_labels: string[]
  threshold: number
  use_similarity_boost: boolean
}

export interface FilterRequest {
  text: string
  rules: FilterRules
  source: string
}

export interface SimilarityMatch {
  text: string
  label: string
  action: string
  similarity: number
}

export interface FilterResponse {
  action: string
  label: string
  confidence: number
  latency_ms: number
  triggered_rules: string[]
  similar_matches: SimilarityMatch[]
  embedding_model: string
  event_id: string | null
}

export interface FilterStats {
  total_events: number
  by_action: Record<string, number>
  by_label: Record<string, number>
  error?: string
}

export async function filterContent(req: FilterRequest): Promise<FilterResponse> {
  const res = await fetch(`${API_BASE}/filter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Filter failed: ${res.status}`)
  return res.json()
}

export async function getFilterStats(): Promise<FilterStats> {
  const res = await fetch(`${API_BASE}/filter/stats`)
  if (!res.ok) throw new Error(`Filter stats failed: ${res.status}`)
  return res.json()
}

export async function getFilterRecent(limit = 20): Promise<{ events: Record<string, unknown>[] }> {
  const res = await fetch(`${API_BASE}/filter/recent?limit=${limit}`)
  if (!res.ok) throw new Error(`Filter recent failed: ${res.status}`)
  return res.json()
}

export interface DatasetStats {
  total_samples: number
  by_label: Record<string, number>
  last_updated: string | null
}

export interface AddExampleResponse {
  success: boolean
  total_samples: number
  message: string
}

export interface RetrainResponse {
  success: boolean
  message: string
  metrics?: Record<string, unknown>
}

export async function addExample(text: string, label: string): Promise<AddExampleResponse> {
  const res = await fetch(`${API_BASE}/dataset/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, label }),
  })
  if (!res.ok) throw new Error(`Add example failed: ${res.status}`)
  return res.json()
}

export async function retrainModel(): Promise<RetrainResponse> {
  const res = await fetch(`${API_BASE}/dataset/retrain`, { method: 'POST' })
  if (!res.ok) throw new Error(`Retrain failed: ${res.status}`)
  return res.json()
}

export async function getDatasetStats(): Promise<DatasetStats> {
  const res = await fetch(`${API_BASE}/dataset/stats`)
  if (!res.ok) throw new Error(`Dataset stats failed: ${res.status}`)
  return res.json()
}
