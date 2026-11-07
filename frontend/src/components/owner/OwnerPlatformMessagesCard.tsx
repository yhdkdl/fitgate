import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getGymPlatformNotices, type PlatformNotice } from "../../api/gyms";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import {
  getSeenPlatformNoticeIds,
  markPlatformNoticesSeen,
} from "../../utils/seenNotices";

export const OwnerPlatformMessagesCard: React.FC = () => {
  const [notices, setNotices] = useState<PlatformNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDismissed, setIsDismissed] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let isMounted = true;
    getGymPlatformNotices()
      .then((data) => {
        if (isMounted) setNotices(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        if (isMounted) setNotices([]);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const seenIds = getSeenPlatformNoticeIds();
  const unreadNotices = notices.filter((n) => !seenIds.includes(n.id));

  if (loading || isDismissed || unreadNotices.length === 0) {
    return null;
  }

  const recentNotices = unreadNotices.slice(0, 3);

  const handleViewAll = () => {
    markPlatformNoticesSeen(notices.map((n) => n.id));
    setIsDismissed(true);
    navigate("/platform-messages");
  };

  const handleDismiss = () => {
    markPlatformNoticesSeen(notices.map((n) => n.id));
    setIsDismissed(true);
  };

  return (
    <Card className="bg-surface border-border p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary shrink-0" />
          <h2 className="text-sm font-bold text-text uppercase tracking-wider">
            Messages from FitGate
          </h2>
          <Badge variant="primary" className="text-[10px]">
            {unreadNotices.length}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={handleDismiss}
            className="text-xs text-text-muted hover:text-text"
          >
            Dismiss
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleViewAll}
            className="text-xs text-primary font-medium"
          >
            View all messages &rarr;
          </Button>
        </div>
      </div>

      <div className="divide-y divide-border/60">
        {recentNotices.map((n) => (
          <div key={n.id} className="py-2.5 first:pt-0 last:pb-0 space-y-1">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-text">{n.title}</h3>
              <span className="text-[11px] text-text-muted">
                {new Date(n.created_at).toLocaleDateString()}
              </span>
            </div>
            <p className="text-xs text-text-muted line-clamp-2">{n.message}</p>
          </div>
        ))}
      </div>
    </Card>
  );
};
