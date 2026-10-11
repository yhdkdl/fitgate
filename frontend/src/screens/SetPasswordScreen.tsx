import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { setPasswordFromInvite } from "../api/gyms";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { getTenantFromHostname } from "../utils/tenant";

export const SetPasswordScreen: React.FC = () => {
  const [token, setToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
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

    if (newPassword.length < 10) {
      setErrorMessage("Password must be at least 10 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);

    try {
      await setPasswordFromInvite(token, newPassword);
      setIsSuccess(true);
    } catch (err: unknown) {
      const errorObj = err as {
        response?: { data?: { detail?: string; new_password?: string[] } };
      };
      const detail = errorObj.response?.data?.detail;
      const pwdErrors = errorObj.response?.data?.new_password;

      if (detail === "token_expired") {
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
                Welcome to{" "}
                <span className="text-primary font-semibold">{tenant}</span>
              </span>
            ) : (
              <span className="inline-block bg-surface-2 px-2.5 py-1 rounded-full text-xs font-medium border border-border">
                Account Activation
              </span>
            )}
          </p>
        </div>

        <Card className="shadow-lg border-border bg-surface">
          <h2 className="text-xl font-semibold text-text mb-2">
            Set Your Password
          </h2>
          <p className="text-sm text-text-muted mb-4">
            Welcome aboard! Choose a secure password to activate your gym owner
            account.
          </p>

          {isSuccess ? (
            <div className="space-y-4">
              <Alert variant="success" role="status">
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
                  error={
                    newPassword && newPassword.length < 10
                      ? "Minimum 10 characters"
                      : undefined
                  }
                >
                  <Input
                    id="set-new-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="At least 10 characters"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    disabled={isSubmitting}
                  />
                </FormField>

                <FormField
                  label="Confirm password"
                  htmlFor="set-confirm-password"
                  required
                  error={
                    confirmPassword && newPassword !== confirmPassword
                      ? "Passwords do not match"
                      : undefined
                  }
                >
                  <Input
                    id="set-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    placeholder="Re-enter your password"
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
