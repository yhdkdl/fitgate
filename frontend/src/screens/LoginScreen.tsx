import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getPublicGymEntry } from "../api/gyms";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { FormField } from "../components/ui/FormField";
import { Input } from "../components/ui/Input";
import { useAuth } from "../context/AuthContext";
import { getTenantFromHostname } from "../utils/tenant";
import { focusFirstInvalidField, validateEmail } from "../utils/validators";

const DEMO_ACCOUNTS = [
  { role: "Owner", email: "owner@demo.local" },
  { role: "Manager", email: "manager@demo.local" },
  { role: "Reception", email: "reception@demo.local" },
  { role: "Trainer", email: "trainer1@demo.local" },
  { role: "Member", email: "member1@demo.local" },
];

export const LoginScreen: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    email?: string;
    password?: string;
  }>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const tenant = getTenantFromHostname();
  const [isDemoGym, setIsDemoGym] = useState(tenant === "demo");

  useEffect(() => {
    if (tenant) {
      if (tenant === "demo") {
        setIsDemoGym(true);
      } else {
        getPublicGymEntry(tenant)
          .then((entry) => {
            if (entry && (entry as { is_demo?: boolean }).is_demo) {
              setIsDemoGym(true);
            }
          })
          .catch(() => {});
      }
    }
  }, [tenant]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const errors: { email?: string; password?: string } = {};
    const emailErr = validateEmail(email);
    if (emailErr) {
      errors.email = emailErr;
    }
    if (!password) {
      errors.password = "Password is required.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      focusFirstInvalidField(
        errors.email ? ["login-email", "login-password"] : ["login-password"]
      );
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);

    try {
      await login({ email: email.trim().toLowerCase(), password });
      const from = (
        location.state as {
          from?: { pathname: string; search?: string; hash?: string };
        }
      )?.from;
      const destination = from
        ? `${from.pathname}${from.search || ""}${from.hash || ""}`
        : "/dashboard";
      navigate(destination, { replace: true });
    } catch (err: unknown) {
      const errorObj = err as {
        status?: number;
        response?: { status?: number; data?: { detail?: string } };
        data?: { detail?: string };
      };
      const status = errorObj.status ?? errorObj.response?.status;
      const detail = errorObj.data?.detail ?? errorObj.response?.data?.detail;

      if (status === 503 && detail === "still_securing") {
        setErrorMessage(
          "This gym domain is currently being secured with an SSL certificate. Please check back shortly once security verification completes."
        );
      } else if (status === 401) {
        setErrorMessage(
          "Invalid email or password. Please check your credentials and try again."
        );
      } else {
        setErrorMessage("Server error, please try again");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-[400px]">
        {/* Branding header */}
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
                Platform Administration
              </span>
            )}
          </p>
        </div>

        <Card className="shadow-lg border-border bg-surface">
          <h2 className="text-xl font-semibold text-text mb-4">Sign in</h2>

          {errorMessage && (
            <Alert variant="danger" className="mb-4 text-sm" role="alert">
              {errorMessage}
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <FormField
              label="Email address"
              htmlFor="login-email"
              required
              error={fieldErrors.email}
            >
              <Input
                id="login-email"
                type="email"
                autoComplete="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email)
                    setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }}
                required
                error={fieldErrors.email}
                disabled={isSubmitting}
              />
            </FormField>

            <FormField
              label="Password"
              htmlFor="login-password"
              required
              error={fieldErrors.password}
            >
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password)
                    setFieldErrors((prev) => ({
                      ...prev,
                      password: undefined,
                    }));
                }}
                required
                error={fieldErrors.password}
                disabled={isSubmitting}
              />
            </FormField>

            <div className="flex items-center justify-end">
              <Link
                to="/forgot-password"
                className="text-sm text-primary hover:text-primary-hover hover:underline py-1"
              >
                Forgot password?
              </Link>
            </div>

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              isLoading={isSubmitting}
            >
              Sign In
            </Button>
          </form>

          {isDemoGym && (
            <div
              className="mt-4 pt-4 border-t border-border"
              data-testid="demo-credentials-panel"
            >
              <details className="group">
                <summary className="font-semibold text-text text-sm cursor-pointer flex items-center justify-between select-none">
                  <span>Demo credentials</span>
                  <span className="text-xs text-primary font-normal group-open:hidden">
                    Show
                  </span>
                </summary>
                <div className="mt-3 space-y-2 pt-2 text-xs">
                  <p className="text-text-muted">
                    Click Fill to populate credentials:
                  </p>
                  {DEMO_ACCOUNTS.map((acc) => (
                    <div
                      key={acc.email}
                      className="flex items-center justify-between p-2 rounded bg-surface-2 border border-border"
                    >
                      <div>
                        <span className="font-medium text-text">{acc.role}: </span>
                        <span className="text-text-muted font-mono">{acc.email}</span>
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setEmail(acc.email);
                          setPassword("FitGateDemo2026!");
                          setFieldErrors({});
                          setErrorMessage(null);
                        }}
                      >
                        Fill
                      </Button>
                    </div>
                  ))}
                </div>
              </details>
            </div>
          )}
        </Card>

        {!tenant && (
          <p className="text-center text-xs text-text-muted mt-4">
            Interested in FitGate for your gym?{" "}
            <Link
              to="/request-demo"
              className="text-primary hover:underline font-medium"
            >
              Request a Demo
            </Link>
          </p>
        )}

        <p className="text-center text-xs text-text-muted mt-4">
          FitGate Multi-Tenant Gym Platform &bull; Secure Authentication
        </p>
      </div>
    </div>
  );
};
