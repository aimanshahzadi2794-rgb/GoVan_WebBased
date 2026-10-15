import React, { useEffect, useState } from "react";
import { api } from "../api";
import StatusPill from "../components/StatusPill.jsx";
import MapView from "../components/MapView.jsx";
import LocationLabel from "../components/LocationLabel.jsx";

const TABS = ["Overview", "Vehicles", "Drivers", "Routes", "Trips", "History", "Reports", "Users", "Organizations", "Alerts"];

const ICON_SHAPES = {
  vehicle: (
    <>
      <rect x="1" y="3" width="15" height="13" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </>
  ),
  driver: (
    <>
      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </>
  ),
  route: (
    <>
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </>
  ),
  trip: <path d="M3 11l19-9-9 19-2-8-8-2z" />,
  alert: (
    <>
      <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 01-3.46 0" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </>
  ),
};

function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {ICON_SHAPES[name]}
    </svg>
  );
}

function SectionTitle({ icon, children }) {
  return (
    <div className="title-row">
      <span className="icon-badge">
        <Icon name={icon} size={16} />
      </span>
      <h2>{children}</h2>
    </div>
  );
}

export default function AdminDashboard({ user }) {
  const [tab, setTab] = useState("Overview");
  const [vehicles, setVehicles] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [users, setUsers] = useState([]);
  const [organizations, setOrganizations] = useState([]);
  const [organizationFilter, setOrganizationFilter] = useState("");
  const [routes, setRoutes] = useState([]);
  const [trips, setTrips] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [fleetSummary, setFleetSummary] = useState(null);
  const [error, setError] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);

  async function refreshAll() {
    try {
      const [v, d, r, t, a, fs, u, o] = await Promise.all([
        api.get("/vehicles/"),
        api.get("/drivers/"),
        api.get("/routes/"),
        api.get("/trips/"),
        api.get("/alerts/"),
        api.get("/vehicles/summary"),
        api.getUsers(),
        api.getOrganizations(),
      ]);
      setVehicles(v);
      setDrivers(d);
      setRoutes(r);
      setTrips(t);
      setAlerts(a);
      setFleetSummary(fs);
      setUsers(u);
      setOrganizations(o);
    } catch (err) {
      setError(err.message);
    } finally {
      setInitialLoading(false);
    }
  }

  useEffect(() => {
    refreshAll();
    // Poll so live trip locations, statuses, and stats update on their own --
    // without this, an admin watching the Trips map would need to manually
    // switch tabs or reload to see a moving vehicle.
    const interval = setInterval(refreshAll, 6000);
    return () => clearInterval(interval);
  }, []);

  const openAlertsCount = alerts.filter((a) => a.status === "open").length;
  const hasOrganizationFilter = organizationFilter !== "";
  const matchesOrganization = (record) => !hasOrganizationFilter
    || (organizationFilter === "unassigned"
      ? record.organization_id == null
      : record.organization_id === Number(organizationFilter));
  const filteredVehicles = vehicles.filter(matchesOrganization);
  const filteredRoutes = routes.filter(matchesOrganization);
  const filteredRouteIds = new Set(filteredRoutes.map((route) => route.id));
  const filteredTrips = hasOrganizationFilter
    ? trips.filter((trip) => filteredRouteIds.has(trip.route_id))
    : trips;
  const activeTripsCount = filteredTrips.filter((trip) => trip.status === "active").length;

  useEffect(() => {
    if (
      organizationFilter
      && organizationFilter !== "unassigned"
      && !organizations.some((organization) => organization.id === Number(organizationFilter))
    ) {
      setOrganizationFilter("");
    }
  }, [organizationFilter, organizations]);

  return (
    <div className="container">
    <div className="page-hero">
  <h2>Fleet command center</h2>
  <p className="hero-sub">Live view of your vehicles, drivers, routes and trips.</p>
  <div className="hero-chips">
    <span className="hero-chip">{filteredVehicles.length} vehicles</span>
    <span className="hero-chip">{drivers.length} drivers</span>
    <span className="hero-chip">{activeTripsCount} active trips</span>
    {openAlertsCount > 0 && <span className="hero-chip alert">{openAlertsCount} open alerts</span>}
  </div>
  <svg className="hero-route-line" viewBox="0 0 700 40" preserveAspectRatio="none">
    <path d="M -10 30 C 100 10, 200 38, 320 18 C 440 -2, 560 28, 710 12" stroke="#fff" strokeWidth="2" strokeDasharray="1 10" strokeLinecap="round" fill="none" />
  </svg>
</div>
      <div className="tabs">
        {TABS.map((t) => (
          <div key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t}
          </div>
        ))}
      </div>

      <div className="inline-form" style={{ marginBottom: 16 }}>
        <label htmlFor="organization-filter">Organization</label>
        <select
          id="organization-filter"
          value={organizationFilter}
          onChange={(event) => setOrganizationFilter(event.target.value)}
        >
          <option value="">All organizations</option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
          <option value="unassigned">Unassigned</option>
        </select>
      </div>

      {error && <div className="error-text" role="alert">{error}</div>}

      {initialLoading ? (
        <div className="card" role="status" aria-live="polite">Loading {tab.toLowerCase()} data...</div>
      ) : (
      <>
      {tab === "Overview" && (
        <Overview
          vehicles={filteredVehicles}
          drivers={drivers}
          routes={filteredRoutes}
          trips={filteredTrips}
          alerts={alerts}
          fleetSummary={hasOrganizationFilter ? null : fleetSummary}
        />
      )}
      {tab === "Vehicles" && (
        <VehiclesTab
          vehicles={filteredVehicles}
          routes={filteredRoutes}
          trips={filteredTrips}
          organizations={organizations}
          onChange={refreshAll}
          setError={setError}
        />
      )}
      {tab === "Drivers" && (
        <DriversTab drivers={drivers} vehicles={vehicles} trips={trips} onChange={refreshAll} setError={setError} />
      )}
      {tab === "Routes" && (
        <RoutesTab
          routes={filteredRoutes}
          vehicles={filteredVehicles}
          trips={filteredTrips}
          organizations={organizations}
          onChange={refreshAll}
          setError={setError}
        />
      )}
      {tab === "Trips" && <TripsTab trips={filteredTrips} routes={filteredRoutes} drivers={drivers} onChange={refreshAll} setError={setError} />}
      {tab === "History" && <HistoryTab trips={filteredTrips} routes={filteredRoutes} drivers={drivers} setError={setError} />}
      {tab === "Reports" && (
        <ReportsTab
          routes={filteredRoutes}
          vehicles={filteredVehicles}
          drivers={drivers}
          organizationFilter={organizationFilter}
          setError={setError}
        />
      )}
      {tab === "Users" && <UsersTab users={users} organizations={organizations} currentUser={user} onChange={refreshAll} setError={setError} />}
      {tab === "Organizations" && <OrganizationsTab organizations={organizations} onChange={refreshAll} setError={setError} />}
      {tab === "Alerts" && <AlertsTab alerts={alerts} onChange={refreshAll} setError={setError} />}
      </>
      )}
    </div>
  );
}

