import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import StatusPill from "../components/StatusPill.jsx";
import LocationLabel from "../components/LocationLabel.jsx";
import EmergencyPanel from "../components/EmergencyPanel.jsx";

const GPS_SEND_INTERVAL_MS = 7000;

function todayForRoute(route) {
  const now = new Date();
  const today = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10);
  const weekday = (now.getDay() + 6) % 7;
  if (route.days_of_week?.length && !route.days_of_week.includes(weekday)) return false;
  if (route.valid_from && today < route.valid_from) return false;
  if (route.valid_to && today > route.valid_to) return false;
  return true;
}

export default function DriverDashboard({ user }) {
  const [trips, setTrips] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [eventsByTrip, setEventsByTrip] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [gpsState, setGpsState] = useState("idle");
  const [queuedCount, setQueuedCount] = useState(0);
  const [screen, setScreen] = useState("trips");
  const [profile, setProfile] = useState({
    phone: user.phone || "",
    license_number: user.license_number || "",
    license_expiry: user.license_expiry || "",
  });
  const [profileSaved, setProfileSaved] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const locationQueue = useRef([]);
  const flushingQueue = useRef(false);
  const lastSentAt = useRef(0);
  const lastGpsFixAt = useRef(0);
  const permissionDenied = useRef(false);

  async function refresh() {
    try {
      const [tripRows, routeRows, vehicleRows] = await Promise.all([
        api.get("/trips/"),
        api.get("/routes/"),
        api.get("/vehicles/"),
      ]);
      setTrips(tripRows);
      setRoutes(routeRows);
      setVehicles(vehicleRows);
      const activeTrips = tripRows.filter((trip) => trip.status === "active");
      const eventRows = await Promise.all(activeTrips.map(async (trip) => [
        trip.id,
        await api.get(`/trips/${trip.id}/stops`),
      ]));
      setEventsByTrip(Object.fromEntries(eventRows));
      setError("");
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

  const activeTrip = trips.find((trip) => trip.status === "active");

  async function startTrip(id) {
    setBusyId(id);
    setError("");
    try {
      await api.post(`/trips/${id}/start`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function endTrip(id) {
    setBusyId(id);
    setError("");
    try {
      await api.post(`/trips/${id}/end`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  const flushLocationQueue = useCallback(async (tripId) => {
    if (flushingQueue.current || !navigator.onLine) return;
    flushingQueue.current = true;
    try {
      while (locationQueue.current.length && navigator.onLine) {
        const queued = locationQueue.current[0];
        if (queued.tripId !== tripId) {
          locationQueue.current.shift();
          continue;
        }
        await api.post(`/trips/${tripId}/location`, queued.point);
        locationQueue.current.shift();
        setQueuedCount(locationQueue.current.length);
      }
    } catch (err) {
      if (err instanceof TypeError || !navigator.onLine) {
        setGpsState("offline");
      } else {
        setError(`GPS update failed: ${err.message}`);
      }
    } finally {
      flushingQueue.current = false;
    }
  }, []);

  useEffect(() => {
    if (!activeTrip) {
      setGpsState("idle");
      locationQueue.current = [];
      setQueuedCount(0);
      return undefined;
    }
    if (!navigator.geolocation) {
      setGpsState("lost");
      setError("This browser does not support GPS location.");
      return undefined;
    }

    let watchId;
    let disposed = false;
    lastSentAt.current = 0;
    lastGpsFixAt.current = Date.now();
    permissionDenied.current = false;
    setGpsState("requesting");
    watchId = navigator.geolocation.watchPosition(
      (position) => {
        if (disposed) return;
        lastGpsFixAt.current = Date.now();
        permissionDenied.current = false;
        setGpsState(navigator.onLine ? "active" : "offline");
        const now = Date.now();
        if (now - lastSentAt.current < GPS_SEND_INTERVAL_MS) return;
        lastSentAt.current = now;
        const point = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        };
        if (!navigator.onLine) {
          locationQueue.current.push({ tripId: activeTrip.id, point });
          setQueuedCount(locationQueue.current.length);
          return;
        }
        locationQueue.current.push({ tripId: activeTrip.id, point });
        setQueuedCount(locationQueue.current.length);
        flushLocationQueue(activeTrip.id);
      },
      (geoError) => {
        if (disposed) return;
        permissionDenied.current = geoError.code === geoError.PERMISSION_DENIED;
        setGpsState(permissionDenied.current ? "permission-denied" : "lost");
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 },
    );
    const gpsTimeout = setInterval(() => {
      if (
        !permissionDenied.current
        && navigator.onLine
        && Date.now() - lastGpsFixAt.current > 20000
      ) {
        setGpsState("lost");
      }
    }, 5000);

    const onOnline = () => {
      setGpsState("requesting");
      flushLocationQueue(activeTrip.id);
    };
    const onOffline = () => setGpsState("offline");
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      disposed = true;
      navigator.geolocation.clearWatch(watchId);
      clearInterval(gpsTimeout);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [activeTrip?.id, flushLocationQueue]);

  useEffect(() => {
    if (!activeTrip || !("wakeLock" in navigator)) return undefined;
    let released = false;
    let wakeLock;
    const requestWakeLock = async () => {
      try {
        const requested = await navigator.wakeLock.request("screen");
        if (released) {
          await requested.release();
        } else {
          wakeLock = requested;
        }
      } catch {
        // Wake Lock is an optional enhancement; trip tracking remains active without it.
      }
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && (!wakeLock || wakeLock.released)) {
        requestWakeLock();
      }
    };
    requestWakeLock();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      released = true;
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (wakeLock && !wakeLock.released) wakeLock.release();
    };
  }, [activeTrip?.id]);

  async function markStopReached(tripId, stopId) {
    setBusyId(tripId);
    setError("");
    try {
      await api.post(`/trips/${tripId}/stops/${stopId}/reached`);
      const events = await api.get(`/trips/${tripId}/stops`);
      setEventsByTrip((current) => ({ ...current, [tripId]: events }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    setSavingProfile(true);
    setProfileSaved(false);
    setError("");
    try {
      const updated = await api.patch("/drivers/me/profile", {
        phone: profile.phone || null,
        license_number: profile.license_number || null,
        license_expiry: profile.license_expiry || null,
      });
      setProfile({
        phone: updated.phone || "",
        license_number: updated.license_number || "",
        license_expiry: updated.license_expiry || "",
      });
      setProfileSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingProfile(false);
    }
  }

  const assignedTrips = trips.filter((trip) => {
    if (trip.status === "active") return true;
    if (trip.status !== "scheduled") return false;
    const route = routes.find((item) => item.id === trip.route_id);
    return route ? todayForRoute(route) : true;
  });
  const gpsLabel = {
    idle: "GPS idle",
    requesting: "GPS connecting…",
    active: "GPS active",
    offline: "GPS active · offline",
    lost: "GPS lost",
    "permission-denied": "GPS permission denied",
  }[gpsState];

  return (
    <div className="container driver-dashboard">
      <div className="section-header">
        <div>
          <h2>{screen === "trips" ? "Today's assigned trips" : "Driver profile"}</h2>
          <p className="driver-welcome">Welcome, {user.name}</p>
        </div>
        <div className="driver-header-actions">
          <button className="secondary" onClick={() => setScreen(screen === "trips" ? "profile" : "trips")}>
            {screen === "trips" ? "My profile" : "My trips"}
          </button>
        </div>
      </div>

      {error && <div className="error-text" role="alert">{error}</div>}
      {loading && <div className="card hint-text" role="status">Loading today&apos;s assigned trips...</div>}
      <EmergencyPanel activeTrip={activeTrip} />

      {!loading && screen === "profile" ? (
        <form className="card driver-profile-form" onSubmit={saveProfile}>
          <label>
            Phone
            <input
              type="tel"
              value={profile.phone}
              onChange={(event) => setProfile({ ...profile, phone: event.target.value })}
            />
          </label>
          <label>
            License number
            <input
              value={profile.license_number}
              onChange={(event) => setProfile({ ...profile, license_number: event.target.value })}
            />
          </label>
          <label>
            License expiry
            <input
              type="date"
              value={profile.license_expiry}
              onChange={(event) => setProfile({ ...profile, license_expiry: event.target.value })}
            />
          </label>
          <button disabled={savingProfile}>{savingProfile ? "Saving..." : "Save profile"}</button>
          {profileSaved && <span className="success-text" role="status">Profile saved.</span>}
        </form>
      ) : !loading && assignedTrips.length === 0 ? (
        <div className="empty-state">
          No trips are assigned for today. Ask your admin to schedule a route and assign it to you.
        </div>
      ) : !loading && assignedTrips.map((trip) => {
        const route = routes.find((item) => item.id === trip.route_id);
        const vehicle = vehicles.find((item) => item.id === route?.vehicle_id);
        const events = eventsByTrip[trip.id] || [];
        const reachedStopIds = new Set(events.map((event) => event.stop_id));
        const orderedStops = [...(route?.stops || [])].sort((a, b) => a.sequence - b.sequence);
        const nextStop = orderedStops.find((stop) => !reachedStopIds.has(stop.id));
        const isActive = trip.status === "active";

        return (
          <section className="card driver-trip-card" key={trip.id}>
            <div className="driver-trip-title">
              <div>
                <h3>{route?.name || `Route ${trip.route_id}`}</h3>
                <div className="driver-trip-meta">
                  <span>Vehicle: {vehicle ? `${vehicle.plate_number} · ${vehicle.model}` : "Not assigned"}</span>
                  <span>Passengers booked: {route?.confirmed_bookings ?? 0}</span>
                </div>
              </div>
              <StatusPill status={trip.status} />
            </div>
            {isActive && (
              <div className={`gps-indicator gps-${gpsState}`} role="status">
                <span className="gps-dot" />
                <strong>{gpsLabel}</strong>
                {queuedCount > 0 && <span>{queuedCount} location update{queuedCount === 1 ? "" : "s"} queued</span>}
                {gpsState === "permission-denied" && (
                  <span>Enable location permission in your browser settings to resume tracking.</span>
                )}
              </div>
            )}
            {trip.last_lat != null && (
              <div className="driver-last-location">
                Last reported location: <LocationLabel lat={trip.last_lat} lng={trip.last_lng} />
              </div>
            )}
            {orderedStops.length > 0 && (
              <div className="driver-stop-list">
                <h4>Route stops</h4>
                <ol>
                  {orderedStops.map((stop) => {
                    const reached = reachedStopIds.has(stop.id);
                    const isNext = nextStop?.id === stop.id;
                    return (
                      <li className={isNext ? "next-stop" : reached ? "reached-stop" : ""} key={stop.id}>
                        <span>{stop.name}</span>
                        {reached ? (
                          <span className="stop-reached-label">Reached</span>
                        ) : isActive && isNext ? (
                          <button
                            className="secondary mark-stop-button"
                            disabled={busyId === trip.id}
                            onClick={() => markStopReached(trip.id, stop.id)}
                          >
                            Mark stop reached
                          </button>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}
            <div className="driver-trip-controls">
              {trip.status === "scheduled" && (
                <button
                  className="driver-trip-button"
                  disabled={busyId === trip.id || Boolean(activeTrip)}
                  onClick={() => startTrip(trip.id)}
                >
                  {busyId === trip.id ? "Starting..." : "Start trip"}
                </button>
              )}
              {isActive && (
                <button
                  className="driver-trip-button danger"
                  disabled={busyId === trip.id}
                  onClick={() => endTrip(trip.id)}
                >
                  {busyId === trip.id ? "Ending..." : "End trip"}
                </button>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
