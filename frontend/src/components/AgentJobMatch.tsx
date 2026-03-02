/**
 * Agent-powered Job Matching Component
 *
 * A beautiful, fully-featured interface for matching candidates to job descriptions
 * using the Agent Catalog-based AI system with enhanced UX and animations.
 */

import { useState, useEffect } from 'react';
import { useMatchCandidates, useMatchCandidatesWithAgent, useHealthCheck, useStats } from '@/hooks/useHRAgent';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Loader2,
  Sparkles,
  User,
  Mail,
  MapPin,
  Briefcase,
  Brain,
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  Database,
  Zap,
  FileText,
  Search,
  Code,
  Eye,
  EyeOff,
  Send,
  Edit3,
  Check,
  X,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Navigation } from '@/components/Navigation';
import { ConditionalWebSocketLogs } from "@/components/ConditionalWebSocketLogs";
import {
  HealthCheckInfo,
  CandidateSearchInfo,
  DatabaseStatsInfo,
  BackendInfo
} from '@/components/BackendInfo';
import { toast } from '@/hooks/use-toast';
import { hrAgentClient, InitialMeetingRequest } from '@/api/hrAgentClient';

export function AgentJobMatch() {
  const [jobDescription, setJobDescription] = useState('');
  const [numResults, setNumResults] = useState(5);
  const [activeTab, setActiveTab] = useState('search');
  const [showBackendInfo, setShowBackendInfo] = useState(false);
  const [searchMethod, setSearchMethod] = useState<'fast' | 'agent'>('agent');
  const [editingEmail, setEditingEmail] = useState<string | null>(null);
  const [emailInput, setEmailInput] = useState('');
  const [meetingRequestLoading, setMeetingRequestLoading] = useState<string | null>(null);

  const matchMutation = useMatchCandidates();
  const agentMatchMutation = useMatchCandidatesWithAgent();
  const { data: healthData } = useHealthCheck();
  const { data: stats } = useStats();

  // Use the appropriate mutation based on search method
  const currentMutation = searchMethod === 'agent' ? agentMatchMutation : matchMutation;

  // Auto-switch to results tab when data is loaded
  useEffect(() => {
    if (currentMutation.isSuccess && currentMutation.data) {
      setActiveTab('results');
    }
  }, [currentMutation.isSuccess, currentMutation.data]);

  // Handle meeting request
  const handleSendMeetingRequest = async (candidate: any) => {
    const email = emailInput || candidate.email;
    
    if (!email) {
      toast({
        title: "Email Required",
        description: "Please provide an email address to send the meeting request.",
        variant: "destructive",
      });
      return;
    }

    try {
      setMeetingRequestLoading(candidate.name);
      
      const request: InitialMeetingRequest = {
        email: email,
        first_name: candidate.name.split(' ')[0] || 'Candidate',
        last_name: candidate.name.split(' ').slice(1).join(' ') || '',
        position: "Software Engineer",
        company_name: "Tech Corp",
      };

      await hrAgentClient.sendMeetingRequest(request);
      
      toast({
        title: "Meeting Request Sent",
        description: `Meeting request sent to ${email}`,
      });
      
      setEditingEmail(null);
      setEmailInput('');
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to send meeting request",
        variant: "destructive",
      });
    } finally {
      setMeetingRequestLoading(null);
    }
  };

  // Handle email edit
  const handleEditEmail = (candidate: any) => {
    setEditingEmail(candidate.name);
    setEmailInput(candidate.email || '');
  };

  const handleCancelEdit = () => {
    setEditingEmail(null);
    setEmailInput('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!jobDescription.trim()) {
      return;
    }

    currentMutation.mutate({
      jobDescription,
      numResults,
    });
  };

  const handleExampleClick = (example: string) => {
    setJobDescription(example);
  };

  const exampleJobs = [
    "Senior React Developer with 5+ years of experience. Must have TypeScript, Redux, and GraphQL. Experience with testing frameworks like Jest and React Testing Library required.",
    "Full Stack Python Developer needed. 3+ years with Django or Flask. Strong database skills (PostgreSQL, MongoDB). Docker and Kubernetes experience preferred.",
    "DevOps Engineer with AWS expertise. Must know Terraform, Kubernetes, and CI/CD pipelines. Python or Go scripting skills required. 4+ years in production environments.",
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <Navigation />

      <div className="container mx-auto p-6 space-y-6 max-w-7xl">
        {/* Header Section */}
        <div className="flex flex-col gap-4 pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg">
                <Sparkles className="h-8 w-8 text-white" />
              </div>
              <div>
                <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  AI Agent Job Matching
                </h1>
                <p className="text-muted-foreground text-lg">
                  Powered by Agent Catalog, LangChain, and Couchbase Vector Search
                </p>
              </div>
            </div>

            {/* Backend Info Toggle */}
            <Button
              variant="outline"
              onClick={() => setShowBackendInfo(!showBackendInfo)}
              className="gap-2 border-slate-300 hover:bg-slate-100"
            >
              {showBackendInfo ? (
                <>
                  <EyeOff className="h-4 w-4" />
                  Hide Backend
                </>
              ) : (
                <>
                  <Code className="h-4 w-4" />
                  Show Backend
                </>
              )}
            </Button>
          </div>

          {/* Status Bar */}
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-6 items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`h-2 w-2 rounded-full animate-pulse ${healthData?.agent_initialized ? 'bg-green-500' : 'bg-yellow-500'}`} />
                  <span className="text-sm font-medium">
                    Agent: {healthData?.agent_initialized ? 'Ready' : 'Initializing'}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium">
                    {stats?.total_candidates || 0} Candidates
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-blue-600" />
                  <span className="text-sm font-medium">
                    Status: {healthData?.status || 'Unknown'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Backend Information */}
          {showBackendInfo && (
            <div className="space-y-4">
              <div className="text-center">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">
                  🔧 Backend Implementation Details
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  Click on any section below to see the backend code and technical details for each operation.
                </p>
              </div>

              <div className="grid gap-4">
                <HealthCheckInfo />
                <CandidateSearchInfo />
                <DatabaseStatsInfo />
              </div>
            </div>
          )}
        </div>

        {/* Main Content */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-2 mx-auto">
            <TabsTrigger value="search" className="gap-2">
              <Search className="h-4 w-4" />
              Search
            </TabsTrigger>
            <TabsTrigger value="results" className="gap-2" disabled={!currentMutation.data}>
              <TrendingUp className="h-4 w-4" />
              Results {currentMutation.data && `(${currentMutation.data.total_found})`}
            </TabsTrigger>
          </TabsList>

          {/* Search Tab */}
          <TabsContent value="search" className="space-y-6">
            {/* Input Form */}
            <Card className="shadow-xl border-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  Job Description
                </CardTitle>
                <CardDescription>
                  Describe the position in detail. Include required skills, experience level, and key responsibilities.
                  The AI agent will analyze your requirements and find the best matching candidates.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Textarea
                      placeholder="Example: Looking for a Senior React Developer with 5+ years of experience..."
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      className="min-h-[200px] text-base"
                    />
                  </div>

                  {/* Quick Examples */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Quick Examples:</label>
                    <div className="flex flex-wrap gap-2">
                      {exampleJobs.map((example, i) => (
                        <Button
                          key={i}
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => handleExampleClick(example)}
                          className="text-left h-auto py-2"
                        >
                          Example {i + 1}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* Search Method Toggle */}
                  <div className="space-y-3">
                    <label className="text-sm font-medium">Search Method:</label>
                    <div className="flex gap-3">
                      <Button
                        type="button"
                        variant={searchMethod === 'fast' ? 'default' : 'outline'}
                        onClick={() => setSearchMethod('fast')}
                        className="flex-1 gap-2"
                      >
                        <Zap className="h-4 w-4" />
                        Fast Search
                        <span className="text-xs opacity-75">Vector similarity</span>
                      </Button>
                      <Button
                        type="button"
                        variant={searchMethod === 'agent' ? 'default' : 'outline'}
                        onClick={() => setSearchMethod('agent')}
                        className="flex-1 gap-2"
                      >
                        <Brain className="h-4 w-4" />
                        AI Agent
                        <span className="text-xs opacity-75">Detailed reasoning</span>
                      </Button>
                    </div>
                  </div>

                  <Separator />

                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <label className="text-sm font-medium whitespace-nowrap">
                        Top Results:
                      </label>
                      <select
                        value={numResults}
                        onChange={(e) => setNumResults(Number(e.target.value))}
                        className="border rounded-lg px-4 py-2 bg-background"
                      >
                        {[3, 5, 10, 15, 20].map((n) => (
                          <option key={n} value={n}>{n} candidates</option>
                        ))}
                      </select>
                    </div>

                    <Button
                      type="submit"
                      size="lg"
                      disabled={!jobDescription.trim() || currentMutation.isPending}
                      className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                    >
                      {currentMutation.isPending ? (
                        <>
                          <Loader2 className="h-5 w-5 animate-spin" />
                          {searchMethod === 'agent' ? 'AI Agent Thinking...' : 'Searching...'}
                        </>
                      ) : (
                        <>
                          {searchMethod === 'agent' ? <Brain className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
                          Find Best Candidates
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>

            {/* Database Stats */}
            {stats && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Database Overview
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Total Candidates</span>
                      <span className="text-2xl font-bold">{stats.total_candidates}</span>
                    </div>
                    <Separator />
                    <div>
                      <span className="text-sm font-medium mb-2 block">Top Skills in Database</span>
                      <div className="flex flex-wrap gap-2">
                        {stats.top_skills.slice(0, 15).map((skill, i) => (
                          <Badge key={i} variant="secondary">{skill}</Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Error Display */}
            {currentMutation.isError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>
                  {currentMutation.error.message}
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results" className="space-y-6">
            {currentMutation.data && (
              <>
                {/* Agent Reasoning - Only show for AI agent search */}
                {searchMethod === 'agent' && currentMutation.data.agent_reasoning && (
                  <Card className="shadow-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-blue-900">
                        <Brain className="h-6 w-6" />
                        AI Agent Analysis
                      </CardTitle>
                      <CardDescription>
                        The agent's reasoning process and candidate selection criteria
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="prose prose-sm max-w-none bg-white/80 p-4 rounded-lg">
                        <p className="whitespace-pre-wrap text-gray-700">
                          {currentMutation.data.agent_reasoning}
                        </p>
                      </div>

                      <Separator />

                      <div className="flex flex-wrap gap-6 text-sm">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                          <span className="font-medium">
                            {currentMutation.data.total_found} candidates found
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-blue-600" />
                          <span className="font-medium">
                            Query time: {currentMutation.data.query_time_seconds}s
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Brain className="h-4 w-4 text-indigo-600" />
                          <span className="font-medium">
                            AI Agent reasoning applied
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Search Results Header - Show for both methods */}
                {searchMethod === 'fast' && (
                  <Card className="shadow-xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-emerald-50">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-green-900">
                        <Zap className="h-6 w-6" />
                        Fast Vector Search Results
                      </CardTitle>
                      <CardDescription>
                        Candidates matched using semantic similarity and vector search
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-6 text-sm">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                          <span className="font-medium">
                            {currentMutation.data.total_found} candidates found
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4 text-blue-600" />
                          <span className="font-medium">
                            Query time: {currentMutation.data.query_time_seconds}s
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Zap className="h-4 w-4 text-emerald-600" />
                          <span className="font-medium">
                            Vector similarity matching
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Candidates */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                      <TrendingUp className="h-6 w-6" />
                      Top Candidates
                    </h2>
                    <Button
                      variant="outline"
                      onClick={() => setActiveTab('search')}
                      className="gap-2"
                    >
                      <Search className="h-4 w-4" />
                      New Search
                    </Button>
                  </div>

                  <div className="grid gap-4">
                    {currentMutation.data.candidates.map((candidate, index) => (
                      <Card
                        key={index}
                        className="hover:shadow-2xl transition-all duration-300 border-2 hover:border-blue-300 group"
                      >
                        <CardHeader className="pb-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="space-y-2 flex-1">
                              <div className="flex items-center gap-3">
                                <div className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-400 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                                  {candidate.name.charAt(0)}
                                </div>
                                <div>
                                  <CardTitle className="flex items-center gap-2 text-xl group-hover:text-blue-600 transition-colors">
                                    {candidate.name}
                                  </CardTitle>
                                  <div className="flex flex-wrap gap-3 text-sm text-muted-foreground mt-1">
                                    {candidate.email && (
                                      <span className="flex items-center gap-1">
                                        <Mail className="h-3 w-3" />
                                        {candidate.email}
                                      </span>
                                    )}
                                    {candidate.location && (
                                      <span className="flex items-center gap-1">
                                        <MapPin className="h-3 w-3" />
                                        {candidate.location}
                                      </span>
                                    )}
                                    <span className="flex items-center gap-1">
                                      <Briefcase className="h-3 w-3" />
                                      {candidate.years_experience} years experience
                                    </span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {candidate.match_score > 0 && (
                              <div className="flex flex-col items-end gap-2">
                                <Badge
                                  variant="default"
                                  className="text-lg px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700"
                                >
                                  {(candidate.match_score * 100).toFixed(0)}% Match
                                </Badge>
                                <Progress
                                  value={candidate.match_score * 100}
                                  className="w-32 h-2"
                                />
                              </div>
                            )}
                          </div>
                        </CardHeader>

                        <CardContent className="space-y-4">
                          {candidate.summary && (
                            <div className="bg-slate-50 p-4 rounded-lg border">
                              <p className="text-sm leading-relaxed text-gray-700">{candidate.summary}</p>
                            </div>
                          )}

                          <div className="grid md:grid-cols-2 gap-4">
                            {candidate.skills.length > 0 && (
                              <div>
                                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                                  <Sparkles className="h-3 w-3" />
                                  Skills
                                </h4>
                                <div className="flex flex-wrap gap-2">
                                  {candidate.skills.map((skill, i) => (
                                    <Badge key={i} variant="secondary" className="px-3 py-1">
                                      {skill}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}

                            {candidate.technical_skills.length > 0 && (
                              <div>
                                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1">
                                  <Zap className="h-3 w-3" />
                                  Technical Skills
                                </h4>
                                <div className="flex flex-wrap gap-2">
                                  {candidate.technical_skills.map((skill, i) => (
                                    <Badge key={i} variant="outline" className="px-3 py-1">
                                      {skill}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Meeting Request Section */}
                          <div className="flex items-center gap-4 pt-4 border-t">
                            <div className="flex-1">
                              {editingEmail === candidate.name ? (
                                <div className="space-y-2">
                                  <Label htmlFor={`email-${candidate.name}`} className="text-sm font-medium">
                                    Email Address
                                  </Label>
                                  <div className="flex gap-2">
                                    <Input
                                      id={`email-${candidate.name}`}
                                      type="email"
                                      placeholder="Enter candidate email"
                                      value={emailInput}
                                      onChange={(e) => setEmailInput(e.target.value)}
                                      className="flex-1"
                                    />
                                    <Button
                                      variant="outline"
                                      onClick={handleCancelEdit}
                                      className="gap-2"
                                    >
                                      <X className="h-4 w-4" />
                                      Cancel
                                    </Button>
                                    <Button
                                      onClick={() => handleSendMeetingRequest(candidate)}
                                      disabled={meetingRequestLoading === candidate.name}
                                      className="gap-2 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                                    >
                                      {meetingRequestLoading === candidate.name ? (
                                        <>
                                          <Loader2 className="h-4 w-4 animate-spin" />
                                          Sending...
                                        </>
                                      ) : (
                                        <>
                                          <Send className="h-4 w-4" />
                                          Send Request
                                        </>
                                      )}
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center gap-2">
                                  <Button
                                    variant="outline"
                                    onClick={() => handleEditEmail(candidate)}
                                    className="gap-2"
                                  >
                                    <Edit3 className="h-4 w-4" />
                                    Edit Email
                                  </Button>
                                  <Button
                                    onClick={() => handleSendMeetingRequest(candidate)}
                                    disabled={meetingRequestLoading === candidate.name || !candidate.email}
                                    className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
                                  >
                                    {meetingRequestLoading === candidate.name ? (
                                      <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        Sending...
                                      </>
                                    ) : (
                                      <>
                                        <Send className="h-4 w-4" />
                                        Send Meeting Request
                                      </>
                                    )}
                                  </Button>
                                </div>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>
      </div>
      <ConditionalWebSocketLogs/>
    </div>
  );
}
