"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl } from "./api";
import type { LiveEvent } from "./types";

const MAX_BUFFERED_EVENTS = 200;
const RECONNECT_DELAY_MS = 2000;

/** Subscribes to the backend's Redis-fed WebSocket, buffering recent events client-side. */
export function useLiveEvents() {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const socket = new WebSocket(wsUrl());
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, RECONNECT_DELAY_MS);
      };
      socket.onerror = () => socket.close();
      socket.onmessage = (message) => {
        try {
          const parsed: LiveEvent = JSON.parse(message.data);
          setEvents((prev) => [parsed, ...prev].slice(0, MAX_BUFFERED_EVENTS));
        } catch {
          // ignore malformed frames
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      socketRef.current?.close();
    };
  }, []);

  return { connected, events };
}
