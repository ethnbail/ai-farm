"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import type { LiveEvent } from "@/lib/types";

export function useLiveEvents() {
  const [status, setStatus] = useState("Connecting");
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/events`);
    let receivedAt = Date.now();
    source.addEventListener("heartbeat", (message: MessageEvent<string>) => {
      try {
        const event = JSON.parse(message.data) as LiveEvent;
        if (event.event_type !== "heartbeat" || !event.created_at) return;
        receivedAt = Date.now();
        setLastHeartbeat(event.created_at);
        setStatus("Live");
      } catch {
        setStatus("Invalid event");
      }
    });
    source.onerror = () => setStatus("Reconnecting");
    const timer = setInterval(() => {
      if (Date.now() - receivedAt > 90_000) setStatus("Waiting for heartbeat");
    }, 5_000);
    return () => {
      source.close();
      clearInterval(timer);
    };
  }, []);

  return { status, lastHeartbeat };
}
