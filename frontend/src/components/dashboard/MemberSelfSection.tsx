import React, { useEffect, useState } from "react";
import { getMemberProfileMe, type Member } from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import { MemberQrCard } from "../attendance/MemberQrCard";
import { AttendanceLogCard } from "../attendance/AttendanceLogCard";
import { MemberCheckoutCard } from "../member/MemberCheckoutCard";


export const MemberSelfSection: React.FC = () => {
  const [profile, setProfile] = useState<Member | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMemberProfileMe();
      setProfile(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load member profile."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center flex flex-col items-center gap-3">
        <Spinner size="md" />
        <p className="text-xs text-text-muted">
          Loading your member dashboard...
        </p>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <Alert variant="danger">{error || "Member profile not found."}</Alert>
    );
  }

  const latest = profile.latest_metrics;
  const hasMetrics = Boolean(
    latest && (latest.weight_kg !== null || latest.height_cm !== null)
  );

  return (
    <div className="space-y-6">
      {/* Welcome & Member Status Banner */}
      <div className="bg-surface border border-border rounded-card p-6 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h2 className="text-xl sm:text-2xl font-bold text-text">
                Welcome, {profile.full_name}
              </h2>
              <Badge variant="success" className="capitalize">
                {profile.status}
              </Badge>
            </div>
            <p className="text-xs text-text-muted">
              Member since {new Date(profile.joined_at).toLocaleDateString()} ·{" "}
              {profile.phone}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              Waiver: Signed{" "}
              {new Date(profile.waiver_accepted_at).toLocaleDateString()}
            </Badge>
          </div>
        </div>
      </div>

      {/* Dynamic QR Pass & Attendance Calendar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <MemberQrCard memberStatus={profile.status} />
        </div>
        <div className="lg:col-span-2">
          <AttendanceLogCard title="My Attendance Calendar" />
        </div>
      </div>

      {/* Online Plan Checkout & Renewal */}
      <MemberCheckoutCard
        memberStatus={profile.status}
        onPaymentInitiated={fetchProfile}
      />


      {/* Body Composition Summary / Estimates */}
      {hasMetrics ? (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
                Body Composition & Estimates
              </h3>
              <span className="text-xs text-text-muted">
                * All calculated values (BMI and Body Fat %) are labeled estimates
              </span>
            </div>
            {(latest?.trainer_name || latest?.recorded_by_name) && (
              <span className="text-xs text-text-muted">
                Recorded by Trainer:{" "}
                <strong className="text-text">
                  {latest.trainer_name || latest.recorded_by_name}
                </strong>
                {latest.recorded_at && (
                  <> on {new Date(latest.recorded_at).toLocaleDateString()}</>
                )}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="bg-surface border-border p-4 text-center space-y-1">
              <span className="text-xs text-text-muted block">Weight</span>
              <span className="text-xl font-extrabold text-text">
                {latest?.weight_kg ? `${latest.weight_kg} kg` : "—"}
              </span>
            </Card>

            <Card className="bg-surface border-border p-4 text-center space-y-1">
              <span className="text-xs text-text-muted block">Height</span>
              <span className="text-xl font-extrabold text-text">
                {latest?.height_cm ? `${latest.height_cm} cm` : "—"}
              </span>
            </Card>

            <Card className="bg-surface border-border p-4 text-center space-y-1">
              <span className="text-xs text-text-muted block">BMI (Est)</span>
              <span className="text-xl font-extrabold text-primary">
                {latest?.estimated_bmi !== null &&
                latest?.estimated_bmi !== undefined
                  ? latest.estimated_bmi
                  : "—"}
              </span>
              <span className="text-[10px] text-text-muted block">Estimate</span>
            </Card>

            <Card className="bg-surface border-border p-4 text-center space-y-1">
              <span className="text-xs text-text-muted block">
                Body Fat (Est)
              </span>
              <span className="text-xl font-extrabold text-primary">
                {latest?.estimated_body_fat_percentage !== null &&
                latest?.estimated_body_fat_percentage !== undefined
                  ? `${latest.estimated_body_fat_percentage}%`
                  : "—"}
              </span>
              <span className="text-[10px] text-text-muted block">
                US Navy Method
              </span>
            </Card>
          </div>

          {/* Measurements History */}
          {profile.body_metrics && profile.body_metrics.length > 0 && (
            <Card className="bg-surface border-border p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                Measurement History
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="border-b border-border text-text-muted">
                    <tr>
                      <th className="py-2 px-3">Date</th>
                      <th className="py-2 px-3">Trainer</th>
                      <th className="py-2 px-3">Weight</th>
                      <th className="py-2 px-3">Height</th>
                      <th className="py-2 px-3">BMI (Est)</th>
                      <th className="py-2 px-3">Body Fat (Est)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {profile.body_metrics.map((m) => (
                      <tr key={m.id || m.recorded_at} className="hover:bg-surface-2/40">
                        <td className="py-2 px-3 text-text">
                          {m.recorded_at
                            ? new Date(m.recorded_at).toLocaleDateString()
                            : "—"}
                        </td>
                        <td className="py-2 px-3 font-medium text-text">
                          {m.trainer_name || m.recorded_by_name || "Trainer"}
                        </td>
                        <td className="py-2 px-3 text-text">
                          {m.weight_kg ? `${m.weight_kg} kg` : "—"}
                        </td>
                        <td className="py-2 px-3 text-text">
                          {m.height_cm ? `${m.height_cm} cm` : "—"}
                        </td>
                        <td className="py-2 px-3 font-semibold text-primary">
                          {m.estimated_bmi ?? "—"}
                        </td>
                        <td className="py-2 px-3 font-semibold text-primary">
                          {m.estimated_body_fat_percentage
                            ? `${m.estimated_body_fat_percentage}%`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      ) : (
        <Card className="bg-surface border-border p-6 text-center space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
            Body Composition & Estimates
          </h3>
          <p className="text-sm text-text-muted">
            Not measured yet. A trainer records measurements.
          </p>
        </Card>
      )}
    </div>
  );
};
