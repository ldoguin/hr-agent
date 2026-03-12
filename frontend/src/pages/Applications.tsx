import { useState, useEffect, useCallback } from "react";
import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  hrAgentClient, Application, PendingEmail, AutoSendSettings, ConversationGrade,
} from "@/api/hrAgentClient";
import {
  RefreshCw, User, Briefcase, Mail, Clock, Send, Loader2, Zap, ZapOff,
  ClipboardList, CheckCircle, AlertTriangle, XCircle, Star, ChevronDown, ChevronUp,
} from "lucide-react";

// ─── helpers ─────────────────────────────────────────────────────────────────

function formatTs(iso?: string) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
}

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "email_sent": return "secondary";
    case "scheduled":  return "default";
    case "cancelled":  return "destructive";
    default:           return "outline";
  }
}

function scoreColor(score: number) {
  if (score >= 9) return "text-green-400";
  if (score >= 7) return "text-lime-400";
  if (score >= 5) return "text-yellow-400";
  if (score >= 3) return "text-orange-400";
  return "text-red-400";
}

function scoreBg(score: number) {
  if (score >= 9) return "bg-green-500/10 border-green-500/30";
  if (score >= 7) return "bg-lime-500/10 border-lime-500/30";
  if (score >= 5) return "bg-yellow-500/10 border-yellow-500/30";
  if (score >= 3) return "bg-orange-500/10 border-orange-500/30";
  return "bg-red-500/10 border-red-500/30";
}

function labelIcon(label: string) {
  switch (label) {
    case "excellent":  return <CheckCircle className="w-3.5 h-3.5 text-green-400" />;
    case "good":       return <CheckCircle className="w-3.5 h-3.5 text-lime-400" />;
    case "acceptable": return <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />;
    case "poor":       return <AlertTriangle className="w-3.5 h-3.5 text-orange-400" />;
    case "failed":     return <XCircle className="w-3.5 h-3.5 text-red-400" />;
    default:           return <Star className="w-3.5 h-3.5 text-muted-foreground" />;
  }
}

// ─── Grade chip (collapsed summary) ──────────────────────────────────────────

function GradeChip({ grade }: { grade: ConversationGrade }) {
  return (
    <div className={`flex items-center gap-1 rounded px-1.5 py-0.5 border text-xs ${scoreBg(grade.score)}`}>
      {labelIcon(grade.label)}
      <span className={`font-bold tabular-nums ${scoreColor(grade.score)}`}>{grade.score}/10</span>
    </div>
  );
}

// ─── Grade panel (expanded detail) ───────────────────────────────────────────

function GradeDetail({ grade }: { grade: ConversationGrade }) {
  return (
    <div className={`rounded-md border p-3 text-xs space-y-1.5 ${scoreBg(grade.score)}`}>
      <div className="flex items-center gap-1.5">
        {labelIcon(grade.label)}
        <span className={`font-semibold capitalize ${scoreColor(grade.score)}`}>
          {grade.label} ({grade.score}/10)
        </span>
      </div>
      {grade.summary && <p className="text-foreground/70">{grade.summary}</p>}
      {grade.off_topic && grade.anomalies.length > 0 && (
        <ul className="text-red-400 space-y-0.5">
          {grade.anomalies.map((a, i) => <li key={i}>⚠ {a}</li>)}
        </ul>
      )}
      {grade.issues.length > 0 && (
        <ul className="text-orange-300/80 space-y-0.5">
          {grade.issues.map((s, i) => <li key={i}>• {s}</li>)}
        </ul>
      )}
      {grade.strengths.length > 0 && (
        <ul className="text-green-300/80 space-y-0.5">
          {grade.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}
        </ul>
      )}
    </div>
  );
}

// ─── Grade button + result for the thread ────────────────────────────────────

