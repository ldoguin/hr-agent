/**
 * Capella AI Toggle Button Component
 * Button to toggle Capella AI service status and show current status
 */

import { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Brain, BrainCog, Loader2 } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { hrAgentClient } from '@/api/hrAgentClient';

export const CapellaAIToggle = () => {
  const [status, setStatus] = useState<{
    enabled: boolean;
    available: boolean;
    message: string;
    loading: boolean;
    error: string | null;
  }>({
    enabled: false,
    available: false,
    message: 'Loading...',
    loading: true,
    error: null,
  });

  // Fetch initial status
  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      setStatus(prev => ({ ...prev, loading: true, error: null }));
      const response = await hrAgentClient.getCapellaAIStatus();
      setStatus({
        enabled: true,
        available: true,
        message: "response.message",
        loading: false,
        error: null,
      });
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch status',
        message: 'Error loading status',
      }));
    }
  };

  const toggleStatus = async () => {
    try {
      setStatus(prev => ({ ...prev, loading: true, error: null }));
      const response = await hrAgentClient.toggleCapellaAI();

      // Refresh status after toggle
      await fetchStatus();

      // Show temporary success message
      setTimeout(() => {
        setStatus(prev => ({
          ...prev,
          message: "response.message,"
        }));
      }, 500);
    } catch (error) {
      setStatus(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to toggle status',
      }));
    }
  };

  const getStatusColor = () => {
    if (status.loading) return 'text-yellow-500';
    if (status.error) return 'text-red-500';
    if (status.enabled && status.available) return 'text-green-500';
    if (status.enabled && !status.available) return 'text-orange-500';
    return 'text-gray-500';
  };

  const getStatusText = () => {
    if (status.loading) return 'Loading...';
    if (status.error) return `Error: ${status.error}`;
    if (status.enabled && status.available) return 'Capella AI: ON';
    if (status.enabled && !status.available) return 'Capella AI: ON (Unavailable)';
    return 'Capella AI: OFF';
  };

  const getTooltipContent = () => {
    if (status.loading) {
      return (
        <div className="text-sm">
          <p>🔄 Loading Capella AI status...</p>
        </div>
      );
    }

    if (status.error) {
      return (
        <div className="text-sm">
          <p>❌ Error: {status.error}</p>
          <p className="text-xs text-muted-foreground mt-1">Click to retry</p>
        </div>
      );
    }

    if (status.enabled && status.available) {
      return (
        <div className="text-sm">
          <p>🤖 Capella AI is ENABLED and AVAILABLE</p>
          <p className="text-xs text-muted-foreground mt-1">Click to disable</p>
        </div>
      );
    }

    if (status.enabled && !status.available) {
      return (
        <div className="text-sm">
          <p>🤖 Capella AI is ENABLED but UNAVAILABLE</p>
          <p className="text-xs text-muted-foreground mt-1">Fallback to OpenAI</p>
          <p className="text-xs text-muted-foreground mt-1">Click to disable</p>
        </div>
      );
    }

    return (
      <div className="text-sm">
        <p>🤖 Capella AI is DISABLED</p>
        <p className="text-xs text-muted-foreground mt-1">Using OpenAI fallback</p>
        <p className="text-xs text-muted-foreground mt-1">Click to enable</p>
      </div>
    );
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            onClick={toggleStatus}
            disabled={status.loading}
            className="h-8 px-2"
          >
            {status.loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                <span className="hidden sm:inline">Loading...</span>
              </>
            ) : status.error ? (
              <>
                <BrainCog className="w-4 h-4 mr-1 text-red-500" />
                <span className="hidden sm:inline">Error</span>
              </>
            ) : status.enabled ? (
              <>
                <Brain className={`w-4 h-4 mr-1 ${getStatusColor()}`} />
                <span className="hidden sm:inline">{getStatusText()}</span>
              </>
            ) : (
              <>
                <BrainCog className="w-4 h-4 mr-1" />
                <span className="hidden sm:inline">{getStatusText()}</span>
              </>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {getTooltipContent()}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
