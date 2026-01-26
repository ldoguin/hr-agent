/**
 * WebSocket Toggle Button Component
 * Button to toggle WebSocket logs visibility via query parameter
 */

import { useState, useEffect } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Button } from './ui/button';
import { Terminal, TerminalSquare } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

export const WebSocketToggle = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [isActive, setIsActive] = useState(false);

  // Check if logs are active based on query param
  useEffect(() => {
    const logParam = searchParams.get('log');
    setIsActive(logParam === 'true');
  }, [searchParams]);

  const toggleLogs = () => {
    const newSearchParams = new URLSearchParams(searchParams);

    if (isActive) {
      // Remove log parameter to deactivate
      newSearchParams.delete('log');
    } else {
      // Add log=true to activate
      newSearchParams.set('log', 'true');
    }

    // Navigate to same page with updated query params
    navigate({
      pathname: location.pathname,
      search: newSearchParams.toString(),
    });
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            onClick={toggleLogs}
            className="h-8 px-2"
          >
            {isActive ? (
              <>
                <TerminalSquare className="w-4 h-4 mr-1 text-blue-500" />
                <span className="hidden sm:inline">Logs ON</span>
              </>
            ) : (
              <>
                <Terminal className="w-4 h-4 mr-1" />
                <span className="hidden sm:inline">Logs</span>
              </>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {isActive ? (
            <div className="text-sm">
              <p>📡 WebSocket logs are ON</p>
              <p className="text-xs text-muted-foreground mt-1">Click to turn off</p>
            </div>
          ) : (
            <div className="text-sm">
              <p>📡 WebSocket logs are OFF</p>
              <p className="text-xs text-muted-foreground mt-1">Click to turn on</p>
            </div>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
