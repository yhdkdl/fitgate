import React, { useCallback, useEffect, useState } from "react";
import {
  correctMemberMetrics,
  getMemberMetrics,
  listGymMembers,
  recordMemberMetrics,
  type BodyMetrics,
  type Member,
  type RecordMetricsPayload,
} from "../../api/members";
import { Alert } from "../ui/Alert";
import { FitnessProfileSection } from "./FitnessProfileSection";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";
import {
  focusFirstInvalidField,
  validateBicep,
  validateBodyFatPercentage,
  validateCalf,
  validateChest,
  validateHeight,
  validateHip,
  validateNeck,
  validateRestingHeartRate,
  validateThigh,
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
  const [chestCm, setChestCm] = useState("");
  const [bicepLeftCm, setBicepLeftCm] = useState("");
  const [bicepRightCm, setBicepRightCm] = useState("");
  const [thighLeftCm, setThighLeftCm] = useState("");
  const [thighRightCm, setThighRightCm] = useState("");
  const [calfLeftCm, setCalfLeftCm] = useState("");
  const [calfRightCm, setCalfRightCm] = useState("");
  const [restingHeartRate, setRestingHeartRate] = useState("");
  const [bodyFatPercentage, setBodyFatPercentage] = useState("");

  // Correction mode state
  const [isCorrectionMode, setIsCorrectionMode] = useState(false);
  const [correctingMetricId, setCorrectingMetricId] = useState<string | null>(
    null
  );
  const [activeTab, setActiveTab] = useState<
    "measurements" | "fitness_profile"
  >("measurements");

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

  const clearForm = () => {
    setWeightKg("");
    setHeightCm("");
    setWaistCm("");
    setNeckCm("");
    setHipCm("");
    setChestCm("");
    setBicepLeftCm("");
    setBicepRightCm("");
    setThighLeftCm("");
    setThighRightCm("");
    setCalfLeftCm("");
    setCalfRightCm("");
    setRestingHeartRate("");
    setBodyFatPercentage("");
    setFieldErrors({});
    setIsCorrectionMode(false);
    setCorrectingMetricId(null);
  };

  const handleSelectMember = async (member: Member) => {
    setSelectedMember(member);
    setMetricsLoading(true);
    setMetricsError(null);
    setFormSuccess(null);
    setFormError(null);
    clearForm();

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

  const startCorrection = (metric: BodyMetrics) => {
    setIsCorrectionMode(true);
    setCorrectingMetricId(metric.id || null);
    setFormSuccess(null);
    setFormError(null);
    setFieldErrors({});

    setWeightKg(metric.weight_kg ? String(metric.weight_kg) : "");
    setHeightCm(metric.height_cm ? String(metric.height_cm) : "");

    const meas = (metric.measurements as Record<string, unknown>) || {};
    setWaistCm(meas.waist_cm ? String(meas.waist_cm) : "");
    setNeckCm(meas.neck_cm ? String(meas.neck_cm) : "");
    setHipCm(meas.hip_cm ? String(meas.hip_cm) : "");
    setChestCm(meas.chest_cm ? String(meas.chest_cm) : "");
    setBicepLeftCm(meas.bicep_left_cm ? String(meas.bicep_left_cm) : "");
    setBicepRightCm(meas.bicep_right_cm ? String(meas.bicep_right_cm) : "");
    setThighLeftCm(meas.thigh_left_cm ? String(meas.thigh_left_cm) : "");
    setThighRightCm(meas.thigh_right_cm ? String(meas.thigh_right_cm) : "");
    setCalfLeftCm(meas.calf_left_cm ? String(meas.calf_left_cm) : "");
    setCalfRightCm(meas.calf_right_cm ? String(meas.calf_right_cm) : "");
    setRestingHeartRate(
      meas.resting_heart_rate !== undefined && meas.resting_heart_rate !== null
        ? String(meas.resting_heart_rate)
        : ""
    );
    setBodyFatPercentage(
      meas.body_fat_percentage !== undefined &&
        meas.body_fat_percentage !== null
        ? String(meas.body_fat_percentage)
        : ""
    );

    // Scroll to form
    const formElement = document.getElementById("measurement-entry-form");
    if (formElement) {
      formElement.scrollIntoView({ behavior: "smooth" });
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
    if (chestCm.trim()) {
      const cErr = validateChest(chestCm);
      if (cErr) errors["metric-chest"] = cErr;
    }
    if (bicepLeftCm.trim()) {
      const bErr = validateBicep(bicepLeftCm);
      if (bErr) errors["metric-bicep-left"] = bErr;
    }
    if (bicepRightCm.trim()) {
      const bErr = validateBicep(bicepRightCm);
      if (bErr) errors["metric-bicep-right"] = bErr;
    }
    if (thighLeftCm.trim()) {
      const tErr = validateThigh(thighLeftCm);
      if (tErr) errors["metric-thigh-left"] = tErr;
    }
    if (thighRightCm.trim()) {
      const tErr = validateThigh(thighRightCm);
      if (tErr) errors["metric-thigh-right"] = tErr;
    }
    if (calfLeftCm.trim()) {
      const clErr = validateCalf(calfLeftCm);
      if (clErr) errors["metric-calf-left"] = clErr;
    }
    if (calfRightCm.trim()) {
      const crErr = validateCalf(calfRightCm);
      if (crErr) errors["metric-calf-right"] = crErr;
    }
    if (restingHeartRate.trim()) {
      const rhrErr = validateRestingHeartRate(restingHeartRate);
      if (rhrErr) errors["metric-rhr"] = rhrErr;
    }
    if (bodyFatPercentage.trim()) {
      const bfErr = validateBodyFatPercentage(bodyFatPercentage);
      if (bfErr) errors["metric-body-fat"] = bfErr;
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
      if (chestCm.trim()) measurements.chest_cm = parseFloat(chestCm);
      if (bicepLeftCm.trim())
        measurements.bicep_left_cm = parseFloat(bicepLeftCm);
      if (bicepRightCm.trim())
        measurements.bicep_right_cm = parseFloat(bicepRightCm);
      if (thighLeftCm.trim())
        measurements.thigh_left_cm = parseFloat(thighLeftCm);
      if (thighRightCm.trim())
        measurements.thigh_right_cm = parseFloat(thighRightCm);
      if (calfLeftCm.trim()) measurements.calf_left_cm = parseFloat(calfLeftCm);
      if (calfRightCm.trim())
        measurements.calf_right_cm = parseFloat(calfRightCm);
      if (restingHeartRate.trim())
        measurements.resting_heart_rate = parseInt(restingHeartRate, 10);
      if (bodyFatPercentage.trim())
        measurements.body_fat_percentage = parseFloat(bodyFatPercentage);

      const payload: RecordMetricsPayload = {
        weight_kg: parseFloat(weightKg),
        height_cm: parseFloat(heightCm),
        waist_cm: waistCm.trim() ? parseFloat(waistCm) : undefined,
        neck_cm: neckCm.trim() ? parseFloat(neckCm) : undefined,
        hip_cm: hipCm.trim() ? parseFloat(hipCm) : undefined,
        chest_cm: chestCm.trim() ? parseFloat(chestCm) : undefined,
        bicep_left_cm: bicepLeftCm.trim() ? parseFloat(bicepLeftCm) : undefined,
        bicep_right_cm: bicepRightCm.trim()
          ? parseFloat(bicepRightCm)
          : undefined,
        thigh_left_cm: thighLeftCm.trim() ? parseFloat(thighLeftCm) : undefined,
        thigh_right_cm: thighRightCm.trim()
          ? parseFloat(thighRightCm)
          : undefined,
        calf_left_cm: calfLeftCm.trim() ? parseFloat(calfLeftCm) : undefined,
        calf_right_cm: calfRightCm.trim() ? parseFloat(calfRightCm) : undefined,
        resting_heart_rate: restingHeartRate.trim()
          ? parseInt(restingHeartRate, 10)
          : undefined,
        body_fat_percentage: bodyFatPercentage.trim()
          ? parseFloat(bodyFatPercentage)
          : undefined,
        measurements:
          Object.keys(measurements).length > 0 ? measurements : undefined,
      };

      if (isCorrectionMode && correctingMetricId) {
        payload.metric_id = correctingMetricId;
        await correctMemberMetrics(selectedMember.id, payload);
        setFormSuccess(
          `Latest measurement entry for ${selectedMember.full_name} successfully corrected.`
        );
      } else {
        await recordMemberMetrics(selectedMember.id, payload);
        setFormSuccess(
          `Body measurements successfully recorded for ${selectedMember.full_name}.`
        );
      }

      clearForm();

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
  const latestMeas = (latest?.measurements as Record<string, unknown>) || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-border pb-3">
        <h2 className="text-xl font-bold text-text">Member Measurements</h2>
        <p className="text-xs text-text-muted">
          Accurately measure and record member body composition for your
          assigned clients.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Assigned Member Search and List */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="bg-surface border-border p-4 space-y-3">
            <h3 className="text-sm font-bold text-text uppercase tracking-wider">
              My Assigned Clients
            </h3>

            <form onSubmit={handleSearchSubmit} className="flex gap-2">
              <Input
                type="text"
                placeholder="Search assigned clients..."
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
                    Loading clients...
                  </p>
                </div>
              ) : members.length === 0 ? (
                <p className="text-xs text-text-muted text-center py-4">
                  No assigned clients found matching your search.
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
                      <div className="flex items-center gap-3">
                        {m.photo_url ? (
                          <AuthenticatedImage
                            src={m.photo_url}
                            alt={m.full_name}
                            className="w-9 h-9 rounded-full object-cover border border-border shrink-0"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-xs border border-border shrink-0">
                            {m.full_name.slice(0, 2).toUpperCase()}
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-sm truncate">
                              {m.full_name}
                            </span>
                            {m.status && (
                              <Badge
                                variant={
                                  m.status === "active"
                                    ? "success"
                                    : "secondary"
                                }
                              >
                                {m.status}
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-text-muted truncate mt-0.5">
                            {m.phone}
                          </div>
                        </div>
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
                No Client Selected
              </h3>
              <p className="text-xs text-text-muted max-w-sm mx-auto">
                Select an assigned client from the list on the left to view
                their measurement history and record new body composition
                metrics.
              </p>
            </Card>
          ) : (
            <div className="space-y-4">
              {/* Member banner with photo (Item K: Trainer sees member profile photo) */}
              <div className="bg-surface-2/60 border border-border rounded-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {selectedMember.photo_url ? (
                    <AuthenticatedImage
                      src={selectedMember.photo_url}
                      alt={selectedMember.full_name}
                      className="w-12 h-12 rounded-full object-cover border border-border"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-sm border border-border">
                      {selectedMember.full_name.slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div>
                    <h3 className="text-base font-bold text-text">
                      {selectedMember.full_name}
                    </h3>
                    <p className="text-xs text-text-muted">
                      {selectedMember.email} · {selectedMember.phone}
                    </p>
                  </div>
                </div>
                <Badge variant="primary">Assigned Client</Badge>
              </div>

              {/* Tabs for Measurements vs Fitness Profile */}
              <div className="flex border-b border-border gap-2">
                <button
                  type="button"
                  data-testid="tab-measurements"
                  onClick={() => setActiveTab("measurements")}
                  className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
                    activeTab === "measurements"
                      ? "border-primary text-primary"
                      : "border-transparent text-text-muted hover:text-text"
                  }`}
                >
                  Measurements & Body Composition
                </button>
                <button
                  type="button"
                  data-testid="tab-fitness-profile"
                  onClick={() => setActiveTab("fitness_profile")}
                  className={`px-4 py-2 text-sm font-semibold border-b-2 transition-colors ${
                    activeTab === "fitness_profile"
                      ? "border-primary text-primary"
                      : "border-transparent text-text-muted hover:text-text"
                  }`}
                >
                  Fitness Profile
                </button>
              </div>

              {activeTab === "fitness_profile" ? (
                <FitnessProfileSection
                  memberId={selectedMember.id}
                  memberName={selectedMember.full_name}
                />
              ) : (
                <>
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
                          Current Body Composition & Derived Metrics
                        </h4>
                        {(latest.trainer_name || latest.recorded_by_name) && (
                          <span className="text-xs text-text-muted">
                            Recorded by:{" "}
                            <strong className="text-text">
                              {latest.trainer_name || latest.recorded_by_name}
                            </strong>
                            {latest.recorded_at && (
                              <>
                                {" "}
                                on{" "}
                                {new Date(
                                  latest.recorded_at
                                ).toLocaleDateString()}
                              </>
                            )}
                            {latest.is_corrected && (
                              <Badge variant="warning" className="ml-2">
                                Corrected
                              </Badge>
                            )}
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-center">
                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            Weight
                          </span>
                          <span className="text-sm font-bold text-text">
                            {latest.weight_kg ? `${latest.weight_kg} kg` : "—"}
                          </span>
                        </div>

                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            Height
                          </span>
                          <span className="text-sm font-bold text-text">
                            {latest.height_cm ? `${latest.height_cm} cm` : "—"}
                          </span>
                        </div>

                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            BMI
                          </span>
                          <span className="text-sm font-bold text-primary">
                            {latest.estimated_bmi !== null &&
                            latest.estimated_bmi !== undefined
                              ? latest.estimated_bmi
                              : "—"}
                          </span>
                          <span className="text-[9px] text-text-muted block">
                            Estimate
                          </span>
                        </div>

                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            Body Fat
                          </span>
                          <span className="text-sm font-bold text-primary">
                            {latestMeas.body_fat_percentage !== undefined &&
                            latestMeas.body_fat_percentage !== null
                              ? `${latestMeas.body_fat_percentage}%`
                              : latest.estimated_body_fat_percentage !== null &&
                                  latest.estimated_body_fat_percentage !==
                                    undefined
                                ? `${latest.estimated_body_fat_percentage}%`
                                : "—"}
                          </span>
                          <span className="text-[9px] text-text-muted block">
                            {latestMeas.body_fat_percentage !== undefined &&
                            latestMeas.body_fat_percentage !== null
                              ? "Measured"
                              : "Estimate"}
                          </span>
                        </div>

                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            Waist/Hip
                          </span>
                          <span className="text-sm font-bold text-text">
                            {latest.waist_to_hip_ratio ?? "—"}
                          </span>
                          <span className="text-[9px] text-text-muted block">
                            Ratio
                          </span>
                        </div>

                        <div className="bg-surface p-2 rounded border border-border">
                          <span className="text-[10px] text-text-muted block">
                            Lean Mass
                          </span>
                          <span className="text-sm font-bold text-text">
                            {latest.lean_body_mass
                              ? `${latest.lean_body_mass} kg`
                              : "—"}
                          </span>
                          <span className="text-[9px] text-text-muted block">
                            {latest.lean_body_mass_label || "—"}
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-4 bg-surface-2/40 border border-border rounded-card text-center text-sm text-text-muted">
                      Not measured yet. Record physical measurements below.
                    </div>
                  )}

                  {/* Record / Correct Measurements Form */}
                  <Card
                    id="measurement-entry-form"
                    className="bg-surface border-border p-5 space-y-4"
                  >
                    <div className="border-b border-border pb-2 flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-text uppercase tracking-wider">
                          {isCorrectionMode
                            ? "Correct Latest Measurement Entry"
                            : "Record New Measurements"}
                        </h4>
                        <p className="text-xs text-text-muted mt-0.5">
                          {isCorrectionMode
                            ? "Correcting values will update the latest entry and mark it corrected in history."
                            : "Weight and height are required; all circumference and vital fields are optional."}
                        </p>
                      </div>
                      {isCorrectionMode && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={clearForm}
                        >
                          Cancel correction
                        </Button>
                      )}
                    </div>

                    {formSuccess && (
                      <Alert variant="success">{formSuccess}</Alert>
                    )}
                    {formError && <Alert variant="error">{formError}</Alert>}

                    <form
                      onSubmit={handleRecordSubmit}
                      className="space-y-4"
                      noValidate
                    >
                      {/* Required primary fields */}
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
                            placeholder="e.g. 75.0 (20 to 400 kg)"
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
                            placeholder="e.g. 180.0 (50 to 260 cm)"
                            value={heightCm}
                            onChange={(e) => setHeightCm(e.target.value)}
                            error={fieldErrors["metric-height"]}
                            className="min-h-[44px]"
                          />
                        </FormField>
                      </div>

                      {/* Core Circumferences */}
                      <div>
                        <h5 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                          Circumferences (cm) - Optional
                        </h5>
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
                              placeholder="e.g. 84.0 (40 to 200 cm)"
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
                              placeholder="e.g. 38.0 (20 to 80 cm)"
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
                              placeholder="40 to 220"
                              value={hipCm}
                              onChange={(e) => setHipCm(e.target.value)}
                              error={fieldErrors["metric-hip"]}
                              className="min-h-[44px]"
                            />
                          </FormField>
                        </div>
                      </div>

                      {/* Additional Limbs & Torso (Item K) */}
                      <div>
                        <h5 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                          Extended Body Measurements (cm) - Optional
                        </h5>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                          <FormField
                            label="Chest (cm)"
                            htmlFor="metric-chest"
                            error={fieldErrors["metric-chest"]}
                          >
                            <Input
                              id="metric-chest"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="50 to 200"
                              value={chestCm}
                              onChange={(e) => setChestCm(e.target.value)}
                              error={fieldErrors["metric-chest"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Left Bicep (cm)"
                            htmlFor="metric-bicep-left"
                            error={fieldErrors["metric-bicep-left"]}
                          >
                            <Input
                              id="metric-bicep-left"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="15 to 80"
                              value={bicepLeftCm}
                              onChange={(e) => setBicepLeftCm(e.target.value)}
                              error={fieldErrors["metric-bicep-left"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Right Bicep (cm)"
                            htmlFor="metric-bicep-right"
                            error={fieldErrors["metric-bicep-right"]}
                          >
                            <Input
                              id="metric-bicep-right"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="15 to 80"
                              value={bicepRightCm}
                              onChange={(e) => setBicepRightCm(e.target.value)}
                              error={fieldErrors["metric-bicep-right"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Left Thigh (cm)"
                            htmlFor="metric-thigh-left"
                            error={fieldErrors["metric-thigh-left"]}
                          >
                            <Input
                              id="metric-thigh-left"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="30 to 120"
                              value={thighLeftCm}
                              onChange={(e) => setThighLeftCm(e.target.value)}
                              error={fieldErrors["metric-thigh-left"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Right Thigh (cm)"
                            htmlFor="metric-thigh-right"
                            error={fieldErrors["metric-thigh-right"]}
                          >
                            <Input
                              id="metric-thigh-right"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="30 to 120"
                              value={thighRightCm}
                              onChange={(e) => setThighRightCm(e.target.value)}
                              error={fieldErrors["metric-thigh-right"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Left Calf (cm)"
                            htmlFor="metric-calf-left"
                            error={fieldErrors["metric-calf-left"]}
                          >
                            <Input
                              id="metric-calf-left"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="20 to 80"
                              value={calfLeftCm}
                              onChange={(e) => setCalfLeftCm(e.target.value)}
                              error={fieldErrors["metric-calf-left"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Right Calf (cm)"
                            htmlFor="metric-calf-right"
                            error={fieldErrors["metric-calf-right"]}
                          >
                            <Input
                              id="metric-calf-right"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="20 to 80"
                              value={calfRightCm}
                              onChange={(e) => setCalfRightCm(e.target.value)}
                              error={fieldErrors["metric-calf-right"]}
                              className="min-h-[44px]"
                            />
                          </FormField>
                        </div>
                      </div>

                      {/* Vitals & Body Fat (Item K) */}
                      <div>
                        <h5 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">
                          Vitals & Body Composition - Optional
                        </h5>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <FormField
                            label="Resting Heart Rate (bpm)"
                            htmlFor="metric-rhr"
                            error={fieldErrors["metric-rhr"]}
                          >
                            <Input
                              id="metric-rhr"
                              type="number"
                              step="1"
                              inputMode="numeric"
                              placeholder="30 to 220 (whole number)"
                              value={restingHeartRate}
                              onChange={(e) =>
                                setRestingHeartRate(e.target.value)
                              }
                              error={fieldErrors["metric-rhr"]}
                              className="min-h-[44px]"
                            />
                          </FormField>

                          <FormField
                            label="Trainer-measured Body Fat %"
                            htmlFor="metric-body-fat"
                            error={fieldErrors["metric-body-fat"]}
                          >
                            <Input
                              id="metric-body-fat"
                              type="number"
                              step="0.1"
                              inputMode="decimal"
                              placeholder="2 to 70 % (caliper or BIA)"
                              value={bodyFatPercentage}
                              onChange={(e) =>
                                setBodyFatPercentage(e.target.value)
                              }
                              error={fieldErrors["metric-body-fat"]}
                              className="min-h-[44px]"
                            />
                          </FormField>
                        </div>
                      </div>

                      <div className="pt-2">
                        <Button
                          type="submit"
                          variant="primary"
                          size="md"
                          disabled={submitting}
                          className="w-full sm:w-auto min-h-[44px]"
                        >
                          {submitting
                            ? "Saving..."
                            : isCorrectionMode
                              ? "Save Correction"
                              : "Record Measurements"}
                        </Button>
                      </div>
                    </form>
                  </Card>

                  {/* Measurement History Table */}
                  {hasHistory && (
                    <Card className="bg-surface border-border p-5 space-y-3">
                      <h4 className="text-sm font-bold text-text uppercase tracking-wider">
                        Measurement History ({metricsHistory.length})
                      </h4>

                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left border-collapse">
                          <thead className="border-b border-border text-text-muted">
                            <tr>
                              <th className="py-2.5 px-3 font-semibold">
                                Date
                              </th>
                              <th className="py-2.5 px-3 font-semibold">
                                Trainer
                              </th>
                              <th className="py-2.5 px-3 font-semibold">
                                Weight
                              </th>
                              <th className="py-2.5 px-3 font-semibold">
                                Height
                              </th>
                              <th className="py-2.5 px-3 font-semibold">BMI</th>
                              <th className="py-2.5 px-3 font-semibold">
                                Body Fat
                              </th>
                              <th className="py-2.5 px-3 font-semibold">
                                Waist/Hip
                              </th>
                              <th className="py-2.5 px-3 font-semibold">
                                Status
                              </th>
                              <th className="py-2.5 px-3 font-semibold text-right">
                                Action
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/60">
                            {metricsHistory.map((m, idx) => {
                              const meas =
                                (m.measurements as Record<string, unknown>) ||
                                {};
                              const isLatest = idx === 0;

                              return (
                                <tr
                                  key={m.id || m.recorded_at}
                                  className="hover:bg-surface-2/40"
                                >
                                  <td className="py-2.5 px-3 text-text">
                                    {m.recorded_at
                                      ? new Date(
                                          m.recorded_at
                                        ).toLocaleDateString()
                                      : "—"}
                                  </td>
                                  <td className="py-2.5 px-3 font-medium text-text">
                                    {m.trainer_name ||
                                      m.recorded_by_name ||
                                      "Trainer"}
                                  </td>
                                  <td className="py-2.5 px-3 text-text">
                                    {m.weight_kg ? `${m.weight_kg} kg` : "—"}
                                  </td>
                                  <td className="py-2.5 px-3 text-text">
                                    {m.height_cm ? `${m.height_cm} cm` : "—"}
                                  </td>
                                  <td className="py-2.5 px-3 font-semibold text-primary">
                                    {m.estimated_bmi ?? "—"}
                                  </td>
                                  <td className="py-2.5 px-3 font-semibold text-primary">
                                    {meas.body_fat_percentage !== undefined &&
                                    meas.body_fat_percentage !== null
                                      ? `${meas.body_fat_percentage}%`
                                      : m.estimated_body_fat_percentage
                                        ? `${m.estimated_body_fat_percentage}%`
                                        : "—"}
                                  </td>
                                  <td className="py-2.5 px-3 text-text">
                                    {m.waist_to_hip_ratio ?? "—"}
                                  </td>
                                  <td className="py-2.5 px-3">
                                    {m.is_corrected ? (
                                      <Badge variant="warning">Corrected</Badge>
                                    ) : (
                                      <Badge variant="neutral">Recorded</Badge>
                                    )}
                                  </td>
                                  <td className="py-2.5 px-3 text-right">
                                    {isLatest ? (
                                      <button
                                        type="button"
                                        onClick={() => startCorrection(m)}
                                        className="text-xs text-primary font-semibold hover:underline"
                                      >
                                        Correct
                                      </button>
                                    ) : (
                                      <span className="text-text-muted text-[10px]">
                                        Locked
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </Card>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