function ThreadGradeSection({ applicationId, hasSession }: { applicationId: string; hasSession: boolean }) {
  const [grade, setGrade] = useState<ConversationGrade | null>(null);
  const [grading, setGrading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Try to load existing grade on mount
  useEffect(() => {
    if (!hasSession) return;
    hrAgentClient.getApplicationGrade(applicationId)
      .then(setGrade)
      .catch(() => {}); // 404 = not graded yet, that's fine
  }, [applicationId, hasSession]);

  const handleGrade = async () => {
    setGrading(true);
    setError(null);
    try {
      const result = await hrAgentClient.gradeApplication(applicationId);
      setGrade(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setGrading(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">Email thread grade</span>
        {hasSession ? (
          <Button size="sm" variant={grade ? "outline" : "default"} onClick={handleGrade} disabled={grading}
            className="h-6 text-xs px-2 gap-1">
            {grading
              ? <><Loader2 className="w-3 h-3 animate-spin" />Grading…</>
              : grade
                ? <><RefreshCw className="w-3 h-3" />Re-grade</>
                : <><ClipboardList className="w-3 h-3" />Grade</>
            }
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">No session linked</span>
        )}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {grade && <GradeDetail grade={grade} />}
    </div>
  );
}

// ─── Pending email panel ──────────────────────────────────────────────────────

function PendingEmailPanel({ applicationId, onSent }: { applicationId: string; onSent: () => void }) {
  const [email, setEmail] = useState<PendingEmail | null>(null);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    hrAgentClient.getPendingEmail(applicationId)
      .then((e) => { if (!cancelled) { setEmail(e); setText(e.text); } })
      .catch(() => { if (!cancelled) setEmail(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [applicationId]);

  const handleSave = async () => {
    setSaving(true); setError(null);
    try {
      const updated = await hrAgentClient.updatePendingEmail(applicationId, text);
      setEmail(updated); setDirty(false);
    } catch (e) { setError(String(e)); }
    finally { setSaving(false); }
  };

  const handleSend = async () => {
    if (dirty) await handleSave();
    setSending(true); setError(null);
    try { await hrAgentClient.sendPendingEmail(applicationId); onSent(); }
    catch (e) { setError(String(e)); }
    finally { setSending(false); }
  };

  if (loading) return <Skeleton className="h-20 w-full rounded-md" />;
  if (!email) return (
    <p className="text-xs text-muted-foreground italic">No pending email.</p>
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
          <Mail className="w-3.5 h-3.5 text-yellow-400" />
          Pending email
          <Badge variant="outline" className="text-xs capitalize ml-1">{email.email_type}</Badge>
        </div>
        <span className="text-xs text-muted-foreground">To: {email.to}</span>
      </div>
      <div className="text-xs text-muted-foreground font-medium">{email.subject}</div>
      <textarea
        className="w-full rounded-md border border-border bg-background text-sm text-foreground p-2.5 font-mono resize-y min-h-[120px] focus:outline-none focus:ring-1 focus:ring-ring"
        value={text}
        onChange={(e) => { setText(e.target.value); setDirty(true); }}
        disabled={sending}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center gap-2 justify-end">
        {dirty && (
          <Button size="sm" variant="outline" onClick={handleSave} disabled={saving || sending}>
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />}Save
          </Button>
        )}
        <Button size="sm" onClick={handleSend} disabled={sending || saving}>
          {sending
            ? <><Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />Sending…</>
            : <><Send className="w-3.5 h-3.5 mr-1.5" />Send</>}
        </Button>
      </div>
    </div>
  );
}

// ─── Application card ─────────────────────────────────────────────────────────

function ApplicationCard({ app, onEmailSent }: { app: Application; onEmailSent: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [grade, setGrade] = useState<ConversationGrade | null>(null);

  // Load existing grade for the collapsed chip
  useEffect(() => {
    if (!app.session_id) return;
    hrAgentClient.getApplicationGrade(app.id)
      .then(setGrade)
      .catch(() => {});
  }, [app.id, app.session_id]);

  return (
    <div
      className="rounded-lg border border-border bg-card px-4 py-3 cursor-pointer select-none transition-colors hover:bg-accent/30"
      onClick={() => setExpanded((v) => !v)}
    >
      {/* ── Collapsed header ── */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <User className="w-4 h-4 text-muted-foreground shrink-0" />
            <span className="font-semibold text-foreground">
              {app.full_name || [app.first_name, app.last_name].filter(Boolean).join(" ") || "—"}
            </span>
            <Badge variant={statusVariant(app.status)} className="capitalize text-xs">
              {app.status.replace(/_/g, " ")}
            </Badge>
            {grade && <GradeChip grade={grade} />}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{app.email}</span>
            {app.position && <span className="flex items-center gap-1"><Briefcase className="w-3 h-3" />{app.position}</span>}
            {app.company_name && <span className="text-muted-foreground/70">{app.company_name}</span>}
          </div>
        </div>
        <div className="flex items-start gap-2 shrink-0">
          <div className="text-right text-xs text-muted-foreground">
            <div className="flex items-center gap-1 justify-end">
              <Clock className="w-3 h-3" />{formatTs(app.created_at)}
            </div>
            {app.email_sent_at && (
              <div className="mt-0.5 text-muted-foreground/60">email sent {formatTs(app.email_sent_at)}</div>
            )}
          </div>
          {expanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground mt-0.5" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground mt-0.5" />}
        </div>
      </div>

      <div className="mt-1.5 text-xs font-mono text-muted-foreground/40 truncate">{app.id}</div>

      {/* ── Expanded detail ── */}
      {expanded && (
        <div
          className="mt-3 pt-3 border-t border-border space-y-4"
          onClick={(e) => e.stopPropagation()} // prevent collapse when interacting inside
        >
          <ThreadGradeSection
            applicationId={app.id}
            hasSession={!!app.session_id}
          />
          <PendingEmailPanel
            applicationId={app.id}
            onSent={() => { setExpanded(false); onEmailSent(); }}
          />
        </div>
      )}
    </div>
  );
}

// ─── Auto-send toggle ─────────────────────────────────────────────────────────

function AutoSendToggle() {
  const [settings, setSettings] = useState<AutoSendSettings | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    hrAgentClient.getAutoSendSettings()
      .then(setSettings)
      .catch(() => setSettings({ enabled: false, min_score: 9 }));
  }, []);

  const toggle = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const updated = await hrAgentClient.setAutoSendSettings({ ...settings, enabled: !settings.enabled });
      setSettings(updated);
    } finally { setSaving(false); }
  };

  if (!settings) return null;

  return (
    <Button
      variant={settings.enabled ? "default" : "outline"} size="sm"
      onClick={toggle} disabled={saving}
      title={settings.enabled ? `Auto-send on (score ≥ ${settings.min_score})` : "Auto-send off — emails queued for review"}
    >
      {saving
        ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
        : settings.enabled ? <Zap className="w-4 h-4 mr-1.5" /> : <ZapOff className="w-4 h-4 mr-1.5" />}
      Auto-send {settings.enabled ? `≥${settings.min_score}` : "off"}
    </Button>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const Applications = () => {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchApplications = useCallback(async () => {
    setLoading(true); setError(null);
    try { setApplications(await hrAgentClient.listApplications()); }
    catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchApplications(); }, [fetchApplications]);

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto px-4 py-6 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Applications</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {loading ? "Loading…" : `${applications.length} application${applications.length !== 1 ? "s" : ""}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <AutoSendToggle />
            <Button variant="outline" size="sm" onClick={fetchApplications} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />Refresh
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-lg" />)}
          </div>
        ) : applications.length === 0 ? (
          <div className="rounded-lg border border-border bg-card px-6 py-12 text-center text-muted-foreground">
            No applications yet.
          </div>
        ) : (
          <ScrollArea className="h-[calc(100vh-200px)]">
            <div className="space-y-3 pr-2">
              {applications.map((app) => (
                <ApplicationCard key={app.id} app={app} onEmailSent={fetchApplications} />
              ))}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
};

export default Applications;
