import React from "react";

export default function StatusPill({ status }) {
  const label = String(status || "").replace(/_/g, " ");
  return <span className={`status-pill status-${status}`}>{label}</span>;
}
