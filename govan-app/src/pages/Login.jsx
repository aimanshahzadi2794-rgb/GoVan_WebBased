import React, { useState } from "react";
import { api } from "../api";

export default function Login({ onLoggedIn }) {
  const [resetToken, setResetToken] = useState(
    () => new URLSearchParams(window.location.search).get("reset_token") || "",
  );
  const [mode, setMode] = useState(() => (
    new URLSearchParams(window.location.search).has("reset_token") ? "reset" : "login"
  ));
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState("passenger");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    if (mode === "reset" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await api.register({ name, email, password, role });
        const user = await api.login(email, password);
        onLoggedIn(user);
      } else if (mode === "forgot") {
        const result = await api.forgotPassword(email);
        setNotice(result.message);
        setMode("login");
      } else if (mode === "reset") {
        const result = await api.resetPassword(resetToken, password);
        api.logout();
        setNotice(result.message);
        setPassword("");
        setConfirmPassword("");
        setResetToken("");
        const url = new URL(window.location.href);
        url.searchParams.delete("reset_token");
        window.history.replaceState({}, "", url);
        setMode("login");
      } else {
        const user = await api.login(email, password);
        onLoggedIn(user);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="centered-screen">
      <div className="route-scene" aria-hidden="true">
  <svg viewBox="0 0 700 500" preserveAspectRatio="xMidYMax slice">
    <path className="route-path" d="M 40 460 C 160 340, 220 420, 320 300 C 430 170, 540 240, 640 110" />
    <circle className="route-pin start" cx="40" cy="460" r="7" />
    <circle className="route-pin end" cx="640" cy="110" r="7" />
    <g className="route-van">
      <circle r="6" fill="#fff" />
    </g>
  </svg>

  <svg className="skyline" viewBox="0 0 700 120" preserveAspectRatio="none">
    <path
      fill="#ffffff"
      d="M0,120 L0,80 L30,80 L30,50 L55,50 L55,90 L80,90 L80,30 L110,30 L110,70 L140,70 L140,45 L170,45 L170,95 L200,95 L200,20 L235,20 L235,65 L265,65 L265,85 L300,85 L300,40 L330,40 L330,75 L365,75 L365,10 L400,10 L400,60 L430,60 L430,90 L460,90 L460,35 L495,35 L495,70 L525,70 L525,50 L560,50 L560,95 L595,95 L595,25 L630,25 L630,80 L660,80 L660,55 L700,55 L700,120 Z"
    />
  </svg>
</div>

      <div className="login-card">
        <div className="login-logo">
          <img src="/logo.svg" alt="TravelEase" />
          <div className="wordmark">
            Travel<span>Ease</span>
          </div>
        </div>
        <p className="sub">
          {mode === "login" && "Sign in to your dashboard"}
          {mode === "register" && "Create an account to get started"}
          {mode === "forgot" && "We will generate a password reset link if your account exists"}
          {mode === "reset" && "Choose a new password for your account"}
        </p>

        {mode !== "reset" && (
          <div className="tabs">
            <div
              className={`tab ${mode === "login" || mode === "forgot" ? "active" : ""}`}
              onClick={() => { setError(""); setNotice(""); setMode("login"); }}
            >
              Log in
            </div>
            <div
              className={`tab ${mode === "register" ? "active" : ""}`}
              onClick={() => { setError(""); setNotice(""); setMode("register"); }}
            >
              Register
            </div>
          </div>
        )}

        <form onSubmit={submit}>
          {mode === "register" && (
            <div className="field">
              <label>Full name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
          )}
          {mode !== "reset" && (
            <div className="field">
              <label>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
          )}
          {(mode === "login" || mode === "register" || mode === "reset") && (
            <div className="field">
              <label>{mode === "reset" ? "New password" : "Password"}</label>
              <input
                type="password"
                minLength={mode === "reset" ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          )}
          {mode === "reset" && (
            <div className="field">
              <label>Confirm new password</label>
              <input
                type="password"
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
          )}
          {mode === "register" && (
            <div className="field">
              <label>I am a...</label>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="passenger">Passenger</option>
                <option value="driver">Driver</option>
                <option value="guardian">Guardian</option>
              </select>
            </div>
          )}

          {error && <div className="error-text">{error}</div>}
          {notice && <div className="hint-text" role="status">{notice}</div>}

          <button type="submit" disabled={busy} style={{ width: "100%" }}>
            {busy
              ? "Please wait..."
              : mode === "login"
                ? "Log in"
                : mode === "register"
                  ? "Create account"
                  : mode === "forgot"
                    ? "Request reset link"
                    : "Reset password"}
          </button>
        </form>

        {mode === "login" && (
          <button
            type="button"
            className="secondary"
            style={{ width: "100%", marginTop: 10 }}
            onClick={() => { setError(""); setNotice(""); setMode("forgot"); }}
          >
            Forgot password?
          </button>
        )}
        {(mode === "forgot" || mode === "reset") && (
          <button
            type="button"
            className="secondary"
            style={{ width: "100%", marginTop: 10 }}
            onClick={() => { setError(""); setNotice(""); setMode("login"); }}
          >
            Back to log in
          </button>
        )}
        <p className="hint-text">Fleet admin? Use the TravelEase Admin Portal on desktop instead.</p>
      </div>
    </div>
  );
}
