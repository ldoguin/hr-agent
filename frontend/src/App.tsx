import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import UploadResumes from "./pages/UploadResumes";
import AgentMatch from "./pages/AgentMatch";
import TraceDashboard from "./pages/TraceDashboard";
import Applications from "./pages/Applications";
import Meetings from "./pages/Meetings";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/upload-resumes" element={<UploadResumes />} />
          <Route path="/agent-match" element={<AgentMatch />} />
          <Route path="/traces" element={<TraceDashboard />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/meetings" element={<Meetings />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
