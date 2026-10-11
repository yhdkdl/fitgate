import React, { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../api/auth";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";

export const ForgotPasswordScreen: React.FC = () => {
  const [email, setEmail] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await requestPasswordReset({ email });
      setIsSubmitted(true);
    } catch {
      // Uniform generic response regardless of whether account exists or fails
      setIsSubmitted(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-text">Reset Password</h1>
          <p className="text-sm text-text-muted mt-1">
            Enter your email to receive a password reset link.
          </p>
        </div>

        <Card className="bg-surface border-border shadow-lg">
          {isSubmitted ? (
            <div className="space-y-4">
              <Alert variant="info" role="alert">
                If the account exists, a reset link has been sent. Please check
                your inbox (and backend logs in local dev).
              </Alert>
              <div className="pt-2 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center w-full px-4 py-2 bg-surface-2 border border-border text-text rounded-input hover:bg-border/60 min-h-[44px]"
                >
                  Return to Sign In
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {errorMessage && (
                <Alert variant="danger" className="text-sm">
                  {errorMessage}
                </Alert>
              )}

              <FormField label="Email address" htmlFor="forgot-email" required>
                <Input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                Send Reset Link
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
