import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function Login({ onLoggedIn }) {
  const [mode, setMode] = useState("login");
  const [needsFirstAdmin, setNeedsFirstAdmin] = useState(false);
  const [checkingBootstrap, setCheckingBootstrap] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getBootstrapStatus()
      .then((status) => {
        if (!cancelled) {
          setNeedsFirstAdmin(status.needs_first_admin);
          setCheckingBootstrap(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setCheckingBootstrap(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await api.post("/auth/register", { name, email, password, role: "admin" });
        setMode("login");
        setNeedsFirstAdmin(false);
      }
      const user = await api.login(email, password);
      onLoggedIn(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="centered-screen admin-auth-screen">
      <div className="admin-auth-scene" aria-hidden="true">
        <svg viewBox="0 0 700 500" preserveAspectRatio="xMidYMax slice">
          <path className="admin-auth-route" d="M 40 460 C 160 340, 220 420, 320 300 C 430 170, 540 240, 640 110" />
          <circle className="admin-auth-pin start" cx="40" cy="460" r="7" />
          <circle className="admin-auth-pin end" cx="640" cy="110" r="7" />
          <g className="admin-auth-van">
            <circle r="6" fill="#fff" />
          </g>
        </svg>
        <div className="admin-auth-copy">
          <span>TRAVELEASE FLEET MANAGEMENT</span>
          <h1>Every route,<br />under control.</h1>
          <p>Manage your fleet and keep every journey moving safely.</p>
        </div>
        <svg className="admin-auth-skyline" viewBox="0 0 700 120" preserveAspectRatio="none">
          <path
            fill="#ffffff"
            d="M0,120 L0,80 L30,80 L30,50 L55,50 L55,90 L80,90 L80,30 L110,30 L110,70 L140,70 L140,45 L170,45 L170,95 L200,95 L200,20 L235,20 L235,65 L265,65 L265,85 L300,85 L300,40 L330,40 L330,75 L365,75 L365,10 L400,10 L400,60 L430,60 L430,90 L460,90 L460,35 L495,35 L495,70 L525,70 L525,50 L560,50 L560,95 L595,95 L595,25 L630,25 L630,80 L660,80 L660,55 L700,55 L700,120 Z"
          />
        </svg>
      </div>
      <div className="login-card admin-login-card">
        <div className="login-logo">
          <img src="/logo.svg" alt="TravelEase" />
          <div className="wordmark">Travel<span>Ease</span></div>
          <span className="admin-portal-label">ADMIN PORTAL</span>
        </div>
        <p className="sub">
          {mode === "login"
            ? "Welcome back. Sign in to manage your fleet."
            : "Create the first administrator account to get started."}
        </p>
        {needsFirstAdmin && (
          <div className="tabs auth-tabs">
            <button
              type="button"
              className={`tab ${mode === "login" ? "active" : ""}`}
              onClick={() => { setError(""); setMode("login"); }}
            >
              Log in
            </button>
            <button
              type="button"
              className={`tab ${mode === "register" ? "active" : ""}`}
              onClick={() => { setError(""); setMode("register"); }}
            >
              Sign up
            </button>
          </div>
        )}
        <form onSubmit={submit}>
          {mode === "register" && needsFirstAdmin && (
            <div className="field">
              <label>Full name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          )}
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="error-text" role="alert">{error}</div>}
          <button type="submit" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Please wait..." : mode === "login" ? "Log in" : "Create admin account"}
          </button>
        </form>
        {checkingBootstrap ? (
          <p className="hint-text" role="status">Checking administrator setup...</p>
        ) : needsFirstAdmin ? (
          <p className="hint-text">First time here? Create the initial admin account to set up your portal.</p>
        ) : (
          <p className="hint-text">Admin accounts are created by an existing administrator.</p>
        )}
      </div>
    </div>
  );
}