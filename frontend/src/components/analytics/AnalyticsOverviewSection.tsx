import React, { useEffect, useState } from "react";
import {
  GymAnalyticsOverview,
  ExpiringMembership,
  getGymAnalyticsOverview,
} from "../../api/analytics";
import { Card, Button, Badge, Modal, Spinner, Alert } from "../ui";
import { ExportDataModal } from "../export/ExportDataModal";

interface AnalyticsOverviewSectionProps {
  onUpgradeClick?: () => void;
}

export const AnalyticsOverviewSection: React.FC<AnalyticsOverviewSectionProps> = ({
  onUpgradeClick,
}) => {
  const [data, setData] = useState<GymAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showExpiringModal, setShowExpiringModal] = useState<boolean>(false);
  const [showExportAttendanceModal, setShowExportAttendanceModal] = useState<boolean>(false);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getGymAnalyticsOverview();
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to load gym analytics overview.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading && !data) {
    return (
      <Card className="p-8 flex flex-col items-center justify-center space-y-3 bg-surface border-border">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">Loading live operational analytics...</p>
      </Card>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-3">
        <Alert variant="danger" title="Analytics Unavailable">
          {error}
        </Alert>
        <Button size="sm" variant="secondary" onClick={fetchAnalytics}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6" data-testid="analytics-overview-section">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-xl font-bold text-text">Operational Overview</h2>
          <p className="text-xs text-text-muted">
            Live operational metrics and membership performance for your gym.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowExportAttendanceModal(true)}
          >
            Export Attendance CSV
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={fetchAnalytics}
            disabled={loading}
          >
            {loading ? <Spinner size="sm" /> : "Refresh"}
          </Button>
        </div>
      </div>

      {/* 4 Core Operational Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Active Members */}
        <Card className="bg-surface border-border p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Active Members</span>
            <Badge variant="success">Active</Badge>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-text" data-testid="stat-active-members">
              {data.active_members}
            </span>
            <span className="text-xs text-text-muted">
              ({data.frozen_members} frozen)
            </span>
          </div>
          <p className="text-[11px] text-text-muted">
            Derived active membership accounts
          </p>
        </Card>

        {/* Metric 2: Today's Check-ins */}
        <Card className="bg-surface border-border p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Today's Check-ins</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary" data-testid="stat-today-checkins">
              {data.today_checkins}
            </span>
            <span className="text-xs text-text-muted">scans</span>
          </div>
          <p className="text-[11px] text-text-muted">
            Check-ins today (Addis Ababa time)
          </p>
        </Card>

        {/* Metric 3: Monthly Net Revenue */}
        <Card className="bg-surface border-border p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Monthly Net Revenue</span>
            <span className="text-[10px] font-semibold text-emerald-500 uppercase tracking-wider">
              {data.currency}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-500" data-testid="stat-monthly-revenue">
              {Number(data.monthly_net_revenue).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <span className="text-xs text-text-muted">{data.currency}</span>
          </div>
          <p className="text-[11px] text-text-muted">
            Confirmed net cash received this month
          </p>
        </Card>

        {/* Metric 4: Memberships Expiring in 7 Days */}
        <Card className="bg-surface border-border p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Expiring in 7 Days</span>
            <Badge variant={data.expiring_memberships_count > 0 ? "warning" : "neutral"}>
              {data.expiring_memberships_count > 0 ? "Action Needed" : "On Track"}
            </Badge>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold text-amber-500" data-testid="stat-expiring-count">
              {data.expiring_memberships_count}
            </span>
            {data.expiring_memberships_count > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowExpiringModal(true)}
                className="text-xs text-primary p-0 h-auto hover:underline"
              >
                View list &rarr;
              </Button>
            )}
          </div>
          <p className="text-[11px] text-text-muted">
            Active plans ending soon without renewal
          </p>
        </Card>
      </div>

      {/* Premium Analytics: Revenue by Plan */}
      <Card className="bg-surface border-border p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-text uppercase tracking-wider">
                Revenue by Membership Plan
              </h3>
              {data.has_analytics ? (
                <Badge variant="success">Pro Analytics</Badge>
              ) : (
                <Badge variant="neutral">Growth / Pro</Badge>
              )}
            </div>
            <p className="text-xs text-text-muted mt-0.5">
              Net cash received breakdown per membership package.
            </p>
          </div>
        </div>

        {data.has_analytics && data.revenue_by_plan ? (
          <div>
            {data.revenue_by_plan.length === 0 ? (
              <div className="text-center py-6 text-text-muted text-xs">
                No confirmed plan payments recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border text-text-muted">
                      <th className="py-2 px-3 font-semibold">Plan Name</th>
                      <th className="py-2 px-3 font-semibold text-center">Payments</th>
                      <th className="py-2 px-3 font-semibold text-right">Net Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {data.revenue_by_plan.map((item) => (
                      <tr key={item.plan_id} className="hover:bg-surface-2/40">
                        <td className="py-2.5 px-3 font-medium text-text">
                          {item.plan_name}
                        </td>
                        <td className="py-2.5 px-3 text-center text-text-muted">
                          {item.payment_count}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-emerald-500">
                          {Number(item.revenue).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}{" "}
                          {data.currency}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="p-6 bg-surface-2/50 rounded-lg border border-dashed border-border text-center space-y-3">
            <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-primary/10 text-primary">
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h4 className="text-sm font-semibold text-text">
                Revenue by Plan Locked
              </h4>
              <p className="text-xs text-text-muted">
                {data.upgrade_prompt ||
                  "Upgrade to Growth or Pro to unlock revenue by plan breakdowns."}
              </p>
            </div>
            {onUpgradeClick && (
              <Button size="sm" variant="primary" onClick={onUpgradeClick}>
                Upgrade Plan
              </Button>
            )}
          </div>
        )}
      </Card>

      {/* Expiring Members Modal */}
      {showExpiringModal && (
        <Modal
          isOpen={showExpiringModal}
          onClose={() => setShowExpiringModal(false)}
          title="Memberships Expiring Within 7 Days"
        >
          <div className="space-y-4">
            <p className="text-xs text-text-muted">
              These members have active subscriptions expiring within 7 days and do
              not have a queued renewal.
            </p>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border text-text-muted sticky top-0 bg-surface">
                    <th className="py-2 px-3 font-semibold">Member</th>
                    <th className="py-2 px-3 font-semibold">Phone</th>
                    <th className="py-2 px-3 font-semibold">Plan</th>
                    <th className="py-2 px-3 font-semibold">End Date</th>
                    <th className="py-2 px-3 font-semibold text-right">Remaining</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {data.expiring_memberships.map((sub: ExpiringMembership) => (
                    <tr key={sub.member_id} className="hover:bg-surface-2/40">
                      <td className="py-2 px-3 font-medium text-text">
                        {sub.member_name}
                      </td>
                      <td className="py-2 px-3 text-text-muted">{sub.member_phone}</td>
                      <td className="py-2 px-3 text-text">{sub.plan_name}</td>
                      <td className="py-2 px-3 text-text-muted">{sub.end_date}</td>
                      <td className="py-2 px-3 text-right">
                        <Badge
                          variant={sub.days_remaining <= 2 ? "danger" : "warning"}
                        >
                          {sub.days_remaining === 0
                            ? "Expires today"
                            : `${sub.days_remaining} day${sub.days_remaining > 1 ? "s" : ""}`}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end pt-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowExpiringModal(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      <ExportDataModal
        isOpen={showExportAttendanceModal}
        onClose={() => setShowExportAttendanceModal(false)}
        exportType="attendance"
      />
    </div>
  );
};
