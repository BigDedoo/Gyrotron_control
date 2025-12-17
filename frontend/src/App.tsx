import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Activity, AlertTriangle, Flame, Gauge, ShieldCheck, Settings, Power, Thermometer, Timer, Zap } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts";

// =========================================================
// Helper UI
// =========================================================
function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={`inline-block size-3 rounded-full mr-2 ${ok ? "bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.25)]" : "bg-red-500 shadow-[0_0_0_3px_rgba(239,68,68,0.25)]"}`} />
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-12 items-center gap-3">
      <div className="col-span-5 text-sm text-muted-foreground">{label}</div>
      <div className="col-span-7">{children}</div>
    </div>
  );
}

function GaugeCard({ title, value, unit, icon: Icon }: { title: string; value: number; unit?: string; icon?: any }) {
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2"><Icon className="size-4" /> {title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold">{value.toFixed(1)}{unit}</div>
      </CardContent>
    </Card>
  );
}

function Indicator({ label, ok, warn = false }: { label: string; ok: boolean; warn?: boolean }) {
  const color = ok ? "bg-emerald-500" : warn ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`inline-block size-2 rounded-full ${color}`}></span>
      <span>{label}</span>
    </div>
  );
}

// =========================================================
// Telemetry (live from backend)
// =========================================================
function useTelemetry() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    // Poll backend every 1000ms
    const id = setInterval(async () => {
      try {
        const res = await fetch("/api/telemetry");
        if (!res.ok) throw new Error("Failed to fetch");
        const point = await res.json();

        setData((prev) => {
          // Keep last 40 points
          const newData = [...prev, point];
          if (newData.length > 40) newData.shift();
          return newData;
        });
      } catch (err) {
        console.error("Telemetry fetch error:", err);
      }
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const latest = data[data.length - 1] || {
    time: 0, ionV: 0, ionI: 0, heatV: 0, heatI: 0, heLvl: 0, Thot: 0, Tcold: 0
  };
  return { data, latest };
}

// =========================================================
// Sections
// =========================================================
function Dashboard({ cpsOn, apsOn, faults, data, latest }: { cpsOn: boolean; apsOn: boolean; faults: string[], data: any[], latest: any }) {
  const ok = faults.length === 0;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base"><Activity className="size-4" /> System Overview</CardTitle>
          <Badge variant={ok ? "default" : "destructive"} className="text-xs px-3 py-1 rounded-full">{ok ? "All systems nominal" : `${faults.length} alarm(s)`}</Badge>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <GaugeCard title="Ion Pump V" value={latest.ionV} unit=" V" icon={Gauge} />
            <GaugeCard title="Ion Pump I" value={latest.ionI} unit=" A" icon={Zap} />
            <GaugeCard title="Heater V" value={latest.heatV} unit=" V" icon={Flame} />
            <GaugeCard title="Heater I" value={latest.heatI} unit=" A" icon={Zap} />
            <GaugeCard title="Liquid He Level" value={latest.heLvl} unit=" %" icon={Gauge} />
            <GaugeCard title="T hot" value={latest.Thot} unit=" °C" icon={Thermometer} />
            <GaugeCard title="T cold" value={latest.Tcold} unit=" °C" icon={Thermometer} />
            <GaugeCard title="Pulse Duration" value={2.5} unit=" ms" icon={Timer} />
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="rounded-2xl">
              <CardHeader className="pb-2"><CardTitle className="text-sm">Heater Voltage (live)</CardTitle></CardHeader>
              <CardContent>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                      <defs>
                        <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8884d8" stopOpacity={0.6} />
                          <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" hide />
                      <YAxis domain={[0, 'dataMax + 2']} width={28} />
                      <Tooltip />
                      <Area type="monotone" dataKey="heatV" stroke="#8884d8" fillOpacity={1} fill="url(#g1)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardHeader className="pb-2"><CardTitle className="text-sm">Ion Pump Current (live)</CardTitle></CardHeader>
              <CardContent>
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ left: 0, right: 0, top: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" hide />
                      <YAxis domain={[0, 'dataMax + 2']} width={28} />
                      <Tooltip />
                      <Line type="monotone" dataKey="ionI" stroke="#82ca9d" dot={false} />
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
          <CardTitle className="text-base flex items-center gap-2"><ShieldCheck className="size-4" /> Quick Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="font-medium mb-2">CPS</div>
            <div className="space-y-1">
              <Indicator label="Ready" ok={cpsOn} />
              <Indicator label="Power Rectifier ON" ok={cpsOn} />
              <Indicator label="Charging Converter ON" ok={false} warn />
              <Indicator label="Protection" ok={true} />
            </div>
          </div>
          <Separator />
          <div>
            <div className="font-medium mb-2">APS</div>
            <div className="space-y-1">
              <Indicator label="Ready" ok={apsOn} />
              <Indicator label="Power Rectifier ON" ok={apsOn} />
              <Indicator label="Charging Converter ON" ok={false} warn />
              <Indicator label="Protection" ok={true} />
            </div>
          </div>
          <Separator />
          <div>
            <div className="font-medium mb-2">Active Alarms</div>
            {faults.length === 0 ? (
              <Badge className="bg-emerald-600">None</Badge>
            ) : (
              <ul className="text-sm list-disc ml-5 space-y-1">
                {faults.map((f, i) => (
                  <li key={i} className="flex items-center gap-2"><AlertTriangle className="size-4 text-amber-500" />{f}</li>
                ))}
              </ul>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PowerTab() {
  const [pulse, setPulse] = useState(2.5);
  const [vcath, setVcath] = useState(6.0);
  const [vanode, setVanode] = useState(5.0);
  const [cpsCmd, setCpsCmd] = useState({ rect: false, conv: false });
  const [apsCmd, setApsCmd] = useState({ rect: false, conv: false });
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Settings className="size-4" /> Setpoints</CardTitle></CardHeader>
        <CardContent className="space-y-6">
          <Labeled label={`Pulse duration: ${pulse.toFixed(2)} ms`}>
            <div id="setpoint-pulse">
              <Slider value={[pulse]} onValueChange={(v) => setPulse(v[0])} min={0} max={10} step={0.1} />
            </div>
          </Labeled>
          <Labeled label={`Cathode voltage: ${vcath.toFixed(2)} V`}>
            <div id="setpoint-cathode">
              <Slider value={[vcath]} onValueChange={(v) => setVcath(v[0])} min={0} max={10} step={0.1} />
            </div>
          </Labeled>
          <Labeled label={`Anode voltage: ${vanode.toFixed(2)} V`}>
            <div id="setpoint-anode">
              <Slider value={[vanode]} onValueChange={(v) => setVanode(v[0])} min={0} max={10} step={0.1} />
            </div>
          </Labeled>
          <div className="flex gap-3 pt-2">
            <Button id="apply-setpoints" className="rounded-2xl">Apply Setpoints</Button>
            <Button variant="outline" className="rounded-2xl">Revert</Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4">
        <Card className="rounded-2xl">
          <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Power className="size-4" /> CPS Commands</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Labeled label="Power Rectifier">
              <div id="cps-rectifier" className="flex items-center gap-3">
                <Switch checked={cpsCmd.rect} onCheckedChange={(v) => setCpsCmd({ ...cpsCmd, rect: v })} />
                <Badge variant={cpsCmd.rect ? "default" : "secondary"}>{cpsCmd.rect ? "ON" : "OFF"}</Badge>
              </div>
            </Labeled>
            <Labeled label="Charging Converter">
              <div id="cps-converter" className="flex items-center gap-3">
                <Switch checked={cpsCmd.conv} onCheckedChange={(v) => setCpsCmd({ ...cpsCmd, conv: v })} />
                <Badge variant={cpsCmd.conv ? "default" : "secondary"}>{cpsCmd.conv ? "ON" : "OFF"}</Badge>
              </div>
            </Labeled>
            <div className="flex gap-3 pt-2">
              <Button className="rounded-2xl" variant="secondary">Protection Reset</Button>
              <Button className="rounded-2xl" variant="outline">Apply</Button>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Power className="size-4" /> APS Commands</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Labeled label="Power Rectifier">
              <div id="aps-rectifier" className="flex items-center gap-3">
                <Switch checked={apsCmd.rect} onCheckedChange={(v) => setApsCmd({ ...apsCmd, rect: v })} />
                <Badge variant={apsCmd.rect ? "default" : "secondary"}>{apsCmd.rect ? "ON" : "OFF"}</Badge>
              </div>
            </Labeled>
            <Labeled label="Charging Converter">
              <div id="aps-converter" className="flex items-center gap-3">
                <Switch checked={apsCmd.conv} onCheckedChange={(v) => setApsCmd({ ...apsCmd, conv: v })} />
                <Badge variant={apsCmd.conv ? "default" : "secondary"}>{apsCmd.conv ? "ON" : "OFF"}</Badge>
              </div>
            </Labeled>
            <div className="flex gap-3 pt-2">
              <Button className="rounded-2xl" variant="secondary">Protection Reset</Button>
              <Button className="rounded-2xl" variant="outline">Apply</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SafetyTab() {
  const items = [
    { g: "Environment", k: ["External interlock", "GS Doors", "Waterflow", "Poor vacuum"] },
    { g: "Supplies", k: ["CMPS ON", "GPPS ON", "IPPS ON", "APS ON", "CPS ON"] },
    { g: "Alarms", k: ["ARC detector", "Overcurrent", "Overvoltage", "Temperature"] },
    { g: "Cryo", k: ["Liquid He gauge", "He level normal"] },
  ];
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      {items.map((grp) => (
        <Card key={grp.g} className="rounded-2xl">
          <CardHeader className="pb-2"><CardTitle className="text-sm">{grp.g}</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 gap-2">
            {grp.k.map((k) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">{k}</span>
                <Badge className="rounded-full">OK</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
      <Card className="rounded-2xl">
        <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><AlertTriangle className="size-4" /> Actions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Button className="rounded-2xl w-full" variant="secondary">Reset Interlocks</Button>
          <Button className="rounded-2xl w-full" variant="destructive">Emergency Shutdown</Button>
        </CardContent>
      </Card>
    </div>
  );
}

function MonitoringTab({ data, latest }: { data: any[], latest: any }) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <Card className="rounded-2xl xl:col-span-2">
        <CardHeader className="pb-2"><CardTitle className="text-base">Live Trends</CardTitle></CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="ionV" stroke="#8884d8" dot={false} />
                <Line type="monotone" dataKey="ionI" stroke="#82ca9d" dot={false} />
                <Line type="monotone" dataKey="heatV" stroke="#ffc658" dot={false} />
                <Line type="monotone" dataKey="heatI" stroke="#ff7300" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 gap-4">
        <GaugeCard title="Liquid He Level" value={latest.heLvl} unit=" %" icon={Gauge} />
        <GaugeCard title="T hot" value={latest.Thot} unit=" °C" icon={Thermometer} />
        <GaugeCard title="T cold" value={latest.Tcold} unit=" °C" icon={Thermometer} />
      </div>
    </div>
  );
}

function PowerFlowTab() {
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-base">Power Flow</CardTitle></CardHeader>
      <CardContent>
        <div className="w-full overflow-hidden rounded-xl border bg-white">
          <img
            src="/power_flow.png"
            alt="Gyrotron Control Architecture Power Flow"
            className="max-w-full max-h-[75vh] mx-auto object-contain"
          />
        </div>
      </CardContent>
    </Card>
  );
}

// =========================================================
// Startup Wizard
// =========================================================
type Step = { key: string; title: string; desc: string; targetTab?: string; targetId?: string; hint?: string };
export const STARTUP_STEPS: Step[] = [
  { key: "prechecks", title: "Pre-checks", desc: "Verify doors closed, waterflow OK, vacuum good, interlocks reset.", targetTab: "safety", hint: "5052: GS Doors, Waterflow, Poor vacuum, External interlock" },
  { key: "ipsp", title: "Ion pump ON", desc: "Ensure ion pump supply is powered.", targetTab: "monitoring", hint: "5017: Ion Pump V/I rising; 5052: IPPS ON" },
  { key: "heater", title: "Heaters ON", desc: "Turn on cathode filament/heater and wait for emission temperature.", targetTab: "monitoring", hint: "5017: Heater V/I; 5013: T hot/cold" },
  { key: "cps_rect", title: "CPS Rectifier ON", desc: "Enable CPS Power Rectifier.", targetTab: "power", targetId: "cps-rectifier", hint: "5068: DO0; 5052: CPS Rectifier ON" },
  { key: "cps_conv", title: "CPS Charging Converter ON", desc: "Enable CPS converter.", targetTab: "power", targetId: "cps-converter", hint: "5068: DO2; 5052: CPS Converter ON" },
  { key: "set_cath", title: "Set Cathode Voltage", desc: "Adjust cathode setpoint (AO1).", targetTab: "power", targetId: "setpoint-cathode", hint: "5024: AO1 Cathode preset" },
  { key: "set_an", title: "Set Anode Voltage", desc: "Adjust anode setpoint (AO2).", targetTab: "power", targetId: "setpoint-anode", hint: "5024: AO2 Anode preset" },
  { key: "set_pulse", title: "Set Pulse Duration", desc: "Adjust pulse duration (AO0).", targetTab: "power", targetId: "setpoint-pulse", hint: "5024: AO0 Pulse duration" },
  { key: "apply", title: "Apply Setpoints", desc: "Apply analog setpoints.", targetTab: "power", targetId: "apply-setpoints", hint: "UI: Apply setpoints button" },
  { key: "aps_rect", title: "APS Rectifier ON", desc: "Enable APS Power Rectifier.", targetTab: "power", targetId: "aps-rectifier", hint: "5069: DO0; 5052: APS Rectifier ON" },
  { key: "aps_conv", title: "APS Charging Converter ON", desc: "Enable APS converter.", targetTab: "power", targetId: "aps-converter", hint: "5069: DO2; 5052: APS Converter ON" },
  { key: "verify", title: "Verify Ready", desc: "Confirm CPS/APS Ready, no alarms, then proceed to operation.", targetTab: "dashboard", hint: "5052: Ready flags; Alarms clear" },
];

function StartupWizard({ goTo }: { goTo: (tab: string, id?: string) => void }) {
  const [i, setI] = useState(0);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const step = STARTUP_STEPS[i];

  function focusTarget() {
    goTo(step.targetTab || "dashboard", step.targetId);
  }
  function markDone() {
    setDone((d) => ({ ...d, [step.key]: true }));
  }
  const canNext = done[step.key] || i === STARTUP_STEPS.length - 1;

  const canMarkDone = i === 0 || done[STARTUP_STEPS[i - 1].key];

  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-base">Startup Sequencer</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-1 space-y-2">
            {STARTUP_STEPS.map((s, idx) => (
              <div key={s.key} className={`px-3 py-2 rounded-xl border text-sm cursor-pointer ${idx === i ? "bg-slate-100 border-slate-300" : "hover:bg-slate-50"}`} onClick={() => setI(idx)}>
                <div className="flex items-center justify-between">
                  <div className="font-medium">{idx + 1}. {s.title}</div>
                  {done[s.key] && <span className="text-emerald-600 text-xs">✔</span>}
                </div>
                <div className="text-muted-foreground text-xs">{s.desc}</div>
                {s.hint && <div className="text-[10px] text-slate-500 mt-1">Hint: {s.hint}</div>}
              </div>
            ))}
          </div>
          <div className="lg:col-span-3">
            <div className="p-4 rounded-xl border bg-white space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm uppercase tracking-wide text-muted-foreground">Step {i + 1} of {STARTUP_STEPS.length}</div>
                  <div className="text-xl font-semibold">{step.title}</div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={focusTarget}>Go to control</Button>
                  <Button variant="secondary" onClick={markDone} disabled={!canMarkDone}>Mark done</Button>
                </div>
              </div>
              <p className="text-sm text-slate-600">{step.desc}</p>
              {step.hint && (
                <div className="text-xs text-slate-500">Signals involved: {step.hint}</div>
              )}
              <div className="pt-2 flex gap-2">
                <Button disabled={i === 0} onClick={() => setI(i - 1)} variant="ghost">Back</Button>
                <Button disabled={!canNext} onClick={() => setI(Math.min(i + 1, STARTUP_STEPS.length - 1))}>Next</Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =========================================================
// Logs
// =========================================================
function LogsTab() {
  const rows = [
    { t: "12:02:41", m: "CPS Rectifier ON" },
    { t: "12:03:02", m: "CPS Converter ON" },
    { t: "12:03:15", m: "Apply setpoints (2.5ms / 6.0V / 5.0V)" },
    { t: "12:07:11", m: "ARC detected on APS – protection active" },
  ];
  return (
    <Card className="rounded-2xl">
      <CardHeader className="pb-2"><CardTitle className="text-base">Event Log (mock)</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-12 text-xs uppercase text-muted-foreground mb-2">
          <div className="col-span-2">Time</div>
          <div className="col-span-10">Message</div>
        </div>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="grid grid-cols-12 items-center text-sm bg-muted/30 rounded-xl px-3 py-2">
              <div className="col-span-2 font-mono">{r.t}</div>
              <div className="col-span-10">{r.m}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// =========================================================
// Root
// =========================================================
export default function GyrotronAdamDashboard() {
  const [tab, setTab] = useState("dashboard");
  const [cpsOn] = useState(true);
  const [apsOn] = useState(false);
  const faults: string[] = [];
  const { data, latest } = useTelemetry();

  function goTo(tabName: string, id?: string) {
    setTab(tabName);
    if (id) {
      // delay to allow tab to mount
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.classList.add("ring", "ring-amber-400", "rounded-xl");
          setTimeout(() => el.classList.remove("ring", "ring-amber-400", "rounded-xl"), 1500);
        }
      }, 50);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 text-slate-900">
      <header className="sticky top-0 z-30 backdrop-blur bg-white/70 border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded-xl bg-slate-900 text-white grid place-items-center">GT</div>
            <div>
              <div className="font-semibold">Gyrotron Power Control</div>
              <div className="text-xs text-muted-foreground">ADAM-5000E • CPS / APS / Interlocks</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot ok={faults.length === 0} />
            <span className="text-sm">{faults.length === 0 ? "Nominal" : "Fault"}</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="rounded-2xl">
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="power">Power</TabsTrigger>
            <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
            <TabsTrigger value="flow">Power Flow</TabsTrigger>
            <TabsTrigger value="safety">Safety</TabsTrigger>
            <TabsTrigger value="startup">Startup</TabsTrigger>
            <TabsTrigger value="logs">Logs</TabsTrigger>
          </TabsList>
          <div className="mt-6" />
          <TabsContent value="dashboard"><Dashboard cpsOn={cpsOn} apsOn={apsOn} faults={faults} data={data} latest={latest} /></TabsContent>
          <TabsContent value="power"><PowerTab /></TabsContent>
          <TabsContent value="monitoring"><MonitoringTab data={data} latest={latest} /></TabsContent>
          <TabsContent value="flow"><PowerFlowTab /></TabsContent>
          <TabsContent value="safety"><SafetyTab /></TabsContent>
          <TabsContent value="startup"><StartupWizard goTo={goTo} /></TabsContent>
          <TabsContent value="logs"><LogsTab /></TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// =========================================================
// Lightweight DEV tests (run in dev only)
// These are not unit-test framework tests, but quick runtime invariants
// =========================================================
if (typeof window !== "undefined" && (import.meta as any)?.env?.MODE !== "production") {
  // Test 1: step keys are unique
  const keys = STARTUP_STEPS.map(s => s.key);
  console.assert(new Set(keys).size === keys.length, "Duplicate keys in STARTUP_STEPS");

  // Test 2: ordering constraints
  function indexOf(k: string) { return STARTUP_STEPS.findIndex(s => s.key === k); }
  console.assert(indexOf("cps_rect") < indexOf("cps_conv"), "CPS rectifier must precede converter");
  console.assert(indexOf("set_cath") < indexOf("apply"), "Set cathode before Apply");
  console.assert(indexOf("set_an") < indexOf("apply"), "Set anode before Apply");
  console.assert(indexOf("aps_rect") < indexOf("aps_conv"), "APS rectifier must precede converter");
  console.assert(indexOf("apply") < indexOf("verify"), "Apply must precede Verify");
}
