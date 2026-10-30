import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProfile } from "../api/auth";
import { getMemberProfileMe, type Member } from "../api/members";
import { getTrainerProfileMe, type Trainer } from "../api/trainers";
import { AuthenticatedImage } from "../components/ui/AuthenticatedImage";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { PasswordChecklist } from "../components/ui/PasswordChecklist";
import { useAuth } from "../context/AuthContext";
import {
  checkPasswordRequirements,
  filterPhoneInput,
  focusFirstInvalidField,
  validateName,
  validatePhone,
} from "../utils/validators";

export const ProfileScreen: React.FC = () => {
  const { user, updateUser, changeUserPassword } = useAuth();

  // Profile fields
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileFieldErrors, setProfileFieldErrors] = useState<
    Record<string, string>
  >({});
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Member photo fields
  const [memberData, setMemberData] = useState<Member | null>(null);
  const [trainerData, setTrainerData] = useState<Trainer | null>(null);

  // Password fields
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordFieldErrors, setPasswordFieldErrors] = useState<
    Record<string, string>
  >({});
  const [isSavingPassword, setIsSavingPassword] = useState(false);

  useEffect(() => {
    async function loadFresh() {
      try {
        const fresh = await getProfile();
        setFullName(fresh.full_name || "");
        setPhone(fresh.phone || "");
      } catch {
        // Fall back to context user
      }
    }
    loadFresh();

    if (user?.role === "member") {
      getMemberProfileMe()
        .then((m) => setMemberData(m))
        .catch(() => {});
    }
    if (user?.role === "trainer") {
      getTrainerProfileMe()
        .then((t) => setTrainerData(t))
        .catch(() => {});
    }
  }, [user?.role]);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSuccess(null);
    setProfileError(null);
    setProfileFieldErrors({});

    const errors: Record<string, string> = {};
    const nameErr = validateName(fullName, "Full name", 2, 100);
    if (nameErr) errors["profile-full-name"] = nameErr;

    if (phone.trim()) {
      const phoneErr = validatePhone(phone, false);
      if (phoneErr) errors["profile-phone"] = phoneErr;
    }

    if (Object.keys(errors).length > 0) {
      setProfileFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setIsSavingProfile(true);

    try {
      await updateUser({
        full_name: fullName.trim(),
        phone: phone.trim(),
      });
      setProfileSuccess("Profile details updated successfully.");
    } catch (err: unknown) {
      const errData = (err as { data?: Record<string, unknown> })?.data;
      if (errData && typeof errData === "object") {
        const serverErrors: Record<string, string> = {};
        if ("full_name" in errData)
          serverErrors["profile-full-name"] = Array.isArray(errData.full_name)
            ? errData.full_name.join(" ")
            : String(errData.full_name);
        if ("phone" in errData)
          serverErrors["profile-phone"] = Array.isArray(errData.phone)
            ? errData.phone.join(" ")
            : String(errData.phone);
        if (Object.keys(serverErrors).length > 0) {
          setProfileFieldErrors(serverErrors);
          focusFirstInvalidField(serverErrors);
        }
      }
      setProfileError(
        err instanceof Error ? err.message : "Failed to update profile."
      );
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordSuccess(null);
    setPasswordError(null);
    setPasswordFieldErrors({});

    const errors: Record<string, string> = {};
    if (!currentPassword) {
      errors["change-current-pwd"] = "Current password is required.";
    }

    const pwdReqs = checkPasswordRequirements(newPassword, confirmPassword);
    if (!pwdReqs.isValid) {
      if (!pwdReqs.hasMinLength)
        errors["change-new-pwd"] =
          "Password must be at least 10 characters long.";
      else if (!pwdReqs.hasNoCommon)
        errors["change-new-pwd"] = "Password is too common.";
      else if (!pwdReqs.hasNotOnlyDigits)
        errors["change-new-pwd"] = "Password cannot be entirely numeric.";
      else if (!pwdReqs.matchesConfirm)
        errors["change-confirm-pwd"] = "New passwords do not match.";
    }

    if (Object.keys(errors).length > 0) {
      setPasswordFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setIsSavingPassword(true);
    try {
      await changeUserPassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSuccess("Password updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordFieldErrors({});
    } catch (err: unknown) {
      const errData = (err as { data?: Record<string, unknown> })?.data;
      if (errData && typeof errData === "object") {
        const serverErrors: Record<string, string> = {};
        if ("current_password" in errData)
          serverErrors["change-current-pwd"] = Array.isArray(
            errData.current_password
          )
            ? errData.current_password.join(" ")
            : String(errData.current_password);
        if ("new_password" in errData)
          serverErrors["change-new-pwd"] = Array.isArray(errData.new_password)
            ? errData.new_password.join(" ")
            : String(errData.new_password);
        if (Object.keys(serverErrors).length > 0) {
          setPasswordFieldErrors(serverErrors);
          focusFirstInvalidField(serverErrors);
        }
      }
      setPasswordError(
        err instanceof Error ? err.message : "Failed to change password."
      );
    } finally {
      setIsSavingPassword(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg text-text">
      {/* Top bar */}
      <header className="border-b border-border bg-surface px-4 py-3 sm:px-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/dashboard"
              className="text-text-muted hover:text-text font-medium text-sm flex items-center gap-1"
            >
              &larr; Back to Dashboard
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{user?.email}</span>
            <Badge variant="primary">{user?.role}</Badge>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
        <h1 className="text-2xl font-bold text-text">Account Settings</h1>

        {user?.role === "trainer" && trainerData && (
          <Card className="bg-surface border-border">
            <h2 className="text-lg font-semibold mb-2 text-text">
              Trainer Profile & Capacity
            </h2>
            <div className="flex items-center justify-between p-4 bg-surface-2/40 rounded-lg border border-border">
              <div>
                <div className="text-sm font-semibold text-text">
                  Workload: {trainerData.client_count} /{" "}
                  {trainerData.max_clients} active clients
                </div>
                <div className="text-xs text-text-muted mt-1">
                  Capacity limit: {trainerData.max_clients} clients
                  {trainerData.specialization &&
                    ` • Specialization: ${trainerData.specialization}`}
                </div>
              </div>
              {trainerData.client_count >= trainerData.max_clients && (
                <Badge variant="warning">At Capacity</Badge>
              )}
            </div>
          </Card>
        )}

        {/* Member Profile Photo Card (Item 14: Member cannot edit photo) */}
        {user?.role === "member" && (
          <Card className="bg-surface border-border">
            <h2 className="text-lg font-semibold mb-2 text-text">
              Account Details
            </h2>
            <p className="text-xs text-text-muted mb-4">
              Member personal details and photo are managed by front desk staff.
              Members may change their password below.
            </p>
            <div className="flex items-center gap-4 bg-surface-2/40 p-4 rounded-lg border border-border">
              <AuthenticatedImage
                src={memberData?.photo_url}
                alt="Your profile"
                fallbackInitials={user?.full_name || user?.email || "M"}
                className="w-16 h-16 rounded-full object-cover border-2 border-primary shrink-0"
                placeholderClassName="w-16 h-16 rounded-full bg-surface-2 border border-border flex items-center justify-center text-text-muted text-xl font-bold shrink-0"
              />
              <div className="text-xs space-y-1">
                <div className="font-bold text-text text-sm">
                  {user?.full_name || "Member"}
                </div>
                <div className="text-text-muted">Email: {user?.email}</div>
                <div className="text-text-muted">
                  Phone: {user?.phone || "—"}
                </div>
              </div>
            </div>
          </Card>
        )}

        <div
          className={`grid grid-cols-1 ${
            user?.role !== "member" ? "md:grid-cols-2" : "max-w-xl"
          } gap-6`}
        >
          {/* Profile details card - Staff, Owner, Super Admin only (Item 14) */}
          {user?.role !== "member" && (
            <Card className="bg-surface border-border">
              <h2 className="text-lg font-semibold mb-4 text-text">
                Profile Information
              </h2>

              {profileSuccess && (
                <Alert variant="success" className="mb-4 text-sm" role="status">
                  {profileSuccess}
                </Alert>
              )}
              {profileError && (
                <Alert variant="danger" className="mb-4 text-sm" role="alert">
                  {profileError}
                </Alert>
              )}

              <form
                onSubmit={handleProfileSubmit}
                className="space-y-4"
                noValidate
              >
                <FormField label="Email" htmlFor="profile-email">
                  <Input
                    id="profile-email"
                    type="email"
                    value={user?.email || ""}
                    disabled
                    helperText="Email cannot be changed."
                  />
                </FormField>

                <FormField
                  label="Full name"
                  htmlFor="profile-full-name"
                  error={profileFieldErrors["profile-full-name"]}
                >
                  <Input
                    id="profile-full-name"
                    type="text"
                    maxLength={100}
                    placeholder="Your full name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    error={profileFieldErrors["profile-full-name"]}
                    disabled={isSavingProfile}
                  />
                </FormField>

                <FormField
                  label="Phone number"
                  htmlFor="profile-phone"
                  error={profileFieldErrors["profile-phone"]}
                >
                  <Input
                    id="profile-phone"
                    type="tel"
                    inputMode="tel"
                    maxLength={20}
                    placeholder="+251 91 234 5678"
                    value={phone}
                    onChange={(e) => setPhone(filterPhoneInput(e.target.value))}
                    error={profileFieldErrors["profile-phone"]}
                    disabled={isSavingProfile}
                  />
                </FormField>

                <Button
                  type="submit"
                  variant="primary"
                  isLoading={isSavingProfile}
                  disabled={isSavingProfile}
                  className="w-full sm:w-auto"
                >
                  Save Profile
                </Button>
              </form>
            </Card>
          )}

          {/* Change password card */}
          <Card className="bg-surface border-border">
            <h2 className="text-lg font-semibold mb-4 text-text">
              Change Password
            </h2>

            {passwordSuccess && (
              <Alert variant="success" className="mb-4 text-sm" role="status">
                {passwordSuccess}
              </Alert>
            )}
            {passwordError && (
              <Alert variant="danger" className="mb-4 text-sm" role="alert">
                {passwordError}
              </Alert>
            )}

            <form
              onSubmit={handlePasswordSubmit}
              className="space-y-4"
              noValidate
            >
              <FormField
                label="Current password"
                htmlFor="change-current-pwd"
                required
                error={passwordFieldErrors["change-current-pwd"]}
              >
                <Input
                  id="change-current-pwd"
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  maxLength={128}
                  required
                  error={passwordFieldErrors["change-current-pwd"]}
                  disabled={isSavingPassword}
                />
              </FormField>

              <FormField
                label="New password"
                htmlFor="change-new-pwd"
                required
                error={passwordFieldErrors["change-new-pwd"]}
              >
                <Input
                  id="change-new-pwd"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  maxLength={128}
                  required
                  error={passwordFieldErrors["change-new-pwd"]}
                  disabled={isSavingPassword}
                />
              </FormField>

              <FormField
                label="Confirm new password"
                htmlFor="change-confirm-pwd"
                required
                error={passwordFieldErrors["change-confirm-pwd"]}
              >
                <Input
                  id="change-confirm-pwd"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  maxLength={128}
                  required
                  error={passwordFieldErrors["change-confirm-pwd"]}
                  disabled={isSavingPassword}
                />
              </FormField>

              <PasswordChecklist
                password={newPassword}
                confirmPassword={confirmPassword}
              />

              <Button
                type="submit"
                variant="primary"
                isLoading={isSavingPassword}
                disabled={isSavingPassword}
                className="w-full sm:w-auto"
              >
                Update Password
              </Button>
            </form>
          </Card>
        </div>
      </main>
    </div>
  );
};
