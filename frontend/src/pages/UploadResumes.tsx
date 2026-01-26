import { useState } from "react";
import { Navigation } from "@/components/Navigation";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Upload, FileText, X, Code, Eye, EyeOff } from "lucide-react";
import { FileUpload } from "@/components/FileUpload";
import { useUploadResume } from "@/hooks/useHRAgent";
import { ConditionalWebSocketLogs } from "@/components/ConditionalWebSocketLogs";
import { ResumeUploadInfo } from "@/components/BackendInfo";

const UploadResumes = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showBackendInfo, setShowBackendInfo] = useState(false);
  const { toast } = useToast();

  // Initialize the useUploadResume hook
  const { mutate: uploadResume, isPending: isUploadingResume } = useUploadResume();
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      toast({
        title: "No files selected",
        description: "Please select at least one resume to upload",
        variant: "destructive",
      });
      return;
    }

    setIsUploading(true);

    // Upload each file using the useUploadResume hook
    // The hook handles success/error toasts and query invalidation automatically
    for (const file of selectedFiles) {
      uploadResume(file);
    }

    // Reset state after uploads are initiated
    // The actual uploads will complete asynchronously
    setSelectedFiles([]);
    setIsUploading(false);
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto space-y-8">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="space-y-3">
              <h1 className="text-4xl font-bold text-foreground">
                Upload Resumes
              </h1>
              <p className="text-muted-foreground text-lg">
                Add new candidate resumes to your database. Supported format: PDF
              </p>
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

          {/* Backend Information */}
          {showBackendInfo && (
            <div className="space-y-4">
              <div className="text-center">
                <h3 className="text-lg font-semibold text-slate-900 mb-4">
                  🔧 Backend Implementation Details
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  Click on the section below to see the backend code and technical details for resume processing.
                </p>
              </div>
              <ResumeUploadInfo />
            </div>
          )}

          {/* Upload Area */}
          <FileUpload onFileSelect={(file) => setSelectedFiles(prev => [...prev, file])} />

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">
                Selected Files ({selectedFiles.length})
              </h3>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 bg-muted/50 rounded-lg border border-border"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-primary" />
                      <div>
                        <p className="font-medium text-foreground">{file.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {(file.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeFile(index)}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upload Button */}
          <Button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || isUploading || isUploadingResume}
            className="w-full h-12 text-base font-semibold"
          >
            {(isUploading || isUploadingResume) ? "Uploading..." : `Upload ${selectedFiles.length} Resume(s)`}
          </Button>
        </div>
      </div>
      <ConditionalWebSocketLogs/>
    </div>
  );
};

export default UploadResumes;
