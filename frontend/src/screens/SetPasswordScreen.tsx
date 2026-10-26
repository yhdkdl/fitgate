import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { setPasswordFromInvite } from "../api/gyms";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { PasswordChecklist } from "../components/ui/PasswordChecklist";
import { getTenantFromHostname } from "../utils/tenant";
import {
  checkPasswordRequirements,
  focusFirstInvalidField,
} from "../utils/validators";

export const SetPasswordScreen: React.FC = () => {
  const [token, setToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    newPassword?: string;
    confirmPassword?: string;
  }>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const tenant = getTenantFromHostname();

  // Read invite token from URL and immediately remove it from address bar
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      setToken(urlToken);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!token) {
      setErrorMessage(
        "Invalid or missing invite link. Please check your invitation email."
      );
      return;
    }

    const errors: { newPassword?: string; confirmPassword?: string } = {};

    const reqs = checkPasswordRequirements(newPassword, confirmPassword);
    if (!reqs.allValid) {
      if (!reqs.minLength) {
        errors.newPassword = "Password must be at least 10 characters long.";
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
      focusFirstInvalidField(
        [
          errors.newPassword ? "set-new-password" : "",
          errors.confirmPassword ? "set-confirm-password" : "",
        ].filter(Boolean)
      );
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);

    try {
      await setPasswordFromInvite(token, newPassword);
      setIsSuccess(true);
    } catch (err: unknown) {
      const errorObj = err as {
        status?: number;
        response?: {
          status?: number;
          data?: { detail?: string; new_password?: string[] };
        };
        data?: { detail?: string; new_password?: string[] };
      };
      const status = errorObj.status ?? errorObj.response?.status;
      const data = errorObj.data ?? errorObj.response?.data;
      const detail = data?.detail;
      const pwdErrors = data?.new_password;

      if (status === 503 || detail === "still_securing") {
        setErrorMessage(
          "This gym domain is currently being secured with an SSL certificate. Please ask your administrator to confirm TLS in the platform dashboard."
        );
      } else if (detail === "token_expired") {
        setErrorMessage(
          "This invitation link has expired. Please contact support for a new invitation."
        );
      } else if (detail === "token_invalid") {
        setErrorMessage(
          "This invitation link is invalid or has already been used."
        );
      } else if (pwdErrors && pwdErrors.length > 0) {
        setErrorMessage(pwdErrors.join(" "));
      } else {
        setErrorMessage(
          "Failed to set password. Please check your connection and try again."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-[420px]">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary/20 text-primary font-bold text-2xl mb-3 border border-primary/30">
            FG
          </div>
          <h1 className="text-2xl font-bold text-text tracking-tight">
            FitGate
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {tenant ? (
              <span className="inline-block bg-surface-2 px-2.5 py-1 rounded-full text-xs font-medium border border-border">
                Gym Portal:{" "}
                <span className="text-primary font-semibold">{tenant}</span>
              </span>
            ) : (
              <span className="inline-block bg-surface-2 px-2.5 py-1 rounded-full text-xs font-medium border border-border">
                Platform Account Setup
              </span>
            )}
          </p>
        </div>

        <Card className="shadow-lg border-border bg-surface">
          <h2 className="text-xl font-semibold text-text mb-2">
            Set Your Password
          </h2>
          <p className="text-sm text-text-muted mb-4">
            Create a secure password to access your FitGate account.
          </p>

          {isSuccess ? (
            <div className="space-y-4">
              <Alert variant="success" className="text-sm" role="alert">
                Your password has been successfully set. Your account is now
                active!
              </Alert>
              <Link to="/login" className="block">
                <Button variant="primary" className="w-full">
                  Proceed to Sign In
                </Button>
              </Link>
            </div>
          ) : (
            <>
              {errorMessage && (
                <Alert variant="danger" className="mb-4 text-sm" role="alert">
                  {errorMessage}
                </Alert>
              )}

              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                <FormField
                  label="New password"
                  htmlFor="set-new-password"
                  required
                  error={fieldErrors.newPassword}
                >
                  <Input
                    id="set-new-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="At least 10 characters"
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
                  label="Confirm password"
                  htmlFor="set-confirm-password"
                  required
                  error={fieldErrors.confirmPassword}
                >
                  <Input
                    id="set-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="Re-enter your password"
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
                  Activate Account & Set Password
                </Button>
              </form>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};
