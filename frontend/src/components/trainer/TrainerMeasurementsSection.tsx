import React, { useCallback, useEffect, useState } from "react";
import {
  getMemberMetrics,
  listGymMembers,
  recordMemberMetrics,
  type BodyMetrics,
  type Member,
} from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";
import {
  focusFirstInvalidField,
  validateHeight,
  validateHip,
  validateNeck,
  validateWaist,
  validateWeight,
} from "../../utils/validators";

export const TrainerMeasurementsSection: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [members, setMembers] = useState<Member[]>([]);

  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsHistory, setMetricsHistory] = useState<BodyMetrics[]>([]);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  // Form inputs
  const [weightKg, setWeightKg] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [waistCm, setWaistCm] = useState("");
  const [neckCm, setNeckCm] = useState("");
  const [hipCm, setHipCm] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const fetchMembers = useCallback(async (query: string) => {
    setSearching(true);
    setSearchError(null);
    try {
      const data = await listGymMembers({
        search: query.trim() || undefined,
        limit: 10,
      });
      setMembers(data);
    } catch (err: unknown) {
      setSearchError(
        err instanceof Error ? err.message : "Failed to search members."
      );
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    fetchMembers("");
  }, [fetchMembers]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchMembers(searchQuery);
  };

  const handleSelectMember = async (member: Member) => {
    setSelectedMember(member);
    setMetricsLoading(true);
    setMetricsError(null);
    setFormSuccess(null);
    setFormError(null);
    setFieldErrors({});
    setWeightKg("");
    setHeightCm("");
    setWaistCm("");
    setNeckCm("");
    setHipCm("");

    try {
      const metrics = await getMemberMetrics(member.id);
      setMetricsHistory(metrics);
    } catch (err: unknown) {
      setMetricsError(
        err instanceof Error
          ? err.message
          : "Failed to load member measurement history."
      );
    } finally {
      setMetricsLoading(false);
    }
  };

  const handleRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMember) return;
    setFormError(null);
    setFormSuccess(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};
    const wErr = validateWeight(weightKg);
    if (wErr) errors["metric-weight"] = wErr;

    const hErr = validateHeight(heightCm);
    if (hErr) errors["metric-height"] = hErr;

    if (waistCm.trim()) {
      const wstErr = validateWaist(waistCm);
      if (wstErr) errors["metric-waist"] = wstErr;
    }

    if (neckCm.trim()) {
      const nckErr = validateNeck(neckCm);
      if (nckErr) errors["metric-neck"] = nckErr;
    }

    if (hipCm.trim()) {
      const hpErr = validateHip(hipCm);
      if (hpErr) errors["metric-hip"] = hpErr;
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setSubmitting(true);

    try {
      const measurements: Record<string, number> = {};
      if (waistCm.trim()) measurements.waist_cm = parseFloat(waistCm);
      if (neckCm.trim()) measurements.neck_cm = parseFloat(neckCm);
      if (hipCm.trim()) measurements.hip_cm = parseFloat(hipCm);

      await recordMemberMetrics(selectedMember.id, {
        weight_kg: parseFloat(weightKg),
        height_cm: parseFloat(heightCm),
        waist_cm: waistCm.trim() ? parseFloat(waistCm) : undefined,
        neck_cm: neckCm.trim() ? parseFloat(neckCm) : undefined,
        hip_cm: hipCm.trim() ? parseFloat(hipCm) : undefined,
        measurements:
          Object.keys(measurements).length > 0 ? measurements : undefined,
      });

      setFormSuccess(
        `Body measurements successfully recorded for ${selectedMember.full_name}.`
      );
      setWeightKg("");
      setHeightCm("");
      setWaistCm("");
      setNeckCm("");
      setHipCm("");
      setFieldErrors({});

      // Refresh metrics history
      const updated = await getMemberMetrics(selectedMember.id);
      setMetricsHistory(updated);
    } catch (err: unknown) {
      setFormError(
        err instanceof Error
          ? err.message
          : "Failed to record member measurements."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const latest = metricsHistory[0] || null;
  const hasHistory = metricsHistory.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-border pb-3">
        <h2 className="text-xl font-bold text-text">Member Measurements</h2>
        <p className="text-xs text-text-muted">
          Accurately measure and record member body composition. All BMI and
          body fat calculations are derived as labeled estimates.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Member Search and List */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="bg-surface border-border p-4 space-y-3">
            <h3 className="text-sm font-bold text-text uppercase tracking-wider">
              Find Member
            </h3>

            <form onSubmit={handleSearchSubmit} className="flex gap-2">
              <Input
                type="text"
                placeholder="Search by name, email, or phone..."
                maxLength={100}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="min-h-[44px] flex-1 text-sm"
              />
              <Button
                type="submit"
                size="md"
                disabled={searching}
                className="min-h-[44px] shrink-0"
              >
                {searching ? "..." : "Search"}
              </Button>
            </form>

            {searchError && <Alert variant="error">{searchError}</Alert>}

            {/* Member Results List */}
            <div className="space-y-2 max-h-96 overflow-y-auto pt-2">
              {searching ? (
                <div className="p-4 text-center">
                  <Spinner size="sm" />
                  <p className="text-xs text-text-muted mt-2">
                    Searching members...
                  </p>
                </div>
              ) : members.length === 0 ? (
                <p className="text-xs text-text-muted text-center py-4">
                  No members found matching your search.
                </p>
              ) : (
                members.map((m) => {
                  const isSelected = selectedMember?.id === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectMember(m)}
                      className={`w-full text-left p-3 rounded-lg border transition-all min-h-[44px] flex flex-col justify-center ${
                        isSelected
                          ? "bg-primary/10 border-primary text-text shadow-sm"
                          : "bg-surface-2/40 border-border/80 hover:bg-surface-2 text-text"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-sm">
                          {m.full_name}
                        </span>
                        {m.status && (
                          <Badge
                            variant={
                              m.status === "active" ? "success" : "secondary"
                            }
                          >
                            {m.status}
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-text-muted flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mt-1">
                        <span>{m.email}</span>
                        <span className="hidden sm:inline">·</span>
                        <span>{m.phone}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: Measurements View & Entry Form */}
        <div className="lg:col-span-7 space-y-4">
          {!selectedMember ? (
            <Card className="bg-surface border-border p-8 text-center space-y-2">
              <span className="text-3xl">📋</span>
              <h3 className="text-base font-bold text-text">
                No Member Selected
              </h3>
              <p className="text-xs text-text-muted max-w-sm mx-auto">
                Select a member from the list on the left to view their
                measurement history and record new body composition metrics.
              </p>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Member banner */}
              <div className="bg-surface-2/60 border border-border rounded-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-lg font-bold text-text">
                    {selectedMember.full_name}
                  </h3>
                  <p className="text-xs text-text-muted">
                    {selectedMember.email} · {selectedMember.phone}
                  </p>
                </div>
                <Badge variant="primary">Selected</Badge>
              </div>

              {/* Latest Estimates or Not Measured Yet */}
              {metricsLoading ? (
                <div className="p-8 text-center bg-surface border border-border rounded-card">
                  <Spinner size="md" />
                  <p className="text-xs text-text-muted mt-2">
                    Loading measurement history...
                  </p>
                </div>
              ) : metricsError ? (
                <Alert variant="error">{metricsError}</Alert>
              ) : hasHistory && latest ? (
                <div className="p-4 bg-primary/5 border border-primary/20 rounded-card space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-primary">
                      Current Body Composition Estimates
                    </h4>
                    {(latest.trainer_name || latest.recorded_by_name) && (
                      <span className="text-xs text-text-muted">
                        Recorded by Trainer:{" "}
                        <strong className="text-text">
                          {latest.trainer_name || latest.recorded_by_name}
                        </strong>
                        {latest.recorded_at && (
                          <>
                            {" "}
                            on{" "}
                            {new Date(latest.recorded_at).toLocaleDateString()}
                          </>
                        )}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                    <div className="bg-surface p-2.5 rounded border border-border">
                      <span className="text-[11px] text-text-muted block">
                        Weight
                      </span>
                      <span className="text-sm sm:text-base font-bold text-text">
                        {latest.weight_kg ? `${latest.weight_kg} kg` : "—"}
                      </span>
                    </div>

                    <div className="bg-surface p-2.5 rounded border border-border">
                      <span className="text-[11px] text-text-muted block">
                        Height
                      </span>
                      <span className="text-sm sm:text-base font-bold text-text">
                        {latest.height_cm ? `${latest.height_cm} cm` : "—"}
                      </span>
                    </div>

                    <div className="bg-surface p-2.5 rounded border border-border">
                      <span className="text-[11px] text-text-muted block">
                        Estimated BMI
                      </span>
                      <span className="text-sm sm:text-base font-bold text-primary">
                        {latest.estimated_bmi !== null &&
                        latest.estimated_bmi !== undefined
                          ? latest.estimated_bmi
                          : "—"}
                      </span>
                      <span className="text-[10px] text-text-muted block">
                        Estimate
                      </span>
                    </div>

                    <div className="bg-surface p-2.5 rounded border border-border">
                      <span className="text-[11px] text-text-muted block">
                        Est. Body Fat %
                      </span>
                      <span className="text-sm sm:text-base font-bold text-primary">
                        {latest.estimated_body_fat_percentage !== null &&
                        latest.estimated_body_fat_percentage !== undefined
                          ? `${latest.estimated_body_fat_percentage}%`
                          : "—"}
                      </span>
                      <span className="text-[10px] text-text-muted block">
                        US Navy Method
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-text-muted text-center">
                    * BMI and US Navy body fat percentage are calculated on read
                    as labeled estimates.
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-surface-2/40 border border-border rounded-card text-center text-sm text-text-muted">
                  Not measured yet. A trainer records measurements.
                </div>
              )}

              {/* Record New Measurements Form */}
              <Card className="bg-surface border-border p-5 space-y-4">
                <div className="border-b border-border pb-2">
                  <h4 className="text-sm font-bold text-text uppercase tracking-wider">
                    Record New Measurements
                  </h4>
                  <p className="text-xs text-text-muted">
                    Enter physical measurements. Weight and height are required;
                    circumferences are optional for US Navy body fat estimation.
                  </p>
                </div>

                {formSuccess && <Alert variant="success">{formSuccess}</Alert>}
                {formError && <Alert variant="error">{formError}</Alert>}

                <form
                  onSubmit={handleRecordSubmit}
                  className="space-y-4"
                  noValidate
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <FormField
                      label="Weight (kg)"
                      htmlFor="metric-weight"
                      required
                      error={fieldErrors["metric-weight"]}
                    >
                      <Input
                        id="metric-weight"
                        type="number"
                        step="0.1"
                        inputMode="decimal"
                        required
                        placeholder="e.g. 75.0"
                        value={weightKg}
                        onChange={(e) => setWeightKg(e.target.value)}
                        error={fieldErrors["metric-weight"]}
                        className="min-h-[44px]"
                      />
                    </FormField>

                    <FormField
                      label="Height (cm)"
                      htmlFor="metric-height"
                      required
                      error={fieldErrors["metric-height"]}
                    >
                      <Input
                        id="metric-height"
                        type="number"
                        step="0.1"
                        inputMode="decimal"
                        required
                        placeholder="e.g. 180.0"
                        value={heightCm}
                        onChange={(e) => setHeightCm(e.target.value)}
                        error={fieldErrors["metric-height"]}
                        className="min-h-[44px]"
                      />
                    </FormField>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <FormField
                      label="Waist (cm)"
                      htmlFor="metric-waist"
                      error={fieldErrors["metric-waist"]}
                    >
                      <Input
                        id="metric-waist"
                        type="number"
                        step="0.1"
                        inputMode="decimal"
                        placeholder="e.g. 84.0"
                        value={waistCm}
                        onChange={(e) => setWaistCm(e.target.value)}
                        error={fieldErrors["metric-waist"]}
                        className="min-h-[44px]"
                      />
                    </FormField>

                    <FormField
                      label="Neck (cm)"
                      htmlFor="metric-neck"
                      error={fieldErrors["metric-neck"]}
                    >
                      <Input
                        id="metric-neck"
                        type="number"
                        step="0.1"
                        inputMode="decimal"
                        placeholder="e.g. 38.0"
                        value={neckCm}
                        onChange={(e) => setNeckCm(e.target.value)}
                        error={fieldErrors["metric-neck"]}
                        className="min-h-[44px]"
                      />
                    </FormField>

                    <FormField
                      label="Hip (cm)"
                      htmlFor="metric-hip"
                      error={fieldErrors["metric-hip"]}
                    >
                      <Input
                        id="metric-hip"
                        type="number"
                        step="0.1"
                        inputMode="decimal"
                        placeholder="e.g. 96.0"
                        value={hipCm}
                        onChange={(e) => setHipCm(e.target.value)}
                        error={fieldErrors["metric-hip"]}
                        className="min-h-[44px]"
                      />
                    </FormField>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button
                      type="submit"
                      disabled={submitting}
                      className="min-h-[44px]"
                    >
                      {submitting ? "Saving..." : "Record Measurements"}
                    </Button>
                  </div>
                </form>
              </Card>

              {/* Historical Measurements Table */}
              {hasHistory && (
                <Card className="bg-surface border-border p-4 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                    Measurement History ({metricsHistory.length})
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead className="border-b border-border text-text-muted">
                        <tr>
                          <th className="py-2 px-3">Date</th>
                          <th className="py-2 px-3">Trainer</th>
                          <th className="py-2 px-3">Weight</th>
                          <th className="py-2 px-3">Height</th>
                          <th className="py-2 px-3">Waist</th>
                          <th className="py-2 px-3">Neck</th>
                          <th className="py-2 px-3">Hip</th>
                          <th className="py-2 px-3">BMI (Est)</th>
                          <th className="py-2 px-3">Body Fat (Est)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {metricsHistory.map((m) => {
                          const circumferences =
                            (m.measurements as Record<string, number>) || {};
                          return (
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
                                {m.trainer_name ||
                                  m.recorded_by_name ||
                                  "Trainer"}
                              </td>
                              <td className="py-2 px-3 text-text">
                                {m.weight_kg ? `${m.weight_kg} kg` : "—"}
                              </td>
                              <td className="py-2 px-3 text-text">
                                {m.height_cm ? `${m.height_cm} cm` : "—"}
                              </td>
                              <td className="py-2 px-3 text-text">
                                {circumferences.waist_cm
                                  ? `${circumferences.waist_cm} cm`
                                  : "—"}
                              </td>
                              <td className="py-2 px-3 text-text">
                                {circumferences.neck_cm
                                  ? `${circumferences.neck_cm} cm`
                                  : "—"}
                              </td>
                              <td className="py-2 px-3 text-text">
                                {circumferences.hip_cm
                                  ? `${circumferences.hip_cm} cm`
                                  : "—"}
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
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
