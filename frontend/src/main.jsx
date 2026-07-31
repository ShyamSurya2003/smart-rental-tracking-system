import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import {
  AlertTriangle,
  BarChart3,
  BellRing,
  CheckCircle2,
  ClipboardList,
  Gauge,
  LineChart as LineChartIcon,
  Mail,
  PackageSearch,
  Radar,
  Search,
  SlidersHorizontal,
  Truck
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import "./styles.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8001`;
const api = axios.create({ baseURL: API_BASE_URL });
const COLORS = ["#0f9f8f", "#2563eb", "#d97706", "#dc2626", "#64748b", "#7c3aed"];

function useApi(path, fallback) {
  const [data, setData] = useState(fallback);
  const [loading, setLoading] = useState(true);

  const load = async (params = {}) => {
    setLoading(true);
    try {
      const response = await api.get(path, { params });
      setData(response.data);
    } catch {
      setData(fallback);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [path]);

  return { data, loading, load, setData };
}

function App() {
  return (
    <Router>
      <div className="app-shell">
        <Sidebar />
        <main className="main-panel">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/equipment" element={<Equipment />} />
            <Route path="/checkin" element={<CheckIn />} />
            <Route path="/mobile-log" element={<MobileLog />} />
            <Route path="/usage" element={<UsageLogs />} />
            <Route path="/anomaly" element={<Anomaly />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/alerts" element={<Alerts />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

function Sidebar() {
  const links = [
    ["/", Gauge, "Dashboard"],
    ["/equipment", Truck, "Live Status"],
    ["/checkin", Radar, "Check-In"],
    ["/usage", ClipboardList, "Usage Logs"],
    ["/anomaly", AlertTriangle, "Anomaly"],
    ["/forecast", LineChartIcon, "Forecast"],
    ["/alerts", PackageSearch, "Alerts"]
  ];
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">SR</div>
        <div>
          <h1>Smart Rental</h1>
          <p>Tracking System</p>
        </div>
      </div>
      <nav>
        {links.map(([to, Icon, label]) => (
          <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

function PageHeader({ eyebrow, title, children }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p>{eyebrow}</p>}
        <h2>{title}</h2>
      </div>
      {children}
    </header>
  );
}

function KpiCard({ label, value, icon: Icon, tone = "mint" }) {
  return (
    <section className={`kpi-card ${tone}`}>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
      <Icon size={22} />
    </section>
  );
}

function Dashboard() {
  const [range, setRange] = useState("30d");
  const { data, load } = useApi("/api/dashboard", {
    kpis: {},
    status_distribution: [],
    utilization_by_type: [],
    engine_idle_trend: [],
    risk_distribution: [],
    demand_forecast: [],
    recent_alerts: []
  });
  useEffect(() => {
    load({ range });
  }, [range]);
  const kpis = data.kpis || {};

  return (
    <>
      <PageHeader eyebrow="Operations overview" title="Equipment Rental Intelligence">
        <FilterStrip compact range={range} setRange={setRange} />
      </PageHeader>
      <div className="kpi-grid">
        <KpiCard label="Total Equipment" value={kpis.total_equipment ?? "-"} icon={Truck} />
        <KpiCard label="Active Rentals" value={kpis.active_rentals ?? "-"} icon={CheckCircle2} tone="blue" />
        <KpiCard label="Overdue Assets" value={kpis.overdue_assets ?? "-"} icon={AlertTriangle} tone="amber" />
        <KpiCard label="Anomaly Alerts" value={kpis.anomaly_alerts ?? "-"} icon={Radar} tone="red" />
        <KpiCard label="Avg Utilization" value={`${kpis.average_utilization ?? "-"}%`} icon={Gauge} tone="steel" />
      </div>
      <div className="chart-grid">
        <ChartPanel title="Equipment Status">
          <Donut data={data.status_distribution} />
        </ChartPanel>
        <ChartPanel title="Utilization by Type">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.utilization_by_type}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="utilization" fill="#0f9f8f" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Engine vs Idle Hours">
          <ResponsiveContainer width="100%" height={270}>
            <LineChart data={data.engine_idle_trend}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="engine" stroke="#2563eb" strokeWidth={3} />
              <Line type="monotone" dataKey="idle" stroke="#d97706" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Demand Forecast">
          <ForecastChart data={data.demand_forecast} />
        </ChartPanel>
      </div>
      <section className="panel">
        <div className="panel-title">
          <h3>Recent Model Alerts</h3>
        </div>
        <div className="alert-list">
          {data.recent_alerts.map((alert) => (
            <AlertItem key={`${alert.equipment_id}-${alert.message}`} alert={alert} />
          ))}
        </div>
      </section>
    </>
  );
}

function Equipment() {
  const [filters, setFilters] = useState(defaultFilters());
  const { data, load } = useApi("/api/equipment", []);
  const { data: options } = useApi("/api/filter-options", defaultFilterOptions());
  useEffect(() => {
    load(cleanFilters(filters));
  }, [filters.search, filters.status, filters.risk, filters.equipment_type, filters.site_id, filters.operator_id]);
  const charts = useMemo(() => buildSummaryCharts(data), [data]);

  return (
    <>
      <PageHeader eyebrow="Live asset board" title="Equipment Live Status" />
      <FilterPanel filters={filters} setFilters={setFilters} options={options} onApply={(current = filters) => load(cleanFilters(current))} />
      <div className="chart-grid three">
        <ChartPanel title="Equipment by Status"><Donut data={charts.status} /></ChartPanel>
        <ChartPanel title="Equipment by Site"><SimpleBar data={charts.sites} dataKey="value" /></ChartPanel>
        <ChartPanel title="Top Idle Equipment"><SimpleBar data={charts.idle} dataKey="idle_hours_per_day" /></ChartPanel>
      </div>
      <DataTable rows={data} />
    </>
  );
}

function CheckIn() {
  const { data: qrData, load: loadQrLogs } = useApi("/api/qr-logs", { total: 0, rows: [] });
  const origin = window.location.origin;
  const loginUrl = `${origin}/mobile-log?action=LOG_IN`;
  const logoutUrl = `${origin}/mobile-log?action=LOG_OUT`;

  useEffect(() => {
    const timer = window.setInterval(() => loadQrLogs(), 3000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <>
      <PageHeader eyebrow="QR desk monitor" title="Equipment Log-In / Log-Out" />
      <section className="qr-workbench">
        <div className="qr-action-row">
          <div className="qr-card display-card">
            <div className="qr-code-frame">
              <QRCodeSVG value={loginUrl} size={220} level="M" />
            </div>
            <strong>Log-In QR</strong>
          </div>
          <div className="qr-card display-card">
            <div className="qr-code-frame">
              <QRCodeSVG value={logoutUrl} size={220} level="M" />
            </div>
            <strong>Log-Out QR</strong>
          </div>
        </div>
      </section>
      <QrLogMonitor rows={qrData.rows || []} />
    </>
  );
}

function MobileLog() {
  const params = new URLSearchParams(window.location.search);
  const initialAction = params.get("action") === "LOG_OUT" ? "LOG_OUT" : "LOG_IN";
  const [form, setForm] = useState({
    action: initialAction,
    equipment_id: "",
    type: "Excavator",
    site_id: "",
    event_date: "2026-07-30",
    engine_hours_per_day: "",
    idle_hours_per_day: "",
    rental_days: "",
    last_operator_id: ""
  });
  const [savedLog, setSavedLog] = useState(null);
  const [formError, setFormError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setFormError("");
    const payload = {
      ...form,
      site_id: form.site_id || null,
      last_operator_id: form.last_operator_id || null,
      engine_hours_per_day: form.action === "LOG_OUT" ? Number(form.engine_hours_per_day) : null,
      idle_hours_per_day: form.action === "LOG_OUT" ? Number(form.idle_hours_per_day) : null,
      rental_days: form.action === "LOG_OUT" ? Number(form.rental_days) : null
    };
    try {
      const response = await api.post("/api/qr-log", payload);
      setSavedLog(response.data.log);
    } catch (error) {
      setFormError(error.response?.data?.detail || "Unable to submit details. Please check the log-in record.");
    }
  };

  return (
    <main className="mobile-page">
      <section className="mobile-card">
        <div className="mobile-badge">{form.action === "LOG_IN" ? "Log-In QR" : "Log-Out QR"}</div>
        <h2>{form.action === "LOG_IN" ? "Enter Log-In Details" : "Enter Log-Out Details"}</h2>
        {formError && <div className="form-error">{formError}</div>}
        {!savedLog ? (
          <form className="mobile-form" onSubmit={submit}>
            <Input label="Equipment ID" value={form.equipment_id} onChange={(v) => setForm({ ...form, equipment_id: v })} />
            <Select label="Type" value={form.type} options={["Excavator", "Crane", "Bulldozer", "Grader"]} onChange={(v) => setForm({ ...form, type: v })} />
            <Input label="Site ID" value={form.site_id} placeholder="NULL allowed" onChange={(v) => setForm({ ...form, site_id: v })} />
            <Input label={form.action === "LOG_IN" ? "Log-In Date" : "Log-Out Date"} type="date" value={form.event_date} onChange={(v) => setForm({ ...form, event_date: v })} />
            <Input label="Driver / Operator ID" value={form.last_operator_id} placeholder="NULL allowed" onChange={(v) => setForm({ ...form, last_operator_id: v })} />
            {form.action === "LOG_OUT" && (
              <>
                <Input label="Engine Hours/Day" type="number" value={form.engine_hours_per_day} onChange={(v) => setForm({ ...form, engine_hours_per_day: v })} />
                <Input label="Idle Hours/Day" type="number" value={form.idle_hours_per_day} onChange={(v) => setForm({ ...form, idle_hours_per_day: v })} />
                <Input label="Rental Days" type="number" value={form.rental_days} onChange={(v) => setForm({ ...form, rental_days: v })} />
              </>
            )}
            <button className="primary-action" type="submit">Submit Details</button>
          </form>
        ) : (
          <SavedLogDetails log={savedLog} />
        )}
      </section>
    </main>
  );
}

function QrLogMonitor({ rows }) {
  return (
    <section className="panel table-panel qr-monitor">
      <div className="panel-title">
        <h3>Submitted QR Details</h3>
        <span className="live-dot">Live</span>
      </div>
      {rows.length === 0 ? (
        <div className="empty-log-state">Scan a QR with your mobile and submit details. The record will appear here automatically.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>Equipment ID</th>
                <th>Type</th>
                <th>Site ID</th>
                <th>Date</th>
                <th>Engine</th>
                <th>Idle</th>
                <th>Rental Days</th>
                <th>Driver / Operator</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.action === "LOG_IN" ? "Log-In" : "Log-Out"}</td>
                  <td>{row.equipment_id}</td>
                  <td>{row.type}</td>
                  <td>{row.site_id || "NULL"}</td>
                  <td>{row.event_date}</td>
                  <td>{row.action === "LOG_IN" ? "-" : row.engine_hours_per_day}</td>
                  <td>{row.action === "LOG_IN" ? "-" : row.idle_hours_per_day}</td>
                  <td>{row.action === "LOG_IN" ? "-" : row.rental_days}</td>
                  <td>{row.last_operator_id || "NULL"}</td>
                  <td><span className="status-pill">{row.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function UsageLogs() {
  const [filters, setFilters] = useState(defaultFilters());
  const { data, load } = useApi("/api/usage-logs", { total: 0, rows: [] });
  const { data: options } = useApi("/api/filter-options", defaultFilterOptions());
  useEffect(() => {
    load({ ...cleanFilters(filters), limit: 100 });
  }, [filters.search, filters.status, filters.risk, filters.equipment_type, filters.site_id, filters.operator_id]);
  const rows = data.rows || [];
  const summary = data.summary || {};
  const scatter = rows.map((row) => ({ x: row.engine_hours_per_day, y: row.idle_hours_per_day, z: row.risk_level }));

  return (
    <>
      <PageHeader eyebrow="Historical records" title="Usage Logs" />
      <FilterPanel filters={filters} setFilters={setFilters} options={options} onApply={(current = filters) => load({ ...cleanFilters(current), limit: 100 })} />
      <div className="kpi-grid">
        <KpiCard label="Runtime Hours" value={summary.runtime_hours ?? "-"} icon={Gauge} />
        <KpiCard label="Fuel Usage" value={summary.fuel_usage ? `${summary.fuel_usage} L` : "-"} icon={Truck} tone="blue" />
        <KpiCard label="Top Location" value={summary.top_location ?? "-"} icon={PackageSearch} tone="blue" />
        <KpiCard label="Idle Hours" value={summary.idle_hours ?? "-"} icon={AlertTriangle} tone="amber" />
        <KpiCard label="Rented Hours" value={summary.total_rented_hours ?? "-"} icon={ClipboardList} tone="steel" />
        <KpiCard label="Downtime" value={summary.downtime ?? "-"} icon={Radar} tone="red" />
      </div>
      <div className="chart-grid">
        <ChartPanel title="Engine Hours vs Idle Hours">
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid />
              <XAxis dataKey="x" name="Engine" />
              <YAxis dataKey="y" name="Idle" />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} />
              <Scatter data={scatter} fill="#0f9f8f" />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="Rental Days Distribution">
          <SimpleBar data={rows.slice(0, 12).map((row) => ({ name: row.equipment_id, value: row.rental_days }))} dataKey="value" />
        </ChartPanel>
        <ChartPanel title="Usage per Site">
          <SimpleBar data={data.usage_per_site || []} dataKey="value" />
        </ChartPanel>
        <ChartPanel title="Under-Utilized Assets (%)">
          <SimpleBar data={data.under_utilized || []} dataKey="value" />
        </ChartPanel>
      </div>
      <section className="panel recommendation-panel">
        <div className="panel-title"><h3>Recommendations</h3></div>
        {(data.recommendations || []).map((item) => <p key={item}>{item}</p>)}
      </section>
      <DataTable rows={rows} total={data.total} />
    </>
  );
}

function Anomaly() {
  const [filters, setFilters] = useState({ search: "", prediction: "All", risk: "All", equipment_type: "All" });
  const { data, load } = useApi("/api/model-results", { total: 0, rows: [] });
  const { data: options } = useApi("/api/filter-options", defaultFilterOptions());
  const { data: summary } = useApi("/api/model-summary", {
    total: 0,
    anomalies: 0,
    normal: 0,
    prediction_distribution: [],
    anomaly_types: [],
    score_buckets: [],
    scatter_rows: []
  });
  useEffect(() => {
    load(cleanFilters(filters));
  }, [filters.search, filters.prediction, filters.risk, filters.equipment_type]);
  const rows = data.rows || [];
  const anomalySummary = useMemo(() => ({
    total: data.total || rows.length,
    anomalies: rows.filter((row) => row.prediction === "Anomaly").length,
    prediction_distribution: Object.entries(countBy(rows, "prediction")).map(([name, value]) => ({ name, value })),
    anomaly_types: Object.entries(countBy(rows.filter((row) => row.prediction === "Anomaly"), "type")).map(([name, value]) => ({ name, value })),
    score_buckets: buildScoreBuckets(rows),
    scatter_rows: rows.slice(0, 180)
  }), [rows, data.total]);
  const longIdleRows = rows.filter((row) => row.idle_hours_per_day >= 8).slice(0, 8);
  const unassignedRows = rows
    .filter((row) => !row.site_id || !row.last_operator_id)
    .map((row) => ({
      name: row.equipment_id,
      value: Math.min(
        100,
        (!row.site_id ? 42 : 0) +
          (!row.last_operator_id ? 38 : 0) +
          Math.min(Number(row.idle_hours_per_day || 0) * 2.2, 16) +
          Math.min(Number(row.rental_days || 0) / 4, 8)
      )
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
  const riskByType = Object.values(
    rows.reduce((acc, row) => {
      const key = row.type || "Unknown";
      const score = Number(row.anomaly_score || 0) * 100;
      acc[key] ||= { name: key, total: 0, count: 0 };
      acc[key].total += score;
      acc[key].count += 1;
      return acc;
    }, {})
  ).map((row) => ({ name: row.name, value: Math.round(row.total / row.count) })).sort((a, b) => b.value - a.value);
  return (
    <>
      <PageHeader title="Anomaly Detection" />
      <section className="filter-panel compact-panel">
        <SearchBox value={filters.search} onChange={(search) => setFilters({ ...filters, search })} onSubmit={(search) => setFilters({ ...filters, search })} />
        <Select label="Prediction" value={filters.prediction} options={options.predictions} onChange={(prediction) => setFilters({ ...filters, prediction })} />
        <Select label="Risk Level" value={filters.risk} options={options.risks} onChange={(risk) => setFilters({ ...filters, risk })} />
        <Select label="Equipment Type" value={filters.equipment_type} options={options.equipment_types} onChange={(equipment_type) => setFilters({ ...filters, equipment_type })} />
      </section>
      <div className="kpi-grid">
        <KpiCard label="Model Records" value={anomalySummary.total ?? "-"} icon={ClipboardList} />
        <KpiCard label="Shown Rows" value={rows.length} icon={AlertTriangle} tone="red" />
        <KpiCard label="Anomalies" value={anomalySummary.anomalies ?? "-"} icon={Radar} tone="amber" />
        <KpiCard label="Long Idle" value={rows.filter((row) => row.idle_hours_per_day >= 8).length} icon={Gauge} tone="red" />
        <KpiCard label="Unassigned" value={rows.filter((row) => !row.site_id || !row.last_operator_id).length} icon={PackageSearch} tone="amber" />
      </div>
      <div className="chart-grid">
        <ChartPanel title="Normal vs Anomaly"><Donut data={anomalySummary.prediction_distribution} /></ChartPanel>
        <ChartPanel title="Anomalies by Type"><SimpleBar data={anomalySummary.anomaly_types} dataKey="value" /></ChartPanel>
        <ChartPanel title="Long Idle Equipment">
          <SimpleBar data={longIdleRows.map((row) => ({ name: row.equipment_id, value: row.idle_hours_per_day }))} dataKey="value" />
        </ChartPanel>
        <ChartPanel title="Assignment Risk Score">
          <SimpleBar data={unassignedRows} dataKey="value" />
        </ChartPanel>
        <ChartPanel title="Average Risk by Type"><SimpleBar data={riskByType} dataKey="value" /></ChartPanel>
        <ChartPanel title="Engine vs Idle Pattern">
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid />
              <XAxis type="number" dataKey="engine_hours_per_day" name="Engine" tickCount={5} />
              <YAxis type="number" dataKey="idle_hours_per_day" name="Idle" tickCount={5} />
              <Tooltip />
              <Scatter data={anomalySummary.scatter_rows} fill="#2563eb" />
            </ScatterChart>
          </ResponsiveContainer>
        </ChartPanel>
      </div>
      <DataTable rows={rows} />
    </>
  );
}

function Forecast() {
  const [range, setRange] = useState("30d");
  const { data, load } = useApi("/api/forecast", []);
  useEffect(() => {
    load({ range });
  }, [range]);
  const latest = data[data.length - 1] || {};
  const demandRows = ["Excavator", "Crane", "Bulldozer", "Grader"].map((name) => ({
    name,
    predicted: latest[name] || 0
  }));
  return (
    <>
      <PageHeader eyebrow="Demand planning" title="Forecasting">
        <FutureFilterStrip range={range} setRange={setRange} />
      </PageHeader>
      <div className="chart-grid">
        <ChartPanel title={`${FUTURE_RANGE_LABELS[range]} Demand Forecast`}><ForecastChart data={data} /></ChartPanel>
        <ChartPanel title="Predicted Demand by Type"><SimpleBar data={demandRows} dataKey="predicted" /></ChartPanel>
      </div>
      <section className="panel insight-grid">
        {demandRows.map((row) => (
          <div key={row.name} className="insight">
            <strong>{row.name}</strong>
            <span>{row.predicted >= 45 ? "High" : row.predicted >= 25 ? "Medium" : "Low"} demand</span>
            <p>{row.predicted >= 45 ? "Increase availability." : row.predicted >= 25 ? "Keep units ready." : "Reassign idle units."}</p>
          </div>
        ))}
      </section>
    </>
  );
}

function Alerts() {
  const [filters, setFilters] = useState({ risk: "All", search: "", alert_type: "All", range: "30d" });
  const { data, load } = useApi("/api/alerts", []);
  useEffect(() => {
    load({ risk: filters.risk, range: filters.range });
  }, [filters.risk, filters.range]);
  const visibleAlerts = data.filter((alert) => {
    const text = `${alert.equipment_id} ${alert.type} ${alert.site_id} ${alert.message}`.toLowerCase();
    const searchHit = !filters.search || text.includes(filters.search.toLowerCase());
    const typeHit = filters.alert_type === "All" || alert.alert_type === filters.alert_type;
    return searchHit && typeHit;
  });
  const chartData = Object.entries(countBy(visibleAlerts, "risk_level")).map(([name, value]) => ({ name, value }));
  return (
    <>
      <PageHeader eyebrow="Risk queue" title="Alerts">
        <SearchBox value={filters.search} onChange={(search) => setFilters({ ...filters, search })} onSubmit={(search) => setFilters({ ...filters, search })} />
      </PageHeader>
      <section className="filter-panel compact-panel">
        <Select label="Range" value={filters.range} options={["30d", "3m", "6m", "1y"]} onChange={(range) => setFilters({ ...filters, range })} />
        <Select label="Risk Level" value={filters.risk} options={["All", "High", "Medium", "Low"]} onChange={(risk) => setFilters({ ...filters, risk })} />
        <Select label="Alert Type" value={filters.alert_type} options={["All", "Return Due", "Overdue"]} onChange={(alert_type) => setFilters({ ...filters, alert_type })} />
      </section>
      <div className="chart-grid three">
        <ChartPanel title="Return Reminders by Risk"><Donut data={chartData} /></ChartPanel>
        <ChartPanel title="Return Reminder Type"><SimpleBar data={Object.entries(countBy(visibleAlerts, "alert_type")).map(([name, value]) => ({ name, value }))} dataKey="value" /></ChartPanel>
      </div>
      <section className="alert-list">
        {visibleAlerts.map((alert) => <AlertItem key={alert.id} alert={alert} />)}
      </section>
    </>
  );
}

function ChartPanel({ title, children }) {
  return (
    <section className="panel chart-panel">
      <div className="panel-title">
        <h3>{title}</h3>
        <BarChart3 size={18} />
      </div>
      {children}
    </section>
  );
}

function Donut({ data }) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={88} paddingAngle={3}>
          {data.map((_, index) => <Cell key={index} fill={COLORS[index % COLORS.length]} />)}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function SimpleBar({ data, dataKey }) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data} margin={{ left: 6, right: 12, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" interval={0} tick={{ fontSize: 12 }} angle={-20} textAnchor="end" height={48} />
        <YAxis />
        <Tooltip />
        <Bar dataKey={dataKey} fill="#2563eb" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ForecastChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="day" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="Excavator" stroke="#0f9f8f" strokeWidth={3} />
        <Line type="monotone" dataKey="Crane" stroke="#2563eb" strokeWidth={3} />
        <Line type="monotone" dataKey="Bulldozer" stroke="#d97706" strokeWidth={3} />
        <Line type="monotone" dataKey="Grader" stroke="#7c3aed" strokeWidth={3} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const RANGE_LABELS = {
  "30d": "Last 30 days",
  "3m": "Last 3 months",
  "6m": "Last 6 months",
  "1y": "Last year"
};

const FUTURE_RANGE_LABELS = {
  "30d": "Next 30 days",
  "3m": "Next 3 months",
  "6m": "Next 6 months",
  "1y": "Next year"
};

function FutureFilterStrip({ range, setRange }) {
  return (
    <label className="filter-chip">
      <SlidersHorizontal size={16} />
      <select value={range} onChange={(event) => setRange(event.target.value)}>
        {Object.entries(FUTURE_RANGE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
  );
}

function FilterStrip({ filters, setFilters, compact = false, range = "30d", setRange = () => {} }) {
  if (compact) {
    return (
      <label className="filter-chip">
        <SlidersHorizontal size={16} />
        <select value={range} onChange={(event) => setRange(event.target.value)}>
          {Object.entries(RANGE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
    );
  }
  return (
    <div className="filter-strip">
      <Select value={filters.equipment_type} options={["All", "Excavator", "Crane", "Bulldozer", "Grader"]} onChange={(equipment_type) => setFilters({ ...filters, equipment_type })} />
      <Select value={filters.status} options={["All", "Active", "Anomaly", "Idle Risk", "Missing Site", "Overdue"]} onChange={(status) => setFilters({ ...filters, status })} />
      <Select value={filters.risk} options={["All", "Low", "Medium", "High"]} onChange={(risk) => setFilters({ ...filters, risk })} />
      <button className="ghost-button" onClick={() => setFilters({ search: "", status: "All", risk: "All", equipment_type: "All" })}>Reset</button>
    </div>
  );
}
function FilterPanel({ filters, setFilters, options = defaultFilterOptions(), onApply }) {
  const update = (key, value) => setFilters({ ...filters, [key]: value });
  const reset = () => {
    const next = defaultFilters();
    setFilters(next);
    setTimeout(() => onApply(next), 0);
  };

  return (
    <section className="filter-panel">
      <div className="filter-panel-head">
        <div className="filter-panel-title">
          <SlidersHorizontal size={18} />
          <strong>Filters</strong>
        </div>
        <SearchBox value={filters.search} onChange={(search) => update("search", search)} onSubmit={(search) => onApply({ ...filters, search })} />
      </div>
      <div className="filter-grid">
        <Select label="Equipment Type" value={filters.equipment_type} options={options.equipment_types} onChange={(value) => update("equipment_type", value)} />
        <Select label="Status" value={filters.status} options={options.statuses} onChange={(value) => update("status", value)} />
        <Select label="Risk Level" value={filters.risk} options={options.risks} onChange={(value) => update("risk", value)} />
        <Select label="Site ID" value={filters.site_id} options={options.sites} onChange={(value) => update("site_id", value)} />
        <Select label="Operator ID" value={filters.operator_id} options={options.operators} onChange={(value) => update("operator_id", value)} />
        <Input label="Min Idle Hours" type="number" value={filters.min_idle} onChange={(value) => update("min_idle", value)} required={false} />
        <Input label="Max Idle Hours" type="number" value={filters.max_idle} onChange={(value) => update("max_idle", value)} required={false} />
        <Input label="Min Rental Days" type="number" value={filters.min_rental_days} onChange={(value) => update("min_rental_days", value)} required={false} />
        <Input label="Max Rental Days" type="number" value={filters.max_rental_days} onChange={(value) => update("max_rental_days", value)} required={false} />
        <div className="filter-actions">
          <button className="primary-action small" type="button" onClick={() => onApply(filters)}>Apply</button>
          <button className="ghost-button" type="button" onClick={reset}>Reset</button>
        </div>
      </div>
    </section>
  );
}

function AlertToast({ toast, onClose }) {
  return (
    <aside className="alert-toast" role="alert">
      <div className="toast-icon">
        <BellRing size={22} />
      </div>
      <div>
        <strong>{toast.title}</strong>
        <p>{toast.message}</p>
        <span><Mail size={14} /> Email queued to {toast.email}</span>
      </div>
      <button type="button" onClick={onClose} aria-label="Dismiss alert">x</button>
    </aside>
  );
}

function SavedLogDetails({ log }) {
  const details = [
    ["Action", log.action === "LOG_IN" ? "Log-In" : "Log-Out"],
    ["Equipment ID", log.equipment_id],
    ["Type", log.type],
    ["Site ID", log.site_id || "NULL"],
    ["Date", log.event_date],
    ["Last Operator ID", log.last_operator_id || "NULL"],
    ["Status", log.status]
  ];
  if (log.action === "LOG_OUT") {
    details.splice(5, 0, ["Engine Hours/Day", log.engine_hours_per_day], ["Idle Hours/Day", log.idle_hours_per_day], ["Rental Days", log.rental_days]);
  }

  return (
    <section className="panel saved-log-panel">
      <div className="panel-title">
        <h3>Saved QR Details</h3>
        <CheckCircle2 size={18} />
      </div>
      <div className="saved-log-grid">
        {details.map(([label, value]) => (
          <div className="saved-log-cell" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function SearchBox({ value, onChange, onSubmit }) {
  return (
    <div className="search-box">
      <Search size={17} />
      <input value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSubmit(event.currentTarget.value)} placeholder="Search equipment, site, operator, status" />
      <button onClick={() => onSubmit(value)}>Search</button>
    </div>
  );
}

function DataTable({ rows, total }) {
  return (
    <section className="panel table-panel">
      <div className="panel-title">
        <h3>Records {total ? `(${total})` : ""}</h3>
      </div>
      {rows.length === 0 ? (
        <div className="empty-log-state">No exact match for these filters. Change one filter or use Reset to view available records.</div>
      ) : (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Equipment ID</th>
              <th>Type</th>
              <th>Site ID</th>
              <th>Check-In</th>
              <th>Check-Out</th>
              <th>Engine</th>
              <th>Idle</th>
              <th>Rental Days</th>
              <th>Operator</th>
              <th>Status</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.equipment_id}</td>
                <td>{row.type}</td>
                <td>{row.site_id || "NULL"}</td>
                <td>{row.check_in_date}</td>
                <td>{row.check_out_date}</td>
                <td>{row.engine_hours_per_day}</td>
                <td>{row.idle_hours_per_day}</td>
                <td>{row.rental_days}</td>
                <td>{row.last_operator_id || "NULL"}</td>
                <td><span className="status-pill">{row.status}</span></td>
                <td><span className={`risk-pill ${row.risk_level?.toLowerCase()}`}>{row.risk_level}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

function AlertItem({ alert }) {
  return (
    <article className={`alert-item ${alert.risk_level?.toLowerCase()}`}>
      <div>
        <strong>{alert.equipment_id} - {alert.type}</strong>
        <p>{alert.message}</p>
        <small>Site {alert.site_id || "NULL"} · Due {alert.check_out_date}</small>
      </div>
      <span>{alert.alert_type}</span>
    </article>
  );
}

function Input({ label, value, onChange, type = "text", placeholder = "", required }) {
  const isRequired = required ?? (label !== "Site ID" && label !== "Last Operator ID");
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} required={isRequired} />
    </label>
  );
}

function Select({ label, value, options, onChange }) {
  return (
    <label className={label ? "field" : "select-only"}>
      {label && <span>{label}</span>}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </label>
  );
}

function buildSummaryCharts(rows) {
  const status = Object.entries(countBy(rows, "status")).map(([name, value]) => ({ name, value }));
  const sites = Object.entries(countBy(rows, "site_id")).map(([name, value]) => ({ name: name === "null" ? "NULL" : name, value })).slice(0, 8);
  const predictions = Object.entries(countBy(rows, "prediction")).map(([name, value]) => ({ name, value }));
  const anomalyTypes = Object.entries(countBy(rows.filter((row) => row.prediction === "Anomaly"), "type")).map(([name, value]) => ({ name, value }));
  const idle = [...rows].sort((a, b) => b.idle_hours_per_day - a.idle_hours_per_day).slice(0, 5).map((row) => ({ name: row.equipment_id, idle_hours_per_day: row.idle_hours_per_day }));
  return { status, sites, idle, predictions, anomalyTypes };
}

function buildScoreBuckets(rows) {
  const buckets = [
    { name: "0-20", min: 0, max: 0.2, value: 0 },
    { name: "20-40", min: 0.2, max: 0.4, value: 0 },
    { name: "40-60", min: 0.4, max: 0.6, value: 0 },
    { name: "60-80", min: 0.6, max: 0.8, value: 0 },
    { name: "80-100", min: 0.8, max: 1.01, value: 0 }
  ];
  rows.forEach((row) => {
    const score = Number(row.anomaly_score || 0);
    const bucket = buckets.find((item) => score >= item.min && score < item.max);
    if (bucket) bucket.value += 1;
  });
  return buckets.map(({ name, value }) => ({ name, value }));
}

function countBy(rows, key) {
  return rows.reduce((acc, row) => {
    const value = String(row[key] ?? "NULL");
    acc[value] = (acc[value] || 0) + 1;
    return acc;
  }, {});
}

function defaultFilters() {
  return {
    search: "",
    status: "All",
    risk: "All",
    equipment_type: "All",
    site_id: "All",
    operator_id: "All",
    min_idle: "",
    max_idle: "",
    min_rental_days: "",
    max_rental_days: ""
  };
}

function defaultFilterOptions() {
  return {
    equipment_types: ["All", "Excavator", "Crane", "Bulldozer", "Grader"],
    statuses: ["All", "Active", "Anomaly", "Idle Risk", "Missing Site", "Overdue"],
    risks: ["All", "Low", "Medium", "High"],
    sites: ["All"],
    operators: ["All"],
    predictions: ["All", "Anomaly", "Normal"]
  };
}

function cleanFilters(filters) {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== "" && value !== null && value !== undefined)
  );
}

createRoot(document.getElementById("root")).render(<App />);
