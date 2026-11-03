import React from "react";
import type { Member } from "../../api/members";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

interface MemberSubscriptionCardProps {
  member: Member;
}

export const MemberSubscriptionCard: React.FC<MemberSubscriptionCardProps> = ({
  member,
}) => {
  const activeSub = member.active_subscription;
  const queuedSub = member.queued_subscription;
  const activeFreeze = member.active_freeze;
  const isPending = member.status === "pending";
  const isFrozen = member.status === "frozen";

  if (!activeSub && isPending) {
    return (
      <Card className="bg-surface border-border p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            My Membership
          </span>
          <Badge variant="warning">Waiting for payment</Badge>
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-bold text-text">No Active Subscription</h3>
          <p className="text-xs text-text-muted">
            Waiting for payment. Please choose a membership plan to activate your account.
          </p>
        </div>
      </Card>
    );
  }

  if (!activeSub) {
    return (
      <Card className="bg-surface border-border p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            My Membership
          </span>
          <Badge variant="danger" className="capitalize">
            {member.status}
          </Badge>
        </div>
        <div className="space-y-1">
          <h3 className="text-lg font-bold text-text">No Active Subscription</h3>
          <p className="text-xs text-text-muted">
            Your membership is currently expired or inactive.
          </p>
        </div>
      </Card>
    );
  }

  // Authoritative days left from backend calculation
  const totalDays = activeSub.total_days ?? 30;
  const remainingDays = activeSub.remaining_days ?? 0;
  const percentage = Math.max(0, Math.min(100, Math.round((remainingDays / totalDays) * 100)));

  const durationDisplay =
    activeSub.duration_value && activeSub.duration_unit
      ? `${activeSub.duration_value} ${
          activeSub.duration_value === 1
            ? activeSub.duration_unit.replace(/s$/, "")
            : activeSub.duration_unit
        }`
      : "1 Month";

  const getStatusBadge = () => {
    if (isPending) return <Badge variant="warning">Waiting for payment</Badge>;
    if (isFrozen) return <Badge variant="warning">Frozen</Badge>;
    if (activeSub.status === "active" && member.status === "active") {
      return <Badge variant="success">Active</Badge>;
    }
    return (
      <Badge variant="secondary" className="capitalize">
        {member.status}
      </Badge>
    );
  };

  return (
    <Card className="bg-surface border-border p-5 space-y-4">
      {/* Top Header: Plan Name and Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/50 pb-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
            Current Membership Plan
          </span>
          <h3 className="text-xl font-bold text-text mt-0.5">{activeSub.plan_name}</h3>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge()}
        </div>
      </div>

      {/* Frozen / Pending Special Banners */}
      {isFrozen && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-500 rounded-lg p-3 text-xs font-medium flex items-center justify-between">
          <span>Subscription temporarily frozen</span>
          <span className="font-bold">
            Frozen until {activeFreeze?.end_date || activeSub.end_date}
          </span>
        </div>
      )}

      {isPending && (
        <div className="bg-amber-500/10 border border-amber-500/30 text-amber-500 rounded-lg p-3 text-xs font-medium">
          Waiting for payment
        </div>
      )}

      {/* Details Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="space-y-0.5">
          <span className="text-text-muted block">Trainer Included</span>
          <span className="font-semibold text-text">
            Trainer included: {activeSub.trainer_inclusive ? "yes" : "no"}
          </span>
        </div>
        <div className="space-y-0.5">
          <span className="text-text-muted block">Plan Duration</span>
          <span className="font-semibold text-text">{durationDisplay}</span>
        </div>
        <div className="space-y-0.5">
          <span className="text-text-muted block">Start Date</span>
          <span className="font-semibold text-text">{activeSub.start_date}</span>
        </div>
        <div className="space-y-0.5">
          <span className="text-text-muted block">End Date</span>
          <span className="font-semibold text-text">{activeSub.end_date}</span>
        </div>
      </div>

      {/* Days Left Bar */}
      {!isPending && (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-text">{remainingDays} days left</span>
            <span className="text-text-muted">
              {remainingDays} of {totalDays} days remaining
            </span>
          </div>
          <div className="w-full bg-surface-2 rounded-full h-2.5 overflow-hidden border border-border/40">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                remainingDays <= 5 ? "bg-amber-500" : "bg-primary"
              }`}
              style={{ width: `${percentage}%` }}
              role="progressbar"
              aria-valuenow={remainingDays}
              aria-valuemin={0}
              aria-valuemax={totalDays}
            />
          </div>
        </div>
      )}

      {/* Queued Next Plan */}
      {queuedSub && (
        <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant="primary">Queued</Badge>
            <span className="text-text font-medium">
              Next plan: {queuedSub.plan_name} starts on {queuedSub.start_date}
            </span>
          </div>
          <span className="text-text-muted text-[11px] hidden sm:inline">
            Active once current plan ends
          </span>
        </div>
      )}
    </Card>
  );
};
