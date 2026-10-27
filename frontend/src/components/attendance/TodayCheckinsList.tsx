import React, { useEffect, useState, useRef } from "react";
import { UserCheck, Edit3, QrCode, Clock, RefreshCw } from "lucide-react";
import {
  getTodayCheckins,
  type TodayCheckinItem,
  type TodayCheckinsResponse,
} from "../../api/attendance";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";
import { Card } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";

interface TodayCheckinsListProps {
  className?: string;
  refreshTrigger?: number; // Optional external trigger to re-fetch immediately (e.g., after a manual override on dashboard)
}

export const TodayCheckinsList: React.FC<TodayCheckinsListProps> = ({
  className = "",
  refreshTrigger = 0,
}) => {
  const [checkins, setCheckins] = useState<TodayCheckinItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchCheckins = async (showSpinner = false) => {
    if (showSpinner) setIsRefreshing(true);
    try {
      const response: TodayCheckinsResponse = await getTodayCheckins();
      setCheckins(response.results);
      setTotalCount(response.total_count);
      setError(null);
    } catch (err: unknown) {
      // Don't overwrite existing list on transient poll error
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Unable to fetch today's check-ins.";
      setError(msg);
    } finally {
      setLoading(false);
      if (showSpinner) setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchCheckins(true);

    // Criterion 13: Poll every 5 seconds for new entrance scans
    pollIntervalRef.current = setInterval(() => {
      if (document.visibilityState === "visible") {
        fetchCheckins(false);
      }
    }, 5000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        fetchCheckins(false);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refreshTrigger]);

  const formatCheckinTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <Card
      className={`bg-surface border-border p-4 sm:p-6 shadow-sm space-y-4 ${className}`}
      role="region"
      aria-label="Today's Check-ins List"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center justify-center">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-base text-text">
                Today's Check-ins
              </h3>
              <Badge variant="success">
                {totalCount} {totalCount === 1 ? "check-in" : "check-ins"}
              </Badge>
            </div>
            <p className="text-xs text-text-muted mt-0.5">
              Live updates from entrance scanner and manual overrides
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span
            className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20"
            title="Polling every 5 seconds"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Live (5s)</span>
          </span>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => fetchCheckins(true)}
            disabled={isRefreshing}
            className="min-h-[44px] min-w-[44px] px-3 flex items-center gap-1 text-xs"
            aria-label="Refresh today's check-ins"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 text-primary ${
                isRefreshing ? "animate-spin" : ""
              }`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="p-8 text-center text-xs text-text-muted">
          Loading today's check-ins...
        </div>
      ) : error && checkins.length === 0 ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
          {error}
        </div>
      ) : checkins.length === 0 ? (
        <div className="p-8 text-center rounded-lg border border-dashed border-border text-text-muted space-y-2">
          <Clock className="w-8 h-8 mx-auto text-text-muted/60" />
          <p className="text-sm font-medium text-text">
            No check-ins recorded yet today
          </p>
          <p className="text-xs text-text-muted max-w-sm mx-auto">
            Scans from the entrance tablet or manual reception overrides will
            appear here within about 5 seconds.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-border/60 max-h-96 overflow-y-auto pr-1">
          {checkins.map((item) => (
            <div
              key={item.id}
              className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-2/40 px-2 rounded-lg transition-colors"
            >
              <div className="flex items-center gap-3">
                <AuthenticatedImage
                  src={item.member_photo_url}
                  alt={item.member_name}
                  fallbackInitials={item.member_name}
                  className="w-11 h-11 rounded-full object-cover border border-border shadow-sm shrink-0"
                  placeholderClassName="w-11 h-11 rounded-full bg-primary/20 text-primary border border-primary/40 flex items-center justify-center font-bold text-sm shrink-0"
                />

                <div>
                  <h4 className="font-semibold text-sm text-text leading-tight">
                    {item.member_name}
                  </h4>
                  <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
                    <Clock className="w-3 h-3 text-text-muted/80" />
                    <span>{formatCheckinTime(item.checked_in_at)}</span>
                    {item.recorded_by_name && item.is_override && (
                      <>
                        <span>•</span>
                        <span>by {item.recorded_by_name}</span>
                      </>
                    )}
                  </div>
                  {item.is_override && item.override_reason && (
                    <p className="text-xs text-amber-400/90 italic mt-0.5">
                      Reason: {item.override_reason}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
                {item.is_override ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                    <Edit3 className="w-3 h-3" />
                    <span>Manual Override</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    <QrCode className="w-3 h-3" />
                    <span>QR Scan</span>
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
