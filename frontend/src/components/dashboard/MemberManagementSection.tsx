import React, { useCallback, useEffect, useState } from "react";
import {
  getGymMemberDetail,
  listGymMembers,
  reactivateMember,
  registerMemberStaffAssisted,
  suspendMember,
  uploadMemberPhoto,
  type Member,
  type StaffMemberRegistrationPayload,
} from "../../api/members";
import { AuthenticatedImage } from "../ui/AuthenticatedImage";
import { useOptionalAuth } from "../../context/AuthContext";
import { Alert } from "../ui/Alert";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FormField } from "../ui/FormField";
import { Input } from "../ui/Input";
import { Spinner } from "../ui/Spinner";
import {
  filterPhoneInput,
  focusFirstInvalidField,
  validateDateOfBirth,
  validateEmail,
  validateName,
  validatePhone,
  validateTextLength,
} from "../../utils/validators";

interface Props {
  userRole?: string;
  gymId?: string;
  onMemberRegistered?: () => void;
}

export const MemberManagementSection: React.FC<Props> = ({
  userRole,
  gymId,
  onMemberRegistered,
}) => {
  const auth = useOptionalAuth();
  const user = auth?.user;
  const activeGymId = gymId || user?.gym_id;
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
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Registration photo state
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  // Form fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [emergencyContact, setEmergencyContact] = useState("");
  const [referralSource, setReferralSource] = useState("");
  const [waiverAccepted, setWaiverAccepted] = useState(false);

  // Member detail modal
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [changingPhoto, setChangingPhoto] = useState(false);
  const [detailPhotoError, setDetailPhotoError] = useState<string | null>(null);
  const [detailPhotoSuccess, setDetailPhotoSuccess] = useState<string | null>(null);

  // Status action state
  const [suspendReason, setSuspendReason] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

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

  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    const ext = file.name.split(".").pop()?.toLowerCase();
    const isAllowedExt =
      ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp";

    if (!allowedTypes.includes(file.type.toLowerCase()) && !isAllowedExt) {
      setFieldErrors((prev) => ({
        ...prev,
        "reg-photo":
          "Unsupported image format. Only JPEG, PNG, and WebP are allowed.",
      }));
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setFieldErrors((prev) => ({
        ...prev,
        "reg-photo": "File size exceeds maximum allowed 2 MB limit.",
      }));
      return;
    }

    setFieldErrors((prev) => {
      const copy = { ...prev };
      delete copy["reg-photo"];
      return copy;
    });

    setPhotoFile(file);
    if (photoPreview) {
      URL.revokeObjectURL(photoPreview);
    }
    setPhotoPreview(URL.createObjectURL(file));
  };

  const handleRemovePhoto = () => {
    if (photoPreview) {
      URL.revokeObjectURL(photoPreview);
    }
    setPhotoFile(null);
    setPhotoPreview(null);
    setFieldErrors((prev) => {
      const copy = { ...prev };
      delete copy["reg-photo"];
      return copy;
    });
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);
    setRegSuccess(null);
    setFieldErrors({});

    const errors: Record<string, string> = {};

    if (photoFile) {
      const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
      const ext = photoFile.name.split(".").pop()?.toLowerCase();
      const isAllowedExt =
        ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp";
      if (!allowedTypes.includes(photoFile.type.toLowerCase()) && !isAllowedExt) {
        errors["reg-photo"] =
          "Unsupported image format. Only JPEG, PNG, and WebP are allowed.";
      } else if (photoFile.size > 2 * 1024 * 1024) {
        errors["reg-photo"] = "File size exceeds maximum allowed 2 MB limit.";
      }
    }

    const nameErr = validateName(fullName, "Full name", 2, 100);
    if (nameErr) errors["reg-full-name"] = nameErr;

    const emailErr = validateEmail(email, true);
    if (emailErr) errors["reg-email"] = emailErr;

    const phoneErr = validatePhone(phone, true);
    if (phoneErr) errors["reg-phone"] = phoneErr;

    if (dateOfBirth) {
      const dobErr = validateDateOfBirth(dateOfBirth);
      if (dobErr) errors["reg-dob"] = dobErr;
    }

    if (emergencyContact.trim()) {
      const ecErr = validateTextLength(
        emergencyContact,
        "Emergency contact",
        2,
        100
      );
      if (ecErr) errors["reg-emergency"] = ecErr;
    }

    if (referralSource.trim()) {
      const refErr = validateTextLength(
        referralSource,
        "Referral source",
        2,
        100
      );
      if (refErr) errors["reg-referral"] = refErr;
    }

    if (!waiverAccepted) {
      errors["reg-waiver"] =
        "Health waiver acceptance is required to register a member.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setSubmitting(true);
    try {
      let uploadedPhotoUrl: string | undefined = undefined;
      const gymId = activeGymId;
      if (photoFile) {
        if (!gymId) {
          const msg = "Active gym could not be determined. Member photo was not saved.";
          setRegError(msg);
          setFieldErrors((prev) => ({ ...prev, "reg-photo": msg }));
          setSubmitting(false);
          return;
        }
        try {
          const res = await uploadMemberPhoto(photoFile, gymId);
          if (!res || !res.url) {
            throw new Error("Photo upload did not return a valid file path. Photo was not saved.");
          }
          uploadedPhotoUrl = res.url;
        } catch (uploadErr: unknown) {
          const msg =
            uploadErr instanceof Error
              ? uploadErr.message
              : "Failed to upload member photo. Photo was not saved. Please ensure it is a valid image under 2MB.";
          setRegError(msg);
          setFieldErrors((prev) => ({ ...prev, "reg-photo": msg }));
          setSubmitting(false);
          return;
        }
      }

      const payload: StaffMemberRegistrationPayload = {
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        waiver_accepted: waiverAccepted,
        date_of_birth: dateOfBirth || null,
        gender: gender || "",
        emergency_contact: emergencyContact.trim(),
        referral_source: referralSource.trim(),
        photo_url: uploadedPhotoUrl,
      };

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
      handleRemovePhoto();
      setFieldErrors({});

      fetchMembers();
      onMemberRegistered?.();
    } catch (err: unknown) {
      const errData = (err as { data?: Record<string, unknown> })?.data;
      if (errData && typeof errData === "object") {
        const serverFieldErrors: Record<string, string> = {};
        if ("full_name" in errData)
          serverFieldErrors["reg-full-name"] = Array.isArray(errData.full_name)
            ? errData.full_name.join(" ")
            : String(errData.full_name);
        if ("email" in errData)
          serverFieldErrors["reg-email"] = Array.isArray(errData.email)
            ? errData.email.join(" ")
            : String(errData.email);
        if ("phone" in errData)
          serverFieldErrors["reg-phone"] = Array.isArray(errData.phone)
            ? errData.phone.join(" ")
            : String(errData.phone);
        if ("date_of_birth" in errData)
          serverFieldErrors["reg-dob"] = Array.isArray(errData.date_of_birth)
            ? errData.date_of_birth.join(" ")
            : String(errData.date_of_birth);
        if ("photo" in errData || "photo_url" in errData) {
          const val = (errData.photo || errData.photo_url) as unknown;
          serverFieldErrors["reg-photo"] = Array.isArray(val)
            ? val.join(" ")
            : String(val);
        }
        if (Object.keys(serverFieldErrors).length > 0) {
          setFieldErrors(serverFieldErrors);
          focusFirstInvalidField(serverFieldErrors);
        }
      }
      setRegError(
        err instanceof Error
          ? err.message
          : "Failed to register member. Please check fields."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDetailPhotoChange = async (
    e: React.ChangeEvent<HTMLInputElement>,
    memberId: string
  ) => {
    const file = e.target.files?.[0];
    const gymId = activeGymId;
    if (!file || !gymId) return;

    setDetailPhotoError(null);
    setDetailPhotoSuccess(null);

    const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
    const ext = file.name.split(".").pop()?.toLowerCase();
    const isAllowedExt =
      ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "webp";

    if (!allowedTypes.includes(file.type.toLowerCase()) && !isAllowedExt) {
      setDetailPhotoError(
        "Unsupported format. Only JPEG, PNG, and WebP are allowed."
      );
      return;
    }

    if (file.size > 2 * 1024 * 1024) {
      setDetailPhotoError("File size exceeds maximum allowed 2 MB limit.");
      return;
    }

    try {
      setChangingPhoto(true);
      const res = await uploadMemberPhoto(file, gymId, memberId);
      setSelectedMember((prev) =>
        prev ? { ...prev, photo_url: res.url } : null
      );
      setDetailPhotoSuccess("Member photo updated successfully.");
      fetchMembers();
    } catch (err: unknown) {
      setDetailPhotoError(
        err instanceof Error ? err.message : "Failed to update member photo."
      );
    } finally {
      setChangingPhoto(false);
    }
  };

  const handleOpenDetail = async (memberId: string) => {
    setSelectedMember(null);
    setActionError(null);
    setActionSuccess(null);
    setSuspendReason("");
    try {
      const detail = await getGymMemberDetail(memberId);
      setSelectedMember(detail);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load member detail."
      );
    }
  };

  const handleSuspend = async () => {
    if (!selectedMember || !suspendReason.trim()) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await suspendMember(selectedMember.id, suspendReason.trim());
      setSelectedMember(res.member);
      setActionSuccess("Member suspended successfully.");
      setSuspendReason("");
      fetchMembers();
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to suspend member."
      );
    } finally {
      setActionLoading(false);
    }
  };

  const handleReactivate = async () => {
    if (!selectedMember) return;
    setActionLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await reactivateMember(selectedMember.id);
      setSelectedMember(res.member);
      setActionSuccess("Member reactivated successfully.");
      fetchMembers();
    } catch (err: unknown) {
      setActionError(
        err instanceof Error ? err.message : "Failed to reactivate member."
      );
    } finally {
      setActionLoading(false);
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
            maxLength={100}
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
          <option value="pending">Pending</option>
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
                  {userRole !== "reception" && (
                    <>
                      <th className="px-4 py-3 font-semibold">Latest BMI</th>
                      <th className="px-4 py-3 font-semibold">Est. Body Fat</th>
                    </>
                  )}
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
                                : m.status === "suspended"
                                  ? "danger"
                                  : "secondary"
                          }
                        >
                          {m.status}
                        </Badge>
                      </td>
                      {userRole !== "reception" && (
                        <>
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
                        </>
                      )}
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

            <form onSubmit={handleRegisterSubmit} className="space-y-3" noValidate>
              <FormField
                label="Full Name"
                htmlFor="reg-full-name"
                required
                error={fieldErrors["reg-full-name"]}
              >
                <Input
                  id="reg-full-name"
                  required
                  maxLength={100}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Kenenisa Bekele"
                  error={fieldErrors["reg-full-name"]}
                  className="min-h-[44px]"
                />
              </FormField>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <FormField
                  label="Email Address"
                  htmlFor="reg-email"
                  required
                  error={fieldErrors["reg-email"]}
                >
                  <Input
                    id="reg-email"
                    type="email"
                    required
                    maxLength={254}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email@example.com"
                    error={fieldErrors["reg-email"]}
                    className="min-h-[44px]"
                  />
                </FormField>

                <FormField
                  label="Phone"
                  htmlFor="reg-phone"
                  required
                  error={fieldErrors["reg-phone"]}
                >
                  <Input
                    id="reg-phone"
                    type="tel"
                    inputMode="tel"
                    required
                    maxLength={20}
                    value={phone}
                    onChange={(e) => setPhone(filterPhoneInput(e.target.value))}
                    placeholder="+251911223344"
                    error={fieldErrors["reg-phone"]}
                    className="min-h-[44px]"
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <FormField
                  label="Date of Birth"
                  htmlFor="reg-dob"
                  error={fieldErrors["reg-dob"]}
                >
                  <Input
                    id="reg-dob"
                    type="date"
                    value={dateOfBirth}
                    onChange={(e) => setDateOfBirth(e.target.value)}
                    error={fieldErrors["reg-dob"]}
                    className="min-h-[44px]"
                  />
                </FormField>

                <FormField label="Gender" htmlFor="reg-gender">
                  <select
                    id="reg-gender"
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
                </FormField>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <FormField
                  label="Emergency Contact"
                  htmlFor="reg-emergency"
                  error={fieldErrors["reg-emergency"]}
                >
                  <Input
                    id="reg-emergency"
                    maxLength={100}
                    value={emergencyContact}
                    onChange={(e) => setEmergencyContact(e.target.value)}
                    placeholder="Name and Phone"
                    error={fieldErrors["reg-emergency"]}
                    className="min-h-[44px]"
                  />
                </FormField>

                <FormField
                  label="Referral Source"
                  htmlFor="reg-referral"
                  error={fieldErrors["reg-referral"]}
                >
                  <Input
                    id="reg-referral"
                    maxLength={100}
                    value={referralSource}
                    onChange={(e) => setReferralSource(e.target.value)}
                    placeholder="Walk-in, friend, etc."
                    error={fieldErrors["reg-referral"]}
                    className="min-h-[44px]"
                  />
                </FormField>
              </div>

              {/* Optional Profile Photo Picker */}
              <div className="space-y-2">
                <FormField
                  label="Profile Photo (Optional)"
                  htmlFor="reg-photo"
                  error={fieldErrors["reg-photo"]}
                  helpText="JPEG, PNG or WebP, up to 2 MB."
                >
                  <div className="flex items-center gap-4">
                    {photoPreview ? (
                      <div className="relative">
                        <img
                          src={photoPreview}
                          alt="Selected member photo preview"
                          className="w-16 h-16 rounded-full object-cover border-2 border-primary"
                        />
                        <button
                          type="button"
                          onClick={handleRemovePhoto}
                          className="absolute -top-1 -right-1 bg-danger text-white rounded-full w-5 h-5 flex items-center justify-center text-xs shadow hover:bg-danger/80"
                          title="Remove photo"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <div className="w-16 h-16 rounded-full bg-surface-2 border border-dashed border-border flex items-center justify-center text-text-muted text-xs text-center p-1">
                        No photo
                      </div>
                    )}

                    <div className="flex-1">
                      <input
                        id="reg-photo"
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={handlePhotoSelect}
                        disabled={submitting}
                        className="text-xs text-text file:mr-3 file:py-2 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-primary file:text-primary-foreground hover:file:opacity-90 cursor-pointer"
                      />
                    </div>
                  </div>
                </FormField>
              </div>

              {/* Health waiver checkbox */}
              <div className="p-3 bg-surface-2/60 border border-border rounded-lg">
                <label className="flex items-start gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    id="reg-waiver"
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
                {fieldErrors["reg-waiver"] && (
                  <p className="text-xs text-danger mt-1" role="alert">
                    {fieldErrors["reg-waiver"]}
                  </p>
                )}
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
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <AuthenticatedImage
                  src={selectedMember.photo_url}
                  alt={selectedMember.full_name}
                  fallbackInitials={selectedMember.full_name}
                  className="w-14 h-14 rounded-full object-cover border-2 border-primary shrink-0"
                  placeholderClassName="w-14 h-14 rounded-full bg-primary/20 text-primary border border-primary/40 flex items-center justify-center font-bold text-lg shrink-0"
                />
                <div>
                  <h3 className="text-lg font-bold text-text">
                    {selectedMember.full_name}
                  </h3>
                  <p className="text-xs text-text-muted">
                    {selectedMember.email}
                  </p>
                  {canRegister && (
                    <label className="text-[11px] text-primary hover:underline cursor-pointer inline-flex items-center gap-1 mt-1">
                      <span>
                        {changingPhoto ? "Uploading..." : "Change Photo"}
                      </span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="hidden"
                        disabled={changingPhoto}
                        onChange={(e) =>
                          handleDetailPhotoChange(e, selectedMember.id)
                        }
                      />
                    </label>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedMember(null);
                  setDetailPhotoError(null);
                  setDetailPhotoSuccess(null);
                  setActionError(null);
                  setActionSuccess(null);
                  setSuspendReason("");
                }}
                className="text-text-muted hover:text-text text-xl p-1"
              >
                ✕
              </button>
            </div>

            {detailPhotoError && (
              <Alert variant="danger" className="text-xs py-2">
                {detailPhotoError}
              </Alert>
            )}
            {detailPhotoSuccess && (
              <Alert variant="success" className="text-xs py-2">
                {detailPhotoSuccess}
              </Alert>
            )}

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
                <Badge
                  variant={
                    selectedMember.status === "active"
                      ? "success"
                      : selectedMember.status === "frozen"
                        ? "warning"
                        : selectedMember.status === "suspended"
                          ? "danger"
                          : "secondary"
                  }
                >
                  {selectedMember.status}
                </Badge>
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

            {/* Latest Calculated Estimates (Owner & Manager view-only; hidden for Reception) */}
            {userRole !== "reception" &&
              (selectedMember.latest_metrics &&
              (selectedMember.latest_metrics.weight_kg || selectedMember.latest_metrics.height_cm) ? (
                <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-primary">
                      Current Body Composition Estimates
                    </h4>
                    {(selectedMember.latest_metrics.trainer_name ||
                      selectedMember.latest_metrics.recorded_by_name) && (
                      <span className="text-[11px] text-text-muted">
                        Recorded by Trainer:{" "}
                        <strong className="text-text">
                          {selectedMember.latest_metrics.trainer_name ||
                            selectedMember.latest_metrics.recorded_by_name}
                        </strong>
                      </span>
                    )}
                  </div>
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
                      <span className="text-sm font-bold text-primary">
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
                      <span className="text-sm font-bold text-primary">
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
              ) : (
                <div className="p-4 bg-surface-2/40 border border-border rounded-lg text-xs text-text-muted text-center">
                  Not measured yet. A trainer records measurements.
                </div>
              ))}

            {/* Owner/Manager Actions: Suspend / Reactivate */}
            {(userRole === "owner" || userRole === "manager") && (
              <div className="p-4 bg-surface-2/40 border border-border rounded-lg space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-text">
                  Membership Status Action
                </h4>
                {selectedMember.status === "suspended" ? (
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <p className="text-xs text-text-muted">
                      This member is currently suspended. Reinstating will restore their account and subscription status.
                    </p>
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={actionLoading}
                      onClick={handleReactivate}
                    >
                      {actionLoading ? "Reactivating..." : "Reactivate Member"}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-text-muted">
                      Suspend this member to block facility entry and access immediately.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <Input
                        type="text"
                        placeholder="Reason for suspension (required, e.g. rule violation)..."
                        value={suspendReason}
                        onChange={(e) => setSuspendReason(e.target.value)}
                        className="text-xs min-h-[38px] flex-1"
                      />
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={actionLoading || !suspendReason.trim()}
                        onClick={handleSuspend}
                        className="min-h-[38px]"
                      >
                        {actionLoading ? "Suspending..." : "Suspend Member"}
                      </Button>
                    </div>
                  </div>
                )}
                {actionError && (
                  <Alert variant="danger" className="text-xs py-2">
                    {actionError}
                  </Alert>
                )}
                {actionSuccess && (
                  <Alert variant="success" className="text-xs py-2">
                    {actionSuccess}
                  </Alert>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};
