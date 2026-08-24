import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { DataState, SystemStatus } from "@/api/types";


const POLL_DELAY_MS = 2000;
const REQUEST_TIMEOUT_MS = 3000;
const STALE_AFTER_MS = 6000;


export function useSystemStatus(enabled: boolean, onUnauthorized: () => void) {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [statusState, setStatusState] = useState<DataState>("unavailable");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setSystemStatus(null);
      setStatusState("unavailable");
      setError(null);
      return;
    }

    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let staleTimer: ReturnType<typeof setTimeout> | undefined;
    let currentController: AbortController | undefined;

    const poll = async () => {
      currentController = new AbortController();
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        currentController?.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const nextStatus = await api.getSystemStatus(currentController.signal);
        const sourceMatchesMode =
          (nextStatus.mode === "simulation" && nextStatus.source === "simulation") ||
          (nextStatus.mode === "opcua_readonly" && nextStatus.source === "opcua");
        if (!sourceMatchesMode || Number.isNaN(Date.parse(nextStatus.timestamp))) {
          throw new Error("System status response is malformed");
        }
        if (!active) return;
        setSystemStatus(nextStatus);
        setStatusState("live");
        setError(nextStatus.monitor_error);
        if (staleTimer) clearTimeout(staleTimer);
        staleTimer = setTimeout(() => {
          if (active) {
            setStatusState("stale");
            setError("System status is stale.");
          }
        }, STALE_AFTER_MS);
      } catch (caught) {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized();
          return;
        }
        setError(timedOut ? "System status request timed out." : "System status is unavailable.");
        setStatusState((current) => (current === "live" ? current : "unavailable"));
      } finally {
        clearTimeout(timeout);
        if (active) pollTimer = setTimeout(poll, POLL_DELAY_MS);
      }
    };

    void poll();
    return () => {
      active = false;
      currentController?.abort();
      if (pollTimer) clearTimeout(pollTimer);
      if (staleTimer) clearTimeout(staleTimer);
    };
  }, [enabled, onUnauthorized]);

  return { systemStatus, statusState, error };
}
