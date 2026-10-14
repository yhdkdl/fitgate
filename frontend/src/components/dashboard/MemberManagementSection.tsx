import React, { useCallback, useEffect, useState } from "react";
import {
  getGymMemberDetail,
  listGymMembers,
  recordMemberMetrics,
  registerMemberStaffAssisted,
  type Member,
  type StaffMemberRegistrationPayload,
} from "../../api/members";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";

interface Props {
  userRole?: string;
  onMemberRegistered?: () => void;
}

export const MemberManagementSection: React.FC<Props> = ({
  userRole,
  onMemberRegistered,
}) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Registration modal state
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);
  const [regSuccess, setRegSuccess] = useState<string | null>(null);

  // Form fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");
  const [referralSource, setReferralSource] = useState("");
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  const [weightKg, setWeightKg] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [neckCm, setNeckCm] = useState("");
  const [waistCm, setWaistCm] = useState("");
  const [hipCm, setHipCm] = useState("");

  // Member detail modal
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [newWeight, setNewWeight] = useState("");
  const [newHeight, setNewHeight] = useState("");
  const [newNeck, setNewNeck] = useState("");
  const [newWaist, setNewWaist] = useState("");
  const [newHip, setNewHip] = useState("");
  const [metricsSubmitting, setMetricsSubmitting] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const canRegister =
    userRole === "owner" || userRole === "manager" || userRole === "reception";

  const fetchMembers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listGymMembers({
        search: search.trim() || undefined,
        status: statusFilter || undefined,
      });
      setMembers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load members.");
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);
    setRegSuccess(null);

    if (!waiverAccepted) {
      setRegError("Health waiver acceptance is required to register a member.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: StaffMemberRegistrationPayload = {
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        waiver_accepted: waiverAccepted,
        date_of_birth: dateOfBirth || null,
        gender: gender || "",
        emergency_contact: emergencyContact.trim(),
        referral_source: referralSource.trim(),
      };

      if (weightKg) payload.weight_kg = parseFloat(weightKg);
      if (heightCm) payload.height_cm = parseFloat(heightCm);

      const measurements: Record<string, number> = {};
      if (neckCm) measurements.neck_cm = parseFloat(neckCm);
      if (waistCm) measurements.waist_cm = parseFloat(waistCm);
      if (hipCm) measurements.hip_cm = parseFloat(hipCm);
      if (Object.keys(measurements).length > 0) {
        payload.measurements = measurements;
      }

      await registerMemberStaffAssisted(payload);
      setRegSuccess(
        `Member ${fullName.trim()} registered successfully. Set-password invite link emailed.`
      );
      // Reset form
      setFullName("");
      setEmail("");
      setPhone("");
      setDateOfBirth("");
      setGender("");
      setEmergencyContact("");
      setReferralSource("");
      setWaiverAccepted(false);
      setWeightKg("");
      setHeightCm("");
      setNeckCm("");
      setWaistCm("");
      setHipCm("");

      fetchMembers();
      onMemberRegistered?.();
    } catch (err: unknown) {
      setRegError(
        err instanceof Error
          ? err.message
          : "Failed to register member. Please check fields."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenDetail = async (memberId: string) => {
    setSelectedMember(null);
    try {
      const detail = await getGymMemberDetail(memberId);
      setSelectedMember(detail);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load member detail."
      );
    }
  };

  const handleAddMetrics = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMember) return;
    setMetricsSubmitting(true);
    setMetricsError(null);
    try {
      const measurements: Record<string, number> = {};
      if (newNeck) measurements.neck_cm = parseFloat(newNeck);
      if (newWaist) measurements.waist_cm = parseFloat(newWaist);
      if (newHip) measurements.hip_cm = parseFloat(newHip);

      await recordMemberMetrics(selectedMember.id, {
        weight_kg: newWeight ? parseFloat(newWeight) : null,
        height_cm: newHeight ? parseFloat(newHeight) : null,
        measurements:
          Object.keys(measurements).length > 0 ? measurements : undefined,
      });

      setMetricsError(null);
      // Refresh detail
      const updated = await getGymMemberDetail(selectedMember.id);
      setSelectedMember(updated);
      setNewWeight("");
      setNewHeight("");
      setNewNeck("");
      setNewWaist("");
      setNewHip("");
      fetchMembers();
    } catch (err: unknown) {
      setMetricsError(
        err instanceof Error ? err.message : "Failed to record metrics."
      );
    } finally {
      setMetricsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Title bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <h2 className="text-xl font-bold text-text">Members Directory</h2>
          <p className="text-xs text-text-muted">
            Manage enrolled members, track body composition estimates, and
            register new members.
          </p>
        </div>

        {canRegister && (
          <Button
            size="md"
            onClick={() => {
              setShowRegisterModal(true);
              setRegError(null);
              setRegSuccess(null);
            }}
            className="self-start sm:self-center min-h-[44px]"
          >
            + Register Member
          </Button>
        )}
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, phone, or email..."
            className="min-h-[44px]"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-surface-2 border border-border text-text rounded-input px-3 py-2 text-sm min-h-[44px] focus:outline-none focus:border-primary"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="expired">Expired</option>
          <option value="frozen">Frozen</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* Members Table */}
      <Card className="bg-surface border-border overflow-hidden">
        {loading ? (
          <div className="p-8 text-center flex flex-col items-center gap-3">
            <Spinner size="md" />
            <p className="text-xs text-text-muted">Loading members list...</p>
          </div>
        ) : members.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <p className="text-sm font-medium text-text">No members found.</p>
            <p className="text-xs text-text-muted">
              {canRegister
                ? "Click 'Register Member' to enroll your first gym member."
                : "No members match the filter criteria."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-2/60 border-b border-border text-xs uppercase text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">Member</th>
                  <th className="px-4 py-3 font-semibold">Phone</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Latest BMI</th>
                  <th className="px-4 py-3 font-semibold">Est. Body Fat</th>
                  <th className="px-4 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {members.map((m) => {
                  const bmi = m.latest_metrics?.estimated_bmi;
                  const bf = m.latest_metrics?.estimated_body_fat_percentage;
                  return (
                    <tr
                      key={m.id}
                      className="hover:bg-surface-2/40 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold text-text">
                          {m.full_name}
                        </div>
                        <div className="text-xs text-text-muted">{m.email}</div>
                      </td>
                      <td className="px-4 py-3 text-text font-mono text-xs">
                        {m.phone}
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={
                            m.status === "active"
                              ? "success"
                              : m.status === "frozen"
                                ? "warning"
                                : "secondary"
                          }
                        >
                          {m.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-text text-xs">
                        {bmi !== undefined && bmi !== null ? (
                          <span>
                            <strong className="font-semibold">{bmi}</strong>{" "}
                            <span className="text-text-muted">(est)</span>
                          </span>
                        ) : (
                          <span className="text-text-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-text text-xs">
                        {bf !== undefined && bf !== null ? (
                          <span>
                            <strong className="font-semibold">{bf}%</strong>{" "}
                            <span className="text-text-muted">(est)</span>
                          </span>
                        ) : (
                          <span className="text-text-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleOpenDetail(m.id)}
                          className="min-h-[36px]"
                        >
                          View Details
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Staff Registration Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 overflow-y-auto">
          <Card className="max-w-lg w-full bg-surface border-border p-6 space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <h3 className="text-lg font-bold text-text">
                Register New Member
              </h3>
              <button
                type="button"
                onClick={() => setShowRegisterModal(false)}
                className="text-text-muted hover:text-text text-xl p-1"
              >
                ✕
              </button>
            </div>

            {regError && <Alert variant="danger">{regError}</Alert>}
            {regSuccess && <Alert variant="success">{regSuccess}</Alert>}

            <form onSubmit={handleRegisterSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-text mb-1">
                  Full Name <span className="text-danger">*</span>
                </label>
                <Input
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Kenenisa Bekele"
                  className="min-h-[44px]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Email Address <span className="text-danger">*</span>
                  </label>
                  <Input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email@example.com"
                    className="min-h-[44px]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Phone <span className="text-danger">*</span>
                  </label>
                  <Input
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+251911223344"
                    className="min-h-[44px]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Date of Birth
                  </label>
                  <Input
                    type="date"
                    value={dateOfBirth}
                    onChange={(e) => setDateOfBirth(e.target.value)}
                    className="min-h-[44px]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Gender
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                    className="w-full bg-surface-2 border border-border text-text rounded-input px-3 py-2 text-sm min-h-[44px]"
                  >
                    <option value="">Select (optional)</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                    <option value="prefer_not_to_say">Prefer not to say</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Emergency Contact
                  </label>
                  <Input
                    value={emergencyContact}
                    onChange={(e) => setEmergencyContact(e.target.value)}
                    placeholder="Name and Phone"
                    className="min-h-[44px]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-text mb-1">
                    Referral Source
                  </label>
                  <Input
                    value={referralSource}
                    onChange={(e) => setReferralSource(e.target.value)}
                    placeholder="Walk-in, friend, etc."
                    className="min-h-[44px]"
                  />
                </div>
              </div>

              {/* Body metrics intake */}
              <div className="pt-2 border-t border-border space-y-2">
                <span className="text-xs font-semibold uppercase text-text-muted">
                  Initial Measurements (Optional)
                </span>
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    type="number"
                    step="0.1"
                    value={weightKg}
                    onChange={(e) => setWeightKg(e.target.value)}
                    placeholder="Weight (kg)"
                    className="min-h-[44px]"
                  />
                  <Input
                    type="number"
                    step="0.1"
                    value={heightCm}
                    onChange={(e) => setHeightCm(e.target.value)}
                    placeholder="Height (cm)"
                    className="min-h-[44px]"
                  />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Input
                    type="number"
                    step="0.1"
                    value={neckCm}
                    onChange={(e) => setNeckCm(e.target.value)}
                    placeholder="Neck (cm)"
                    className="min-h-[44px]"
                  />
                  <Input
                    type="number"
                    step="0.1"
                    value={waistCm}
                    onChange={(e) => setWaistCm(e.target.value)}
                    placeholder="Waist (cm)"
                    className="min-h-[44px]"
                  />
                  <Input
                    type="number"
                    step="0.1"
                    value={hipCm}
                    onChange={(e) => setHipCm(e.target.value)}
                    placeholder="Hip (cm)"
                    className="min-h-[44px]"
                  />
                </div>
              </div>

              {/* Health waiver checkbox */}
              <div className="p-3 bg-surface-2/60 border border-border rounded-lg">
                <label className="flex items-start gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    required
                    checked={waiverAccepted}
                    onChange={(e) => setWaiverAccepted(e.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-border text-primary"
                  />
                  <span className="text-xs text-text">
                    I confirm the member has reviewed and accepted the physical
                    activity health and liability waiver.{" "}
                    <span className="text-danger">*</span>
                  </span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowRegisterModal(false)}
                  className="min-h-[44px]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={submitting || !waiverAccepted}
                  className="min-h-[44px]"
                >
                  {submitting ? "Registering..." : "Confirm & Send Invite"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Member Detail & Metrics Modal */}
      {selectedMember && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 overflow-y-auto">
          <Card className="max-w-xl w-full bg-surface border-border p-6 space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <div>
                <h3 className="text-lg font-bold text-text">
                  {selectedMember.full_name}
                </h3>
                <p className="text-xs text-text-muted">
                  {selectedMember.email}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedMember(null)}
                className="text-text-muted hover:text-text text-xl p-1"
              >
                ✕
              </button>
            </div>

            {/* Member info grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs bg-surface-2/40 p-3 rounded-lg border border-border">
              <div>
                <span className="text-text-muted block">Phone</span>
                <span className="font-semibold text-text">
                  {selectedMember.phone}
                </span>
              </div>
              <div>
                <span className="text-text-muted block">Status</span>
                <Badge variant="primary">{selectedMember.status}</Badge>
              </div>
              <div>
                <span className="text-text-muted block">Gender</span>
                <span className="font-semibold text-text capitalize">
                  {selectedMember.gender || "Not specified"}
                </span>
              </div>
              <div>
                <span className="text-text-muted block">Emergency Contact</span>
                <span className="font-semibold text-text">
                  {selectedMember.emergency_contact || "None"}
                </span>
              </div>
              <div>
                <span className="text-text-muted block">Joined</span>
                <span className="font-semibold text-text">
                  {new Date(selectedMember.joined_at).toLocaleDateString()}
                </span>
              </div>
              <div>
                <span className="text-text-muted block">Waiver Accepted</span>
                <span className="font-semibold text-success">
                  ✓{" "}
                  {new Date(
                    selectedMember.waiver_accepted_at
                  ).toLocaleDateString()}
                </span>
              </div>
            </div>

            {/* Latest Calculated Estimates */}
            <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-primary">
                Current Body Composition Estimates
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="bg-surface p-2 rounded border border-border">
                  <span className="text-[11px] text-text-muted block">
                    Weight
                  </span>
                  <span className="text-sm font-bold text-text">
                    {selectedMember.latest_metrics?.weight_kg
                      ? `${selectedMember.latest_metrics.weight_kg} kg`
                      : "—"}
                  </span>
                </div>
                <div className="bg-surface p-2 rounded border border-border">
                  <span className="text-[11px] text-text-muted block">
                    Height
                  </span>
                  <span className="text-sm font-bold text-text">
                    {selectedMember.latest_metrics?.height_cm
                      ? `${selectedMember.latest_metrics.height_cm} cm`
                      : "—"}
                  </span>
                </div>
                <div className="bg-surface p-2 rounded border border-border">
                  <span className="text-[11px] text-text-muted block">
                    Estimated BMI
                  </span>
                  <span className="text-sm font-bold text-text">
                    {selectedMember.latest_metrics?.estimated_bmi !== null &&
                    selectedMember.latest_metrics?.estimated_bmi !== undefined
                      ? selectedMember.latest_metrics.estimated_bmi
                      : "—"}
                  </span>
                </div>
                <div className="bg-surface p-2 rounded border border-border">
                  <span className="text-[11px] text-text-muted block">
                    Est. Body Fat %
                  </span>
                  <span className="text-sm font-bold text-text">
                    {selectedMember.latest_metrics
                      ?.estimated_body_fat_percentage !== null &&
                    selectedMember.latest_metrics
                      ?.estimated_body_fat_percentage !== undefined
                      ? `${selectedMember.latest_metrics.estimated_body_fat_percentage}%`
                      : "—"}
                  </span>
                </div>
              </div>
              <p className="text-[11px] text-text-muted text-center pt-1">
                * BMI and US Navy body fat percentage are calculated on read as
                labeled estimates.
              </p>
            </div>

            {/* Record New Measurements */}
            <form
              onSubmit={handleAddMetrics}
              className="border-t border-border pt-3 space-y-3"
            >
              <h4 className="text-xs font-bold text-text uppercase">
                Record New Measurements
              </h4>
              {metricsError && <Alert variant="error">{metricsError}</Alert>}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                <Input
                  type="number"
                  step="0.1"
                  placeholder="Weight (kg)"
                  value={newWeight}
                  onChange={(e) => setNewWeight(e.target.value)}
                  className="min-h-[44px]"
                />
                <Input
                  type="number"
                  step="0.1"
                  placeholder="Height (cm)"
                  value={newHeight}
                  onChange={(e) => setNewHeight(e.target.value)}
                  className="min-h-[44px]"
                />
                <Input
                  type="number"
                  step="0.1"
                  placeholder="Neck (cm)"
                  value={newNeck}
                  onChange={(e) => setNewNeck(e.target.value)}
                  className="min-h-[44px]"
                />
                <Input
                  type="number"
                  step="0.1"
                  placeholder="Waist (cm)"
                  value={newWaist}
                  onChange={(e) => setNewWaist(e.target.value)}
                  className="min-h-[44px]"
                />
                <Input
                  type="number"
                  step="0.1"
                  placeholder="Hip (cm)"
                  value={newHip}
                  onChange={(e) => setNewHip(e.target.value)}
                  className="min-h-[44px]"
                />
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  type="submit"
                  size="sm"
                  disabled={metricsSubmitting}
                  className="min-h-[44px]"
                >
                  {metricsSubmitting ? "Saving..." : "Record Measurements"}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};
