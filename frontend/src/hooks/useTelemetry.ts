import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { DataState, SignalQuality, SignalValue, TelemetryPoint } from "@/api/types";


const POLL_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 3000;
const STALE_AFTER_MS = 5000;
const BUFFER_SIZE = 40;


const SIGNAL_KEYS = ["ionV", "ionI", "heatV", "heatI", "heLvl", "Thot", "Tcold"] as const;
const QUALITY_VALUES: SignalQuality[] = ["good", "uncertain", "bad", "unavailable"];


function validateSignal(sample: SignalValue): void {
  const usable = sample.quality === "good" || sample.quality === "uncertain";
  if (
    !QUALITY_VALUES.includes(sample.quality) ||
    sample.unit.length === 0 ||
    (sample.source_timestamp !== null && Number.isNaN(Date.parse(sample.source_timestamp))) ||
    (usable && (sample.value === null || !Number.isFinite(sample.value))) ||
    (!usable && sample.value !== null)
  ) {
    throw new Error("Telemetry signal is malformed");
  }
}


function validateTelemetry(point: TelemetryPoint): DataState {
  if (
    !["simulation", "opcua"].includes(point.source) ||
    Number.isNaN(Date.parse(point.timestamp)) ||
    !Number.isFinite(point.sequence)
  ) {
    throw new Error("Telemetry response is malformed");
  }
  const samples = SIGNAL_KEYS.map((key) => point[key]);
  samples.forEach(validateSignal);
  return samples.every((sample) => sample.quality === "good") ? "live" : "degraded";
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
        const nextState = validateTelemetry(point);
        if (!active) return;
        setData((previous) => [...previous, point].slice(-BUFFER_SIZE));
        setDataState(nextState);
        setLastSuccessfulAt(point.timestamp);
        setError(nextState === "degraded" ? "One or more telemetry signals are degraded." : null);
        scheduleStale();
      } catch (caught) {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 401) {
          onUnauthorized();
          return;
        }
        if (caught instanceof ApiError && caught.status === 503) {
          const backendState = caught.message.toLowerCase().includes("unavailable")
            ? "unavailable"
            : "stale";
          setError(caught.message);
          setDataState(backendState);
        } else {
          setError(timedOut ? "Telemetry request timed out." : "Telemetry is unavailable.");
          setDataState((current) =>
            current === "live" || current === "degraded" || current === "stale"
              ? "stale"
              : "unavailable"
          );
        }
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
