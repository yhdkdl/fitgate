import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMemberProfileMe, type Member } from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Spinner } from "../ui/Spinner";
import { MemberQrCard } from "../attendance/MemberQrCard";
import { AttendanceLogCard } from "../attendance/AttendanceLogCard";
import { MemberCheckoutCard } from "../member/MemberCheckoutCard";
import { MemberFitnessProfileCard } from "../member/MemberFitnessProfileCard";
import { MemberPaymentHistoryCard } from "../member/MemberPaymentHistoryCard";

interface MemberSelfSectionProps {
  view?: "home" | "membership" | "payments" | "all";
}

export const MemberSelfSection: React.FC<MemberSelfSectionProps> = ({
  view = "all",
}) => {
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
      {/* Pending Member Alert Banner */}
      {profile.status === "pending" && (view === "home" || view === "all") && (
        <div className="bg-primary/10 border border-primary/30 rounded-card p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-base font-bold text-text">
              No active plan yet. Choose a plan to start checking in.
            </h3>
            <p className="text-xs text-text-muted">
              Select a membership plan to activate your account and check-in
              pass.
            </p>
          </div>
          <Link to="/membership">
            <Button
              variant="primary"
              size="md"
              className="whitespace-nowrap w-full sm:w-auto min-h-[40px]"
            >
              My membership
            </Button>
          </Link>
        </div>
      )}

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
      {(view === "home" || view === "all") && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <MemberQrCard memberStatus={profile.status} />
          </div>
          <div className="lg:col-span-2">
            <AttendanceLogCard title="My Attendance Calendar" />
          </div>
        </div>
      )}

      {/* My Trainer Card (Shown on Home and My membership if on a trainer-inclusive plan) */}
      {(view === "home" || view === "membership" || view === "all") &&
        profile.is_on_trainer_plan && (
          <Card className="bg-surface border-border p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-text-muted block">
                  My Trainer
                </span>
                {profile.assigned_trainer ? (
                  <div className="flex items-center gap-3 mt-2">
                    {profile.assigned_trainer.photo_url ? (
                      <AuthenticatedImage
                        src={profile.assigned_trainer.photo_url}
                        alt={profile.assigned_trainer.name}
                        className="w-12 h-12 rounded-full object-cover border border-border"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-sm border border-border">
                        {profile.assigned_trainer.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </div>
                    )}
                    <div>
                      <p className="text-base font-bold text-text">
                        {profile.assigned_trainer.name}
                      </p>
                      {profile.assigned_trainer.specialization && (
                        <p className="text-xs text-text-muted mt-0.5">
                          {profile.assigned_trainer.specialization}
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm font-medium text-amber-500 mt-2 flex items-center gap-2">
                    <Badge variant="warning">Pending</Badge>
                    <span>Trainer not assigned yet</span>
                  </p>
                )}
              </div>
              {profile.assigned_trainer && (
                <Badge variant="primary">Assigned</Badge>
              )}
            </div>
          </Card>
        )}

      {/* Fitness Profile (Read-Only) */}
      {profile.is_on_trainer_plan && (view === "home" || view === "all") && (
        <MemberFitnessProfileCard />
      )}

      {/* Online Plan Checkout & Renewal */}
      {(view === "membership" || view === "all") && (
        <MemberCheckoutCard
          memberStatus={profile.status}
          onPaymentInitiated={fetchProfile}
        />
      )}

      {/* Body Composition Summary / Estimates */}
      {(view === "home" || view === "all") &&
        (hasMetrics ? (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
                  Body Composition & Estimates
                </h3>
                <span className="text-xs text-text-muted">
                  * All calculated values (BMI and Body Fat %) are labeled
                  estimates
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

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">Weight</span>
                <span className="text-lg font-extrabold text-text">
                  {latest?.weight_kg ? `${latest.weight_kg} kg` : "—"}
                </span>
              </Card>

              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">Height</span>
                <span className="text-lg font-extrabold text-text">
                  {latest?.height_cm ? `${latest.height_cm} cm` : "—"}
                </span>
              </Card>

              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">BMI</span>
                <span className="text-lg font-extrabold text-primary">
                  {latest?.estimated_bmi !== null &&
                  latest?.estimated_bmi !== undefined
                    ? latest.estimated_bmi
                    : "—"}
                </span>
                <span className="text-[10px] text-text-muted block">
                  Estimate
                </span>
              </Card>

              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">Body Fat</span>
                <span className="text-lg font-extrabold text-primary">
                  {latest?.measurements &&
                  (latest.measurements as Record<string, unknown>)
                    .body_fat_percentage !== undefined
                    ? `${(latest.measurements as Record<string, unknown>).body_fat_percentage}%`
                    : latest?.estimated_body_fat_percentage !== null &&
                        latest?.estimated_body_fat_percentage !== undefined
                      ? `${latest.estimated_body_fat_percentage}%`
                      : "—"}
                </span>
                <span className="text-[10px] text-text-muted block">
                  {latest?.measurements &&
                  (latest.measurements as Record<string, unknown>)
                    .body_fat_percentage !== undefined
                    ? "Measured"
                    : "Estimate"}
                </span>
              </Card>

              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">Waist/Hip</span>
                <span className="text-lg font-extrabold text-text">
                  {latest?.waist_to_hip_ratio !== null &&
                  latest?.waist_to_hip_ratio !== undefined
                    ? latest.waist_to_hip_ratio
                    : "—"}
                </span>
                <span className="text-[10px] text-text-muted block">Ratio</span>
              </Card>

              <Card className="bg-surface border-border p-3 text-center space-y-1">
                <span className="text-xs text-text-muted block">Lean Mass</span>
                <span className="text-lg font-extrabold text-text">
                  {latest?.lean_body_mass !== null &&
                  latest?.lean_body_mass !== undefined
                    ? `${latest.lean_body_mass} kg`
                    : "—"}
                </span>
                <span className="text-[10px] text-text-muted block">
                  {latest?.lean_body_mass_label || "—"}
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
                        <th className="py-2 px-3">BMI</th>
                        <th className="py-2 px-3">Body Fat</th>
                        <th className="py-2 px-3">Waist/Hip</th>
                        <th className="py-2 px-3">Lean Mass</th>
                        <th className="py-2 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {profile.body_metrics.map((m) => (
                        <tr
                          key={m.id || m.recorded_at}
                          className="hover:bg-surface-2/40"
                        >
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
                            {m.measurements &&
                            (m.measurements as Record<string, unknown>)
                              .body_fat_percentage !== undefined
                              ? `${(m.measurements as Record<string, unknown>).body_fat_percentage}%`
                              : m.estimated_body_fat_percentage
                                ? `${m.estimated_body_fat_percentage}%`
                                : "—"}
                          </td>
                          <td className="py-2 px-3 text-text">
                            {m.waist_to_hip_ratio ?? "—"}
                          </td>
                          <td className="py-2 px-3 text-text">
                            {m.lean_body_mass ? `${m.lean_body_mass} kg` : "—"}
                          </td>
                          <td className="py-2 px-3">
                            {m.is_corrected ? (
                              <Badge variant="warning">Corrected</Badge>
                            ) : (
                              <Badge variant="neutral">Recorded</Badge>
                            )}
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
        ))}

      {/* Payment History & Receipts */}
      {(view === "payments" || view === "all") && <MemberPaymentHistoryCard />}
    </div>
  );
};
