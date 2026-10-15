import React, { useEffect, useState } from "react";
import { api } from "../api";
import MapView from "./MapView.jsx";
import StatusPill from "./StatusPill.jsx";

const POLL_INTERVAL_MS = 6000;
const LOCATION_STALE_AFTER_MS = 60000;

export default function PassengerLiveRoute({ passengerId, title = "My route" }) {
  const [trips, setTrips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const activeTrips = await api.getActiveTripsForMe(passengerId);
        if (!cancelled) {
          setTrips(activeTrips);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    refresh();
    const pollId = setInterval(refresh, POLL_INTERVAL_MS);
    const clockId = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      cancelled = true;
      clearInterval(pollId);
      clearInterval(clockId);
    };
  }, [passengerId]);

  return (
    <section className="card live-route-card" aria-label={title}>
      <div className="section-header">
        <h2>{title}</h2>
        <span className="live-refresh-label">Updates every 6 seconds</span>
      </div>
      {loading && <div className="hint-text" role="status">Loading live route...</div>}
      {error && <div className="error-text" role="alert">{error}</div>}
      {!loading && !error && trips.length === 0 && (
        <div className="empty-state compact">No active trip is currently running for this passenger&apos;s confirmed bookings.</div>
      )}
      {!error && trips.map((trip) => {
        const stale = !trip.last_location_at
          || now - new Date(trip.last_location_at).getTime() > LOCATION_STALE_AFTER_MS;
        const lastSeen = trip.last_location_at
          ? new Date(trip.last_location_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : null;
        const stops = trip.stops.map((stop) => ({
          id: stop.id,
          name: stop.name,
          lat: stop.lat,
          lng: stop.lng,
          sequence: stop.sequence,
        }));
        const vehicleMarker = !stale && trip.last_lat != null && trip.last_lng != null
          ? [{ lat: trip.last_lat, lng: trip.last_lng, label: `Vehicle · ${trip.vehicle_plate || "No plate"}` }]
          : [];
        const hasMapPoints = stops.length > 0 || vehicleMarker.length > 0;

        return (
          <article className="live-trip" key={trip.id}>
            {trips.length > 1 && <h3>{trip.route_name}</h3>}
            <div className="live-trip-details">
              <span><strong>Status:</strong> <StatusPill status={trip.status} /></span>
              <span><strong>Driver:</strong> {trip.driver_name}</span>
              <span><strong>Vehicle:</strong> {trip.vehicle_plate || "Not assigned"}</span>
              <span><strong>Next stop:</strong> {trip.next_stop_name || "No upcoming stop"}</span>
              <span>
                <strong>Boarding stop:</strong> {trip.boarding_stop_name || "Not set"}
                {" · "}
                ETA {trip.eta_minutes == null ? "unavailable" : `approx. ${trip.eta_minutes} min`}
              </span>
            </div>
            {stale && (
              <div className="location-lost" role="status">
                Location signal lost, last seen {lastSeen || "unknown"}.
              </div>
            )}
            {hasMapPoints ? (
              <MapView
                markers={vehicleMarker}
                stops={stops}
                height={300}
              />
            ) : (
              <div className="empty-state compact">Route stops are not available for this trip.</div>
            )}
          </article>
        );
      })}
    </section>
  );
}
