import React, { useEffect, useRef, useState } from "react";
import {
  fetchNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  type NotificationItem,
} from "../../api/notifications";

export const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadNotifications = async () => {
    try {
      setIsLoading(true);
      const data = await fetchNotifications();
      setNotifications(data.results || []);
      setUnreadCount(data.unread_count || 0);
    } catch {
      // Ignore network errors on background poll
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 60000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await markNotificationAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignore
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // Ignore
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case "subscription_renewal_reminder":
        return "Renewal Reminder";
      case "subscription_reminder":
        return "Reminder";
      case "gym_subscription_reminder":
        return "Platform Reminder";
      case "gym_grace_period_expired":
        return "Grace Period Alert";
      case "member_renewal_due":
        return "Staff Notice";
      case "payment_confirmed":
        return "Payment";
      case "freeze_approved":
        return "Freeze Approved";
      case "freeze_rejected":
        return "Freeze Rejected";
      default:
        return type.replace(/_/g, " ");
    }
  };

  return (
    <div className="relative inline-block" ref={containerRef}>
      {/* Bell Button */}
      <button
        type="button"
        aria-label="Notifications"
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) loadNotifications();
        }}
        className="relative p-2 rounded-input text-text-muted hover:text-text hover:bg-surface-2 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-primary/40"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {unreadCount > 0 && (
          <span
            data-testid="unread-badge"
            className="absolute top-1 right-1 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white bg-primary rounded-full shadow-sm"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-surface border border-border rounded-card shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-text">Notifications</span>
              {unreadCount > 0 && (
                <span className="text-xs bg-primary/20 text-primary font-semibold px-2 py-0.5 rounded-full">
                  {unreadCount} unread
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                type="button"
                onClick={handleMarkAllRead}
                className="text-xs text-primary hover:underline font-medium min-h-[32px] px-2"
              >
                Mark all as read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto divide-y divide-border">
            {isLoading && notifications.length === 0 ? (
              <div className="py-8 text-center text-text-muted text-xs">
                Loading notifications...
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-10 px-4 text-center text-text-muted">
                <div className="w-10 h-10 rounded-full bg-surface-2 mx-auto mb-2 flex items-center justify-center text-text-muted">
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                    />
                  </svg>
                </div>
                <p className="text-sm font-medium text-text">No notifications</p>
                <p className="text-xs mt-0.5">You're all caught up!</p>
              </div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-3.5 transition-colors flex items-start gap-3 hover:bg-surface-2/60 ${
                    !notif.is_read
                      ? "bg-primary/5 border-l-2 border-l-primary"
                      : "opacity-80"
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-primary truncate">
                        {getTypeLabel(notif.type)}
                      </span>
                      <span className="text-[10px] text-text-muted shrink-0">
                        {formatDate(notif.created_at)}
                      </span>
                    </div>

                    <p className="text-xs text-text leading-relaxed break-words">
                      {notif.message}
                    </p>

                    {!notif.is_read && (
                      <div className="mt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={(e) => handleMarkAsRead(notif.id, e)}
                          className="text-[11px] text-text-muted hover:text-primary transition-colors font-medium px-2 py-1 rounded bg-surface border border-border hover:border-primary/40 min-h-[28px]"
                        >
                          Mark as read
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
