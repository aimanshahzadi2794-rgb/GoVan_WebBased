import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function NotificationsBell() {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadNotifications() {
    try {
      setNotifications(await api.get("/notifications/"));
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 15000);
    return () => clearInterval(interval);
  }, []);

  async function markRead(notification) {
    if (notification.read_at) return;
    try {
      const updated = await api.patch(`/notifications/${notification.id}/read`);
      setNotifications((current) => current.map((item) => (
        item.id === updated.id ? updated : item
      )));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  const unreadCount = notifications.filter((item) => !item.read_at).length;

  return (
    <div className="notification-menu">
      <button
        className="notification-bell"
        aria-label={`Notifications, ${unreadCount} unread`}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
          <path d="M10 21h4" />
        </svg>
        {unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? "99+" : unreadCount}</span>}
      </button>
      {isOpen && (
        <div className="notification-popover">
          <div className="notification-popover-title">
            <strong>Notifications</strong>
            <span>{unreadCount} unread</span>
          </div>
          {error && <div className="notification-error" role="alert">{error}</div>}
          {loading ? (
            <p className="notification-empty" role="status">Loading notifications...</p>
          ) : notifications.length === 0 ? (
            <p className="notification-empty">You&apos;re all caught up.</p>
          ) : (
            <ul>
              {notifications.map((notification) => (
                <li className={notification.read_at ? "is-read" : "is-unread"} key={notification.id}>
                  <button className="notification-item" onClick={() => markRead(notification)}>
                    <strong>{notification.title}</strong>
                    <span>{notification.message}</span>
                    <time dateTime={notification.created_at}>
                      {new Date(notification.created_at).toLocaleString()}
                    </time>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
