import { NavLink } from "@/components/NavLink";
import { Search, Upload, Sparkles, Activity, FileText, CalendarDays } from "lucide-react";

export const Navigation = () => {
  return (
    <nav className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-foreground">Agentic HR Sourcing</h2>
          </div>

          <div className="flex items-center gap-2">
            <NavLink
              to="/"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <Search className="w-4 h-4" />
              <span>Search Candidates</span>
            </NavLink>

            <NavLink
              to="/agent-match"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <Sparkles className="w-4 h-4" />
              <span>AI Agent Match</span>
            </NavLink>

            <NavLink
              to="/upload-resumes"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <Upload className="w-4 h-4" />
              <span>Upload Resumes</span>
            </NavLink>
            <NavLink
              to="/traces"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <Activity className="w-4 h-4" />
              <span>Traces</span>
            </NavLink>

            <NavLink
              to="/applications"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <FileText className="w-4 h-4" />
              <span>Applications</span>
            </NavLink>

            <NavLink
              to="/meetings"
              className="flex items-center gap-2 px-4 py-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
              activeClassName="bg-accent text-foreground font-medium"
            >
              <CalendarDays className="w-4 h-4" />
              <span>Meetings</span>
            </NavLink>

          </div>
        </div>
      </div>
    </nav>
  );
};
