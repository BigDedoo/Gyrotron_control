import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { DataState, TelemetryPoint } from "@/api/types";


const POLL_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 3000;
const STALE_AFTER_MS = 5000;
const BUFFER_SIZE = 40;


function validateTelemetry(point: TelemetryPoint): void {
  const values = [
    point.sequence,
    point.ionV,
    point.ionI,
    point.heatV,
    point.heatI,
    point.heLvl,
    point.Thot,
    point.Tcold,
  ];
  if (
    point.source !== "simulation" ||
    Number.isNaN(Date.parse(point.timestamp)) ||
    values.some((value) => !Number.isFinite(value))
  ) {
    throw new Error("Telemetry response is malformed");
  }
}


export function useTelemetry(enabled: boolean, onUnauthorized: () => void) {
  const [data, setData] = useState<TelemetryPoint[]>([]);
  const [dataState, setDataState] = useState<DataState>("unavailable");
  const [lastSuccessfulAt, setLastSuccessfulAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setData([]);
      setDataState("unavailable");
      setLastSuccessfulAt(null);
      setError(null);
      return;
    }

    let active = true;
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    let staleTimer: ReturnType<typeof setTimeout> | undefined;
    let currentController: AbortController | undefined;

    const scheduleStale = () => {
      if (staleTimer) clearTimeout(staleTimer);
      staleTimer = setTimeout(() => {
        if (active) {
          setDataState("stale");
          setError("Telemetry is stale; displayed values are not current.");
        }
      }, STALE_AFTER_MS);
    };

    const poll = async () => {
      currentController = new AbortController();
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        currentController?.abort();
      }, REQUEST_TIMEOUT_MS);

      try {
        const point = await api.getTelemetry(currentController.signal);
        validateTelemetry(point);
        if (!active) return;
        setData((previous) => [...previous, point].slice(-BUFFER_SIZE));
        setDataState("live");
        setLastSuccessfulAt(new Date().toISOString());
        setError(null);
        scheduleStale();
      } catch (caught) {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized();
          return;
        }
        setError(timedOut ? "Telemetry request timed out." : "Telemetry is unavailable.");
        setDataState((current) => (current === "live" ? current : "unavailable"));
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

  return {
    data,
    latest: data.at(-1) ?? null,
    dataState,
    lastSuccessfulAt,
    error,
  };
}
