import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { PasswordChecklist } from "../components/ui/PasswordChecklist";
import { useAuth } from "../context/AuthContext";
import {
  checkPasswordRequirements,
  focusFirstInvalidField,
} from "../utils/validators";

export const ForcedChangePasswordScreen: React.FC = () => {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    currentPassword?: string;
    newPassword?: string;
    confirmPassword?: string;
  }>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { changeUserPassword } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const errors: {
      currentPassword?: string;
      newPassword?: string;
      confirmPassword?: string;
    } = {};

    if (!currentPassword) {
      errors.currentPassword = "Current password is required.";
    }

    const reqs = checkPasswordRequirements(newPassword, confirmPassword);
    if (!reqs.allValid) {
      if (!reqs.minLength) {
        errors.newPassword =
          "New password must be at least 10 characters long.";
      } else if (!reqs.notNumeric) {
        errors.newPassword = "New password cannot be only digits.";
      } else if (!reqs.notCommon) {
        errors.newPassword =
          "New password is too common; choose a stronger one.";
      } else if (!reqs.matchesConfirm) {
        errors.confirmPassword = "New passwords do not match.";
      }
    }

    if (newPassword && currentPassword && newPassword === currentPassword) {
      errors.newPassword =
        "New password must be different from current password.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(
        [
          errors.currentPassword ? "forced-current-password" : "",
          errors.newPassword ? "forced-new-password" : "",
          errors.confirmPassword ? "forced-confirm-password" : "",
        ].filter(Boolean)
      );
      return;
    }

    setFieldErrors({});
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
              error={fieldErrors.currentPassword}
            >
              <Input
                id="forced-current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => {
                  setCurrentPassword(e.target.value);
                  if (fieldErrors.currentPassword) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      currentPassword: undefined,
                    }));
                  }
                }}
                required
                error={fieldErrors.currentPassword}
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="New password"
              htmlFor="forced-new-password"
              required
              error={fieldErrors.newPassword}
            >
              <Input
                id="forced-new-password"
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => {
                  setNewPassword(e.target.value);
                  if (fieldErrors.newPassword) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      newPassword: undefined,
                    }));
                  }
                }}
                required
                error={fieldErrors.newPassword}
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="Confirm new password"
              htmlFor="forced-confirm-password"
              required
              error={fieldErrors.confirmPassword}
            >
              <Input
                id="forced-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (fieldErrors.confirmPassword) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      confirmPassword: undefined,
                    }));
                  }
                }}
                required
                error={fieldErrors.confirmPassword}
                disabled={isSubmitting}
              />
            </FormField>

            <PasswordChecklist
              password={newPassword}
              confirmPassword={confirmPassword}
            />

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              isLoading={isSubmitting}
              disabled={isSubmitting}
            >
              Update Password and Continue
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};
