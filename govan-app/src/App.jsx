import React, { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { api } from "./api";
import Login from "./pages/Login.jsx";
import DriverDashboard from "./pages/DriverDashboard.jsx";
import PassengerDashboard from "./pages/PassengerDashboard.jsx";
import GuardianDashboard from "./pages/GuardianDashboard.jsx";
import TopBar from "./components/TopBar.jsx";
import OfflineBanner from "./components/OfflineBanner.jsx";

export default function App() {
  const [user, setUser] = useState(() => (
    new URLSearchParams(window.location.search).has("reset_token")
      ? null
      : api.currentUser()
  ));

  function handleLogout() {
    api.logout();
    setUser(null);
  }

  if (!user) {
    return (
      <>
        <OfflineBanner />
        <Login onLoggedIn={setUser} />
      </>
    );
  }

  if (user.role === "admin") {
    return (
      <>
        <OfflineBanner />
        <div className="centered-screen">
          <div className="login-card" style={{ textAlign: "center" }}>
            <div className="login-logo">
              <img src="/logo.svg" alt="TravelEase" />
              <div className="wordmark">Travel<span>Ease</span></div>
            </div>
            <p className="sub">
              This app is for drivers and passengers. As an <strong>admin</strong>, please use the
              TravelEase Admin Portal on desktop instead.
            </p>
            <button className="secondary" onClick={handleLogout} style={{ width: "100%" }}>
              Log out
            </button>
          </div>
        </div>
      </>
    );
  }

  const dashboardByRole = {
    driver: <DriverDashboard user={user} />,
    passenger: <PassengerDashboard user={user} />,
    guardian: <GuardianDashboard user={user} />,
  };

  return (
    <>
      <OfflineBanner />
      <div className="app-shell">
        <TopBar user={user} onLogout={handleLogout} />
        <Routes>
          <Route path="/" element={dashboardByRole[user.role] || <Navigate to="/" />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </>
  );
}