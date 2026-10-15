import React, { useEffect, useState } from "react";
import {
  getMemberProfileMe,
  recordMemberMetricsMe,
  type Member,
} from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";
import { MemberQrCard } from "../attendance/MemberQrCard";
import { AttendanceLogCard } from "../attendance/AttendanceLogCard";

export const MemberSelfSection: React.FC = () => {
  const [profile, setProfile] = useState<Member | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New measurements form
  const [weightKg, setWeightKg] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [neckCm, setNeckCm] = useState("");
  const [waistCm, setWaistCm] = useState("");
  const [hipCm, setHipCm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [metricsSuccess, setMetricsSuccess] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);

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

  const handleRecordMetrics = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setMetricsSuccess(null);
    setMetricsError(null);
    try {
      const measurements: Record<string, number> = {};
      if (neckCm) measurements.neck_cm = parseFloat(neckCm);
      if (waistCm) measurements.waist_cm = parseFloat(waistCm);
      if (hipCm) measurements.hip_cm = parseFloat(hipCm);

      await recordMemberMetricsMe({
        weight_kg: weightKg ? parseFloat(weightKg) : null,
        height_cm: heightCm ? parseFloat(heightCm) : null,
        measurements:
          Object.keys(measurements).length > 0 ? measurements : undefined,
      });

      setMetricsSuccess("Body composition measurements recorded successfully.");
      setMetricsError(null);
      setWeightKg("");
      setHeightCm("");
      setNeckCm("");
      setWaistCm("");
      setHipCm("");
      fetchProfile();
    } catch (err: unknown) {
      setMetricsError(
        err instanceof Error ? err.message : "Failed to record measurements."
      );
    } finally {
      setSubmitting(false);
    }
  };

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

      {/* Body Composition Summary Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
            Body Composition & Estimates
          </h3>
          <span className="text-xs text-text-muted">
            * All calculated values are labeled estimates
          </span>
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
      </div>

      {/* Record New Measurements */}
      <Card className="bg-surface border-border p-6 space-y-4">
        <div className="border-b border-border pb-2">
          <h3 className="text-base font-bold text-text">
            Log New Measurements
          </h3>
          <p className="text-xs text-text-muted">
            Update your body composition to track your fitness progress over
            time.
          </p>
        </div>

        {metricsSuccess && <Alert variant="success">{metricsSuccess}</Alert>}
        {metricsError && <Alert variant="error">{metricsError}</Alert>}

        <form onSubmit={handleRecordMetrics} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Weight (kg)
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g. 74.5"
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                className="min-h-[44px]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Height (cm)
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g. 180.0"
                value={heightCm}
                onChange={(e) => setHeightCm(e.target.value)}
                className="min-h-[44px]"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Neck Circumference (cm)
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g. 39.5"
                value={neckCm}
                onChange={(e) => setNeckCm(e.target.value)}
                className="min-h-[44px]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Waist Circumference (cm)
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g. 84.0"
                value={waistCm}
                onChange={(e) => setWaistCm(e.target.value)}
                className="min-h-[44px]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Hip Circumference (cm)
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="e.g. 96.0"
                value={hipCm}
                onChange={(e) => setHipCm(e.target.value)}
                className="min-h-[44px]"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button
              type="submit"
              disabled={
                submitting ||
                (!weightKg && !heightCm && !neckCm && !waistCm && !hipCm)
              }
              className="min-h-[44px]"
            >
              {submitting ? "Saving..." : "Record Measurements"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};
