"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import type { LiveEvent } from "@/lib/types";
import { eventTypes, parseEvent } from "@/lib/farm-state";

const LiveContext = createContext({
  status: "Connecting",
  lastHeartbeat: null as string | null,
});

// One connection across route transitions. EventSource resumes business events by ID.
export function LiveEventsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
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
    const seen = new Set<string>();
    const refresh = (message: MessageEvent<string>) => {
      const event = parseEvent(message.data);
      if (!event || seen.has(event.id)) return;
      seen.add(event.id);
      if (seen.size > 512) seen.delete(seen.values().next().value!);
      window.dispatchEvent(new CustomEvent("ai-farm:event", { detail: event }));
      window.dispatchEvent(new Event("ai-farm:update"));
    };
    for (const event of eventTypes.filter((e) => e !== "heartbeat"))
      source.addEventListener(event, refresh);
    source.onerror = () => setStatus("Reconnecting");
    const timer = setInterval(() => {
      if (Date.now() - receivedAt > 90_000) setStatus("Waiting for heartbeat");
    }, 5_000);
    return () => {
      source.close();
      clearInterval(timer);
    };
  }, []);
  return (
    <LiveContext.Provider value={{ status, lastHeartbeat }}>
      {children}
    </LiveContext.Provider>
  );
}

export function useLiveEvents() {
  return useContext(LiveContext);
}
