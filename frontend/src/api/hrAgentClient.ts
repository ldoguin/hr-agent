/**
 * API Client for Agentic HR Recruitment System
 *
 * This client connects the React frontend to the FastAPI backend
 * running the Agent Catalog-based candidate matching system.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Types
export interface Candidate {
  name: string;
  email?: string;
  location?: string;
  years_experience: number;
  skills: string[];
  technical_skills: string[];
  summary?: string;
  match_score: number;
}

export interface JobMatchRequest {
  job_description: string;
  num_results?: number;
}

export interface JobMatchResponse {
  candidates: Candidate[];
  agent_reasoning: string;
  total_found: number;
  query_time_seconds: number;
}

export interface ResumeUploadResponse {
  success: boolean;
  message: string;
  filename: string;
  candidate_name?: string;
}

export interface HealthResponse {
  status: string;
  agent_initialized: boolean;
  couchbase_connected: boolean;
  ai_services_available: boolean;
}

export interface DatabaseStats {
  total_candidates: number;
  top_skills: string[];
  database_status: string;
}

export interface InitialMeetingRequest {
  email: string;
  first_name?: string;
  last_name?: string;
  position?: string;
  company_name?: string;
}

export interface InitialMeetingResponse {
  application_id: string;
}

// API Client Class
class HRAgentClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  /**
   * Check API health status
   */
  async toggleCapellaAI(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Check API health status
   */
  async getCapellaAIStatus(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
  /**
   * Check API health status
   */
  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseURL}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Match candidates to a job description using direct vector search (FAST)
   * Uses /api/search for near-instant results without agent reasoning overhead
   */
  async matchCandidates(
    jobDescription: string,
    numResults: number = 5
  ): Promise<JobMatchResponse> {
    const response = await fetch(`${this.baseURL}/api/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_description: jobDescription,
        num_results: numResults,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || 'Failed to match candidates');
    }

    return response.json();
  }

  /**
   * Match candidates using the full AI agent reasoning loop (SLOW but more detailed)
   * Uses /api/match with ReAct agent for intelligent multi-step reasoning
   */
  async matchCandidatesWithAgent(
    jobDescription: string,
    numResults: number = 5
  ): Promise<JobMatchResponse> {
    const response = await fetch(`${this.baseURL}/api/match`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_description: jobDescription,
        num_results: numResults,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || 'Failed to match candidates');
    }

    return response.json();
  }

  /**
   * Upload a resume PDF for processing
   */
  async uploadResume(file: File): Promise<ResumeUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseURL}/api/upload-resume`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || 'Failed to upload resume');
    }

    return response.json();
  }

  /**
   * Get list of all candidates
   */
  async listCandidates(limit: number = 10, offset: number = 0): Promise<Candidate[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    const response = await fetch(`${this.baseURL}/api/candidates?${params}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch candidates: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get database statistics
   */
  async getStats(): Promise<DatabaseStats> {
    const response = await fetch(`${this.baseURL}/api/stats`);

    if (!response.ok) {
      throw new Error(`Failed to fetch stats: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Send initial meeting request email and create application document
   */
  async sendMeetingRequest(request: InitialMeetingRequest): Promise<InitialMeetingResponse> {
    const response = await fetch(`${this.baseURL}/api/send_meeting_request`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(error.error || 'Failed to send meeting request');
    }

    return response.json();
  }
}

// Export singleton instance
export const hrAgentClient = new HRAgentClient();

// Export class for custom instances
export default HRAgentClient;
