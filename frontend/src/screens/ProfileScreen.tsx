import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProfile } from "../api/auth";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { useAuth } from "../context/AuthContext";

export const ProfileScreen: React.FC = () => {
  const { user, updateUser, changeUserPassword } = useAuth();

  // Profile fields
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [phone, setPhone] = useState(user?.phone || "");
  const [profileSuccess, setProfileSuccess] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Password fields
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
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
  }, []);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSuccess(null);
    setProfileError(null);
    setIsSavingProfile(true);

    try {
      await updateUser({
        full_name: fullName,
        phone: phone,
      });
      setProfileSuccess("Profile details updated successfully.");
    } catch (err: unknown) {
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

    if (newPassword.length < 10) {
      setPasswordError("New password must be at least 10 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
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
    } catch (err: unknown) {
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

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Profile details card */}
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

            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <FormField label="Email" htmlFor="profile-email">
                <Input
                  id="profile-email"
                  type="email"
                  value={user?.email || ""}
                  disabled
                  helperText="Email cannot be changed."
                />
              </FormField>

              <FormField label="Full name" htmlFor="profile-full-name">
                <Input
                  id="profile-full-name"
                  type="text"
                  placeholder="Your full name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={isSavingProfile}
                />
              </FormField>

              <FormField label="Phone number" htmlFor="profile-phone">
                <Input
                  id="profile-phone"
                  type="tel"
                  placeholder="+251 91 234 5678"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={isSavingProfile}
                />
              </FormField>

              <Button
                type="submit"
                variant="primary"
                isLoading={isSavingProfile}
                className="w-full sm:w-auto"
              >
                Save Profile
              </Button>
            </form>
          </Card>

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

            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <FormField
                label="Current password"
                htmlFor="change-current-pwd"
                required
              >
                <Input
                  id="change-current-pwd"
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  disabled={isSavingPassword}
                />
              </FormField>

              <FormField
                label="New password"
                htmlFor="change-new-pwd"
                required
                helperText="Minimum 10 characters"
              >
                <Input
                  id="change-new-pwd"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  disabled={isSavingPassword}
                />
              </FormField>

              <FormField
                label="Confirm new password"
                htmlFor="change-confirm-pwd"
                required
              >
                <Input
                  id="change-confirm-pwd"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  disabled={isSavingPassword}
                />
              </FormField>

              <Button
                type="submit"
                variant="primary"
                isLoading={isSavingPassword}
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
