/**
 * Backend Info Component
 *
 * Displays backend code explanations and technical details
 * for the HR recruitment system when users click buttons.
 *
 * Enhanced to provide deeper technical insights, especially for
 * LangChain ReAct agents, Agent Catalog v1.0.0 tools, and AI services.
 */

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Code,
  Database,
  Zap,
  Upload,
  Search,
  ChevronDown,
  ChevronRight,
  Server,
  FileText,
  Activity,
} from 'lucide-react';

interface BackendInfoProps {
  title: string;
  description: string;
  endpoint?: string;
  method?: string;
  technicalDetails: string[];
  className?: string;
}

export function BackendInfo({
  title,
  description,
  endpoint,
  method = 'GET',
  technicalDetails,
  className = '',
}: BackendInfoProps) {
  const [isOpen, setIsOpen] = useState(false);

  const getMethodColor = (method: string) => {
    switch (method.toUpperCase()) {
      case 'GET': return 'bg-blue-500';
      case 'POST': return 'bg-green-500';
      case 'PUT': return 'bg-yellow-500';
      case 'DELETE': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <Card className={`border-2 border-slate-300 bg-slate-50 ${className}`}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-slate-100 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-slate-200">
                  <Server className="h-5 w-5 text-slate-700" />
                </div>
                <div>
                  <CardTitle className="text-lg flex items-center gap-2 text-slate-900">
                    {title}
                    <Badge variant="outline" className="text-xs border-slate-400 text-slate-700">
                      Backend
                    </Badge>
                  </CardTitle>
                  <CardDescription className="mt-1 text-slate-600">
                    {description}
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {endpoint && (
                  <Badge className={`${getMethodColor(method)} text-white`}>
                    {method} {endpoint}
                  </Badge>
                )}
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 text-slate-700" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-slate-700" />
                )}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-slate-900 mb-2 flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Technical Details
              </h4>
              <ul className="space-y-2">
                {technicalDetails.map((detail, index) => (
                  <li key={index} className="text-sm text-slate-700 flex items-start gap-2">
                    <span className="text-slate-600 mt-1" aria-hidden="true">•</span>
                    {detail}
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

// Pre-configured backend info components for common operations
export function HealthCheckInfo() {
  return (
    <BackendInfo
      title="System Health Check"
      description="Monitors the status of AI agent, database, and services"
      endpoint="/health"
      method="GET"
      technicalDetails={[
        "Checks if LangChain ReAct agent is initialized with Agent Catalog v1.0.0 tools and prompts",
        "Verifies Couchbase database connectivity and vector search index setup",
        "Confirms AI services availability (Capella AI priority, OpenAI fallback)",
        "Validates agent executor with hr_recruiter_assistant prompt and search_candidates_vector tool",
        "Returns real-time status for UI status bar used by AgentJobMatch component",
      ]}
    />
  );
}

export function ResumeUploadInfo() {
  return (
    <BackendInfo
      title="Resume Upload Processing"
      description="Handles PDF resume uploads and background processing"
      endpoint="/api/upload-resume"
      method="POST"
      technicalDetails={[
        "Accepts PDF files from UploadResumes page and validates file format",
        "Saves uploaded files to configured resumes directory for processing",
        "Queues background tasks using FastAPI BackgroundTasks for async processing",
        "Extracts text content from PDFs using PyPDF2 or similar PDF parsing library",
        "Analyzes extracted text with LLM (Capella AI priority, OpenAI fallback) to structure candidate data",
        "Generates vector embeddings for semantic search using configured embeddings model",
        "Stores structured candidate profiles and embeddings in Couchbase vector store",
        "Triggers React Query cache invalidation to refresh UI database statistics",
      ]}
    />
  );
}

export function CandidateSearchInfo() {
  return (
    <BackendInfo
      title="Fast Candidate Search"
      description="Direct vector search for candidate matching"
      endpoint="/api/search"
      method="POST"
      technicalDetails={[
        "Bypasses full LangChain ReAct agent reasoning loop for instant results",
        "Calls search_candidates_vector tool directly without Agent Catalog prompt orchestration",
        "Generates embeddings for job description using configured embeddings model (Capella AI priority)",
        "Performs vector similarity search against Couchbase vector index with configurable top-k results",
        "Returns ranked candidates with semantic similarity scores and structured metadata",
        "Parses tool output to extract candidate details (name, skills, experience, contact info)",
        "Provides simplified reasoning text for UI display without full agent chain-of-thought",
        "Near-instant response time (< 2 seconds) for UI responsiveness via 'Find Best Candidates' button",
      ]}
    />
  );
}

export function DatabaseStatsInfo() {
  return (
    <BackendInfo
      title="Database Statistics"
      description="Provides candidate database overview and metrics"
      endpoint="/api/stats"
      method="GET"
      technicalDetails={[
        "Executes N1QL queries against Couchbase bucket/scope/collection to count total candidates",
        "Uses UNNEST clause to extract and aggregate skills from candidate metadata arrays",
        "Performs real-time database connectivity validation via Couchbase cluster health checks",
        "Returns structured statistics object with candidate count, skills distribution, and connection status",
        "Updates AgentJobMatch component's database overview section with fresh metrics",
        "Triggers React Query cache refresh after resume processing completes",
        "Provides data for UI dashboard showing system utilization and candidate pool growth",
      ]}
    />
  );
}

export function AgentMatchInfo() {
  return (
    <BackendInfo
      title="AI Agent Job Matching"
      description="Full AI agent reasoning for comprehensive candidate evaluation"
      endpoint="/api/match"
      method="POST"
      technicalDetails={[
        "Initializes LangChain ReAct agent with Agent Catalog v1.0.0 prompt 'hr_recruiter_assistant'",
        "Uses hr_recruiter_assistant prompt template with tools and tool_names variables populated",
        "Agent follows ReAct pattern: Question → Thought → Action → Action Input → Observation → Final Answer",
        "Invokes search_candidates_vector tool with job description to find semantic matches",
        "Agent analyzes intermediate tool results and may iterate with additional reasoning steps",
        "Processes agent chain-of-thought output to extract structured candidate recommendations",
        "Returns detailed agent reasoning alongside ranked candidates with match explanations",
        "Supports complex multi-step reasoning for nuanced job requirements and candidate evaluation",
        "Timeout protection (60s) with fallback parsing if agent execution exceeds limits",
        "WebSocket streaming of intermediate agent steps for real-time UI feedback",
      ]}
    />
  );
}
