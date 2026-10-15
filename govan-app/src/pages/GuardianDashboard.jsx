import React, { useEffect, useState } from "react";
import { api } from "../api";
import PassengerLiveRoute from "../components/PassengerLiveRoute.jsx";

export default function GuardianDashboard({ user }) {
  const [passengers, setPassengers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function loadPassengers() {
      setError("");
      try {
        const linkedPassengers = await api.getGuardianPassengers();
        if (!cancelled) setPassengers(linkedPassengers);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadPassengers();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="container">
      <div className="passenger-hero">
        <h2>Welcome, {user.name}</h2>
        <p className="hero-sub">Your children and dependents linked to TravelEase.</p>
      </div>
      <div className="card">
        <div className="section-header">
          <h2>My children/dependents</h2>
        </div>
        {loading && <div className="hint-text" role="status">Loading linked passengers...</div>}
        {error && <div className="error-text" role="alert">{error}</div>}
        {!loading && !error && passengers.length === 0 && (
          <div className="empty-state">
            No passengers are linked to your account yet. Contact your administrator to set up a link.
          </div>
        )}
        {!loading && passengers.length > 0 && (
          <>
            <div className="route-cards">
              {passengers.map((passenger) => (
                <article className="route-card" key={passenger.id}>
                  <div className="route-glyph" aria-hidden="true">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="8" r="4" />
                      <path d="M5 21v-2a7 7 0 0114 0v2" />
                    </svg>
                  </div>
                  <div className="route-info">
                    <h3>{passenger.name}</h3>
                    <div className="stops-line">{passenger.email}</div>
                  </div>
                  <span className="status-pill status-confirmed">{passenger.relationship}</span>
                </article>
              ))}
            </div>
            {passengers.map((passenger) => (
              <PassengerLiveRoute
                key={`live-${passenger.id}`}
                passengerId={passenger.id}
                title={`${passenger.name}'s route`}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
