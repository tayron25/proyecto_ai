import { useCallback, useEffect, useRef, useState } from "react";
import type { ClientCommand, GameState } from "../types";

const WS_URL = "ws://127.0.0.1:8000/ws/game";

export function useGameSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const pendingCommandRef = useRef<Record<string, unknown>>({});
  const [connected, setConnected] = useState(false);
  const [gameState, setGameState] = useState<GameState | null>(null);

  const sendPayload = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      pendingCommandRef.current = { ...pendingCommandRef.current, ...payload };
      return;
    }
    ws.send(JSON.stringify(payload));
  }, []);

  useEffect(() => {
    let reconnect: number | undefined;
    let closed = false;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        ws.send(JSON.stringify({}));
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          reconnect = window.setTimeout(connect, 1200);
        }
      };
      ws.onerror = () => setConnected(false);
      ws.onmessage = (event) => {
        setGameState(JSON.parse(event.data) as GameState);
      };
    };

    connect();

    return () => {
      closed = true;
      window.clearTimeout(reconnect);
      wsRef.current?.close();
    };
  }, []);

  const sendFrame = useCallback((frame: string, videoTime: number, paused = false) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }
    const message = { frame, videoTime, paused, ...pendingCommandRef.current };
    pendingCommandRef.current = {};
    ws.send(JSON.stringify(message));
  }, []);

  const sendCommand = useCallback((command: ClientCommand, videoTime = 0) => {
    sendPayload({ command, videoTime });
  }, [sendPayload]);

  const selectGame = useCallback((selectedGame: string) => {
    sendPayload({ selectedGame });
  }, [sendPayload]);

  return { connected, gameState, sendFrame, sendCommand, selectGame };
}
