import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyMemberEmail } from "../api/members";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";

export const VerifyEmailScreen: React.FC = () => {
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get("token") || "";

  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasExecutedRef = React.useRef(false);

  useEffect(() => {
    if (hasExecutedRef.current) return;

    // Retrieve token from search params or URL query string
    const params = new URLSearchParams(window.location.search);
    const token = tokenFromUrl || params.get("token");

    if (!token) {
      setLoading(false);
      setError("No verification token was provided.");
      return;
    }

    hasExecutedRef.current = true;

    // Strip token from address bar to prevent browser history leaks
    window.history.replaceState({}, document.title, window.location.pathname);

    async function executeVerification() {
      try {
        await verifyMemberEmail(token as string);
        setSuccess(true);
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : "Email verification failed. The link may have expired or already been used.";
        setError(message);
      } finally {
        setLoading(false);
      }
    }

    executeVerification();
  }, [tokenFromUrl]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <Card className="max-w-md w-full bg-surface border-border p-6 sm:p-8 space-y-6 text-center shadow-card">
        {loading ? (
          <div className="py-8 space-y-4">
            <Spinner size="lg" />
            <h1 className="text-xl font-bold text-text">
              Verifying Your Email...
            </h1>
            <p className="text-sm text-text-muted">
              Please wait while we confirm your member account credentials.
            </p>
          </div>
        ) : success ? (
          <div className="space-y-6">
            <div className="w-14 h-14 mx-auto rounded-full bg-success/10 text-success flex items-center justify-center border border-success/20">
              <span className="text-2xl">✓</span>
            </div>

            <div className="space-y-2">
              <Badge variant="success">Email Verified</Badge>
              <h1 className="text-2xl font-bold text-text">
                Account Activated
              </h1>
              <p className="text-sm text-text-muted">
                Your email address has been verified successfully. You can now
                sign in to access your workout tracking, plans, and check-in QR
                code.
              </p>
            </div>

            <Link to="/login" className="block pt-2">
              <Button size="lg" className="w-full min-h-[44px]">
                Sign In to Member Portal
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="w-14 h-14 mx-auto rounded-full bg-danger/10 text-danger flex items-center justify-center border border-danger/20">
              <span className="text-2xl">⚠️</span>
            </div>

            <div className="space-y-2">
              <Badge variant="danger">Verification Failed</Badge>
              <h1 className="text-2xl font-bold text-text">Unable to Verify</h1>
              <Alert variant="danger" className="text-left">
                {error}
              </Alert>
              <p className="text-xs text-text-muted pt-2">
                Verification links expire after 24 hours and can only be used
                once.
              </p>
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Link to="/register">
                <Button size="md" className="w-full min-h-[44px]">
                  Register Again
                </Button>
              </Link>
              <Link to="/login">
                <Button
                  variant="secondary"
                  size="md"
                  className="w-full min-h-[44px]"
                >
                  Return to Sign In
                </Button>
              </Link>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};
