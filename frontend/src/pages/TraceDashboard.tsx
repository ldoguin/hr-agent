import { useState, useEffect, useCallback } from "react";
import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  hrAgentClient,
  TraceSession,
  TraceLog,
  TraceLogContent,
  ConversationGrade,
} from "@/api/hrAgentClient";
import {
  RefreshCw,
  ChevronRight,
  MessageSquare,
  Wrench,
  Bot,
  User,
  Zap,
  Activity,
  ClipboardList,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
  CalendarDays,
  Search,
  X,
} from "lucide-react";

// ─── helpers ─────────────────────────────────────────────────────────────────

function formatTs(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function spanLabel(names: string[]) {
  if (!names || names.length === 0) return "unknown";
  return names[names.length - 1];
}

function sessionShort(session: string) {
  return session.slice(0, 8) + "…";
}

// ─── score helpers ────────────────────────────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 9) return "text-green-400";
  if (score >= 7) return "text-lime-400";
  if (score >= 5) return "text-yellow-400";
  if (score >= 3) return "text-orange-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 9) return "bg-green-500/10 border-green-500/30";
  if (score >= 7) return "bg-lime-500/10 border-lime-500/30";
  if (score >= 5) return "bg-yellow-500/10 border-yellow-500/30";
  if (score >= 3) return "bg-orange-500/10 border-orange-500/30";
  return "bg-red-500/10 border-red-500/30";
}

function labelIcon(label: string) {
  switch (label) {
    case "excellent":  return <CheckCircle className="w-4 h-4 text-green-400" />;
    case "good":       return <CheckCircle className="w-4 h-4 text-lime-400" />;
    case "acceptable": return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
    case "poor":       return <AlertTriangle className="w-4 h-4 text-orange-400" />;
    case "failed":     return <XCircle className="w-4 h-4 text-red-400" />;
    default:           return <Star className="w-4 h-4 text-muted-foreground" />;
  }
}

// ─── content kind config ──────────────────────────────────────────────────────

type KindMeta = { label: string; color: string; icon: React.ReactNode };

function kindMeta(kind: TraceLogContent["kind"]): KindMeta {
  switch (kind) {
    case "user":            return { label: "User",        color: "bg-blue-500/10 border-blue-500/30 text-blue-400",       icon: <User className="w-3 h-3" /> };
    case "assistant":       return { label: "Assistant",   color: "bg-green-500/10 border-green-500/30 text-green-400",    icon: <Bot className="w-3 h-3" /> };
    case "tool-call":       return { label: "Tool Call",   color: "bg-orange-500/10 border-orange-500/30 text-orange-400", icon: <Wrench className="w-3 h-3" /> };
    case "tool-result":     return { label: "Tool Result", color: "bg-purple-500/10 border-purple-500/30 text-purple-400", icon: <Zap className="w-3 h-3" /> };
    case "chat-completion": return { label: "LLM",         color: "bg-yellow-500/10 border-yellow-500/30 text-yellow-400", icon: <MessageSquare className="w-3 h-3" /> };
    case "begin":           return { label: "Begin",       color: "bg-teal-500/10 border-teal-500/30 text-teal-400",       icon: <Activity className="w-3 h-3" /> };
    case "end":             return { label: "End",         color: "bg-teal-500/10 border-teal-500/30 text-teal-400",       icon: <Activity className="w-3 h-3" /> };
    default:                return { label: kind,          color: "bg-muted border-border text-muted-foreground",          icon: <Activity className="w-3 h-3" /> };
  }
}

function logSummary(content: TraceLogContent): string {
  switch (content.kind) {
    case "user":            return content.value?.slice(0, 120) ?? "";
    case "assistant":       return content.value?.slice(0, 120) ?? "";
    case "tool-call":       return `${content.tool_name}(${JSON.stringify(content.tool_args ?? {}).slice(0, 80)})`;
    case "tool-result":     return `${content.status ?? ""} — ${String(content.tool_result ?? "").slice(0, 100)}`;
    case "chat-completion": return content.output?.slice(0, 120) ?? "";
    case "begin":           return "span started";
    case "end":             return "span ended";
    default:                return JSON.stringify(content).slice(0, 120);
  }
}

// ─── LogEntry ─────────────────────────────────────────────────────────────────

