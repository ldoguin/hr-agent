import { useState } from "react";
import { Navigation } from "@/components/Navigation";
import { FileUpload } from "@/components/FileUpload";
import { CandidateSelector } from "@/components/CandidateSelector";
import { SearchMethodSelect } from "@/components/SearchMethodSelect";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { ConditionalWebSocketLogs } from "@/components/ConditionalWebSocketLogs";

const Index = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [topK, setTopK] = useState(5);
  const [searchMethod, setSearchMethod] = useState("hybrid");
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const handleFindCandidates = async () => {
    if (!selectedFile) {
      toast({
        title: "No file selected",
        description: "Please upload a job description PDF first",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    
    // Simulate API call - replace with actual Couchbase integration
    setTimeout(() => {
      setIsLoading(false);
      toast({
        title: "Search completed",
        description: `Found ${topK} matching candidates using ${searchMethod} search`,
      });
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <div className="container mx-auto px-4 py-8 flex items-center justify-center min-h-[calc(100vh-4rem)]">
        <div className="w-full max-w-3xl space-y-8">
          {/* Header */}
          <div className="space-y-3">
            <h1 className="text-4xl font-bold text-foreground">
              Find Matching Candidates
            </h1>
            <p className="text-muted-foreground text-lg">
              Upload a Job Description PDF. We will find the best matching candidates
              using enhanced hybrid search.
            </p>
          </div>

        {/* Main Form */}
        <div className="space-y-6">
          {/* File Upload */}
          <FileUpload onFileSelect={setSelectedFile} />

          {/* Top K Candidates */}
          <CandidateSelector value={topK} onChange={setTopK} />

          {/* Search Method */}
          <SearchMethodSelect value={searchMethod} onChange={setSearchMethod} />

          {/* Find Candidates Button */}
          <Button
            onClick={handleFindCandidates}
            disabled={!selectedFile || isLoading}
            className="w-full h-12 text-base font-semibold bg-primary hover:bg-primary/90 text-primary-foreground"
          >
            {isLoading ? "Searching..." : "Find Candidates"}
          </Button>
        </div>

          {/* Footer Info */}
          <div className="text-center text-sm text-muted-foreground">
            <p>
              Powered by Couchbase vector search and AI-driven candidate matching
            </p>
          </div>
        </div>
      </div>
      <ConditionalWebSocketLogs/>
    </div>
  );
};

export default Index;
