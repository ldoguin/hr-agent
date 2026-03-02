/**
 * Custom React hook for WebSocket log connection
 * Connects to the FastAPI WebSocket endpoint for real-time logs
 */

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface WebSocketLog {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'debug' | 'system';
  sessionId?: string;
}

interface WebSocketStatus {
  isConnected: boolean;
  sessionId: string | null;
  error: string | null;
}

export const useWebSocketLogs = () => {
  const [logs, setLogs] = useState<WebSocketLog[]>([]);
  const [status, setStatus] = useState<WebSocketStatus>({
    isConnected: false,
    sessionId: null,
    error: null,
  });
  const [isAutoScroll, setIsAutoScroll] = useState(true);
  const [searchParams] = useSearchParams();
  const [isActive, setIsActive] = useState(false);

  // Check if logs should be active based on query parameter
  useEffect(() => {
    const logParam = searchParams.get('log');
    setIsActive(logParam === 'true');
  }, [searchParams]);

  // Parse log message to determine type and format
  const parseLogMessage = useCallback((message: string): WebSocketLog => {
    let type: WebSocketLog['type'] = 'info';
    let parsedMessage = message;

    // Detect log type from message content
    if (message.startsWith('🔑 Your session ID:')) {
      type = 'system';
    } else if (message.includes('[ERROR]') || message.includes('❌')) {
      type = 'error';
    } else if (message.includes('[WARNING]') || message.includes('⚠️')) {
      type = 'warning';
    } else if (message.includes('[SUCCESS]') || message.includes('✅')) {
      type = 'success';
    } else if (message.includes('[DEBUG]')) {
      type = 'debug';
    } else if (message.includes('[INFO]')) {
      type = 'info';
    }

    // Extract session ID if present
    const sessionMatch = message.match(/Session ([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/i);
    const sessionId = sessionMatch ? sessionMatch[1] : undefined;

    return {
      id: Date.now().toString(),
      timestamp: new Date().toISOString(),
      message: parsedMessage,
      type,
      sessionId,
    };
  }, []);

  // Add log to the list
  const addLog = useCallback((message: string) => {
    const log = parseLogMessage(message);
    setLogs((prevLogs) => {
      // Limit to 100 logs to prevent memory issues
      const newLogs = [...prevLogs, log];
      return newLogs.slice(-100);
    });
  }, [parseLogMessage]);

  // Clear all logs
  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  // Toggle auto-scroll
  const toggleAutoScroll = useCallback(() => {
    setIsAutoScroll((prev) => !prev);
  }, []);

  useEffect(() => {
    // Only connect if logs are active (log=true query param)
    if (!isActive) {
      // Reset status when deactivated
      setStatus({
        isConnected: false,
        sessionId: null,
        error: null,
      });
      return;
    }

    // Connect to WebSocket
    const websocketUrl = API_BASE_URL.replace('http', 'ws') + '/ws/logs';
    let socket: WebSocket;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectDelay = 3000; // 3 seconds

    const connect = () => {
      try {
        socket = new WebSocket(websocketUrl);

        socket.onopen = () => {
          setStatus({
            isConnected: true,
            sessionId: null,
            error: null,
          });
          reconnectAttempts = 0;
          console.log('🔌 WebSocket connected successfully');
        };

        socket.onmessage = (event) => {
          const message = event.data;
          addLog(message);

          // Extract session ID from welcome message
          if (message.startsWith('🔑 Your session ID:')) {
            const sessionId = message.split(': ')[1];
            setStatus((prev) => ({
              ...prev,
              sessionId,
            }));
          }
        };

        socket.onclose = () => {
          setStatus((prev) => ({
            ...prev,
            isConnected: false,
            error: 'WebSocket connection closed',
          }));
          console.log('🔌 WebSocket connection closed');

          // Attempt to reconnect only if still active
          if (isActive && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(`🔄 Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
            setTimeout(connect, reconnectDelay);
          } else {
            console.log('❌ Max reconnection attempts reached or logs deactivated');
          }
        };

        socket.onerror = (error) => {
          setStatus((prev) => ({
            ...prev,
            error: `WebSocket error: ${error.type}`,
          }));
          console.error('❌ WebSocket error:', error);
        };

      } catch (error) {
        setStatus((prev) => ({
          ...prev,
          error: `Failed to connect: ${error instanceof Error ? error.message : String(error)}`,
        }));
        console.error('❌ WebSocket connection error:', error);
      }
    };

    // Start connection
    connect();

    // Cleanup on unmount
    return () => {
      if (socket) {
        socket.close();
      }
    };

  }, [addLog, isActive]);

  return {
    logs,
    status,
    isAutoScroll,
    clearLogs,
    toggleAutoScroll,
    addLog, // Expose for manual log addition (testing)
  };
};

export type { WebSocketLog, WebSocketStatus };
