import { useState, useEffect, useCallback } from "react";
import { Navigation } from "@/components/Navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { hrAgentClient, Meeting } from "@/api/hrAgentClient";
import { RefreshCw, CalendarDays, Clock, Timer } from "lucide-react";

function formatDatetime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function isUpcoming(start_time: string) {
  try { return new Date(start_time) > new Date(); } catch { return false; }
}

function applicationId(meeting_id: string) {
  return meeting_id.replace(/^application::/, "");
}

const Meetings = () => {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await hrAgentClient.listMeetings();
      setMeetings(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchMeetings(); }, [fetchMeetings]);

  const upcoming = meetings.filter((m) => isUpcoming(m.start_time));
  const past = meetings.filter((m) => !isUpcoming(m.start_time));

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <div className="container mx-auto px-4 py-6 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Scheduled Meetings</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {loading
                ? "Loading…"
                : `${upcoming.length} upcoming · ${past.length} past`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchMeetings} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))}
          </div>
        ) : meetings.length === 0 ? (
          <div className="rounded-lg border border-border bg-card px-6 py-12 text-center text-muted-foreground">
            No meetings scheduled yet.
          </div>
        ) : (
          <ScrollArea className="h-[calc(100vh-200px)]">
            <div className="space-y-6 pr-2">
              {upcoming.length > 0 && (
                <section>
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Upcoming
                  </h2>
                  <div className="space-y-3">
                    {upcoming.map((m, i) => (
                      <MeetingCard key={`${m.meeting_id}-${i}`} meeting={m} />
                    ))}
                  </div>
                </section>
              )}
              {past.length > 0 && (
                <section>
                  <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Past
                  </h2>
                  <div className="space-y-3 opacity-60">
                    {past.map((m, i) => (
                      <MeetingCard key={`${m.meeting_id}-${i}`} meeting={m} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
};

function MeetingCard({ meeting }: { meeting: Meeting }) {
  const upcoming = isUpcoming(meeting.start_time);
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <CalendarDays className="w-4 h-4 text-muted-foreground shrink-0" />
            <span className="font-semibold text-foreground">
              {formatDatetime(meeting.start_time)}
            </span>
            <Badge variant={upcoming ? "default" : "secondary"} className="text-xs">
              {upcoming ? "upcoming" : "past"}
            </Badge>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(meeting.start_time)} – {formatTime(meeting.end_time)}
            </span>
            {meeting.duration_minutes && (
              <span className="flex items-center gap-1">
                <Timer className="w-3 h-3" />
                {meeting.duration_minutes} min
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="mt-1.5 text-xs font-mono text-muted-foreground/40 truncate">
        {applicationId(meeting.meeting_id)}
      </div>
    </div>
  );
}

export default Meetings;
