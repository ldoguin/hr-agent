/**
 * WebSocket Logs Component
 * Displays real-time logs from the FastAPI WebSocket endpoint
 * at the bottom of the page with auto-scrolling and filtering
 */

import { useEffect, useRef } from 'react';
import { useWebSocketLogs, WebSocketLog } from '@/hooks/useWebSocketLogs';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { Info, Wifi, WifiOff, Trash2, ScrollText, Pause, Play } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

const LogTypeColors = {
  info: 'bg-blue-500/10 text-blue-600 border-blue-200',
  success: 'bg-green-500/10 text-green-600 border-green-200',
  warning: 'bg-yellow-500/10 text-yellow-600 border-yellow-200',
  error: 'bg-red-500/10 text-red-600 border-red-200',
  debug: 'bg-purple-500/10 text-purple-600 border-purple-200',
  system: 'bg-gray-500/10 text-gray-600 border-gray-200',
};

const LogTypeIcons = {
  info: 'ℹ️',
  success: '✅',
  warning: '⚠️',
  error: '❌',
  debug: '🔍',
  system: '🖥️',
};

export const WebSocketLogs = () => {
  const [searchParams] = useSearchParams();
  const logParam = searchParams.get('log');
  const isActive = logParam === 'true';

  const {
    logs,
    status,
    isAutoScroll,
    clearLogs,
    toggleAutoScroll,
  } = useWebSocketLogs();

  const logContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && logContainerRef.current) {
      const container = logContainerRef.current;
      container.scrollTop = container.scrollHeight;
    }
  }, [logs, isAutoScroll]);

  // Format timestamp for display
  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return '--:--:--';
    }
  };

  // Get log type badge
  const getLogTypeBadge = (type: WebSocketLog['type']) => {
    const colors = LogTypeColors[type] || LogTypeColors.info;
    const icon = LogTypeIcons[type] || LogTypeIcons.info;

    return (
      <Badge className={`${colors} font-mono text-xs`}>
        {icon} {type.toUpperCase()}
      </Badge>
    );
  };

  // Get log message with session highlighting
  const getLogMessage = (log: WebSocketLog) => {
    if (log.sessionId) {
      return (
        <span>
          <span className="font-mono text-blue-600">{log.sessionId.substring(0, 8)}...</span>
          <span className="ml-2">{log.message.replace(`Session ${log.sessionId}`, '').trim()}</span>
        </span>
      );
    }
    return log.message;
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-background border-t border-border z-50">
      <div className="container mx-auto px-4 py-2">
        {/* Header with controls */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-semibold text-foreground flex items-center">
              <ScrollText className="w-4 h-4 mr-1" />
              Real-time System Logs
            </h3>

            {/* Connection status */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge variant={status.isConnected ? 'default' : 'destructive'} className="ml-2">
                    {status.isConnected ? (
                      <>
                        <Wifi className="w-3 h-3 mr-1" /> Connected
                      </>
                    ) : (
                      <>
                        <WifiOff className="w-3 h-3 mr-1" /> Disconnected
                      </>
                    )}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {status.isConnected ? (
                    <div className="text-sm">
                      <p>✅ WebSocket connected</p>
                      {status.sessionId && (
                        <p className="font-mono text-xs mt-1">
                          Session: {status.sessionId.substring(0, 8)}...
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="text-sm">
                      <p>❌ WebSocket disconnected</p>
                      {status.error && (
                        <p className="text-xs text-red-500 mt-1">{status.error}</p>
                      )}
                    </div>
                  )}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={toggleAutoScroll}
                    className="h-7 px-2"
                  >
                    {isAutoScroll ? (
                      <>
                        <Pause className="w-3 h-3 mr-1" /> Pause
                      </>
                    ) : (
                      <>
                        <Play className="w-3 h-3 mr-1" /> Auto-scroll
                      </>
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isAutoScroll ? 'Pause auto-scrolling' : 'Enable auto-scrolling'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearLogs}
                    disabled={logs.length === 0}
                    className="h-7 px-2"
                  >
                    <Trash2 className="w-3 h-3 mr-1" /> Clear
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Clear all logs</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2"
                  >
                    <Info className="w-3 h-3 mr-1" /> Info
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <div className="text-sm max-w-xs">
                    <p>📡 Real-time logs from WebSocket</p>
                    <p className="mt-1">🔄 Auto-reconnects if disconnected</p>
                    <p className="mt-1">📜 Max 100 logs stored</p>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>

        {/* Log display area */}
        <div className="border border-border rounded-md overflow-hidden">
          <ScrollArea className="h-[150px]">
            <div
              ref={logContainerRef}
              className="p-2 space-y-1 text-sm"
            >
              {logs.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground">
                  {status.isConnected ? (
                    <>📡 Waiting for logs... Your session is connected</>
                  ) : (
                    <>🔌 Connecting to WebSocket server...</>
                  )}
                </div>
              ) : (
                logs.map((log) => (
                  <div
                    key={log.id}
                    className={`p-2 rounded border-l-4 ${LogTypeColors[log.type] || LogTypeColors.info} break-words`}
                  >
                    <div className="flex items-start space-x-2">
                      <div className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimestamp(log.timestamp)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          {getLogTypeBadge(log.type)}
                          {log.sessionId && (
                            <span className="font-mono text-xs text-muted-foreground">
                              Session: {log.sessionId.substring(0, 8)}...
                            </span>
                          )}
                        </div>
                        <div className="text-foreground">
                          {getLogMessage(log)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Status bar */}
        <div className="text-xs text-muted-foreground mt-1 flex justify-between items-center">
          <span>
            {logs.length} log{logs.length !== 1 ? 's' : ''} • {isAutoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          </span>
          <span className="flex items-center">
            {status.isConnected ? (
              <>
                <span className="w-2 h-2 bg-green-500 rounded-full mr-1 animate-pulse"></span>
                Connected to WebSocket
              </>
            ) : (
              <>
                <span className="w-2 h-2 bg-red-500 rounded-full mr-1"></span>
                Disconnected
              </>
            )}
          </span>
        </div>
      </div>
    </div>
  );
};
