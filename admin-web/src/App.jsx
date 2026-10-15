import React, { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { api } from "./api";
import Login from "./pages/Login.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import TopBar from "./components/TopBar.jsx";

export default function App() {
  const [user, setUser] = useState(api.currentUser());

  function handleLogout() {
    api.logout();
    setUser(null);
  }

  if (!user) {
    return <Login onLoggedIn={setUser} />;
  }

  if (user.role !== "admin") {
    return (
      <div className="centered-screen">
        <div className="login-card" style={{ textAlign: "center" }}>
          <div className="login-logo">
            <img src="/logo.svg" alt="TravelEase" />
            <div className="wordmark">Travel<span>Ease</span> Admin</div>
          </div>
          <p className="sub">
            This portal is for administrators only. As a <strong>{user.role}</strong>, please use the
            TravelEase app on your phone instead.
          </p>
          <button className="secondary" onClick={handleLogout} style={{ width: "100%" }}>
            Log out
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <TopBar user={user} onLogout={handleLogout} />
      <Routes>
        <Route path="/" element={<AdminDashboard user={user} />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </div>
  );
}