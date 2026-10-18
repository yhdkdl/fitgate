import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { confirmPasswordReset } from "../api/auth";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { PasswordChecklist } from "../components/ui/PasswordChecklist";
import {
  checkPasswordRequirements,
  focusFirstInvalidField,
} from "../utils/validators";

export const ResetPasswordScreen: React.FC = () => {
  // Read token from URL on mount and remove it immediately from address bar
  const [token, setToken] = useState<string>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      return params.get("token") || "";
    }
    return "";
  });

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    newPassword?: string;
    confirmPassword?: string;
  }>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Remove token from address bar immediately to avoid leakage in browser history/logs
    if (
      typeof window !== "undefined" &&
      window.location.search.includes("token")
    ) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!token) {
      setErrorMessage(
        "Reset token is missing or invalid. Please request a new reset link."
      );
      return;
    }

    const errors: { newPassword?: string; confirmPassword?: string } = {};
    const reqs = checkPasswordRequirements(newPassword, confirmPassword);
    if (!reqs.allValid) {
      if (!reqs.minLength) {
        errors.newPassword = "New password must be at least 10 characters long.";
      } else if (!reqs.notNumeric) {
        errors.newPassword = "Password cannot be only digits.";
      } else if (!reqs.notCommon) {
        errors.newPassword = "Password is too common; choose a stronger one.";
      } else if (!reqs.matchesConfirm) {
        errors.confirmPassword = "Passwords do not match.";
      }
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField([
        errors.newPassword ? "reset-new-password" : "",
        errors.confirmPassword ? "reset-confirm-password" : "",
      ].filter(Boolean));
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);
    try {
      await confirmPasswordReset({
        token,
        new_password: newPassword,
      });
      setIsSuccess(true);
      setToken("");
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "The reset link is invalid or expired. Please request a new link.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-[420px]">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-text">Set New Password</h1>
          <p className="text-sm text-text-muted mt-1">
            Create a secure password for your FitGate account.
          </p>
        </div>

        <Card className="bg-surface border-border shadow-lg">
          {isSuccess ? (
            <div className="space-y-4">
              <Alert variant="success" role="alert">
                Password reset complete! You can now sign in with your new
                password.
              </Alert>
              <div className="pt-2">
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center w-full px-4 py-2 bg-primary text-white rounded-input hover:bg-primary-hover min-h-[44px]"
                >
                  Proceed to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {errorMessage && (
                <Alert variant="danger" className="text-sm" role="alert">
                  {errorMessage}
                </Alert>
              )}

              {!token && (
                <Alert variant="warning" className="text-sm">
                  No reset token detected in the URL. If you navigated here
                  directly, please use the link provided in your email.
                </Alert>
              )}

              <FormField
                label="New password"
                htmlFor="reset-new-password"
                required
                error={fieldErrors.newPassword}
              >
                <Input
                  id="reset-new-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 10 characters"
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    if (fieldErrors.newPassword) {
                      setFieldErrors((prev) => ({ ...prev, newPassword: undefined }));
                    }
                  }}
                  required
                  error={fieldErrors.newPassword}
                  disabled={isSubmitting || !token}
                />
              </FormField>

              <FormField
                label="Confirm new password"
                htmlFor="reset-confirm-password"
                required
                error={fieldErrors.confirmPassword}
              >
                <Input
                  id="reset-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (fieldErrors.confirmPassword) {
                      setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                    }
                  }}
                  required
                  error={fieldErrors.confirmPassword}
                  disabled={isSubmitting || !token}
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
                disabled={!token || isSubmitting}
              >
                Reset Password
              </Button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="text-sm text-text-muted hover:text-text hover:underline"
                >
                  Back to Sign In
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
};
