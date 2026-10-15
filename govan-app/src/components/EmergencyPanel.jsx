import React, { useEffect, useState } from "react";
import { api } from "../api";
import StatusPill from "./StatusPill.jsx";

function currentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("This browser does not support GPS."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => resolve({ lat: coords.latitude, lng: coords.longitude }),
      reject,
      { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 },
    );
  });
}

export default function EmergencyPanel({ activeTrip }) {
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingAlerts, setLoadingAlerts] = useState(true);

  async function loadAlerts() {
    try {
      setAlerts(await api.get("/alerts/mine"));
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAlerts(false);
    }
  }

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 15000);
    return () => clearInterval(interval);
  }, []);

  async function raiseSOS() {
    if (!confirm("Send an SOS alert to TravelEase administrators?")) return;
    setSending(true);
    setError("");
    setNotice("");
    let location = null;
    try {
      location = await currentPosition();
    } catch {
      location = null;
    }

    try {
      await api.post("/alerts/", {
        trip_id: activeTrip?.id ?? null,
        lat: location?.lat ?? null,
        lng: location?.lng ?? null,
      });
      setNotice(location
        ? "Alert sent with your current location."
        : "Alert sent. Current location was unavailable, so no coordinates were attached.");
      await loadAlerts();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="emergency-panel" aria-label="Emergency alerts">
      <div className="emergency-action">
        <div>
          <strong>Emergency assistance</strong>
          <span>Sends your active trip and current location when available.</span>
        </div>
        <button className="sos-button" disabled={sending} onClick={raiseSOS}>
          {sending ? "Sending..." : "SOS"}
        </button>
      </div>
      {notice && <p className="emergency-notice" role="status">{notice}</p>}
      {error && <p className="emergency-error" role="alert">{error}</p>}
      <div className="my-alerts">
        <strong>My alerts</strong>
        {loadingAlerts ? (
          <span role="status">Loading alert history...</span>
        ) : alerts.length === 0 ? (
          <span>No alerts raised.</span>
        ) : (
          <ul>
            {alerts.map((alert) => (
              <li key={alert.id}>
                <span>Alert #{alert.id} · {new Date(alert.created_at).toLocaleString()}</span>
                <StatusPill status={alert.status} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
