import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { useAuth } from "../context/AuthContext";

export const ForcedChangePasswordScreen: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { changeUserPassword } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (newPassword.length < 10) {
      setErrorMessage("New password must be at least 10 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("New passwords do not match.");
      return;
    }

    if (newPassword === currentPassword) {
      setErrorMessage("New password must be different from current password.");
      return;
    }

    setIsSubmitting(true);
    try {
      await changeUserPassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      navigate("/dashboard");
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to change password. Please check your credentials.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-[420px]">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-warning/20 text-warning font-bold text-2xl mb-3 border border-warning/30">
            !
          </div>
          <h1 className="text-2xl font-bold text-text">
            Password Change Required
          </h1>
          <p className="text-sm text-text-muted mt-1">
            You must change your password before continuing to your account.
          </p>
        </div>

        <Card className="bg-surface border-border shadow-lg">
          {errorMessage && (
            <Alert variant="danger" className="mb-4 text-sm" role="alert">
              {errorMessage}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <FormField
              label="Current password"
              htmlFor="forced-current-password"
              required
            >
              <Input
                id="forced-current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="New password"
              htmlFor="forced-new-password"
              required
              helperText="Minimum 10 characters"
            >
              <Input
                id="forced-new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="Confirm new password"
              htmlFor="forced-confirm-password"
              required
            >
              <Input
                id="forced-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                disabled={isSubmitting}
              />
            </FormField>

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              isLoading={isSubmitting}
            >
              Update Password and Continue
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};
