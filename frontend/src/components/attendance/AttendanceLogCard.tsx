import React, { useEffect, useState, useCallback } from "react";
import {
  Calendar,
  CheckCircle2,
  XCircle,
  Minus,
  RefreshCw,
} from "lucide-react";
import {
  getAttendanceLog,
  type AttendanceLogResponse,
  type DailyAttendanceItem,
} from "../../api/attendance";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { Spinner } from "../ui/Spinner";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";

interface AttendanceLogCardProps {
  memberId?: string;
  memberName?: string;
  title?: string;
}

export const AttendanceLogCard: React.FC<AttendanceLogCardProps> = ({
  memberId,
  memberName,
  title = "Attendance History",
}) => {
  const [logData, setLogData] = useState<AttendanceLogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rangeDays, setRangeDays] = useState<number>(14);

  const fetchLog = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const today = new Date();
      const pastDate = new Date();
      pastDate.setDate(today.getDate() - rangeDays + 1);

      const startDate = pastDate.toISOString().split("T")[0];
      const endDate = today.toISOString().split("T")[0];

      const data = await getAttendanceLog({
        memberId,
        startDate,
        endDate,
      });
      setLogData(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load attendance calendar."
      );
    } finally {
      setLoading(false);
    }
  }, [memberId, rangeDays]);

  useEffect(() => {
    fetchLog();
  }, [fetchLog]);

  const totalAttended =
    logData?.days.filter((d) => d.status === "present").length || 0;
  const totalEligible =
    logData?.days.filter((d) => d.status !== "blank").length || 0;

  return (
    <Card className="bg-surface border-border p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary" />
            <h3 className="font-bold text-base text-text">
              {title} {memberName ? `— ${memberName}` : ""}
            </h3>
          </div>
          <p className="text-xs text-text-muted mt-0.5">
            Daily check-in logs. Days outside your active subscription are
            blank.
          </p>
        </div>

        {/* Range Selector & Refresh */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex bg-surface-2 p-1 rounded-lg border border-border">
            {[7, 14, 30].map((days) => (
              <button
                key={days}
                onClick={() => setRangeDays(days)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md min-h-[36px] transition-colors ${
                  rangeDays === days
                    ? "bg-primary text-white shadow-sm"
                    : "text-text-muted hover:text-text"
                }`}
              >
                {days}d
              </button>
            ))}
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={fetchLog}
            disabled={loading}
            className="min-h-[36px] px-2.5"
            aria-label="Refresh attendance history"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="h-40 flex items-center justify-center">
          <Spinner size="md" />
        </div>
      ) : error ? (
        <Alert variant="danger">{error}</Alert>
      ) : !logData || logData.days.length === 0 ? (
        <div className="text-center py-8 text-sm text-text-muted">
          No attendance entries recorded for this period.
        </div>
      ) : (
        <div>
          {/* Summary Stats */}
          <div className="flex flex-wrap items-center gap-3 mb-4 p-3 bg-surface-2/60 rounded-xl border border-border/60 text-xs">
            <div className="flex items-center gap-1.5 font-medium">
              <span className="text-text-muted">Check-ins:</span>
              <Badge variant="primary">{totalAttended}</Badge>
            </div>
            <div className="flex items-center gap-1.5 font-medium">
              <span className="text-text-muted">Active Days:</span>
              <span className="font-semibold text-text">{totalEligible}</span>
            </div>
            {logData.subscription_period.start_date && (
              <div className="text-text-muted text-[11px] ml-auto">
                Sub Period: {logData.subscription_period.start_date} to{" "}
                {logData.subscription_period.end_date}
              </div>
            )}
          </div>

          {/* Daily Calendar Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
            {logData.days.map((item: DailyAttendanceItem) => {
              const dateObj = new Date(item.date);
              const dayName = dateObj.toLocaleDateString("en-US", {
                weekday: "short",
              });
              const dayMonth = dateObj.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              });

              const isPresent = item.status === "present";
              const isAbsent = item.status === "absent";

              return (
                <div
                  key={item.date}
                  className={`p-2.5 rounded-xl border flex flex-col items-center justify-between min-h-[74px] transition-all ${
                    isPresent
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : isAbsent
                        ? "bg-rose-500/5 border-rose-500/20 text-rose-400"
                        : "bg-surface-2/30 border-border/40 text-text-muted/60 opacity-60"
                  }`}
                >
                  <span className="text-[10px] uppercase font-bold tracking-wider text-text-muted">
                    {dayName}
                  </span>
                  <span className="text-xs font-semibold text-text">
                    {dayMonth}
                  </span>

                  <div className="mt-1 flex items-center justify-center">
                    {isPresent ? (
                      <span className="flex items-center gap-1 font-bold text-sm text-emerald-400">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />✓
                      </span>
                    ) : isAbsent ? (
                      <span className="flex items-center gap-1 font-bold text-sm text-rose-400">
                        <XCircle className="w-4 h-4 text-rose-400" />✗
                      </span>
                    ) : (
                      <span className="text-xs text-text-muted flex items-center gap-0.5">
                        <Minus className="w-3.5 h-3.5 text-text-muted/40" />
                        blank
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
};
