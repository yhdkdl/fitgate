import React, { useEffect, useState } from "react";
import {
  dismissFirstRunChecklist,
  getFirstRunChecklist,
  type FirstRunChecklistResponse,
} from "../../api/gyms";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";

interface FirstRunChecklistCardProps {
  onOpenBranding?: () => void;
  onOpenStaff?: () => void;
}

export const FirstRunChecklistCard: React.FC<FirstRunChecklistCardProps> = ({
  onOpenBranding,
  onOpenStaff,
}) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<FirstRunChecklistResponse | null>(null);
  const [dismissing, setDismissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function loadChecklist() {
      try {
        setLoading(true);
        const res = await getFirstRunChecklist();
        if (isMounted) setData(res);
      } catch (err: unknown) {
        if (isMounted) {
          const msg =
            (err as { data?: { detail?: string } })?.data?.detail ||
            "Unable to load onboarding checklist.";
          setError(msg);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadChecklist();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleDismiss = async () => {
    try {
      setDismissing(true);
      await dismissFirstRunChecklist();
      setData((prev) => (prev ? { ...prev, is_dismissed: true } : null));
    } catch (err: unknown) {
      const msg =
        (err as { data?: { detail?: string } })?.data?.detail ||
        "Unable to dismiss checklist.";
      setError(msg);
    } finally {
      setDismissing(false);
    }
  };

  if (loading) {
    return (
      <Card className="bg-surface border-border p-4 flex items-center justify-center">
        <Spinner size="sm" />
        <span className="text-xs text-text-muted ml-2">
          Checking onboarding progress...
        </span>
      </Card>
    );
  }

  if (!data || data.is_dismissed) {
    return null;
  }

  const items = Object.entries(data.items || {});
  const completedCount = items.filter(([, item]) => item.completed).length;
  const totalCount = items.length;
  const progressPercent =
    totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <Card className="bg-[#12151B] border border-white/10 rounded-2xl p-6 space-y-4 shadow-xl text-white">
      {error && <Alert variant="danger">{error}</Alert>}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-white">
              First-Run Onboarding Checklist
            </h2>
            <Badge variant={data.all_completed ? "success" : "primary"}>
              {completedCount}/{totalCount} Completed
            </Badge>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Follow these essential steps to prepare your gym for operation.
            Tasks tick automatically from real application data.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={handleDismiss}
          disabled={dismissing}
          className="text-slate-300 hover:text-white bg-white/5 border border-white/10 hover:bg-white/10 self-start sm:self-center"
        >
          {dismissing ? "Dismissing..." : "Dismiss Checklist"}
        </Button>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden border border-white/10">
        <div
          className="bg-lime-400 h-2 rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(163,230,53,0.5)]"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Checklist items */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        {items.map(([key, item]) => (
          <div
            key={key}
            className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 transition-colors ${
              item.completed
                ? "bg-lime-500/10 border-lime-500/30 text-white"
                : "bg-white/[0.03] border-white/10 text-slate-400"
            }`}
          >
            <div className="flex items-center gap-3">
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  item.completed
                    ? "bg-lime-400 text-black shadow-[0_0_8px_rgba(163,230,53,0.4)]"
                    : "border border-white/10 text-slate-500 bg-white/5"
                }`}
              >
                {item.completed ? "✓" : "○"}
              </span>
              <span
                className={`text-sm font-medium ${item.completed ? "text-white" : "text-slate-400"}`}
              >
                {item.label}
              </span>
            </div>

            {key === "add_branding" && !item.completed && onOpenBranding && (
              <Button size="sm" variant="secondary" onClick={onOpenBranding} className="bg-white/5 border-white/10 text-white">
                Customize
              </Button>
            )}

            {key === "add_staff" && !item.completed && onOpenStaff && (
              <Button size="sm" variant="secondary" onClick={onOpenStaff} className="bg-white/5 border-white/10 text-white">
                Invite Staff
              </Button>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
};
