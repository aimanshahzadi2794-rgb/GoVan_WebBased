import React, { useEffect, useState } from "react";

export default function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    const setOnline = () => setIsOnline(true);
    const setOffline = () => setIsOnline(false);
    const onConnectionChange = (event) => setIsOnline(event.detail.online);
    window.addEventListener("online", setOnline);
    window.addEventListener("offline", setOffline);
    window.addEventListener("travelease:connection", onConnectionChange);
    return () => {
      window.removeEventListener("online", setOnline);
      window.removeEventListener("offline", setOffline);
      window.removeEventListener("travelease:connection", onConnectionChange);
    };
  }, []);

  return isOnline ? null : (
    <div className="offline-banner" role="status">
      You are offline. The app shell is available; live data will refresh when you reconnect.
    </div>
  );
}
