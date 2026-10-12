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
}

export const FirstRunChecklistCard: React.FC<FirstRunChecklistCardProps> = ({
  onOpenBranding,
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
    <Card className="bg-surface border-border p-6 space-y-4">
      {error && <Alert variant="danger">{error}</Alert>}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-text">
              First-Run Onboarding Checklist
            </h2>
            <Badge variant={data.all_completed ? "success" : "primary"}>
              {completedCount}/{totalCount} Completed
            </Badge>
          </div>
          <p className="text-xs text-text-muted mt-1">
            Follow these essential steps to prepare your gym for operation.
            Tasks tick automatically from real application data.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={handleDismiss}
          disabled={dismissing}
          className="text-text-muted hover:text-text self-start sm:self-center"
        >
          {dismissing ? "Dismissing..." : "Dismiss Checklist"}
        </Button>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-surface-2 rounded-full h-2 overflow-hidden border border-border">
        <div
          className="bg-primary h-2 rounded-full transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Checklist items */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        {items.map(([key, item]) => (
          <div
            key={key}
            className={`p-3 rounded-lg border flex items-center justify-between gap-3 ${
              item.completed
                ? "bg-success/5 border-success/30 text-text"
                : "bg-surface-2/40 border-border text-text-muted"
            }`}
          >
            <div className="flex items-center gap-3">
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  item.completed
                    ? "bg-success text-white"
                    : "border border-border text-text-muted bg-surface-2"
                }`}
              >
                {item.completed ? "✓" : "○"}
              </span>
              <span
                className={`text-sm font-medium ${item.completed ? "text-text" : "text-text-muted"}`}
              >
                {item.label}
              </span>
            </div>

            {key === "add_branding" && !item.completed && onOpenBranding && (
              <Button size="sm" variant="secondary" onClick={onOpenBranding}>
                Customize
              </Button>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
};
