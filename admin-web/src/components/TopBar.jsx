import React from "react";

export default function TopBar({ user, onLogout }) {
  return (
    <div className="topbar">
      <div className="brand">
        <img src="/logo.svg" alt="TravelEase" />
        TravelEase
      </div>
      <div className="user-chip">
        <span>{user.name}</span>
        <span className="badge">{user.role}</span>
        <button className="secondary" onClick={onLogout}>
          Log out
        </button>
      </div>
    </div>
  );
}
