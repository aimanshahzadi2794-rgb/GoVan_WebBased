import React, { useEffect, useState } from "react";
import { api } from "../api";
import StatusPill from "../components/StatusPill.jsx";
import PassengerLiveRoute from "../components/PassengerLiveRoute.jsx";
import EmergencyPanel from "../components/EmergencyPanel.jsx";

export default function PassengerDashboard({ user }) {
  const [routes, setRoutes] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [trips, setTrips] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyRouteId, setBusyRouteId] = useState(null);
  const [boardingStopByRoute, setBoardingStopByRoute] = useState({});
  const [dropoffStopByRoute, setDropoffStopByRoute] = useState({});

  async function refresh() {
    try {
      const [r, b, t] = await Promise.all([
        api.get("/routes/"),
        api.get("/bookings/"),
        api.get("/trips/"),
      ]);
      setRoutes(r);
      setBookings(b);
      setTrips(t);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
  refresh();
  const interval = setInterval(refresh, 6000);
  return () => clearInterval(interval);
}, []);

  async function book(routeId) {
    setBusyRouteId(routeId);
    setError("");
    try {
      const route = routes.find((item) => item.id === routeId);
      const selectedStopId = boardingStopByRoute[routeId] ?? route?.stops?.[0]?.id;
      const selectedDropoffStopId = dropoffStopByRoute[routeId]
        ?? route?.stops?.find((stop) => stop.sequence > (route.stops.find((item) => item.id === selectedStopId)?.sequence ?? -1))?.id;
      await api.post("/bookings/", {
        route_id: routeId,
        ...(selectedStopId ? { boarding_stop_id: selectedStopId } : {}),
        ...(selectedDropoffStopId ? { dropoff_stop_id: selectedDropoffStopId } : {}),
      });
      await refresh();
    } catch (err) {
      if (err.message.toLowerCase().includes("full capacity")) {
        setError("No seats remain on this route. Availability is being refreshed.");
        await refresh();
      } else {
        setError(err.message);
      }
    } finally {
      setBusyRouteId(null);
    }
  }

  async function cancel(bookingId) {
    setError("");
    try {
      await api.patch(`/bookings/${bookingId}/cancel`);
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  const myConfirmedRouteIds = new Set(
    bookings.filter((b) => b.status === "confirmed").map((b) => b.route_id)
  );
  return (
    <div className="container">
      <div className="passenger-hero">
  <div className="hero-row">
    <div>
      <h2>Welcome, {user.name}</h2>
      <p className="hero-sub">Here&apos;s what&apos;s moving on your routes today.</p>
    </div>
  </div>
  <svg className="hero-route-line" viewBox="0 0 700 40" preserveAspectRatio="none">
    <path d="M -10 30 C 100 10, 200 38, 320 18 C 440 -2, 560 28, 710 12" stroke="#fff" strokeWidth="2" strokeDasharray="1 10" strokeLinecap="round" fill="none" />
  </svg>
</div>

      {error && <div className="error-text">{error}</div>}
      {loading && <div className="card hint-text" role="status">Loading routes and bookings...</div>}
      {!loading && (
        <>
      <EmergencyPanel activeTrip={trips.find((trip) => trip.status === "active")} />

      <PassengerLiveRoute title="My route" />

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="section-header">
  <div className="title-row">
    <span className="icon-badge">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 20l-5.5-2.5V5L9 7.5m0 12.5l6-2.5m-6 2.5V7.5m6 10V5l5.5 2.5v12.5L15 17.5m0 2.5V7.5m0 0L9 5" />
      </svg>
    </span>
    <h2>Available routes</h2>
  </div>
</div>
        {routes.length === 0 ? (
          <div className="empty-state illustrated">
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M9 20l-5.5-2.5V5L9 7.5m0 12.5l6-2.5m-6 2.5V7.5m6 10V5l5.5 2.5v12.5L15 17.5m0 2.5V7.5m0 0L9 5" />
  </svg>
  <p>No routes have been published yet.</p>
</div>
        ) : (
          <div className="route-cards">
  {routes.map((r) => {
    const alreadyBooked = myConfirmedRouteIds.has(r.id);
    const stopsLine = r.stops && r.stops.length > 0 ? r.stops.map((s) => s.name).join(" · ") : "No stops added yet";
    return (
      <div className="route-card" key={r.id}>
        <div className="route-glyph">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 20l-5.5-2.5V5L9 7.5m0 12.5l6-2.5m-6 2.5V7.5m6 10V5l5.5 2.5v12.5L15 17.5m0 2.5V7.5m0 0L9 5" />
          </svg>
        </div>
        <div className="route-info">
          <h3>{r.name}</h3>
          <div className="stops-line">{stopsLine}</div>
        </div>
        <div className="route-times">
          <div>
            Pickup
            <strong>{r.pickup_time || "—"}</strong>
          </div>
          <div>
            Drop
            <strong>{r.drop_time || "—"}</strong>
          </div>
        </div>
        <div className="route-action">
          {alreadyBooked ? (
            <StatusPill status="confirmed" />
          ) : (
          <>
            {r.stops?.length > 0 && (
              <label className="boarding-stop-select">
                Boarding stop
                <select
                  value={boardingStopByRoute[r.id] ?? r.stops[0].id}
                  onChange={(event) => setBoardingStopByRoute((current) => ({
                    ...current,
                    [r.id]: Number(event.target.value),
                  }))}
                >
                  {r.stops.map((stop) => (
                    <option key={stop.id} value={stop.id}>{stop.name}</option>
                  ))}
                </select>
              </label>
            )}
            {r.stops?.length > 1 && (
              <label className="boarding-stop-select">
                Drop-off stop
                <select
                  value={(() => {
                    const boardId = boardingStopByRoute[r.id] ?? r.stops[0].id;
                    const boardSequence = r.stops.find((stop) => stop.id === boardId)?.sequence ?? -1;
                    const possibleDropoffs = r.stops.filter((stop) => stop.sequence > boardSequence);
                    const selectedDropoff = possibleDropoffs.find(
                      (stop) => stop.id === dropoffStopByRoute[r.id],
                    );
                    return selectedDropoff?.id ?? possibleDropoffs[0]?.id ?? "";
                  })()}
                  onChange={(event) => setDropoffStopByRoute((current) => ({
                    ...current,
                    [r.id]: Number(event.target.value),
                  }))}
                >
                  {r.stops
                    .filter((stop) => stop.sequence > (
                      r.stops.find((item) => item.id === (boardingStopByRoute[r.id] ?? r.stops[0].id))?.sequence ?? -1
                    ))
                    .map((stop) => <option key={stop.id} value={stop.id}>{stop.name}</option>)}
                </select>
              </label>
            )}
            {r.seats_left != null && (
              <div className={`seats-left ${r.seats_left === 0 ? "full" : ""}`}>
                Seats left: <strong>{r.seats_left}</strong>
              </div>
            )}
            {r.seats_left == null && (
              <div className="seats-left">Seats left: capacity not set</div>
            )}
            <button disabled={busyRouteId === r.id || r.seats_left === 0} onClick={() => book(r.id)}>
              {r.seats_left === 0 ? "Fully booked" : busyRouteId === r.id ? "Booking..." : "Book seat"}
            </button>
          </>
        )}
        </div>
      </div>
    );
  })}
</div>
        )}
      </div>

      <div className="card">
        <div className="section-header">
  <div className="title-row">
    <span className="icon-badge">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </span>
    <h2>Booking history</h2>
  </div>
</div>
        {bookings.length === 0 ? (
          <div className="empty-state illustrated">
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="12" cy="12" r="9" />
    <path d="M9 12l2 2 4-4" />
  </svg>
  <p>You haven&apos;t booked any seats yet.</p>
</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Route</th>
                <th>Boarding</th>
                <th>Drop-off</th>
                <th>Booked</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bookings.map((b) => (
                <tr key={b.id}>
                  <td>{routes.find((r) => r.id === b.route_id)?.name || b.route_id}</td>
                  <td>{b.boarding_stop_name || routes.find((r) => r.id === b.route_id)?.stops?.find((stop) => stop.id === b.boarding_stop_id)?.name || "—"}</td>
                  <td>{b.dropoff_stop_name || routes.find((r) => r.id === b.route_id)?.stops?.find((stop) => stop.id === b.dropoff_stop_id)?.name || "—"}</td>
                  <td>{new Date(b.created_at).toLocaleDateString()}</td>
                  <td>
                    <StatusPill status={b.status} />
                  </td>
                  <td>
                    {b.status === "confirmed" && (
                      <button className="secondary" onClick={() => cancel(b.id)}>
                        Cancel
                      </button>
                    )}
                  </td>
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
