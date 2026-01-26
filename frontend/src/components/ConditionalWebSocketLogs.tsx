/**
 * Conditional WebSocket Logs Wrapper
 * Handles conditional rendering of WebSocketLogs based on query parameter
 * This ensures React Hooks are called in consistent order
 */

import { useSearchParams } from 'react-router-dom';
import { WebSocketLogs } from './WebSocketLogs';

export const ConditionalWebSocketLogs = () => {
  const [searchParams] = useSearchParams();
  const logParam = searchParams.get('log');
  const isActive = logParam === 'true';

  // Conditional rendering happens here, outside the WebSocketLogs component
  // This ensures all hooks in WebSocketLogs are called consistently
  if (!isActive) {
    return null;
  }

  // When active, render the WebSocketLogs component
  // All hooks inside WebSocketLogs will be called in the same order every time
  return <WebSocketLogs />;
};
