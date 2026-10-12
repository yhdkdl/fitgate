import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getPublicGymEntry, type GymPublicEntryResponse } from "../api/gyms";
import { Alert } from "../components/ui/Alert";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "../context/AuthContext";
import { getTenantFromHostname } from "../utils/tenant";

export const GymEntryScreen: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const tenant = getTenantFromHostname();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<GymPublicEntryResponse | null>(null);
  const [securing, setSecuring] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If user is already authenticated on this gym, offer redirect or allow dashboard access
    let isMounted = true;

    async function loadGymEntry() {
      try {
        setLoading(true);
        setError(null);
        const res = await getPublicGymEntry(tenant || undefined);
        if (!isMounted) return;

        if (res.still_securing) {
          setSecuring(true);
          setData(res);
        } else {
          setSecuring(false);
          setData(res);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const errObj = err as {
          status?: number;
          data?: {
            still_securing?: boolean;
            message?: string;
            detail?: string;
          };
        };
        if (errObj.status === 503 || errObj.data?.still_securing) {
          setSecuring(true);
          setData({
            still_securing: true,
            name: errObj.data?.detail || tenant || "Gym Portal",
            message:
              errObj.data?.message ||
              "This gym portal is still being secured. Please check back shortly.",
          });
        } else {
          setError(
            errObj.data?.detail ||
              "Unable to load gym portal. Please verify the web address."
          );
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadGymEntry();

    return () => {
      isMounted = false;
    };
  }, [tenant]);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-text-muted">Loading gym portal...</p>
        </div>
      </div>
    );
  }

  // Subdomain is still securing
  if (securing) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <Card className="max-w-md w-full bg-surface border-border p-6 text-center space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-warning/10 text-warning flex items-center justify-center border border-warning/20">
            <span className="text-xl font-bold">🔒</span>
          </div>

          <div>
            <Badge variant="warning" className="mb-2">
              Still Being Secured
            </Badge>
            <h1 className="text-xl font-bold text-text">
              {data?.name || "Gym Portal"}
            </h1>
            <p className="text-sm text-text-muted mt-2">
              {data?.message ||
                "This gym portal is still being secured. Please check back shortly."}
            </p>
          </div>

          <div className="bg-surface-2 p-3 rounded-lg border border-border text-xs text-text-muted text-left">
            <p className="font-semibold text-text mb-1">
              Notice for Members and Staff:
            </p>
            TLS security validation is currently finalizing for this subdomain.
            Log in and registration will become available as soon as encryption
            certificate issuance is confirmed.
          </div>

          <div className="pt-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.location.reload()}
              className="w-full"
            >
              Refresh Status
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <Card className="max-w-md w-full bg-surface border-border p-6 space-y-4">
          <Alert variant="danger">{error || "Gym not found."}</Alert>
          <div className="flex justify-center">
            <Button variant="secondary" onClick={() => navigate("/login")}>
              Go to Login
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const brandAccent = data.brand_color || "var(--primary)";

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-border bg-surface px-4 py-3 sm:px-6 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {data.logo ? (
              <img
                src={data.logo}
                alt={`${data.name} logo`}
                className="w-10 h-10 rounded-lg object-cover border border-border"
              />
            ) : (
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-lg text-white border"
                style={{
                  backgroundColor: data.brand_color
                    ? data.brand_color
                    : "#2563EB",
                  borderColor: data.brand_color ? data.brand_color : "#2563EB",
                }}
              >
                {data.name.charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <span className="font-bold text-base tracking-tight text-text block">
                {data.name}
              </span>
              <span className="text-xs text-text-muted">
                {data.location || "Ethiopia"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <Button size="sm" onClick={() => navigate("/dashboard")}>
                Go to Dashboard
              </Button>
            ) : (
              <Link to="/login">
                <Button size="sm" variant="primary">
                  Sign In
                </Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Hero & Welcome */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8 sm:py-12 space-y-8">
        <div
          className="bg-surface border border-border rounded-card p-6 sm:p-10 relative overflow-hidden"
          style={{
            borderLeftWidth: "6px",
            borderLeftColor: brandAccent,
          }}
        >
          <div className="max-w-2xl space-y-4">
            <Badge variant="primary">Welcome to {data.name}</Badge>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-text tracking-tight">
              Manage your fitness journey with {data.name}
            </h1>
            <p className="text-base text-text-muted">
              Fast QR check-ins, automated training programs, membership
              tracking, and trainer support.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link to="/login">
                <Button size="lg" className="min-h-[44px]">
                  Member & Staff Sign In
                </Button>
              </Link>
              <Button
                size="lg"
                variant="secondary"
                disabled
                title="Member registration opening in Sprint 7"
                className="min-h-[44px]"
              >
                Register (Sprint 7)
              </Button>
            </div>
          </div>
        </div>

        {/* Gym Information Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <Card className="bg-surface border-border p-6 space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
              Location & Facility
            </h2>
            <p className="text-lg font-bold text-text">
              {data.location || "Central Location"}
            </p>
            <p className="text-sm text-text-muted">
              Equipped with modern fitness equipment, lockers, and certified
              trainers.
            </p>
          </Card>

          <Card className="bg-surface border-border p-6 space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
              Contact & Inquiries
            </h2>
            <p className="text-lg font-bold text-text">
              {data.phone || "Front Desk Contact"}
            </p>
            <p className="text-sm text-text-muted">
              Currency accepted: {data.currency || "ETB"}
            </p>
          </Card>
        </div>

        {/* Membership Plans Section (Sprint 10 Preview) */}
        <div className="bg-surface border border-border rounded-card p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
            <div>
              <h2 className="text-lg font-bold text-text">Membership Plans</h2>
              <p className="text-xs text-text-muted">
                Flexible subscription durations tailored to your goals.
              </p>
            </div>
            <Badge variant="secondary">Plans Available Soon</Badge>
          </div>

          <div className="p-6 bg-surface-2/40 border border-border/60 rounded-lg text-center space-y-2">
            <p className="text-sm text-text-muted">
              Online plan purchasing and subscription enrollment will be
              available shortly.
            </p>
            <p className="text-xs text-text-muted">
              For in-person registration, please visit the gym reception.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-surface px-4 py-6 text-center text-xs text-text-muted">
        <p>
          &copy; {new Date().getFullYear()} {data.name}. Powered by FitGate
          Platform.
        </p>
      </footer>
    </div>
  );
};