function ReportsTab({ routes, vehicles, drivers, organizationFilter, setError }) {
  const [fromDate, setFromDate] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 29);
    return formatDateInput(date);
  });
  const [toDate, setToDate] = useState(() => formatDateInput(new Date()));
  const [routeId, setRouteId] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [driverId, setDriverId] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadReport() {
      setLoading(true);
      setError("");
      try {
        const filters = {
          from: fromDate,
          to: toDate,
          route_id: routeId,
          vehicle_id: vehicleId,
          driver_id: driverId,
          ...(organizationFilter === "unassigned"
            ? { unassigned_organization: true }
            : organizationFilter
              ? { organization_id: organizationFilter }
              : {}),
        };
        const result = await api.getReportSummary(filters);
        if (!cancelled) setReport(result);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadReport();
    return () => {
      cancelled = true;
    };
  }, [fromDate, toDate, routeId, vehicleId, driverId, organizationFilter, setError]);

  function downloadCsv() {
    if (!report) return;
    const columns = [
      ["Trip ID", "trip_id"],
      ["Route", "route_name"],
      ["Vehicle", "vehicle_plate"],
      ["Driver", "driver_name"],
      ["Status", "status"],
      ["Created", "created_at"],
      ["Started", "started_at"],
      ["Ended", "ended_at"],
      ["Duration (minutes)", "duration_minutes"],
      ["Delay (minutes)", "delay_minutes"],
      ["Passengers booked", "passengers_booked"],
    ];
    const escapeCsv = (value) => {
      const text = value == null ? "" : String(value);
      return `"${text.replaceAll('"', '""')}"`;
    };
    const rows = [
      columns.map(([label]) => escapeCsv(label)).join(","),
      ...report.trip_history.map((trip) => columns
        .map(([, key]) => escapeCsv(trip[key]))
        .join(",")),
    ];
    const blob = new Blob([rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `travelease-trip-report-${fromDate}-to-${toDate}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="card">
        <div className="section-header">
          <SectionTitle icon="clock">Reports</SectionTitle>
        </div>
        <div className="inline-form">
          <label>
            From
            <input type="date" value={fromDate} max={toDate} onChange={(event) => setFromDate(event.target.value)} />
          </label>
          <label>
            To
            <input type="date" value={toDate} min={fromDate} onChange={(event) => setToDate(event.target.value)} />
          </label>
          <label>
            Route
            <select value={routeId} onChange={(event) => setRouteId(event.target.value)}>
              <option value="">All routes</option>
              {routes.map((route) => <option key={route.id} value={route.id}>{route.name}</option>)}
            </select>
          </label>
          <label>
            Vehicle
            <select value={vehicleId} onChange={(event) => setVehicleId(event.target.value)}>
              <option value="">All vehicles</option>
              {vehicles.map((vehicle) => (
                <option key={vehicle.id} value={vehicle.id}>{vehicle.plate_number} - {vehicle.model}</option>
              ))}
            </select>
          </label>
          <label>
            Driver
            <select value={driverId} onChange={(event) => setDriverId(event.target.value)}>
              <option value="">All drivers</option>
              {drivers.map((driver) => <option key={driver.id} value={driver.id}>{driver.name}</option>)}
            </select>
          </label>
          <button type="button" onClick={downloadCsv} disabled={!report || report.trip_history.length === 0}>
            Download CSV
          </button>
        </div>
        {loading && <p className="hint-text">Loading report...</p>}
      </div>

      {report && (
        <>
          <div className="grid-cards">
            <StatCard
              icon="clock"
              tone="blue"
              label="Average trip duration"
              value={report.average_duration_minutes == null ? "—" : `${report.average_duration_minutes} min`}
            />
            <StatCard
              icon="trip"
              tone="amber"
              label="Average delay"
              value={report.average_delay_minutes == null ? "—" : `${report.average_delay_minutes} min`}
            />
            <StatCard icon="alert" tone="coral" label="SOS alerts" value={report.sos_count} />
            <StatCard icon="trip" tone="teal" label="Trips in period" value={report.trip_history.length} />
          </div>
          <div className="grid-cards">
            <ReportBarChart
              title="Trips per day"
              rows={report.trips_per_day.map((item) => ({
                label: item.date,
                value: item.trips,
              }))}
            />
            <ReportBarChart
              title="On-time vs delayed"
              rows={[
                { label: "On time (≤ 5 min late)", value: report.on_time_vs_delayed.on_time },
                { label: "Delayed (> 5 min)", value: report.on_time_vs_delayed.delayed },
              ]}
            />
            <ReportBarChart
              title="Passengers booked per route"
              rows={report.passengers_booked_per_route.map((item) => ({
                label: item.route_name,
                value: item.passengers_booked,
              }))}
            />
            <ReportBarChart
              title="Completed vs cancelled"
              rows={[
                { label: "Completed", value: report.completed_vs_cancelled.completed },
                { label: "Cancelled", value: report.completed_vs_cancelled.cancelled },
              ]}
            />
          </div>
          <div className="card">
            <div className="section-header">
              <SectionTitle icon="trip">Filtered trip history</SectionTitle>
            </div>
            {report.trip_history.length === 0 ? (
              <div className="empty-state">No trips match these report filters.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Route</th><th>Vehicle</th><th>Driver</th><th>Status</th>
                    <th>Started</th><th>Duration</th><th>Delay</th><th>Passengers</th>
                  </tr>
                </thead>
                <tbody>
                  {report.trip_history.map((trip) => (
                    <tr key={trip.trip_id}>
                      <td>{trip.route_name}</td>
                      <td>{trip.vehicle_plate || "—"}</td>
                      <td>{trip.driver_name}</td>
                      <td>{trip.status}</td>
                      <td>{trip.started_at ? formatDateTime(trip.started_at) : "—"}</td>
                      <td>{trip.duration_minutes == null ? "—" : `${trip.duration_minutes} min`}</td>
                      <td>{trip.delay_minutes == null ? "—" : `${trip.delay_minutes} min`}</td>
                      <td>{trip.passengers_booked}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ReportBarChart({ title, rows }) {
  const maximum = Math.max(1, ...rows.map((row) => row.value));
  return (
    <div className="card">
      <h3>{title}</h3>
      {rows.length === 0 ? (
        <div className="empty-state">No data for this period.</div>
      ) : rows.map((row) => (
        <div key={row.label} style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
            <span>{row.label}</span><strong>{row.value}</strong>
          </div>
          <div style={{ height: 10, background: "var(--border, #e6eaf0)", borderRadius: 8 }}>
            <div
              style={{
                width: `${(row.value / maximum) * 100}%`,
                height: "100%",
                background: "var(--primary, #2f6fed)",
                borderRadius: 8,
                minWidth: row.value > 0 ? 4 : 0,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function formatDateInput(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function Overview({ vehicles, drivers, routes, trips, alerts, fleetSummary }) {
  const activeTrips = trips.filter((t) => t.status === "active").length;
  const openAlerts = alerts.filter((a) => a.status === "open").length;
  return (
    <div>
      <div className="grid-cards">
        <StatCard icon="vehicle" tone="blue" label="Vehicles" value={vehicles.length} />
        <StatCard icon="driver" tone="teal" label="Drivers" value={drivers.length} />
        <StatCard icon="route" tone="green" label="Routes" value={routes.length} />
        <StatCard icon="trip" tone="amber" label="Active trips" value={activeTrips} />
        <StatCard icon="alert" tone="coral" label="Open alerts" value={openAlerts} />
      </div>
      {openAlerts > 0 && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <strong style={{ color: "var(--danger)" }}>
            {openAlerts} unresolved emergency alert{openAlerts > 1 ? "s" : ""}
          </strong>{" "}
          — check the Alerts tab.
        </div>
      )}
      {fleetSummary && <FleetOverviewCard summary={fleetSummary} />}
    </div>
  );
}

function ProgressBar({ label, pct }) {
  return (
    <div className="progress-row">
      <div className="progress-label">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

function FleetOverviewCard({ summary }) {
  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="vehicle">Fleet Overview</SectionTitle>
      </div>

      <div style={{ fontSize: 28, fontWeight: 800, color: "var(--navy)", marginBottom: 14 }}>
        {summary.total_vehicles} Total Vehicles
      </div>

      <div className="fleet-counts">
        <div className="fleet-count-chip">
          <span className="dot on-route" /> {summary.on_route} On Route
        </div>
        <div className="fleet-count-chip">
          <span className="dot idle" /> {summary.idle} Idle
        </div>
        <div className="fleet-count-chip">
          <span className="dot maintenance" /> {summary.maintenance} Maintenance
        </div>
        <div className="fleet-count-chip">
          <span className="dot offline" /> {summary.offline} Offline
        </div>
      </div>

      <ProgressBar label="Fleet Utilization" pct={summary.utilization_pct} />
      <ProgressBar label="Average Occupancy" pct={summary.average_occupancy_pct} />

      <p className="hint-text" style={{ marginTop: 0 }}>
        {summary.occupied_capacity} of {summary.total_capacity} total seats occupied across the fleet ({summary.available_capacity} available).
      </p>
    </div>
  );
}

function StatCard({ label, value, icon, tone = "blue" }) {
  return (
    <div className="stat-card">
      {icon && (
        <div className={`stat-icon ${tone}`}>
          <Icon name={icon} size={22} />
        </div>
      )}
      <div>
        <div className="value">{value}</div>
        <div className="label">{label}</div>
      </div>
    </div>
  );
}

function VehiclesTab({ vehicles, routes, trips, organizations, onChange, setError }) {
  const [plate, setPlate] = useState("");
  const [model, setModel] = useState("");
  const [capacity, setCapacity] = useState(12);
  const [organizationId, setOrganizationId] = useState("");
  const [search, setSearch] = useState("");
  const [editingVehicleId, setEditingVehicleId] = useState(null);
  const [vehicleEdit, setVehicleEdit] = useState({});

  const [expandedVehicleId, setExpandedVehicleId] = useState(null);
  const [maintenanceHistory, setMaintenanceHistory] = useState([]);
  const [maintDesc, setMaintDesc] = useState("");
  const [maintCost, setMaintCost] = useState("");

  async function addVehicle(e) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/vehicles/", {
        plate_number: plate,
        model,
        capacity: Number(capacity),
        organization_id: organizationId ? Number(organizationId) : null,
      });
      setPlate("");
      setModel("");
      setCapacity(12);
      setOrganizationId("");
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function setStatus(id, status) {
    try {
      await api.patch(`/vehicles/${id}/status`, { status });
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  function beginVehicleEdit(vehicle) {
    setEditingVehicleId(vehicle.id);
    setVehicleEdit({
      plate_number: vehicle.plate_number,
      model: vehicle.model,
      capacity: vehicle.capacity,
      ownership_type: vehicle.ownership_type,
      organization_id: vehicle.organization_id ? String(vehicle.organization_id) : "",
    });
  }

  async function saveVehicle(e, id) {
    e.preventDefault();
    setError("");
    try {
      await api.patch(`/vehicles/${id}`, {
        ...vehicleEdit,
        capacity: Number(vehicleEdit.capacity),
        organization_id: vehicleEdit.organization_id ? Number(vehicleEdit.organization_id) : null,
      });
      setEditingVehicleId(null);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleMaintenance(vehicleId) {
    if (expandedVehicleId === vehicleId) {
      setExpandedVehicleId(null);
      return;
    }
    setExpandedVehicleId(vehicleId);
    try {
      const history = await api.get(`/vehicles/${vehicleId}/maintenance`);
      setMaintenanceHistory(history);
    } catch (err) {
      setError(err.message);
    }
  }

  async function logMaintenance(vehicleId) {
    if (!maintDesc.trim()) return;
    try {
      await api.post(`/vehicles/${vehicleId}/maintenance`, {
        description: maintDesc,
        cost: maintCost === "" ? null : Number(maintCost),
      });
      setMaintDesc("");
      setMaintCost("");
      const history = await api.get(`/vehicles/${vehicleId}/maintenance`);
      setMaintenanceHistory(history);
    } catch (err) {
      setError(err.message);
    }
  }

  // A vehicle isn't linked to trips directly -- trips reference a route,
  // and a route references a vehicle -- so we go through routes to count
  // how many trips this vehicle has actually run.
  function tripStatsForVehicle(vehicleId) {
    const routeIds = new Set(routes.filter((r) => r.vehicle_id === vehicleId).map((r) => r.id));
    const vehicleTrips = trips.filter((t) => routeIds.has(t.route_id));
    return { total: vehicleTrips.length };
  }

  const filteredVehicles = vehicles.filter(
    (v) =>
      v.plate_number.toLowerCase().includes(search.toLowerCase()) ||
      v.model.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="vehicle">Vehicles</SectionTitle>
      </div>
      <form className="inline-form" onSubmit={addVehicle}>
        <input placeholder="Plate number" value={plate} onChange={(e) => setPlate(e.target.value)} required />
        <input placeholder="Model" value={model} onChange={(e) => setModel(e.target.value)} required />
        <input
          type="number"
          min="1"
          placeholder="Capacity"
          value={capacity}
          onChange={(e) => setCapacity(e.target.value)}
        />
        <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
          <option value="">No organization</option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
        </select>
        <button type="submit">Add vehicle</button>
      </form>

      {vehicles.length > 0 && (
        <input
          placeholder="Search by plate number or model..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: "100%", marginBottom: 16 }}
        />
      )}

      {vehicles.length === 0 ? (
        <div className="empty-state">No vehicles registered yet.</div>
      ) : filteredVehicles.length === 0 ? (
        <div className="empty-state">No vehicles match &quot;{search}&quot;.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Plate</th>
              <th>Model</th>
              <th>Capacity</th>
              <th>Organization</th>
              <th>Occupied</th>
              <th>Available</th>
              <th>Status</th>
              <th>Trips</th>
              <th>Actions</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredVehicles.map((v) => {
              const stats = tripStatsForVehicle(v.id);
              const displayStatus = v.on_route ? "on-route" : v.status;
              const isExpanded = expandedVehicleId === v.id;
              return (
                <React.Fragment key={v.id}>
                  <tr>
                    <td>{v.plate_number}</td>
                    <td>{v.model}</td>
                    <td>{v.capacity}</td>
                    <td>{organizations.find((organization) => organization.id === v.organization_id)?.name || "—"}</td>
                    <td>{v.occupied_capacity}</td>
                    <td>{v.available_capacity}</td>
                    <td>
                      <StatusPill status={displayStatus} />
                    </td>
                    <td>{stats.total}</td>
                    <td>
                      <select
                        value={v.status}
                        onChange={(e) => setStatus(v.id, e.target.value)}
                        disabled={v.on_route}
                        title={v.on_route ? "Can't change status while on a route" : ""}
                      >
                        <option value="active">Active</option>
                        <option value="idle">Idle</option>
                        <option value="maintenance">Maintenance</option>
                        <option value="offline">Offline</option>
                      </select>
                    </td>
                    <td>
                      <button className="secondary" onClick={() => (
                        editingVehicleId === v.id ? setEditingVehicleId(null) : beginVehicleEdit(v)
                      )}>
                        {editingVehicleId === v.id ? "Cancel" : "Edit"}
                      </button>{" "}
                      <button className="secondary" onClick={() => toggleMaintenance(v.id)}>
                        {isExpanded ? "Close" : "Maintenance"}
                      </button>
                    </td>
                  </tr>
                  {editingVehicleId === v.id && (
                    <tr>
                      <td colSpan={10}>
                        <form className="inline-form" onSubmit={(event) => saveVehicle(event, v.id)}>
                          <input
                            placeholder="Plate number"
                            value={vehicleEdit.plate_number}
                            onChange={(event) => setVehicleEdit({ ...vehicleEdit, plate_number: event.target.value })}
                            required
                          />
                          <input
                            placeholder="Model"
                            value={vehicleEdit.model}
                            onChange={(event) => setVehicleEdit({ ...vehicleEdit, model: event.target.value })}
                            required
                          />
                          <input
                            type="number"
                            min="1"
                            value={vehicleEdit.capacity}
                            onChange={(event) => setVehicleEdit({ ...vehicleEdit, capacity: event.target.value })}
                            required
                          />
                          <select
                            value={vehicleEdit.ownership_type}
                            onChange={(event) => setVehicleEdit({ ...vehicleEdit, ownership_type: event.target.value })}
                          >
                            <option value="internal">Internal</option>
                            <option value="external">External</option>
                          </select>
                          <select
                            value={vehicleEdit.organization_id}
                            onChange={(event) => setVehicleEdit({ ...vehicleEdit, organization_id: event.target.value })}
                          >
                            <option value="">No organization</option>
                            {organizations.map((organization) => (
                              <option key={organization.id} value={organization.id}>{organization.name}</option>
                            ))}
                          </select>
                          <button type="submit">Save vehicle</button>
                        </form>
                      </td>
                    </tr>
                  )}
                  {isExpanded && (
                    <tr>
                      <td colSpan={10}>
                        <div className="card" style={{ background: "var(--surface-soft)", margin: "8px 0" }}>
                          <div className="inline-form" style={{ marginBottom: maintenanceHistory.length > 0 ? 12 : 0 }}>
                            <input
                              placeholder="Description (e.g. Oil change)"
                              value={maintDesc}
                              onChange={(e) => setMaintDesc(e.target.value)}
                              style={{ minWidth: 220 }}
                            />
                            <input
                              placeholder="Cost (optional)"
                              type="number"
                              step="any"
                              value={maintCost}
                              onChange={(e) => setMaintCost(e.target.value)}
                            />
                            <button type="button" onClick={() => logMaintenance(v.id)}>
                              Log maintenance
                            </button>
                          </div>
                          {maintenanceHistory.length === 0 ? (
                            <div className="empty-state">No maintenance logged for this vehicle yet.</div>
                          ) : (
                            <table>
                              <thead>
                                <tr>
                                  <th>Date</th>
                                  <th>Description</th>
                                  <th>Cost</th>
                                </tr>
                              </thead>
                              <tbody>
                                {maintenanceHistory.map((m) => (
                                  <tr key={m.id}>
                                    <td>{new Date(m.date).toLocaleDateString()}</td>
                                    <td>{m.description}</td>
                                    <td>{m.cost != null ? `$${m.cost.toFixed(2)}` : "—"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function DriversTab({ drivers, vehicles, trips, onChange, setError }) {
  const [search, setSearch] = useState("");

  async function assign(driverId, vehicleId) {
    try {
      await api.patch(`/drivers/${driverId}/assign`, { vehicle_id: vehicleId ? Number(vehicleId) : null });
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  function updateDriverField(driverId, field, value) {
    const driver = drivers.find((item) => item.id === driverId);
    if (!driver) return;
    setDriverEdits((current) => ({
      ...current,
      [driverId]: {
        ...(current[driverId] || {
          license_number: driver.license_number || "",
          phone: driver.phone || "",
          license_expiry: driver.license_expiry || "",
        }),
        [field]: value,
      },
    }));
  }

  const [driverEdits, setDriverEdits] = useState({});

  async function saveDriverProfile(driver) {
    try {
      const profile = driverEdits[driver.id] || {
        license_number: driver.license_number,
        phone: driver.phone,
        license_expiry: driver.license_expiry,
      };
      await api.updateUser(driver.id, {
        ...profile,
        license_expiry: profile.license_expiry || null,
      });
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  function tripStatsForDriver(driverId) {
    const driverTrips = trips.filter((t) => t.driver_id === driverId);
    return {
      total: driverTrips.length,
      active: driverTrips.filter((t) => t.status === "active").length,
    };
  }

  const filteredDrivers = drivers.filter(
    (d) =>
      d.name.toLowerCase().includes(search.toLowerCase()) ||
      d.email.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="driver">Drivers</SectionTitle>
      </div>
      <p className="hint-text" style={{ marginTop: 0 }}>
        Drivers register themselves from the login screen with role &quot;Driver&quot;. Assign each one to a vehicle here.
      </p>
      {drivers.length > 0 && (
        <input
          placeholder="Search by name or email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: "100%", marginBottom: 16 }}
        />
      )}
      {drivers.length === 0 ? (
        <div className="empty-state">No drivers registered yet.</div>
      ) : filteredDrivers.length === 0 ? (
        <div className="empty-state">No drivers match &quot;{search}&quot;.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Assigned vehicle</th>
              <th>License number</th>
              <th>Phone</th>
              <th>License expiry</th>
              <th>Trips</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredDrivers.map((d) => {
              const stats = tripStatsForDriver(d.id);
              return (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.email}</td>
                  <td>
                    <select value={d.vehicle_id || ""} onChange={(e) => assign(d.id, e.target.value)}>
                      <option value="">Unassigned</option>
                      {vehicles.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.plate_number}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      value={(driverEdits[d.id]?.license_number ?? d.license_number) || ""}
                      onChange={(event) => updateDriverField(d.id, "license_number", event.target.value)}
                      aria-label={`License number for ${d.name}`}
                    />
                  </td>
                  <td>
                    <input
                      type="tel"
                      value={(driverEdits[d.id]?.phone ?? d.phone) || ""}
                      onChange={(event) => updateDriverField(d.id, "phone", event.target.value)}
                      aria-label={`Phone for ${d.name}`}
                    />
                  </td>
                  <td>
                    <input
                      type="date"
                      value={(driverEdits[d.id]?.license_expiry ?? d.license_expiry) || ""}
                      onChange={(event) => updateDriverField(d.id, "license_expiry", event.target.value)}
                      aria-label={`License expiry for ${d.name}`}
                    />
                  </td>
                  <td>
                    {stats.total} {stats.active > 0 && <StatusPill status="active" />}
                  </td>
                  <td><button className="secondary" onClick={() => saveDriverProfile(d)}>Save</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function UsersTab({ users, organizations, currentUser, onChange, setError }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("passenger");
  const [organizationId, setOrganizationId] = useState("");
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(false);
  const [linkingPassengerId, setLinkingPassengerId] = useState(null);
  const [guardianLinks, setGuardianLinks] = useState({});
  const [guardianSelections, setGuardianSelections] = useState({});
  const [guardianRelationships, setGuardianRelationships] = useState({});

  const guardianUsers = users.filter((userItem) => userItem.role === "guardian" && userItem.is_active);

  async function createUser(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.createUser({
        name,
        email,
        password,
        role,
        organization_id: organizationId ? Number(organizationId) : null,
      });
      setName("");
      setEmail("");
      setPassword("");
      setRole("passenger");
      setOrganizationId("");
      await onChange();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function editFor(userItem) {
    return edits[userItem.id] || {
      name: userItem.name,
      role: userItem.role,
      is_active: userItem.is_active,
      organization_id: userItem.organization_id ? String(userItem.organization_id) : "",
    };
  }

  function updateEdit(userId, field, value) {
    const userItem = users.find((item) => item.id === userId);
    if (!userItem) return;
    setEdits((current) => ({
      ...current,
      [userId]: { ...editFor(userItem), [field]: value },
    }));
  }

  async function saveUser(userId) {
    setError("");
    try {
      const edit = editFor(users.find((item) => item.id === userId));
      await api.updateUser(userId, {
        ...edit,
        organization_id: edit.organization_id ? Number(edit.organization_id) : null,
      });
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleGuardianLinks(passengerId) {
    if (linkingPassengerId === passengerId) {
      setLinkingPassengerId(null);
      return;
    }
    setError("");
    try {
      const links = await api.getPassengerGuardians(passengerId);
      setGuardianLinks((current) => ({ ...current, [passengerId]: links }));
      setGuardianSelections((current) => ({
        ...current,
        [passengerId]: current[passengerId] || String(guardianUsers[0]?.id || ""),
      }));
      setGuardianRelationships((current) => ({
        ...current,
        [passengerId]: current[passengerId] || "Parent/Guardian",
      }));
      setLinkingPassengerId(passengerId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function addGuardian(passengerId) {
    const guardianId = Number(guardianSelections[passengerId]);
    if (!guardianId) return;
    setError("");
    try {
      await api.linkGuardian(passengerId, {
        guardian_id: guardianId,
        relationship: guardianRelationships[passengerId] || "Parent/Guardian",
      });
      const links = await api.getPassengerGuardians(passengerId);
      setGuardianLinks((current) => ({ ...current, [passengerId]: links }));
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeGuardian(passengerId, guardianId) {
    if (!window.confirm("Unlink this guardian from the passenger?")) return;
    setError("");
    try {
      await api.unlinkGuardian(passengerId, guardianId);
      const links = await api.getPassengerGuardians(passengerId);
      setGuardianLinks((current) => ({ ...current, [passengerId]: links }));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="driver">Users</SectionTitle>
      </div>
      <form className="inline-form" onSubmit={createUser}>
        <input placeholder="Full name" value={name} onChange={(event) => setName(event.target.value)} required />
        <input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <input type="password" placeholder="Password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <select value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="admin">Admin</option>
          <option value="driver">Driver</option>
          <option value="passenger">Passenger</option>
          <option value="guardian">Guardian</option>
        </select>
        <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
          <option value="">No organization</option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
        </select>
        <button type="submit" disabled={busy}>{busy ? "Creating..." : "Create user"}</button>
      </form>

      {users.length === 0 ? (
        <div className="empty-state">No users found.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Organization</th>
              <th>Created</th>
              <th>Active</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((userItem) => {
              const edit = editFor(userItem);
              const isSelf = userItem.id === currentUser.id;
              const passengerGuardianLinks = guardianLinks[userItem.id] || [];
              const linkedGuardianIds = new Set(passengerGuardianLinks.map((link) => link.guardian_id));
              const availableGuardianUsers = guardianUsers.filter((guardian) => !linkedGuardianIds.has(guardian.id));
              return (
                <React.Fragment key={userItem.id}>
                <tr key={userItem.id}>
                  <td>
                    <input value={edit.name} onChange={(event) => updateEdit(userItem.id, "name", event.target.value)} />
                  </td>
                  <td>{userItem.email}</td>
                  <td>
                    <select
                      value={edit.role}
                      disabled={isSelf}
                      onChange={(event) => updateEdit(userItem.id, "role", event.target.value)}
                    >
                      <option value="admin">Admin</option>
                      <option value="driver">Driver</option>
                      <option value="passenger">Passenger</option>
                      <option value="guardian">Guardian</option>
                    </select>
                  </td>
                  <td>
                    <select
                      value={edit.organization_id}
                      onChange={(event) => updateEdit(userItem.id, "organization_id", event.target.value)}
                    >
                      <option value="">No organization</option>
                      {organizations.map((organization) => (
                        <option key={organization.id} value={organization.id}>{organization.name}</option>
                      ))}
                    </select>
                  </td>
                  <td>{formatDateTime(userItem.created_at)}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={edit.is_active}
                      disabled={isSelf}
                      onChange={(event) => updateEdit(userItem.id, "is_active", event.target.checked)}
                      aria-label={`Active: ${userItem.email}`}
                    />
                  </td>
                  <td>
                    <button className="secondary" onClick={() => saveUser(userItem.id)}>Save</button>
                    {userItem.role === "passenger" && (
                      <button className="secondary" onClick={() => toggleGuardianLinks(userItem.id)}>
                        {linkingPassengerId === userItem.id ? "Close guardians" : "Link guardian"}
                      </button>
                    )}
                  </td>
                </tr>
                {userItem.role === "passenger" && linkingPassengerId === userItem.id && (
                  <tr key={`${userItem.id}-guardians`}>
                    <td colSpan="7">
                      {availableGuardianUsers.length === 0 ? (
                        <span>
                          {guardianUsers.length === 0
                            ? "Create an active guardian account first."
                            : "All active guardians are already linked."}
                        </span>
                      ) : (
                        <div className="inline-form">
                          <select
                            value={
                              availableGuardianUsers.some(
                                (guardian) => String(guardian.id) === guardianSelections[userItem.id],
                              )
                                ? guardianSelections[userItem.id]
                                : String(availableGuardianUsers[0].id)
                            }
                            onChange={(event) => setGuardianSelections((current) => ({
                              ...current,
                              [userItem.id]: event.target.value,
                            }))}
                          >
                            {availableGuardianUsers.map((guardian) => (
                              <option key={guardian.id} value={guardian.id}>{guardian.name} ({guardian.email})</option>
                            ))}
                          </select>
                          <input
                            aria-label={`Relationship to ${userItem.name}`}
                            placeholder="Relationship"
                            value={guardianRelationships[userItem.id] || ""}
                            onChange={(event) => setGuardianRelationships((current) => ({
                              ...current,
                              [userItem.id]: event.target.value,
                            }))}
                          />
                          <button
                            className="secondary"
                            onClick={() => addGuardian(userItem.id)}
                            disabled={!guardianSelections[userItem.id]}
                          >
                            Add guardian
                          </button>
                        </div>
                      )}
                      {passengerGuardianLinks.map((link) => {
                        const guardian = users.find((item) => item.id === link.guardian_id);
                        return (
                          <div key={link.id}>
                            {guardian?.name || `User ${link.guardian_id}`} — {link.relationship}
                            {" "}
                            <button
                              className="secondary"
                              onClick={() => removeGuardian(userItem.id, link.guardian_id)}
                            >
                              Unlink
                            </button>
                          </div>
                        );
                      })}
                    </td>
                  </tr>
                )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function OrganizationsTab({ organizations, onChange, setError }) {
  const organizationTypes = [
    { value: "school", label: "School" },
    { value: "university", label: "University" },
    { value: "company", label: "Company" },
    { value: "fleet_owner", label: "Fleet owner" },
  ];
  const [name, setName] = useState("");
  const [type, setType] = useState("school");
  const [contactEmail, setContactEmail] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [edit, setEdit] = useState({});

  async function createOrganization(event) {
    event.preventDefault();
    setError("");
    try {
      await api.createOrganization({
        name,
        type,
        contact_email: contactEmail || null,
      });
      setName("");
      setType("school");
      setContactEmail("");
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  function startEdit(organization) {
    setEditingId(organization.id);
    setEdit({
      name: organization.name,
      type: organization.type,
      contact_email: organization.contact_email || "",
    });
  }

  async function saveEdit(organizationId) {
    setError("");
    try {
      await api.updateOrganization(organizationId, {
        ...edit,
        contact_email: edit.contact_email || null,
      });
      setEditingId(null);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeOrganization(organizationId) {
    const organization = organizations.find((item) => item.id === organizationId);
    if (!window.confirm(`Delete ${organization?.name || "this organization"}? Associated users, vehicles, and routes will become unassigned.`)) {
      return;
    }
    setError("");
    try {
      await api.deleteOrganization(organizationId);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="driver">Organizations</SectionTitle>
      </div>
      <form className="inline-form" onSubmit={createOrganization}>
        <input placeholder="Organization name" value={name} onChange={(event) => setName(event.target.value)} required />
        <select value={type} onChange={(event) => setType(event.target.value)}>
          {organizationTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        <input
          type="email"
          placeholder="Contact email (optional)"
          value={contactEmail}
          onChange={(event) => setContactEmail(event.target.value)}
        />
        <button type="submit">Add organization</button>
      </form>
      {organizations.length === 0 ? (
        <div className="empty-state">No organizations yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Contact email</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {organizations.map((organization) => (
              <tr key={organization.id}>
                <td>
                  {editingId === organization.id
                    ? <input value={edit.name} onChange={(event) => setEdit({ ...edit, name: event.target.value })} />
                    : organization.name}
                </td>
                <td>
                  {editingId === organization.id ? (
                    <select value={edit.type} onChange={(event) => setEdit({ ...edit, type: event.target.value })}>
                      {organizationTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  ) : organizationTypes.find((item) => item.value === organization.type)?.label || organization.type}
                </td>
                <td>
                  {editingId === organization.id
                    ? (
                      <input
                        type="email"
                        value={edit.contact_email}
                        onChange={(event) => setEdit({ ...edit, contact_email: event.target.value })}
                      />
                    )
                    : organization.contact_email || "—"}
                </td>
                <td>{formatDateTime(organization.created_at)}</td>
                <td>
                  {editingId === organization.id ? (
                    <>
                      <button className="secondary" onClick={() => saveEdit(organization.id)}>Save</button>{" "}
                      <button className="secondary" onClick={() => setEditingId(null)}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="secondary" onClick={() => startEdit(organization)}>Edit</button>{" "}
                      <button className="secondary" onClick={() => removeOrganization(organization.id)}>Delete</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function RoutesTab({ routes, vehicles, trips, organizations, onChange, setError }) {
  const weekDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const [name, setName] = useState("");
  const [vehicleId, setVehicleId] = useState("");
  const [organizationId, setOrganizationId] = useState("");
  const [pickup, setPickup] = useState("");
  const [drop, setDrop] = useState("");
  const [daysOfWeek, setDaysOfWeek] = useState([]);
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [search, setSearch] = useState("");
  const [editingRouteId, setEditingRouteId] = useState(null);

  const [pendingStops, setPendingStops] = useState([]);
  const [stopName, setStopName] = useState("");
  const [stopLat, setStopLat] = useState("");
  const [stopLng, setStopLng] = useState("");

  function addStopToList(e) {
    e.preventDefault();
    if (!stopName || stopLat === "" || stopLng === "") return;
    setPendingStops([...pendingStops, { name: stopName, lat: Number(stopLat), lng: Number(stopLng), sequence: pendingStops.length }]);
    setStopName("");
    setStopLat("");
    setStopLng("");
  }

  function removeStopFromList(index) {
    setPendingStops(pendingStops.filter((_, i) => i !== index).map((s, i) => ({ ...s, sequence: i })));
  }

  function moveStop(index, offset) {
    const target = index + offset;
    if (target < 0 || target >= pendingStops.length) return;
    const reordered = [...pendingStops];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    setPendingStops(reordered.map((stop, sequence) => ({ ...stop, sequence })));
  }

  function startRouteEdit(route) {
    setEditingRouteId(route.id);
    setName(route.name);
    setPickup(route.pickup_time || "");
    setDrop(route.drop_time || "");
    setVehicleId(route.vehicle_id ? String(route.vehicle_id) : "");
    setOrganizationId(route.organization_id ? String(route.organization_id) : "");
    setDaysOfWeek(route.days_of_week || []);
    setValidFrom(route.valid_from || "");
    setValidTo(route.valid_to || "");
    setPendingStops(route.stops.map(({ name: stopLabel, lat, lng, sequence }) => ({
      name: stopLabel, lat, lng, sequence,
    })));
  }

  function clearRouteForm() {
    setEditingRouteId(null);
    setName("");
    setPickup("");
    setDrop("");
    setVehicleId("");
    setOrganizationId("");
    setDaysOfWeek([]);
    setValidFrom("");
    setValidTo("");
    setPendingStops([]);
  }

  function useMyLocationForStop() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      setStopLat(pos.coords.latitude.toFixed(6));
      setStopLng(pos.coords.longitude.toFixed(6));
    });
  }

  async function saveRoute(e) {
    e.preventDefault();
    setError("");
    try {
      const routeData = {
        name,
        pickup_time: pickup,
        drop_time: drop,
        vehicle_id: vehicleId ? Number(vehicleId) : null,
        organization_id: organizationId ? Number(organizationId) : null,
        days_of_week: daysOfWeek,
        valid_from: validFrom || null,
        valid_to: validTo || null,
        stops: pendingStops,
      };
      if (editingRouteId) {
        await api.patch(`/routes/${editingRouteId}`, routeData);
      } else {
        await api.post("/routes/", routeData);
      }
      clearRouteForm();
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    const route = routes.find((item) => item.id === id);
    if (!window.confirm(`Delete route "${route?.name || id}"? This cannot be undone.`)) return;
    setError("");
    try {
      await api.del(`/routes/${id}`);
      await onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  function tripStatsForRoute(routeId) {
    const routeTrips = trips.filter((t) => t.route_id === routeId);
    return {
      total: routeTrips.length,
      active: routeTrips.filter((t) => t.status === "active").length,
    };
  }

  const filteredRoutes = routes.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.stops.some((s) => s.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="route">Routes</SectionTitle>
      </div>

      <form className="inline-form" onSubmit={saveRoute}>
        <input placeholder="Route name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Pickup time" value={pickup} onChange={(e) => setPickup(e.target.value)} />
        <input placeholder="Drop time" value={drop} onChange={(e) => setDrop(e.target.value)} />
        <input type="date" aria-label="Schedule valid from" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
        <input type="date" aria-label="Schedule valid to" value={validTo} onChange={(e) => setValidTo(e.target.value)} />
        <select value={vehicleId} onChange={(e) => setVehicleId(e.target.value)}>
          <option value="">No vehicle yet</option>
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.plate_number}
            </option>
          ))}
        </select>
        <select value={organizationId} onChange={(e) => setOrganizationId(e.target.value)}>
          <option value="">No organization</option>
          {organizations.map((organization) => (
            <option key={organization.id} value={organization.id}>{organization.name}</option>
          ))}
        </select>
        <button type="submit">{editingRouteId ? "Save route" : "Add route"}</button>
        {editingRouteId && <button type="button" className="secondary" onClick={clearRouteForm}>Cancel edit</button>}
      </form>

      <div className="card" style={{ background: "var(--surface-soft)", marginBottom: 16 }}>
        <strong>Schedule days</strong>
        <div className="inline-form" style={{ margin: "8px 0 12px" }}>
          {weekDays.map((day, index) => (
            <label key={day}>
              <input
                type="checkbox"
                checked={daysOfWeek.includes(index)}
                onChange={(event) => setDaysOfWeek((current) => (
                  event.target.checked
                    ? [...current, index].sort((a, b) => a - b)
                    : current.filter((value) => value !== index)
                ))}
              />
              {day}
            </label>
          ))}
        </div>
        <p className="hint-text" style={{ marginTop: 0 }}>
          Add stops one at a time, with real coordinates -- this is what lets a passenger be auto-assigned to
          their nearest stop when they book.
        </p>
        <div className="inline-form" style={{ marginBottom: pendingStops.length > 0 ? 12 : 0 }}>
          <input placeholder="Stop name" value={stopName} onChange={(e) => setStopName(e.target.value)} />
          <input placeholder="Latitude" type="number" step="any" value={stopLat} onChange={(e) => setStopLat(e.target.value)} />
          <input placeholder="Longitude" type="number" step="any" value={stopLng} onChange={(e) => setStopLng(e.target.value)} />
          <button type="button" className="secondary" onClick={useMyLocationForStop}>
            Use my location
          </button>
          <button type="button" onClick={addStopToList}>
            Add stop
          </button>
        </div>
        {pendingStops.length > 0 && (
          <table>
            <tbody>
              {pendingStops.map((s, i) => (
                <tr key={i}>
                  <td>{i + 1}.</td>
                  <td>{s.name}</td>
                  <td>{s.lat.toFixed(4)}, {s.lng.toFixed(4)}</td>
                  <td>
                    <button type="button" className="secondary" disabled={i === 0} onClick={() => moveStop(i, -1)}>↑</button>{" "}
                    <button type="button" className="secondary" disabled={i === pendingStops.length - 1} onClick={() => moveStop(i, 1)}>↓</button>{" "}
                    <button type="button" className="secondary" onClick={() => removeStopFromList(i)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {routes.length > 0 && (
        <input
          placeholder="Search by route name or stop..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: "100%", marginBottom: 16 }}
        />
      )}

      {routes.length === 0 ? (
        <div className="empty-state">No routes yet.</div>
      ) : filteredRoutes.length === 0 ? (
        <div className="empty-state">No routes match &quot;{search}&quot;.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Stops</th>
              <th>Distance</th>
              <th>Est. Duration</th>
              <th>Pickup</th>
              <th>Drop</th>
              <th>Schedule</th>
              <th>Organization</th>
              <th>Vehicle</th>
              <th>Trips</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredRoutes.map((r) => {
              const stats = tripStatsForRoute(r.id);
              return (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.stops.length > 0 ? r.stops.map((s) => s.name).join(", ") : "—"}</td>
                  <td>{r.distance_km > 0 ? `${r.distance_km} km` : "—"}</td>
                  <td>{r.estimated_duration_min > 0 ? `~${r.estimated_duration_min} min` : "—"}</td>
                  <td>{r.pickup_time || "—"}</td>
                  <td>{r.drop_time || "—"}</td>
                  <td>
                    {(r.days_of_week || []).map((day) => weekDays[day]).join(", ") || "No days"}
                    <div>{r.valid_from || "Any date"} – {r.valid_to || "No end date"}</div>
                  </td>
                  <td>{organizations.find((organization) => organization.id === r.organization_id)?.name || "—"}</td>
                  <td>{vehicles.find((v) => v.id === r.vehicle_id)?.plate_number || "Unassigned"}</td>
                  <td>
                    {stats.total} {stats.active > 0 && <StatusPill status="active" />}
                  </td>
                  <td>
                    <button
                      className="secondary"
                      disabled={stats.active > 0}
                      title={stats.active > 0 ? "Cannot edit a route with an in-progress trip" : "Edit route"}
                      onClick={() => startRouteEdit(r)}
                    >
                      Edit
                    </button>{" "}
                    <button
                      className="secondary"
                      disabled={stats.active > 0}
                      title={stats.active > 0 ? "Cannot delete a route with an in-progress trip" : "Delete route"}
                      onClick={() => remove(r.id)}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function TripsTab({ trips, routes, drivers, onChange, setError }) {
  const [routeId, setRouteId] = useState("");
  const [driverId, setDriverId] = useState("");

  async function schedule(e) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/trips/", { route_id: Number(routeId), driver_id: Number(driverId) });
      setRouteId("");
      setDriverId("");
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="trip">Trips</SectionTitle>
      </div>
      <form className="inline-form" onSubmit={schedule}>
        <select value={routeId} onChange={(e) => setRouteId(e.target.value)} required>
          <option value="">Select route</option>
          {routes.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
        <select value={driverId} onChange={(e) => setDriverId(e.target.value)} required>
          <option value="">Select driver</option>
          {drivers.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <button type="submit">Schedule trip</button>
      </form>

      <TripPathViewer trips={trips} routes={routes} setError={setError} />

      {trips.some((t) => t.status === "active" && t.last_lat) && (
        <div style={{ marginBottom: 18 }}>
          <MapView
            markers={trips
              .filter((t) => t.status === "active" && t.last_lat && t.last_lng)
              .map((t) => ({
                lat: t.last_lat,
                lng: t.last_lng,
                label: `${routes.find((r) => r.id === t.route_id)?.name || "Route"} — ${
                  drivers.find((d) => d.id === t.driver_id)?.name || "Driver"
                }`,
              }))}
            height={320}
          />
        </div>
      )}

      {trips.length === 0 ? (
        <div className="empty-state">No trips scheduled yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Route</th>
              <th>Driver</th>
              <th>Status</th>
              <th>Last location</th>
            </tr>
          </thead>
          <tbody>
            {trips.map((t) => (
              <tr key={t.id}>
                <td>{routes.find((r) => r.id === t.route_id)?.name || t.route_id}</td>
                <td>{drivers.find((d) => d.id === t.driver_id)?.name || t.driver_id}</td>
                <td>
                  <StatusPill status={t.status} />
                </td>
                <td>
                  <LocationLabel lat={t.last_lat} lng={t.last_lng} />
                  {t.last_accuracy != null && (
                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                      ±{Math.round(t.last_accuracy)}m accuracy
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDuration(startedAt, endedAt) {
  if (!startedAt || !endedAt) return "—";
  const minutes = Math.round((new Date(endedAt) - new Date(startedAt)) / 60000);
  if (minutes < 60) return `${minutes} min`;
  const hrs = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return `${hrs}h ${rem}m`;
}

function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function HistoryTab({ trips, routes, drivers, setError }) {
  const [routeFilter, setRouteFilter] = useState("");
  const [driverFilter, setDriverFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const completedTrips = trips.filter((t) => t.status === "completed");

  const filtered = completedTrips.filter((t) => {
    if (routeFilter && t.route_id !== Number(routeFilter)) return false;
    if (driverFilter && t.driver_id !== Number(driverFilter)) return false;
    if (fromDate && t.ended_at && new Date(t.ended_at) < new Date(fromDate)) return false;
    if (toDate && t.ended_at && new Date(t.ended_at) > new Date(`${toDate}T23:59:59`)) return false;
    return true;
  });

  const totalMinutes = filtered.reduce((sum, t) => {
    if (!t.started_at || !t.ended_at) return sum;
    return sum + (new Date(t.ended_at) - new Date(t.started_at)) / 60000;
  }, 0);

  return (
    <div>
      <div className="grid-cards">
        <StatCard label="Completed trips" value={filtered.length} />
        <StatCard label="Total time on road" value={`${Math.round(totalMinutes / 60)}h`} />
      </div>

      <div className="card">
        <div className="section-header">
          <SectionTitle icon="clock">Trip History</SectionTitle>
        </div>

        <div className="inline-form">
          <select value={routeFilter} onChange={(e) => setRouteFilter(e.target.value)}>
            <option value="">All routes</option>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <select value={driverFilter} onChange={(e) => setDriverFilter(e.target.value)}>
            <option value="">All drivers</option>
            {drivers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} title="From date" />
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} title="To date" />
        </div>

        {filtered.length > 0 && (
          <TripPathViewer trips={filtered} routes={routes} setError={setError} showStopEvents />
        )}

        {completedTrips.length === 0 ? (
          <div className="empty-state">No completed trips yet -- history fills in as trips finish.</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">No completed trips match these filters.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Route</th>
                <th>Driver</th>
                <th>Started</th>
                <th>Ended</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => (
                <tr key={t.id}>
                  <td>{routes.find((r) => r.id === t.route_id)?.name || t.route_id}</td>
                  <td>{drivers.find((d) => d.id === t.driver_id)?.name || t.driver_id}</td>
                  <td>{formatDateTime(t.started_at)}</td>
                  <td>{formatDateTime(t.ended_at)}</td>
                  <td>{formatDuration(t.started_at, t.ended_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function TripPathViewer({ trips, routes, setError, showStopEvents = false }) {
  const [selectedTripId, setSelectedTripId] = useState("");
  const [pathData, setPathData] = useState(null);
  const [stopEvents, setStopEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (trips.length === 0) {
      setSelectedTripId("");
    } else if (!trips.some((trip) => trip.id === Number(selectedTripId))) {
      setSelectedTripId(String(trips[0].id));
    }
  }, [trips, selectedTripId]);

  useEffect(() => {
    if (!selectedTripId) {
      setPathData(null);
      setStopEvents([]);
      return undefined;
    }

    let cancelled = false;
    async function loadPath() {
      try {
        const [result, stops] = await Promise.all([
          api.getTripPath(selectedTripId),
          api.getTripStops(selectedTripId),
        ]);
        if (!cancelled) {
          setPathData(result);
          setStopEvents(stops);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    setPathData(null);
    setStopEvents([]);
    setLoading(true);
    loadPath();
    const interval = setInterval(loadPath, 6000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [selectedTripId, setError]);

  const positions = pathData?.map((location) => [location.lat, location.lng]) || [];
  const lastLocation = pathData?.[pathData.length - 1];
  const selectedTrip = trips.find((trip) => trip.id === Number(selectedTripId));
  const selectedRoute = routes.find((route) => route.id === selectedTrip?.route_id);

  return (
    <div style={{ margin: "18px 0" }}>
      <div className="inline-form">
        <label htmlFor="trip-path-select">Recorded GPS path</label>
        <select
          id="trip-path-select"
          value={selectedTripId}
          onChange={(event) => setSelectedTripId(event.target.value)}
          disabled={trips.length === 0}
        >
          {trips.map((trip) => (
            <option key={trip.id} value={trip.id}>
              Trip {trip.id} — {trip.status}
            </option>
          ))}
        </select>
        {loading && <span>Loading path…</span>}
      </div>
      {pathData?.length > 0 ? (
        <MapView
          markers={lastLocation ? [{
            lat: lastLocation.lat,
            lng: lastLocation.lng,
            label: `Trip ${selectedTripId} — latest location`,
          }] : []}
          path={positions}
          height={320}
        />
      ) : (
        <div className="empty-state">
          {selectedTrip ? "No GPS points have been recorded for this trip yet." : "No trips available."}
        </div>
      )}
      {showStopEvents && pathData && (
        <table>
          <thead>
            <tr>
              <th>Stop</th>
              <th>Arrived</th>
              <th>Departed</th>
              <th>Dwell</th>
              <th>Long stop</th>
            </tr>
          </thead>
          <tbody>
            {stopEvents.length === 0 ? (
              <tr><td colSpan="5">No stop arrivals recorded for this trip.</td></tr>
            ) : stopEvents.map((event) => (
              <tr key={event.id}>
                <td>{selectedRoute?.stops.find((stop) => stop.id === event.stop_id)?.name || "Unknown stop"}</td>
                <td>{formatDateTime(event.arrived_at)}</td>
                <td>{formatDateTime(event.departed_at)}</td>
                <td>{formatDwell(event.dwell_seconds)}</td>
                <td>
                  {event.long_stop
                    ? <span className="status-pill status-attention">Long stop</span>
                    : <span className="status-pill status-completed">No</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDwell(seconds) {
  if (seconds == null) return "In progress";
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return minutes > 0 ? `${minutes}m ${remainingSeconds}s` : `${remainingSeconds}s`;
}

function AlertsTab({ alerts, onChange, setError }) {
  async function resolve(id) {
    try {
      await api.patch(`/alerts/${id}/resolve`);
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="card">
      <div className="section-header">
        <SectionTitle icon="alert">Emergency alerts</SectionTitle>
      </div>
      {alerts.length === 0 ? (
        <div className="empty-state">No alerts have been raised.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Raised by (user id)</th>
              <th>Trip</th>
              <th>Location</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a) => (
              <tr key={a.id}>
                <td>{a.raised_by_id}</td>
                <td>{a.trip_id || "—"}</td>
                <td><LocationLabel lat={a.lat} lng={a.lng} /></td>
                <td>
                  <StatusPill status={a.status} />
                </td>
                <td>
                  {a.status === "open" && (
                    <button className="secondary" onClick={() => resolve(a.id)}>
                      Mark resolved
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}