function LogEntry({
  log, expanded, onToggle, grade, onGrade, grading,
}: {
  log: TraceLog;
  expanded: boolean;
  onToggle: () => void;
  grade?: ConversationGrade;
  onGrade: () => void;
  grading: boolean;
}) {
  const { content } = log;
  const meta = kindMeta(content.kind);
  return (
    <div className={`border rounded-lg p-3 transition-colors hover:bg-accent/30 ${meta.color}`}>
      <div className="flex items-start gap-2">
        <div className="mt-0.5 shrink-0 cursor-pointer" onClick={onToggle}>{meta.icon}</div>
        <div className="flex-1 min-w-0 cursor-pointer" onClick={onToggle}>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className={`text-xs px-1.5 py-0 ${meta.color}`}>{meta.label}</Badge>
            <span className="text-xs text-muted-foreground font-mono">{formatTs(log.timestamp)}</span>
            {content.kind === "tool-call" && content.tool_name && (
              <span className="text-xs font-mono font-medium">{content.tool_name}</span>
            )}
            {content.kind === "tool-result" && (
              <Badge variant="outline" className={`text-xs px-1.5 py-0 ${content.status === "error" ? "border-red-500/50 text-red-400" : "border-green-500/50 text-green-400"}`}>
                {content.status ?? "unknown"}
              </Badge>
            )}
            {grade && (
              <span className={`text-xs font-bold tabular-nums ${scoreColor(grade.score)}`} title={grade.summary}>
                {grade.score}/10
              </span>
            )}
            {grade?.stored_at && (
              <span className="text-xs text-muted-foreground/50" title={`Stored ${formatTs(grade.stored_at)}`}>saved</span>
            )}
          </div>
          <p className="text-sm mt-1 text-foreground/80 truncate">{logSummary(content)}</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost" size="sm"
            className="h-6 px-1.5 text-xs text-muted-foreground hover:text-foreground gap-1"
            onClick={e => { e.stopPropagation(); onGrade(); }}
            disabled={grading}
            title="Grade this log entry"
          >
            {grading ? (
              <><Loader2 className="w-3 h-3 animate-spin" />Grading…</>
            ) : grade ? (
              <><RefreshCw className="w-3 h-3" />Re-grade</>
            ) : (
              <><ClipboardList className="w-3 h-3" />Grade</>
            )}
          </Button>
          <ChevronRight
            className={`w-4 h-4 text-muted-foreground transition-transform cursor-pointer ${expanded ? "rotate-90" : ""}`}
            onClick={onToggle}
          />
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-border/50">
          {grade && (
            <div className={`rounded-md border p-2 mb-3 text-xs ${scoreBg(grade.score)}`}>
              <div className="flex items-center gap-1.5 mb-1">
                {labelIcon(grade.label)}
                <span className={`font-semibold capitalize ${scoreColor(grade.score)}`}>{grade.label} ({grade.score}/10)</span>
              </div>
              {grade.summary && <p className="text-foreground/70">{grade.summary}</p>}
              {grade.off_topic && <p className="text-red-400 mt-1">⚠ Off-topic detected</p>}
            </div>
          )}
          <pre className="text-xs font-mono whitespace-pre-wrap break-all text-foreground/70 max-h-64 overflow-y-auto">
            {JSON.stringify(content, null, 2)}
          </pre>
          {log.annotations && (
            <div className="mt-2">
              <span className="text-xs text-muted-foreground">annotations: </span>
              <pre className="text-xs font-mono text-foreground/60">{JSON.stringify(log.annotations, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── GradePanel ───────────────────────────────────────────────────────────────

function GradePanel({ grade, onClose }: { grade: ConversationGrade; onClose: () => void }) {
  return (
    <div className={`rounded-lg border p-4 ${scoreBg(grade.score)}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`text-4xl font-bold tabular-nums ${scoreColor(grade.score)}`}>
            {grade.score}<span className="text-lg text-muted-foreground">/10</span>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              {labelIcon(grade.label)}
              <span className="font-semibold capitalize text-foreground">{grade.label}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-0.5 max-w-lg">{grade.summary}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} className="shrink-0 text-muted-foreground">✕</Button>
      </div>

      {(grade.strengths.length > 0 || grade.issues.length > 0) && (
        <div className="mt-3 grid grid-cols-2 gap-3">
          {grade.strengths.length > 0 && (
            <div>
              <div className="text-xs font-medium text-green-400 mb-1.5 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Strengths
              </div>
              <ul className="space-y-1">
                {grade.strengths.map((s, i) => (
                  <li key={i} className="text-xs text-foreground/70 flex gap-1.5">
                    <span className="text-green-400 shrink-0">·</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {grade.issues.length > 0 && (
            <div>
              <div className="text-xs font-medium text-orange-400 mb-1.5 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> Issues
              </div>
              <ul className="space-y-1">
                {grade.issues.map((s, i) => (
                  <li key={i} className="text-xs text-foreground/70 flex gap-1.5">
                    <span className="text-orange-400 shrink-0">·</span>{s}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {grade.off_topic && grade.anomalies.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <div className="text-xs font-medium text-red-400 mb-1.5 flex items-center gap-1">
            <XCircle className="w-3 h-3" /> Off-topic / anomalies detected
          </div>
          <ul className="space-y-1">
            {grade.anomalies.map((a, i) => (
              <li key={i} className="text-xs text-foreground/70 flex gap-1.5">
                <span className="text-red-400 shrink-0">·</span>{a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {grade.off_topic && grade.anomalies.length === 0 && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <div className="text-xs font-medium text-red-400 flex items-center gap-1">
            <XCircle className="w-3 h-3" /> Off-topic content detected
          </div>
        </div>
      )}

      {grade.error && (
        <p className="mt-2 text-xs text-red-400">Error: {grade.error}</p>
      )}
    </div>
  );
}

// ─── SessionPanel ─────────────────────────────────────────────────────────────

function SessionPanel({
  session, selected, grade, onClick,
}: {
  session: TraceSession;
  selected: boolean;
  grade?: ConversationGrade;
  onClick: () => void;
}) {
  const toolCalls = session.logs.filter(l => l.content.kind === "tool-call").length;
  const hasError  = session.logs.some(l => l.content.kind === "tool-result" && l.content.status === "error");

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2.5 rounded-lg border transition-colors ${
        selected
          ? "bg-primary/10 border-primary/40 text-foreground"
          : "bg-background border-border hover:bg-accent/40 text-muted-foreground hover:text-foreground"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-mono font-medium truncate">{spanLabel(session.span_name)}</span>
        <div className="flex items-center gap-1 shrink-0">
          {grade && (
            <span className={`text-xs font-bold tabular-nums ${scoreColor(grade.score)}`}>
              {grade.score}/10
            </span>
          )}
          {grade?.off_topic && <Badge variant="destructive" className="text-xs px-1 py-0">⚠ off-topic</Badge>}
          {hasError && <Badge variant="destructive" className="text-xs px-1 py-0">err</Badge>}
        </div>
      </div>
      <div className="text-xs text-muted-foreground mt-0.5">{formatTs(session.started_at)}</div>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-xs text-muted-foreground">{session.logs.length} logs</span>
        {toolCalls > 0 && <span className="text-xs text-orange-400">{toolCalls} tools</span>}
      </div>
      <div className="text-xs font-mono text-muted-foreground/60 mt-0.5">{sessionShort(session.session)}</div>
    </button>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

const TraceDashboard = () => {
  const [sessions, setSessions]         = useState<TraceSession[]>([]);
  const [total, setTotal]               = useState(0);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [selectedSession, setSelected]  = useState<TraceSession | null>(null);
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh]   = useState(false);
  // session-level grades keyed by session ID
  const [grades, setGrades]             = useState<Record<string, ConversationGrade>>({});
  const [grading, setGrading]           = useState<string | null>(null);
  // per-log grades keyed by log identifier
  const [logGrades, setLogGrades]       = useState<Record<string, ConversationGrade>>({});
  const [gradingLog, setGradingLog]     = useState<string | null>(null);
  const [selectedDate, setSelectedDate]       = useState<string>("");  // YYYY-MM-DD or ""
  const [sessionFilter, setSessionFilter]     = useState<string>("");  // partial or full session ID
  const [sessionFilterInput, setSessionFilterInput] = useState<string>(""); // debounced input

  // Apply session filter on Enter or after a short pause
  const applySessionFilter = (value: string) => {
    setSessionFilter(value.trim());
    setSelected(null);
  };

  const fetchTraces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Pass session filter only when it looks like a full UUID (36 chars);
      // partial IDs are filtered client-side from the full result set.
      const sessionParam = sessionFilter.length === 36 ? sessionFilter : undefined;
      const data = await hrAgentClient.getTraces(50, 0, sessionParam, selectedDate || undefined);
      if (data.error) setError(data.error);
      const sorted = [...data.sessions].sort((a, b) =>
        (b.started_at ?? "").localeCompare(a.started_at ?? "")
      );
      setSessions(sorted);
      setTotal(data.total);
      if (selectedSession) {
        const updated = sorted.find(s => s.session === selectedSession.session);
        if (updated) setSelected(updated);
      }
      // Seed stored grades from the API response
      const seedSessionGrades: Record<string, ConversationGrade> = {};
      const seedLogGrades: Record<string, ConversationGrade> = {};
      for (const s of sorted) {
        if (s.stored_grade) seedSessionGrades[s.session] = s.stored_grade;
        if (s.log_grades) Object.assign(seedLogGrades, s.log_grades);
      }
      setGrades(prev => ({ ...seedSessionGrades, ...prev }));
      setLogGrades(prev => ({ ...seedLogGrades, ...prev }));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [selectedSession]);

  useEffect(() => { fetchTraces(); }, [selectedDate, sessionFilter]);

  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchTraces, 5000);
    return () => clearInterval(id);
  }, [autoRefresh, fetchTraces]);

  async function handleGradeLog(session: TraceSession, logId: string) {
    setGradingLog(logId);
    try {
      const result = await hrAgentClient.gradeLog(session.session, logId);
      setLogGrades(prev => ({ ...prev, [logId]: result }));
    } catch (e) {
      setLogGrades(prev => ({
        ...prev,
        [logId]: {
          session: session.session, log_id: logId, grade_scope: "log",
          score: 0, label: "failed", summary: "", issues: [], strengths: [],
          off_topic: false, anomalies: [], error: String(e),
        },
      }));
    } finally {
      setGradingLog(null);
    }
  }

  async function handleGrade(session: TraceSession) {
    setGrading(session.session);
    try {
      const result = await hrAgentClient.gradeSession(session.session);
      setGrades(prev => ({ ...prev, [session.session]: result }));
    } catch (e) {
      setGrades(prev => ({
        ...prev,
        [session.session]: {
          session: session.session,
          score: 0,
          label: "failed",
          summary: "",
          issues: [],
          strengths: [],
          error: String(e),
        },
      }));
    } finally {
      setGrading(null);
    }
  }

  function toggleLog(id: string) {
    setExpandedLogs(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  // Client-side filter for partial session ID matches
  const visibleSessions = sessionFilter
    ? sessions.filter(s => s.session.toLowerCase().includes(sessionFilter.toLowerCase()))
    : sessions;

  const timelineLogs  = selectedSession
    ? [...selectedSession.logs].sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? ""))
    : [];
  const toolCallCount = timelineLogs.filter(l => l.content.kind === "tool-call").length;
  const llmCallCount  = timelineLogs.filter(l => l.content.kind === "chat-completion").length;
  const hasError      = timelineLogs.some(l => l.content.kind === "tool-result" && l.content.status === "error");
  const currentGrade  = selectedSession ? grades[selectedSession.session] : undefined;
  const isGrading     = selectedSession ? grading === selectedSession.session : false;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Navigation />

      <div className="flex-1 flex flex-col container mx-auto px-4 py-6 gap-4">
        {/* Header */}
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Agent Traces</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {visibleSessions.length} of {total} session{total !== 1 ? "s" : ""}
              {selectedDate && <span className="ml-1">on {selectedDate}</span>}
              {sessionFilter && <span className="ml-1 font-mono">· "{sessionFilter}"</span>}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Session ID search */}
            <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-2 h-9">
              <Search className="w-4 h-4 text-muted-foreground shrink-0" />
              <input
                type="text"
                placeholder="Session ID…"
                value={sessionFilterInput}
                onChange={e => setSessionFilterInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && applySessionFilter(sessionFilterInput)}
                onBlur={() => applySessionFilter(sessionFilterInput)}
                className="bg-transparent text-sm text-foreground outline-none w-40 placeholder:text-muted-foreground/50 font-mono"
              />
              {sessionFilterInput && (
                <button onClick={() => { setSessionFilterInput(""); applySessionFilter(""); }} className="text-muted-foreground hover:text-foreground">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {/* Date filter */}
            <div className="flex items-center gap-1.5 rounded-md border border-border bg-background px-2 h-9">
              <CalendarDays className="w-4 h-4 text-muted-foreground shrink-0" />
              <input
                type="date"
                value={selectedDate}
                onChange={e => { setSelectedDate(e.target.value); setSelected(null); }}
                className="bg-transparent text-sm text-foreground outline-none w-36 [color-scheme:dark]"
              />
              {selectedDate && (
                <button onClick={() => { setSelectedDate(""); setSelected(null); }} className="text-muted-foreground hover:text-foreground">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <Button
              variant="outline" size="sm"
              onClick={() => setAutoRefresh(v => !v)}
              className={autoRefresh ? "border-green-500/50 text-green-400" : ""}
            >
              <Activity className="w-4 h-4 mr-1.5" />
              {autoRefresh ? "Live" : "Auto-refresh"}
            </Button>
            <Button variant="outline" size="sm" onClick={fetchTraces} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 flex gap-4 min-h-0" style={{ height: "calc(100vh - 200px)" }}>

          {/* Session list */}
          <div className="w-72 shrink-0 flex flex-col gap-2">
            <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider px-1">Sessions</div>
            <ScrollArea className="flex-1 rounded-lg border border-border bg-card">
              <div className="p-2 flex flex-col gap-1.5">
                {loading && sessions.length === 0 &&
                  Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                  ))
                }
                {!loading && sessions.length === 0 && (
                  <div className="text-center text-sm text-muted-foreground py-8">
                    No traces yet.<br />Run an agent action to see traces here.
                  </div>
                )}
                {visibleSessions.map(s => (
                  <SessionPanel
                    key={s.session}
                    session={s}
                    selected={selectedSession?.session === s.session}
                    grade={grades[s.session]}
                    onClick={() => { setSelected(s); setExpandedLogs(new Set()); }}
                  />
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* Detail panel */}
          <div className="flex-1 flex flex-col gap-3 min-w-0">
            {!selectedSession ? (
              <div className="flex-1 flex items-center justify-center rounded-lg border border-dashed border-border text-muted-foreground text-sm">
                Select a session to inspect its logs
              </div>
            ) : (
              <>
                {/* Session header */}
                <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-foreground">{spanLabel(selectedSession.span_name)}</span>
                      {hasError && <Badge variant="destructive">error</Badge>}
                    </div>
                    <div className="text-xs font-mono text-muted-foreground mt-0.5 break-all">{selectedSession.session}</div>
                    <div className="text-xs text-muted-foreground mt-1">{formatTs(selectedSession.started_at)}</div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="flex gap-3 text-center">
                      <div>
                        <div className="text-lg font-bold text-foreground">{timelineLogs.length}</div>
                        <div className="text-xs text-muted-foreground">logs</div>
                      </div>
                      <div>
                        <div className="text-lg font-bold text-orange-400">{toolCallCount}</div>
                        <div className="text-xs text-muted-foreground">tools</div>
                      </div>
                      <div>
                        <div className="text-lg font-bold text-yellow-400">{llmCallCount}</div>
                        <div className="text-xs text-muted-foreground">LLM</div>
                      </div>
                    </div>
                    {currentGrade && (
                      <div className={`rounded-md border px-3 py-1 text-center ${scoreBg(currentGrade.score)}`}>
                        <div className={`text-lg font-bold tabular-nums leading-none ${scoreColor(currentGrade.score)}`}>
                          {currentGrade.score}<span className="text-xs text-muted-foreground">/10</span>
                        </div>
                        <div className="text-xs text-muted-foreground capitalize mt-0.5">{currentGrade.label}</div>
                      </div>
                    )}
                    <Button
                      size="sm"
                      variant={currentGrade ? "outline" : "default"}
                      onClick={() => handleGrade(selectedSession)}
                      disabled={isGrading}
                      className="shrink-0"
                    >
                      {isGrading ? (
                        <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" />Grading…</>
                      ) : currentGrade ? (
                        <><RefreshCw className="w-4 h-4 mr-1.5" />Re-grade</>
                      ) : (
                        <><ClipboardList className="w-4 h-4 mr-1.5" />Grade</>
                      )}
                    </Button>
                  </div>
                </div>

                {/* Grade result */}
                {currentGrade && (
                  <GradePanel
                    grade={currentGrade}
                    onClose={() => setGrades(prev => {
                      const next = { ...prev };
                      delete next[selectedSession.session];
                      return next;
                    })}
                  />
                )}

                {/* Timeline */}
                <ScrollArea className="flex-1 rounded-lg border border-border bg-card">
                  <div className="p-3 flex flex-col gap-2">
                    {timelineLogs.map(log => (
                      <LogEntry
                        key={log.identifier}
                        log={log}
                        expanded={expandedLogs.has(log.identifier)}
                        onToggle={() => toggleLog(log.identifier)}
                        grade={logGrades[log.identifier]}
                        onGrade={() => handleGradeLog(selectedSession, log.identifier)}
                        grading={gradingLog === log.identifier}
                      />
                    ))}
                  </div>
                </ScrollArea>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TraceDashboard;
