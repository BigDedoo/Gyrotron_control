import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Activity,
  AlertTriangle,
  Flame,
  Gauge,
  ShieldCheck,
  Settings,
  Power,
  Thermometer,
  Timer,
  Zap,
  type LucideIcon,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

import { api, ApiError } from "@/api/client";
import type {
  ComponentState,
  ComponentStatus,
  CommandCapability,
  ConditionState,
  ConnectionState,
  DataState,
  EventCategory,
  EventRecord,
  InterlockStatus,
  LogicalCommand,
  OverallState,
  SessionUser,
  SignalQuality,
  SignalValue,
  StateSignalValue,
  SystemStatus,
  TelemetryPoint,
} from "@/api/types";
import { useSystemStatus } from "@/hooks/useSystemStatus";
import { useTelemetry } from "@/hooks/useTelemetry";
import Login from "@/components/Login";
import AdminTab from "@/components/AdminTab";


type DisplayState =
  | ComponentState
  | ConditionState
  | ConnectionState
  | DataState
  | OverallState
  | SignalQuality;

const UNKNOWN_COMPONENT: ComponentStatus = {
  state: "unknown",
  ready: "unknown",
  rectifier: "unknown",
  converter: "unknown",
  protection: "unknown",
  signals: {},
};


function stateClasses(state: DisplayState): string {
  if (["ok", "on", "connected", "live", "nominal", "good"].includes(state)) {
    return "bg-emerald-600 text-white";
  }
  if (["fault", "error", "unavailable", "disconnected"].includes(state)) {
    return "bg-red-600 text-white";
  }
  if (["simulation", "simulated", "degraded", "stale", "connecting", "uncertain"].includes(state)) {
    return "bg-amber-500 text-slate-950";
  }
  return "bg-slate-500 text-white";
}


function StateBadge({ state }: { state: DisplayState }) {
  return <Badge className={`rounded-full ${stateClasses(state)}`}>{state.toUpperCase()}</Badge>;
}


function StatusDot({ state }: { state: DisplayState }) {
  const color = stateClasses(state).split(" ")[0];
  return <span className={`inline-block size-3 rounded-full mr-2 ${color}`} />;
}


function Labeled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-12 items-center gap-3">
      <div className="col-span-5 text-sm text-muted-foreground">{label}</div>
      <div className="col-span-7">{children}</div>
    </div>
  );
}


