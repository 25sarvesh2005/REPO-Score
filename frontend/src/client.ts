/**
 * Typed HTTP Client for RepoScore API.
 * Adheres strictly to docs/api/ENDPOINT_CATALOG.md and RFC 7807 problem details.
 */

import {
  EvaluationAcceptedResponse,
  EvaluationCancelResponse,
  EvaluationCreateRequest,
  EvaluationHistoryItemResponse,
  EvaluationRecordResponse,
  EvaluationStatusResponse,
  PaginatedEvidenceResponse,
  RepositoryRegistrationRequest,
  RepositoryResponse,
  RuntimeTelemetryResponse,
  ScorecardResponse,
  AIInterpretationResponse,
} from './types';

export class RepoScoreApiError extends Error {
  public readonly status: number;
  public readonly correlationId?: string;
  public readonly problemDetails?: Record<string, unknown>;

  constructor(status: number, message: string, correlationId?: string, problemDetails?: Record<string, unknown>) {
    super(message);
    this.name = 'RepoScoreApiError';
    this.status = status;
    this.correlationId = correlationId;
    this.problemDetails = problemDetails;
  }
}

export class RepoScoreClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has('Content-Type') && options.body) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, { ...options, headers });
    const correlationId = response.headers.get('X-Correlation-ID') || undefined;

    if (!response.ok) {
      let problem: Record<string, unknown> = {};
      try {
        problem = await response.json();
      } catch {
        // Not a JSON response
      }
      const message = (problem.detail as string) || (problem.title as string) || `HTTP error ${response.status}`;
      throw new RepoScoreApiError(response.status, message, correlationId, problem);
    }

    return (await response.json()) as T;
  }

  // Repository Operations
  public async registerRepository(request: RepositoryRegistrationRequest): Promise<RepositoryResponse> {
    return this.request<RepositoryResponse>('/api/v1/repositories', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  public async listRepositories(limit = 50, offset = 0): Promise<RepositoryResponse[]> {
    return this.request<RepositoryResponse[]>(`/api/v1/repositories?limit=${limit}&offset=${offset}`);
  }

  public async getRepository(id: string): Promise<RepositoryResponse> {
    return this.request<RepositoryResponse>(`/api/v1/repositories/${id}`);
  }

  // Evaluation Orchestration
  public async createEvaluation(request: EvaluationCreateRequest): Promise<EvaluationAcceptedResponse> {
    return this.request<EvaluationAcceptedResponse>('/api/v1/evaluations', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  public async listEvaluations(params?: { repository_id?: string; status?: string; limit?: number; offset?: number }): Promise<EvaluationRecordResponse[]> {
    const query = new URLSearchParams();
    if (params?.repository_id) query.set('repository_id', params.repository_id);
    if (params?.status) query.set('status', params.status);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<EvaluationRecordResponse[]>(`/api/v1/evaluations${qs}`);
  }

  public async getEvaluation(id: string): Promise<EvaluationRecordResponse> {
    return this.request<EvaluationRecordResponse>(`/api/v1/evaluations/${id}`);
  }

  public async getEvaluationStatus(id: string): Promise<EvaluationStatusResponse> {
    return this.request<EvaluationStatusResponse>(`/api/v1/evaluations/${id}/status`);
  }

  public async cancelEvaluation(id: string): Promise<EvaluationCancelResponse> {
    return this.request<EvaluationCancelResponse>(`/api/v1/evaluations/${id}/cancel`, {
      method: 'POST',
    });
  }

  // Score & Exploration
  public async getEvaluationScore(id: string): Promise<ScorecardResponse> {
    return this.request<ScorecardResponse>(`/api/v1/evaluations/${id}/score`);
  }

  public async getEvaluationEvidence(
    id: string,
    params?: { category?: string; severity?: string; limit?: number; offset?: number }
  ): Promise<PaginatedEvidenceResponse> {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.severity) query.set('severity', params.severity);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<PaginatedEvidenceResponse>(`/api/v1/evaluations/${id}/evidence${qs}`);
  }

  public async getEvaluationRuntime(id: string): Promise<RuntimeTelemetryResponse> {
    return this.request<RuntimeTelemetryResponse>(`/api/v1/evaluations/${id}/runtime`);
  }

  public async getEvaluationAI(id: string): Promise<AIInterpretationResponse> {
    return this.request<AIInterpretationResponse>(`/api/v1/evaluations/${id}/ai`);
  }

  public async getEvaluationHistory(id: string, limit = 10): Promise<EvaluationHistoryItemResponse[]> {
    return this.request<EvaluationHistoryItemResponse[]>(`/api/v1/evaluations/${id}/history?limit=${limit}`);
  }
}
