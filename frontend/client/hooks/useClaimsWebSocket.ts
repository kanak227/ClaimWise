import { useEffect, useCallback } from "react";
import { toast } from "sonner";
import { ClaimResponse } from "@/api/claims";

interface ClaimEvent {
  type: "claim.created" | "claim.updated";
  data: ClaimResponse;
}

interface UseClaimsWebSocketProps {
  onClaimCreated?: (claim: ClaimResponse) => void;
  onClaimUpdated?: (claim: ClaimResponse) => void;
}

export const useClaimsWebSocket = ({
  onClaimCreated,
  onClaimUpdated,
}: UseClaimsWebSocketProps) => {
  const connectWebSocket = useCallback(() => {
    // Check if WebSocket is enabled (set VITE_ENABLE_WEBSOCKET=true to enable)
    // By default, WebSocket is disabled to avoid connection errors if backend doesn't support it
    const enableWebSocket = import.meta.env.VITE_ENABLE_WEBSOCKET === "true";
    
    if (!enableWebSocket) {
      // WebSocket is disabled by default - no connection attempted
      return { ws: null, close: () => {} };
    }

    // Get WebSocket URL from environment or construct from API base
    // Defaults to ws://localhost:8000/ws/claims for FastAPI backend
    const wsBaseUrl = import.meta.env.VITE_WS_BASE_URL || 
      import.meta.env.VITE_API_BASE_URL?.replace(/^http/, "ws") || 
      "ws://localhost:8000";
    const wsUrl = `${wsBaseUrl}/ws/claims`;

    let reconnectTimeout: NodeJS.Timeout | null = null;
    let shouldReconnect = true;

    const createConnection = () => {
      try {
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("WebSocket connected");
          shouldReconnect = true;
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as ClaimEvent;

            if (message.type === "claim.created") {
              onClaimCreated?.(message.data);
              toast.success("New claim received");
            } else if (message.type === "claim.updated") {
              onClaimUpdated?.(message.data);
              toast.info("Claim updated by system");
            }
          } catch (error) {
            console.error("Failed to parse WebSocket message:", error);
          }
        };

        ws.onerror = (error) => {
          // Silently handle WebSocket errors - don't show toasts to users
          console.warn("WebSocket connection error (backend may not support WebSocket):", error);
        };

        ws.onclose = (event) => {
          console.log("WebSocket disconnected", event.code, event.reason);
          // Only attempt to reconnect if WebSocket was enabled and connection wasn't intentionally closed
          if (shouldReconnect && event.code !== 1000) {
            reconnectTimeout = setTimeout(() => {
              console.log("Attempting WebSocket reconnect...");
              createConnection();
            }, 5000); // Increase delay to 5 seconds
          }
        };

        return ws;
      } catch (error) {
        console.warn("Failed to create WebSocket connection:", error);
        return null;
      }
    };

    const ws = createConnection();
    
    return {
      ws,
      close: () => {
        shouldReconnect = false;
        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
        }
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.close(1000, "Component unmounting");
        }
      }
    } as { ws: WebSocket | null; close: () => void };
  }, [onClaimCreated, onClaimUpdated]);

  useEffect(() => {
    const connection = connectWebSocket();

    return () => {
      if (connection) {
        connection.close();
      }
    };
  }, [connectWebSocket]);
};