function GaugeCard({
  title,
  sample,
  fallbackUnit,
  icon: Icon,
  dataState,
}: {
  title: string;
  sample: SignalValue | null;
  fallbackUnit?: string;
  icon: LucideIcon;
  dataState: DataState;
}) {
  const usable = sample?.quality === "good" || sample?.quality === "uncertain";
  const value = usable ? sample.value : null;
  const unit = sample?.unit ?? fallbackUnit ?? "";
  const quality = sample?.quality ?? "unavailable";
  const impaired = dataState !== "live" || quality !== "good";
  return (
    <Card className={`rounded-2xl ${impaired ? "border-amber-400 bg-amber-50/40" : ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Icon className="size-4" /> {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold">
          {value === null ? "—" : value.toFixed(1)}{value === null ? "" : ` ${unit}`}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <StateBadge state={quality} />
          {dataState !== "live" && <StateBadge state={dataState} />}
        </div>
        {sample?.source_timestamp && (
          <div className="mt-1 text-[11px] text-slate-500">
            Source time: {new Date(sample.source_timestamp).toLocaleString()}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


type ChartPoint = {
  timestamp: string;
  ionV: number | null;
  ionI: number | null;
  heatV: number | null;
  heatI: number | null;
};


function chartValue(sample: SignalValue): number | null {
  return sample.quality === "good" || sample.quality === "uncertain" ? sample.value : null;
}


function chartData(data: TelemetryPoint[]): ChartPoint[] {
  return data.map((point) => ({
    timestamp: point.timestamp,
    ionV: chartValue(point.ionV),
    ionI: chartValue(point.ionI),
    heatV: chartValue(point.heatV),
    heatI: chartValue(point.heatI),
  }));
}


function Indicator({ label, state }: { label: string; state: DisplayState }) {
  return (
    <div className="flex items-center justify-between gap-2 text-sm">
      <span>{label}</span>
      <StateBadge state={state} />
    </div>
  );
}


function SignalDetail({ signal }: { signal: StateSignalValue | undefined }) {
  if (!signal) return <span className="text-[11px] text-slate-500">Unmapped</span>;
  return (
    <div className="mt-1 flex flex-wrap items-center justify-end gap-1 text-[11px] text-slate-500">
      {!signal.mapped && <span>Unmapped</span>}
      <StateBadge state={signal.quality} />
      {signal.data_state !== "live" && <StateBadge state={signal.data_state} />}
      {signal.observed_at && <span>Observed {new Date(signal.observed_at).toLocaleTimeString()}</span>}
    </div>
  );
}


function ComponentIndicator({ label, state, signal }: { label: string; state: DisplayState; signal?: StateSignalValue }) {
  return (
    <div>
      <Indicator label={label} state={state} />
      <SignalDetail signal={signal} />
    </div>
  );
}


function capabilityReason(capabilities: CommandCapability[], command: LogicalCommand): string {
  const capability = capabilities.find((item) => item.command === command);
  return capability
    ? `Unavailable: ${capability.reasons[0]}`
    : "Unavailable: backend command capability could not be verified";
}


function ModeBanner({
  status,
  statusState,
  telemetryState,
  statusError,
  telemetryError,
}: {
  status: SystemStatus | null;
  statusState: DataState;
  telemetryState: DataState;
  statusError: string | null;
  telemetryError: string | null;
}) {
  if (!status) {
    return (
      <div className="border-b border-red-300 bg-red-100 px-4 py-3 text-center text-sm font-semibold text-red-900" role="alert">
        SYSTEM STATUS UNAVAILABLE — machine state is UNKNOWN and hardware controls are disabled.
        {statusError && <span className="ml-2 font-normal">{statusError}</span>}
      </div>
    );
  }

  const readonly = status.mode === "opcua_readonly";

  return (
    <div className={`border-b px-4 py-3 ${readonly ? "border-blue-300 bg-blue-100 text-blue-950" : "border-amber-300 bg-amber-100 text-amber-950"}`} role="status">
      <div className="max-w-7xl mx-auto flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="font-bold tracking-wide">
            {readonly ? "PLC MONITORING — READ ONLY" : "SIMULATION MODE — NO PLC CONNECTED"}
          </div>
          <div className="text-xs">
            {readonly
              ? "COMMANDS DISABLED. Telemetry is read from the configured OPC UA monitor; quality is shown per signal."
              : "All telemetry is generated by the backend. Hardware commands are unavailable."}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span>Status feed: <StateBadge state={statusState} /></span>
          <span>Connection: <StateBadge state={status.connection_state} /></span>
          <span>Telemetry: <StateBadge state={telemetryState} /></span>
        </div>
      </div>
      {(statusError || telemetryError) && (
        <div className="max-w-7xl mx-auto mt-2 text-xs font-medium" role="alert">
          {[statusError, telemetryError].filter(Boolean).join(" ")}
        </div>
      )}
    </div>
  );
}


function Dashboard({
  status,
  data,
  latest,
  telemetryState,
  lastSuccessfulAt,
}: {
  status: SystemStatus | null;
  data: TelemetryPoint[];
  latest: TelemetryPoint | null;
  telemetryState: DataState;
  lastSuccessfulAt: string | null;
}) {
  const cps = status?.cps ?? UNKNOWN_COMPONENT;
  const aps = status?.aps ?? UNKNOWN_COMPONENT;
  const overallState: DisplayState = telemetryState !== "live"
    ? telemetryState
    : status?.overall_state ?? "unknown";
  const trends = chartData(data);
  const sourceLabel = (latest?.source ?? status?.source ?? "simulation") === "opcua"
    ? "OPC UA"
    : "SIMULATION";

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2 flex flex-row items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base"><Activity className="size-4" /> System Overview</CardTitle>
          <StateBadge state={overallState} />
        </CardHeader>
        <CardContent>
          {telemetryState !== "live" && (
            <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="alert">
              Telemetry is {telemetryState}. Values below are {latest ? "the last received samples and are not current" : "unavailable"}.
            </div>
          )}
          <div className="mb-4 text-xs text-slate-500">
            Source: <strong>{sourceLabel}</strong> · Last successful update: {lastSuccessfulAt ? new Date(lastSuccessfulAt).toLocaleString() : "never"}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <GaugeCard title="Ion Pump V" sample={latest?.ionV ?? null} fallbackUnit="V" icon={Gauge} dataState={telemetryState} />
            <GaugeCard title="Ion Pump I" sample={latest?.ionI ?? null} fallbackUnit="A" icon={Zap} dataState={telemetryState} />
            <GaugeCard title="Heater V" sample={latest?.heatV ?? null} fallbackUnit="V" icon={Flame} dataState={telemetryState} />
            <GaugeCard title="Heater I" sample={latest?.heatI ?? null} fallbackUnit="A" icon={Zap} dataState={telemetryState} />
            <GaugeCard title="Liquid He Level" sample={latest?.heLvl ?? null} fallbackUnit="%" icon={Gauge} dataState={telemetryState} />
            <GaugeCard title="T hot" sample={latest?.Thot ?? null} fallbackUnit="degC" icon={Thermometer} dataState={telemetryState} />
            <GaugeCard title="T cold" sample={latest?.Tcold ?? null} fallbackUnit="degC" icon={Thermometer} dataState={telemetryState} />
            <GaugeCard title="Actual Pulse Duration" sample={null} fallbackUnit="ms" icon={Timer} dataState="unavailable" />
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="rounded-2xl">
              <CardHeader className="pb-2"><CardTitle className="text-sm">Heater Voltage — {sourceLabel}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trends} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8884d8" stopOpacity={0.6} />
                          <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="timestamp" hide />
                      <YAxis domain={[0, "dataMax + 2"]} width={28} unit=" V" />
                      <Tooltip labelFormatter={(value) => new Date(String(value)).toLocaleTimeString()} />
                      <Area type="monotone" dataKey="heatV" stroke="#8884d8" fillOpacity={1} fill="url(#g1)" unit=" V" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardHeader className="pb-2"><CardTitle className="text-sm">Ion Pump Current — {sourceLabel}</CardTitle></CardHeader>
              <CardContent>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trends} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="timestamp" hide />
                      <YAxis domain={[0, "dataMax + 2"]} width={28} unit=" A" />
                      <Tooltip labelFormatter={(value) => new Date(String(value)).toLocaleTimeString()} />
                      <Line type="monotone" dataKey="ionI" stroke="#82ca9d" dot={false} unit=" A" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2"><ShieldCheck className="size-4" /> Backend Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="font-medium mb-2">CPS</div>
            <div className="space-y-2">
              <ComponentIndicator label="Overall" state={cps.state} signal={cps.signals.state} />
              <ComponentIndicator label="Ready" state={cps.ready} signal={cps.signals.ready} />
              <ComponentIndicator label="Power Rectifier" state={cps.rectifier} signal={cps.signals.rectifier} />
              <ComponentIndicator label="Charging Converter" state={cps.converter} signal={cps.signals.converter} />
              <ComponentIndicator label="Protection" state={cps.protection} signal={cps.signals.protection} />
            </div>
          </div>
          <Separator />
          <div>
            <div className="font-medium mb-2">APS</div>
            <div className="space-y-2">
              <ComponentIndicator label="Overall" state={aps.state} signal={aps.signals.state} />
              <ComponentIndicator label="Ready" state={aps.ready} signal={aps.signals.ready} />
              <ComponentIndicator label="Power Rectifier" state={aps.rectifier} signal={aps.signals.rectifier} />
              <ComponentIndicator label="Charging Converter" state={aps.converter} signal={aps.signals.converter} />
              <ComponentIndicator label="Protection" state={aps.protection} signal={aps.signals.protection} />
            </div>
          </div>
          <Separator />
          <div>
            <div className="font-medium mb-2">Active Alarms</div>
            {!status || status.alarms.monitoring_state === "unavailable" ? (
              <div className="rounded-lg border border-red-300 bg-red-50 p-2 text-sm text-red-900">Alarm monitoring unavailable</div>
            ) : status.alarms.monitoring_state === "incomplete" ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">Alarm state incomplete</div>
            ) : status.alarms.monitoring_state === "no_active" ? (
              <div className="flex items-center gap-2 text-sm"><StateBadge state="ok" /> No active alarms</div>
            ) : (
              <ul className="text-sm space-y-1">
                {status.alarms.active.map((alarm) => (
                  <li key={alarm.code} className="flex items-center gap-2">
                    <AlertTriangle className="size-4 text-red-600" />
                    <span>{alarm.message}</span>
                    <Badge variant="outline">{alarm.severity?.toUpperCase() ?? "SEVERITY UNCONFIGURED"}</Badge>
                  </li>
                ))}
              </ul>
            )}
            {status && (
              <div className="mt-2 text-[11px] text-slate-500">
                Trustworthy state signals: {status.coverage.trustworthy}/{status.coverage.total} · Mapped: {status.coverage.mapped}/{status.coverage.total}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function PowerTab({ status, capabilities }: { status: SystemStatus | null; capabilities: CommandCapability[] }) {
  const [pulse, setPulse] = useState(2.5);
  const [vcath, setVcath] = useState(6.0);
  const [vanode, setVanode] = useState(5.0);
  const cps = status?.cps ?? UNKNOWN_COMPONENT;
  const aps = status?.aps ?? UNKNOWN_COMPONENT;

  function resetRequestedValues() {
    setPulse(2.5);
    setVcath(6.0);
    setVanode(5.0);
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Settings className="size-4" /> Requested Setpoints — local draft only</CardTitle></CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            These are uncommitted requested values only. No actual PLC setpoint is available and Apply is disabled.
          </div>
          <Labeled label={`Requested pulse duration: ${pulse.toFixed(2)} ms`}>
            <div id="setpoint-pulse"><Slider value={[pulse]} onValueChange={(value) => setPulse(value[0])} min={0} max={10} step={0.1} /></div>
          </Labeled>
          <Labeled label={`Requested cathode voltage: ${vcath.toFixed(2)} V`}>
            <div id="setpoint-cathode"><Slider value={[vcath]} onValueChange={(value) => setVcath(value[0])} min={0} max={10} step={0.1} /></div>
          </Labeled>
          <Labeled label={`Requested anode voltage: ${vanode.toFixed(2)} V`}>
            <div id="setpoint-anode"><Slider value={[vanode]} onValueChange={(value) => setVanode(value[0])} min={0} max={10} step={0.1} /></div>
          </Labeled>
          <div className="flex gap-3 pt-2">
            <Button id="apply-setpoints" className="rounded-2xl" disabled title={capabilityReason(capabilities, "setpoint.apply")}>Apply Setpoints</Button>
            <Button variant="outline" className="rounded-2xl" onClick={resetRequestedValues}>Revert requested edits</Button>
          </div>
          <div className="text-xs text-slate-500">Actual pulse, cathode, and anode values: UNAVAILABLE</div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4">
        <PowerCommands title="CPS Commands" component={cps} prefix="cps" capabilities={capabilities} />
        <PowerCommands title="APS Commands" component={aps} prefix="aps" capabilities={capabilities} />
      </div>
    </div>
  );
}


function PowerCommands({ title, component, prefix, capabilities }: { title: string; component: ComponentStatus; prefix: "cps" | "aps"; capabilities: CommandCapability[] }) {
  const rectifierCommand: LogicalCommand = prefix === "cps" ? "cps.rectifier.set" : "aps.rectifier.set";
  const converterCommand: LogicalCommand = prefix === "cps" ? "cps.converter.set" : "aps.converter.set";
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Power className="size-4" /> {title}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="text-xs font-medium text-amber-800">Commands disabled — read-only application</div>
        <Labeled label="Power Rectifier">
          <div id={`${prefix}-rectifier`} className="flex items-center gap-3">
            <Switch checked={component.rectifier === "on"} disabled title={capabilityReason(capabilities, rectifierCommand)} aria-label={`${title} power rectifier read-only indication`} />
            <StateBadge state={component.rectifier} />
          </div>
          <SignalDetail signal={component.signals.rectifier} />
        </Labeled>
        <Labeled label="Charging Converter">
          <div id={`${prefix}-converter`} className="flex items-center gap-3">
            <Switch checked={component.converter === "on"} disabled title={capabilityReason(capabilities, converterCommand)} aria-label={`${title} charging converter read-only indication`} />
            <StateBadge state={component.converter} />
          </div>
          <SignalDetail signal={component.signals.converter} />
        </Labeled>
        <div className="flex gap-3 pt-2">
          <Button className="rounded-2xl" variant="secondary" disabled title={capabilityReason(capabilities, "protection.reset")}>Protection Reset</Button>
          <Button className="rounded-2xl" variant="outline" disabled title={capabilityReason(capabilities, converterCommand)}>Apply</Button>
        </div>
      </CardContent>
    </Card>
  );
}


function SafetyTab({ status, capabilities }: { status: SystemStatus | null; capabilities: CommandCapability[] }) {
  const groups = status?.interlocks.reduce<Record<string, InterlockStatus[]>>((result, item) => {
    (result[item.group] ??= []).push(item);
    return result;
  }, {}) ?? {};

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      {Object.entries(groups).map(([group, items]) => (
        <Card key={group} className="rounded-2xl">
          <CardHeader className="pb-2"><CardTitle className="text-sm">{group}</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 gap-2">
            {items.map((item) => (
              <div key={item.logical_name} className="rounded-lg border p-2">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm text-muted-foreground">{item.name}</span>
                  <StateBadge state={item.state} />
                </div>
                <SignalDetail signal={item.signal} />
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
      {Object.keys(groups).length === 0 && (
        <Card className="rounded-2xl xl:col-span-2 border-red-300">
          <CardContent className="p-6 text-sm font-medium text-red-800">Interlock data is unavailable. No safe state is being asserted.</CardContent>
        </Card>
      )}
      <Card className="rounded-2xl">
        <CardHeader className="pb-2"><CardTitle className="text-sm">Alarm Monitoring</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {!status || status.alarms.monitoring_state === "unavailable" ? (
            <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">Alarm monitoring unavailable</div>
          ) : status.alarms.monitoring_state === "incomplete" ? (
            <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">Alarm state incomplete — no all-clear is asserted</div>
          ) : status.alarms.monitoring_state === "no_active" ? (
            <div className="flex items-center gap-2 text-sm"><StateBadge state="ok" /> No active alarms</div>
          ) : (
            <div className="flex items-center gap-2 text-sm"><StateBadge state="fault" /> Confirmed active alarm(s)</div>
          )}
          {status?.alarms.signals.map((signal) => {
            const alarmState: ConditionState = signal.interpreted_state === "active"
              ? "fault"
              : signal.interpreted_state === "inactive"
                ? "ok"
                : "unknown";
            return (
              <div key={signal.logical_name} className="rounded-lg border p-2">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span>{signal.display_name}</span>
                  <div className="flex items-center gap-1">
                    {signal.severity && <Badge variant="outline">{signal.severity.toUpperCase()}</Badge>}
                    <StateBadge state={alarmState} />
                  </div>
                </div>
                <SignalDetail signal={signal} />
              </div>
            );
          })}
        </CardContent>
      </Card>
      <Card className="rounded-2xl">
        <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><AlertTriangle className="size-4" /> Actions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
            No reset or shutdown command is implemented. Physical and PLC safety systems remain authoritative.
          </div>
          <Button className="rounded-2xl w-full" variant="secondary" disabled title={capabilityReason(capabilities, "interlock.reset")}>Reset Interlocks</Button>
          <Button className="rounded-2xl w-full" variant="destructive" disabled title={capabilityReason(capabilities, "emergency.shutdown")}>Emergency Shutdown — unavailable</Button>
        </CardContent>
      </Card>
    </div>
  );
}


function MonitoringTab({ data, latest, dataState }: { data: TelemetryPoint[]; latest: TelemetryPoint | null; dataState: DataState }) {
  const trends = chartData(data);
  const sourceLabel = latest?.source === "opcua" ? "OPC UA" : "simulation";
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Telemetry Trends — {sourceLabel}</CardTitle>
          <StateBadge state={dataState} />
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" tickFormatter={(value) => new Date(String(value)).toLocaleTimeString()} />
                <YAxis />
                <Tooltip labelFormatter={(value) => new Date(String(value)).toLocaleString()} />
                <Line type="monotone" dataKey="ionV" name="Ion V" stroke="#8884d8" dot={false} unit=" V" />
                <Line type="monotone" dataKey="ionI" name="Ion I" stroke="#82ca9d" dot={false} unit=" A" />
                <Line type="monotone" dataKey="heatV" name="Heater V" stroke="#ffc658" dot={false} unit=" V" />
                <Line type="monotone" dataKey="heatI" name="Heater I" stroke="#ff7300" dot={false} unit=" A" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 gap-4">
        <GaugeCard title="Liquid He Level" sample={latest?.heLvl ?? null} fallbackUnit="%" icon={Gauge} dataState={dataState} />
        <GaugeCard title="T hot" sample={latest?.Thot ?? null} fallbackUnit="degC" icon={Thermometer} dataState={dataState} />
        <GaugeCard title="T cold" sample={latest?.Tcold ?? null} fallbackUnit="degC" icon={Thermometer} dataState={dataState} />
      </div>
    </div>
  );
}


function PowerFlowTab() {
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-base">Power Flow — reference diagram</CardTitle></CardHeader>
      <CardContent>
        <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          Static reference only. This view does not display live power flow.
        </div>
        <div className="w-full overflow-hidden rounded-xl border bg-white">
          <img src="/power_flow.png" alt="Gyrotron Control Architecture Power Flow" className="max-w-full max-h-[75vh] mx-auto object-contain" />
        </div>
      </CardContent>
    </Card>
  );
}


type Step = { key: string; title: string; desc: string; targetTab?: string; targetId?: string; hint?: string };
const STARTUP_STEPS: Step[] = [
  { key: "prechecks", title: "Pre-checks", desc: "Review doors, waterflow, vacuum and interlock indications.", targetTab: "safety", hint: "Future PLC signals: GS Doors, Waterflow, Poor vacuum, External interlock" },
  { key: "ipsp", title: "Ion pump review", desc: "Review available read-only ion pump telemetry and quality.", targetTab: "monitoring", hint: "Telemetry does not establish hardware readiness" },
  { key: "heater", title: "Heater review", desc: "Review available read-only heater telemetry and quality.", targetTab: "monitoring", hint: "Telemetry does not establish hardware readiness" },
  { key: "cps_rect", title: "CPS Rectifier guidance", desc: "Future operator step; command unavailable.", targetTab: "power", targetId: "cps-rectifier" },
  { key: "cps_conv", title: "CPS Converter guidance", desc: "Future operator step; command unavailable.", targetTab: "power", targetId: "cps-converter" },
  { key: "set_cath", title: "Draft Cathode Voltage", desc: "Edit a local requested value only.", targetTab: "power", targetId: "setpoint-cathode" },
  { key: "set_an", title: "Draft Anode Voltage", desc: "Edit a local requested value only.", targetTab: "power", targetId: "setpoint-anode" },
  { key: "set_pulse", title: "Draft Pulse Duration", desc: "Edit a local requested value only.", targetTab: "power", targetId: "setpoint-pulse" },
  { key: "apply", title: "Apply Setpoints guidance", desc: "Hardware application is unavailable.", targetTab: "power", targetId: "apply-setpoints" },
  { key: "aps_rect", title: "APS Rectifier guidance", desc: "Future operator step; command unavailable.", targetTab: "power", targetId: "aps-rectifier" },
  { key: "aps_conv", title: "APS Converter guidance", desc: "Future operator step; command unavailable.", targetTab: "power", targetId: "aps-converter" },
  { key: "verify", title: "Review summary", desc: "Manual review only; this does not establish machine readiness.", targetTab: "dashboard" },
];


function StartupWizard({ goTo, status }: { goTo: (tab: string, id?: string) => void; status: SystemStatus | null }) {
  const [index, setIndex] = useState(0);
  const [reviewed, setReviewed] = useState<Record<string, boolean>>({});
  const step = STARTUP_STEPS[index];
  const canNext = reviewed[step.key] || index === STARTUP_STEPS.length - 1;
  const canMarkReviewed = index === 0 || reviewed[STARTUP_STEPS[index - 1].key];
  const observedState = step.key.startsWith("cps_")
    ? step.key === "cps_rect" ? status?.cps.rectifier : status?.cps.converter
    : step.key.startsWith("aps_")
      ? step.key === "aps_rect" ? status?.aps.rectifier : status?.aps.converter
      : null;

  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-base">Startup Guidance — non-authoritative</CardTitle></CardHeader>
      <CardContent>
        <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Manual review marks are navigation aids only. They do not verify PLC state, interlocks, or machine readiness.
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-1 space-y-2">
            {STARTUP_STEPS.map((item, itemIndex) => (
              <button
                type="button"
                key={item.key}
                className={`w-full text-left px-3 py-2 rounded-xl border text-sm ${itemIndex === index ? "bg-slate-100 border-slate-300" : "hover:bg-slate-50"}`}
                onClick={() => setIndex(itemIndex)}
              >
                <div className="flex items-center justify-between">
                  <div className="font-medium">{itemIndex + 1}. {item.title}</div>
                  {reviewed[item.key] && <span className="text-blue-600 text-xs">Reviewed</span>}
                </div>
                <div className="text-muted-foreground text-xs">{item.desc}</div>
              </button>
            ))}
          </div>
          <div className="lg:col-span-3">
            <div className="p-4 rounded-xl border bg-white space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm uppercase tracking-wide text-muted-foreground">Guidance step {index + 1} of {STARTUP_STEPS.length}</div>
                  <div className="text-xl font-semibold">{step.title}</div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => goTo(step.targetTab || "dashboard", step.targetId)}>View related screen</Button>
                  <Button
                    variant="secondary"
                    onClick={() => setReviewed((current) => ({ ...current, [step.key]: true }))}
                    disabled={!canMarkReviewed}
                  >
                    Mark reviewed — not verified
                  </Button>
                </div>
              </div>
              <p className="text-sm text-slate-600">{step.desc}</p>
              {observedState && (
                <div className="flex items-center gap-2 rounded-lg border bg-slate-50 p-2 text-sm">
                  PLC observed (read only): <StateBadge state={observedState} />
                </div>
              )}
              {step.hint && <div className="text-xs text-slate-500">{step.hint}</div>}
              <div className="pt-2 flex gap-2">
                <Button disabled={index === 0} onClick={() => setIndex(index - 1)} variant="ghost">Back</Button>
                <Button disabled={!canNext} onClick={() => setIndex(Math.min(index + 1, STARTUP_STEPS.length - 1))}>Next</Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}


function LogsTab({ enabled, onUnauthorized }: { enabled: boolean; onUnauthorized: () => void }) {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [nextBeforeId, setNextBeforeId] = useState<number | null>(null);
  const [category, setCategory] = useState<EventCategory | "">("");
  const [severity, setSeverity] = useState<"" | "info" | "warning" | "critical">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = useCallback(async (beforeId?: number) => {
    setLoading(true);
    try {
      const response = await api.getEvents({
        limit: 50,
        beforeId,
        category: category || undefined,
        severity: severity || undefined,
      });
      setEvents((current) => beforeId
        ? [...current, ...response.events.filter((event) => !current.some((item) => item.id === event.id))]
        : response.events);
      setNextBeforeId(response.next_before_id);
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
      } else {
        setError(caught instanceof ApiError ? caught.message : "Event history is unavailable.");
      }
    } finally {
      setLoading(false);
    }
  }, [category, severity, onUnauthorized]);

  useEffect(() => {
    if (!enabled) return;
    void loadEvents();
    const timer = setInterval(() => void loadEvents(), 5000);
    return () => clearInterval(timer);
  }, [enabled, loadEvents]);

  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2 flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-base">Backend-observed Event History</CardTitle>
        <Button variant="outline" size="sm" disabled={loading} onClick={() => void loadEvents()}>Refresh</Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg border border-blue-300 bg-blue-50 p-3 text-xs text-blue-900">
          Persistent application event history. This records what the backend observed; it is not a complete PLC or safety historian.
        </div>
        <div className="flex flex-wrap gap-3">
          <select className="rounded-lg border bg-white px-3 py-2 text-sm" value={category} onChange={(event) => setCategory(event.target.value as EventCategory | "")}>
            <option value="">All categories</option>
            {(["application", "monitoring", "machine_state", "interlock", "alarm", "security", "operator", "command"] as EventCategory[]).map((value) => (
              <option key={value} value={value}>{value.replace("_", " ")}</option>
            ))}
          </select>
          <select className="rounded-lg border bg-white px-3 py-2 text-sm" value={severity} onChange={(event) => setSeverity(event.target.value as typeof severity)}>
            <option value="">All severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        {error && <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900" role="alert">{error}</div>}
        {!error && loading && events.length === 0 && <div className="text-sm text-slate-500">Loading event history…</div>}
        {!error && !loading && events.length === 0 && <div className="text-sm text-slate-500">No backend-observed events match these filters.</div>}
        <div className="space-y-2">
          {events.map((event) => (
            <div key={event.id} className="grid grid-cols-1 gap-2 rounded-xl border bg-muted/20 px-3 py-3 md:grid-cols-12 md:items-center">
              <div className="text-xs font-mono text-slate-600 md:col-span-2">{new Date(event.recorded_at).toLocaleString()}</div>
              <div className="md:col-span-2"><Badge variant="outline">{event.category.replace("_", " ").toUpperCase()}</Badge></div>
              <div className="text-sm md:col-span-6">
                <div className="font-medium">{event.message}</div>
                <div className="text-xs text-slate-500">{event.actor ? `Actor: ${event.actor}` : `Source: ${event.source}`}{event.target ? ` · ${event.target}` : ""}</div>
              </div>
              <div className="md:col-span-2 md:text-right">{event.severity ? <Badge variant="outline">{event.severity.toUpperCase()}</Badge> : "—"}</div>
            </div>
          ))}
        </div>
        {nextBeforeId && (
          <Button variant="outline" disabled={loading} onClick={() => void loadEvents(nextBeforeId)}>Load older events</Button>
        )}
      </CardContent>
    </Card>
  );
}


export default function GyrotronAdamDashboard() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [tab, setTab] = useState("dashboard");
  const [commandCapabilities, setCommandCapabilities] = useState<CommandCapability[]>([]);

  const handleUnauthorized = useCallback(() => {
    setUser(null);
    setAuthError("Your session expired. Please sign in again.");
  }, []);

  const telemetry = useTelemetry(user !== null, handleUnauthorized);
  const system = useSystemStatus(user !== null, handleUnauthorized);

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    api.getCommandCapabilities(controller.signal)
      .then((response) => setCommandCapabilities(response.capabilities))
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 401) handleUnauthorized();
      });
    return () => controller.abort();
  }, [user, handleUnauthorized]);

  useEffect(() => {
    let active = true;
    api.getSession()
      .then((sessionUser) => {
        if (active) setUser(sessionUser);
      })
      .catch((caught) => {
        if (active && (!(caught instanceof ApiError) || caught.status !== 401)) {
          setAuthError("Unable to validate the current session.");
        }
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => { active = false; };
  }, []);

  async function handleLogout() {
    try {
      await api.logout();
      setUser(null);
      setAuthError(null);
      setTab("dashboard");
    } catch (caught) {
      setAuthError(caught instanceof ApiError ? caught.message : "Sign out failed; your server session remains active.");
    }
  }

  function goTo(tabName: string, id?: string) {
    setTab(tabName);
    if (id) {
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) {
          element.scrollIntoView({ behavior: "smooth", block: "center" });
          element.classList.add("ring", "ring-amber-400", "rounded-xl");
          setTimeout(() => element.classList.remove("ring", "ring-amber-400", "rounded-xl"), 1500);
        }
      }, 50);
    }
  }

  if (authLoading) {
    return <div className="min-h-screen grid place-items-center bg-slate-100 text-sm text-slate-600">Validating application session…</div>;
  }
  if (!user) {
    return (
      <div>
        {authError && <div className="bg-red-100 p-2 text-center text-sm text-red-800" role="alert">{authError}</div>}
        <Login onLogin={(sessionUser) => { setUser(sessionUser); setAuthError(null); }} />
      </div>
    );
  }

  const displayOverall: DisplayState = system.statusState !== "live"
    ? system.statusState
    : telemetry.dataState !== "live"
      ? telemetry.dataState
      : system.systemStatus?.overall_state ?? "unknown";
  const authoritativeStatus = system.statusState === "live" ? system.systemStatus : null;
  const applicationLabel = system.systemStatus?.mode === "opcua_readonly"
    ? "PLC Monitoring HMI · Read only · Commands disabled"
    : "Simulation HMI · CPS / APS / Interlocks";

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 text-slate-900">
      <header className="sticky top-0 z-30 backdrop-blur bg-white/90 border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-xl bg-slate-900 text-white grid place-items-center">GT</div>
            <div>
              <div className="font-semibold">Gyrotron Power Control</div>
              <div className="text-xs text-muted-foreground">{applicationLabel}</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2"><StatusDot state={displayOverall} /><span className="text-sm">{displayOverall.toUpperCase()}</span></div>
            <div className="flex items-center gap-2 border-l pl-4">
              <span className="text-sm font-medium text-slate-600">{user.username} <span className="text-xs text-muted-foreground">({user.role})</span></span>
              {user.role === "admin" && (
                <Button variant="ghost" size="sm" onClick={() => setTab("admin")} className="h-8 text-xs text-muted-foreground hover:text-blue-600 mr-1">Admin</Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => void handleLogout()} className="h-8 text-xs text-muted-foreground hover:text-red-600">Sign out</Button>
            </div>
          </div>
        </div>
      </header>

      <ModeBanner
        status={system.systemStatus}
        statusState={system.statusState}
        telemetryState={telemetry.dataState}
        statusError={system.error}
        telemetryError={telemetry.error}
      />

      {authError && <div className="max-w-7xl mx-auto mt-4 rounded-lg bg-red-100 p-3 text-sm text-red-800" role="alert">{authError}</div>}

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="rounded-2xl flex flex-wrap h-auto">
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="power">Power</TabsTrigger>
            <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
            <TabsTrigger value="flow">Power Flow</TabsTrigger>
            <TabsTrigger value="safety">Safety</TabsTrigger>
            <TabsTrigger value="startup">Startup</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
          </TabsList>
          <div className="mt-6" />
          <TabsContent value="dashboard">
            <Dashboard
              status={authoritativeStatus}
              data={telemetry.data}
              latest={telemetry.latest}
              telemetryState={telemetry.dataState}
              lastSuccessfulAt={telemetry.lastSuccessfulAt}
            />
          </TabsContent>
          <TabsContent value="power"><PowerTab status={authoritativeStatus} capabilities={user ? commandCapabilities : []} /></TabsContent>
          <TabsContent value="monitoring"><MonitoringTab data={telemetry.data} latest={telemetry.latest} dataState={telemetry.dataState} /></TabsContent>
          <TabsContent value="flow"><PowerFlowTab /></TabsContent>
          <TabsContent value="safety"><SafetyTab status={authoritativeStatus} capabilities={user ? commandCapabilities : []} /></TabsContent>
          <TabsContent value="startup"><StartupWizard goTo={goTo} status={authoritativeStatus} /></TabsContent>
          <TabsContent value="logs"><LogsTab enabled={tab === "logs"} onUnauthorized={handleUnauthorized} /></TabsContent>
          {user.role === "admin" && <TabsContent value="admin"><AdminTab /></TabsContent>}
        </Tabs>
      </main>
    </div>
  );
}


if (typeof window !== "undefined" && import.meta.env.MODE !== "production") {
  const keys = STARTUP_STEPS.map((step) => step.key);
  console.assert(new Set(keys).size === keys.length, "Duplicate keys in STARTUP_STEPS");
  const indexOf = (key: string) => STARTUP_STEPS.findIndex((step) => step.key === key);
  console.assert(indexOf("cps_rect") < indexOf("cps_conv"), "CPS rectifier guidance must precede converter guidance");
  console.assert(indexOf("set_cath") < indexOf("apply"), "Cathode draft must precede Apply guidance");
  console.assert(indexOf("set_an") < indexOf("apply"), "Anode draft must precede Apply guidance");
  console.assert(indexOf("aps_rect") < indexOf("aps_conv"), "APS rectifier guidance must precede converter guidance");
}
