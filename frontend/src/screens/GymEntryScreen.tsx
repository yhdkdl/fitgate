import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  CalendarCheck,
  Check,
  CreditCard,
  Dumbbell,
  ExternalLink,
  Flame,
  Lock,
  MapPin,
  Phone,
  QrCode,
  ShieldAlert,
  Users,
  Zap,
} from "lucide-react";
import { getPublicGymEntry, type GymPublicEntryResponse } from "../api/gyms";
import { useAuth } from "../context/AuthContext";
import { getTenantFromHostname } from "../utils/tenant";
import LightRays from "../components/ui/LightRays";
import {
  getGymLandingCustomization,
  resolveHeroImage,
  type GymLandingCustomization,
} from "../utils/gymLandingCustomization";

export const GymEntryScreen: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isPreview = searchParams.get("preview") === "true";
  const { user } = useAuth();
  const tenant = getTenantFromHostname();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<GymPublicEntryResponse | null>(null);
  const [securing, setSecuring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customization, setCustomization] = useState<GymLandingCustomization>({});

  // Redirect authenticated users to dashboard unless in explicit preview mode
  useEffect(() => {
    if (user && !isPreview) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate, isPreview]);

  useEffect(() => {
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

        // Load gym owner custom landing options from storage
        const custom = getGymLandingCustomization(res.subdomain || tenant || res.gym_id);
        setCustomization(custom);
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
            online_payment_verified: false,
            has_group_classes: false,
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
      <div className="min-h-screen bg-[#070A11] flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-slate-700 border-t-[#A3E635] rounded-full animate-spin" />
          <p className="text-sm font-semibold text-slate-400">Loading gym portal...</p>
        </div>
      </div>
    );
  }

  // If securing but no full gym data loaded yet, show minimal fallback
  if (securing && !data?.name) {
    return (
      <div className="min-h-screen bg-[#070A11] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center space-y-5 shadow-2xl">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-500/15 text-amber-400 flex items-center justify-center border border-amber-500/30">
            <Lock className="w-7 h-7" />
          </div>
          <div>
            <span className="inline-block px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30 mb-3">
              Still Being Secured
            </span>
            <h1 className="text-2xl font-black text-white uppercase">Gym Portal</h1>
            <p className="text-sm text-slate-400 mt-2">
              This gym portal is still being secured. Please check back shortly.
            </p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-extrabold uppercase tracking-wider text-slate-950 bg-amber-400 hover:bg-amber-300 rounded-xl transition"
          >
            Refresh Status
          </button>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#070A11] flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-5 text-center shadow-2xl">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-red-500/15 text-red-400 flex items-center justify-center border border-red-500/30">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <div className="text-sm text-red-300 font-medium">
            {error || "Gym not found."}
          </div>
          <div>
            <button
              onClick={() => navigate("/login")}
              className="inline-flex items-center justify-center gap-2 px-6 py-2.5 text-xs font-extrabold uppercase tracking-wider text-slate-950 bg-[#A3E635] hover:bg-[#BEF264] rounded-xl transition"
            >
              Go to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  const brandAccent = data.brand_color || "#A3E635";
  const heroCoverUrl = resolveHeroImage(customization);
  const heroMotto = customization.heroMotto || "Train Hard. Stay Strong.";
  const heroSubtitle =
    customization.heroSubtitle ||
    "Manage your fitness journey with " +
      data.name +
      ". Fast QR check-ins, automated training programs, membership tracking, and trainer support.";
  const operatingHours =
    customization.operatingHours || "Mon - Sun: 6:00 AM - 10:00 PM";

  return (
    <div className="min-h-screen bg-[#070A11] text-slate-100 selection:bg-[#A3E635] selection:text-slate-950 flex flex-col font-sans w-full overflow-x-hidden">
      {/* Top Preview Admin Bar when logged in as Gym Owner */}
      {user && isPreview && (
        <div className="w-full bg-[#111C33] border-b border-blue-500/40 px-4 py-2 text-xs text-blue-200 sticky top-0 z-50 flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse" />
            <span className="font-bold uppercase tracking-wider">
              Gym Owner Live Preview Mode
            </span>
            <span className="text-slate-400 hidden sm:inline">
              &bull; Viewing public landing page as prospective members see it
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/settings"
              className="px-2.5 py-1 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-200 border border-blue-400/40 font-semibold transition"
            >
              Edit Branding &amp; UI
            </Link>
            <Link
              to="/dashboard"
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-white font-semibold transition"
            >
              Return to Dashboard &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Top Utility Ribbon - Full Width */}
      <div className="w-full bg-[#0D1424] border-b border-slate-800/80 px-4 sm:px-8 lg:px-12 py-2 text-xs text-slate-400">
        <div className="w-full max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            {data.location && (
              <span className="flex items-center gap-1.5 text-slate-300">
                <MapPin className="w-3.5 h-3.5 text-[#A3E635]" />
                <span>{data.location}</span>
              </span>
            )}
            {(data.public_contact_phone || data.phone) && (
              <>
                <span className="hidden sm:inline-block text-slate-600">&bull;</span>
                <span className="flex items-center gap-1 text-slate-300">
                  <Phone className="w-3.5 h-3.5 text-[#A3E635]" />
                  <span>Tel: {data.public_contact_phone || data.phone}</span>
                </span>
              </>
            )}
            <span className="hidden md:inline-block text-slate-600">&bull;</span>
            <span className="hidden md:inline-block">Hours: {operatingHours}</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-slate-400">
              Currency: <strong className="text-white">{data.currency || "ETB"}</strong>
            </span>
            <Link
              to="/login"
              className="text-white hover:text-[#A3E635] transition font-bold"
            >
              Member Sign In &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Security Verification Banner when still securing */}
      {securing && (
        <div className="w-full bg-amber-950/40 border-b border-amber-500/40 px-4 py-3">
          <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-amber-200 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40">
                Still Being Secured
              </span>
              <span className="font-bold text-white">Notice for Members and Staff:</span>
              <span className="text-slate-300">
                {data.message ||
                  "This gym portal is still being secured. Please check back shortly."}
              </span>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="px-3 py-1 rounded-lg text-xs font-bold bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/40 transition shrink-0"
            >
              Refresh Status
            </button>
          </div>
        </div>
      )}

      {/* Main Sticky Header - Full Width */}
      <header className="sticky top-0 z-40 bg-[#070A11]/95 backdrop-blur-md border-b border-slate-800/80 w-full">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 h-20 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-3 text-white transition focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded-lg p-1"
          >
            {data.logo ? (
              <img
                src={data.logo}
                alt={`${data.name} logo`}
                className="w-11 h-11 rounded-xl object-cover border border-slate-700 shadow-md"
              />
            ) : (
              <div
                className="w-11 h-11 rounded-xl flex items-center justify-center font-black text-xl text-slate-950 shadow-lg"
                style={{
                  backgroundColor: brandAccent,
                  boxShadow: `0 4px 14px ${brandAccent}33`,
                }}
              >
                {data.name.charAt(0).toUpperCase()}
              </div>
            )}
            <div>
              <span className="text-xl sm:text-2xl font-black tracking-tight block leading-tight text-white uppercase">
                {data.name}
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block leading-tight">
                {data.location || "Premier Fitness Facility"}
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav
            aria-label="Gym navigation"
            className="hidden md:flex items-center gap-8 text-sm font-semibold tracking-wide text-slate-300"
          >
            <a
              href="#programs"
              className="hover:text-white transition-colors py-2 focus-visible:ring-2 rounded"
              style={{ ":hover": { color: brandAccent } } as React.CSSProperties}
            >
              Programs
            </a>
            <a
              href="#about"
              className="hover:text-white transition-colors py-2 focus-visible:ring-2 rounded"
            >
              About
            </a>
            <a
              href="#plans"
              className="hover:text-white transition-colors py-2 focus-visible:ring-2 rounded"
            >
              Plans &amp; Pricing
            </a>
            <a
              href="#location"
              className="hover:text-white transition-colors py-2 focus-visible:ring-2 rounded"
            >
              Location &amp; Hours
            </a>
          </nav>

          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            {user ? (
              <Link
                to="/dashboard"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-extrabold uppercase tracking-wider text-slate-950 rounded-xl shadow-lg transition min-h-[44px]"
                style={{ backgroundColor: brandAccent }}
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center px-4 py-2.5 text-sm font-bold text-white bg-slate-900/90 hover:bg-slate-800 border border-slate-700 rounded-xl transition min-h-[44px]"
                >
                  Log in
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center justify-center gap-1.5 px-5 py-2.5 text-sm font-extrabold uppercase tracking-wider text-slate-950 rounded-xl shadow-lg transition min-h-[44px]"
                  style={{
                    backgroundColor: brandAccent,
                    boxShadow: `0 4px 14px ${brandAccent}40`,
                  }}
                >
                  <span>Register</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 w-full">
        {/* Dynamic Hero Section with React Bits <LightRays /> Background */}
        <section className="relative overflow-hidden w-full border-b border-slate-800/80 bg-[#070A11] min-h-[85vh] flex flex-col justify-center">
          {/* Animated LightRays with Gym Brand Accent */}
          <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
            <LightRays
              raysOrigin="top-center"
              raysColor={brandAccent}
              raysSpeed={0.8}
              lightSpread={0.65}
              rayLength={3.2}
              rayDensity={1.2}
              glow={0.55}
              haze={0.3}
              atmosphere={0.85}
              intensity={1.15}
              followMouse={true}
              mouseInfluence={0.12}
              noiseAmount={0.04}
              distortion={0.06}
              pulsating={false}
              cursorShadow={true}
              clickPulse={true}
              intro={true}
              lightMode={false}
              opacity={0.85}
            />
            {/* Soft dark vignette overlays */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#070A11] via-transparent to-black/30 pointer-events-none" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#070A11]/40 to-[#070A11] pointer-events-none" />
          </div>

          {/* Foreground Hero Content */}
          <div className="relative z-10 w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 py-16 sm:py-24">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
              {/* Left Column: Gym Hero Details */}
              <div className="lg:col-span-7 space-y-6">
                <div
                  className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider border"
                  style={{
                    backgroundColor: `${brandAccent}15`,
                    borderColor: `${brandAccent}40`,
                    color: brandAccent,
                  }}
                >
                  <Flame className="w-4 h-4" />
                  <span>{heroMotto}</span>
                </div>

                <h1 className="text-4xl sm:text-6xl xl:text-7xl font-black tracking-tight text-white uppercase leading-[1.06]">
                  Welcome to {data.name}
                </h1>

                <p className="text-base sm:text-lg text-slate-300/90 font-normal leading-relaxed max-w-2xl">
                  {heroSubtitle}
                </p>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-2">
                  <a
                    href="#plans"
                    className="inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-extrabold uppercase tracking-wider text-slate-950 rounded-xl shadow-xl transition min-h-[50px]"
                    style={{
                      backgroundColor: brandAccent,
                      boxShadow: `0 8px 24px ${brandAccent}44`,
                    }}
                  >
                    <span>Choose Plan</span>
                    <ArrowRight className="w-5 h-5" />
                  </a>

                  <Link
                    to="/login"
                    className="inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-bold text-white bg-slate-900/90 hover:bg-slate-800 border border-slate-700 hover:border-slate-500 rounded-xl transition min-h-[50px] backdrop-blur-xs"
                  >
                    <span>Member Login</span>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </Link>

                  <Link
                    to="/register"
                    className="inline-flex items-center justify-center gap-2 px-6 py-4 text-base font-bold text-slate-300 hover:text-white transition"
                  >
                    <span>New Member? Register &rarr;</span>
                  </Link>
                </div>

                {/* Key Pillars */}
                <div className="pt-6 grid grid-cols-3 gap-6 border-t border-slate-800/80 max-w-xl">
                  <div>
                    <div className="text-2xl sm:text-4xl font-black text-white">90s</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      Dynamic QR Pass
                    </div>
                  </div>
                  <div>
                    <div
                      className="text-2xl sm:text-4xl font-black"
                      style={{ color: brandAccent }}
                    >
                      100%
                    </div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      Certified Coaches
                    </div>
                  </div>
                  <div>
                    <div className="text-2xl sm:text-4xl font-black text-white">7 Days</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      Facility Access
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Hero Graphic with Floating Cards */}
              <div className="lg:col-span-5 relative">
                <div className="relative mx-auto max-w-lg lg:max-w-none">
                  {/* Outer Glow Ring */}
                  <div
                    className="absolute -inset-2 rounded-3xl blur-2xl opacity-60"
                    style={{
                      background: `radial-gradient(circle, ${brandAccent}66 0%, transparent 70%)`,
                    }}
                  />

                  {/* Main Gym Hero Image */}
                  <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-slate-900 shadow-2xl">
                    <img
                      src={heroCoverUrl}
                      alt={`${data.name} Facility`}
                      className="w-full h-[460px] object-cover object-center filter brightness-95 contrast-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#070A11] via-transparent to-black/30" />

                    {/* Integrated Pill Bar */}
                    <div className="absolute bottom-4 right-4 left-4 p-4 rounded-xl bg-slate-950/80 backdrop-blur-md border border-slate-800/90 grid grid-cols-2 gap-3 text-left">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border"
                          style={{
                            backgroundColor: `${brandAccent}20`,
                            color: brandAccent,
                            borderColor: `${brandAccent}40`,
                          }}
                        >
                          <QrCode className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white uppercase tracking-wider">
                            Fast Entrance
                          </div>
                          <div className="text-[10px] text-slate-400">Dynamic QR Scanner</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border"
                          style={{
                            backgroundColor: `${brandAccent}20`,
                            color: brandAccent,
                            borderColor: `${brandAccent}40`,
                          }}
                        >
                          <CreditCard className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white uppercase tracking-wider">
                            Direct Payments
                          </div>
                          <div className="text-[10px] text-slate-400">Telebirr &amp; Banks</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Floating Micro-Card 1: Dynamic QR Badge */}
                  <div className="absolute -top-4 -left-4 sm:-left-6 bg-slate-900/95 border border-slate-700/80 rounded-xl p-3.5 shadow-2xl backdrop-blur-md flex items-center gap-3 max-w-[240px]">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 border"
                      style={{
                        backgroundColor: `${brandAccent}20`,
                        color: brandAccent,
                        borderColor: `${brandAccent}40`,
                      }}
                    >
                      <QrCode className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">
                        90s Dynamic QR
                      </div>
                      <div className="text-[11px] text-slate-400 font-medium">
                        Instant entrance scan
                      </div>
                    </div>
                  </div>

                  {/* Floating Micro-Card 2: Trainer & Coaching */}
                  <div className="absolute -top-4 -right-4 sm:-right-6 bg-slate-900/95 border border-slate-700/80 rounded-xl p-3.5 shadow-2xl backdrop-blur-md flex items-center gap-3 max-w-[250px]">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/40">
                      <Users className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">
                        Trainer Coaching
                      </div>
                      <div className="text-[11px] text-slate-400 font-medium">
                        Verified progress metrics
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Full-Width 4-Pill Feature Strip */}
        <div className="w-full bg-[#0B101C] border-b border-slate-800/80 py-6">
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-slate-700 transition">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${brandAccent}15`, color: brandAccent }}
              >
                <Dumbbell className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Top Equipment
                </div>
                <div className="text-xs text-slate-400">
                  Advanced &amp; safe machines
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-slate-700 transition">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${brandAccent}15`, color: brandAccent }}
              >
                <Users className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Expert Coaches
                </div>
                <div className="text-xs text-slate-400">
                  Certified trainer guidance
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-slate-700 transition">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${brandAccent}15`, color: brandAccent }}
              >
                <CalendarCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Flexible Timings
                </div>
                <div className="text-xs text-slate-400">
                  Open 7 days a week
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-slate-700 transition">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${brandAccent}15`, color: brandAccent }}
              >
                <Zap className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Touchless Check-in
                </div>
                <div className="text-xs text-slate-400">
                  Zero door waiting time
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Programs Section */}
        <section
          id="programs"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span
                className="text-xs font-bold uppercase tracking-widest block mb-2"
                style={{ color: brandAccent }}
              >
                Training &amp; Fitness Pathways
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                Our Programs &amp; Amenities
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                Built to support lifters, athletes, and beginners with structured workouts and expert coaches.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Program 1 */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-44 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=600&q=80"
                      alt="Strength Training"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-9 h-9 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-white border border-slate-700">
                      <Dumbbell className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="p-5">
                    <h3 className="text-lg font-bold text-white mb-2">Strength &amp; Hypertrophy</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Barbells, free weights, Olympic racks, and targeted resistance machines for progressive overload.
                    </p>
                  </div>
                </div>
                <div className="px-5 pb-5">
                  <a
                    href="#plans"
                    className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider"
                    style={{ color: brandAccent }}
                  >
                    <span>View Plans</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Program 2 */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-44 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=600&q=80"
                      alt="Functional HIIT"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-9 h-9 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-white border border-slate-700">
                      <Zap className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="p-5">
                    <h3 className="text-lg font-bold text-white mb-2">Cardio &amp; Fat Loss</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      High-intensity interval stations, treadmills, assault bikes, and stamina conditioning circuits.
                    </p>
                  </div>
                </div>
                <div className="px-5 pb-5">
                  <a
                    href="#plans"
                    className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider"
                    style={{ color: brandAccent }}
                  >
                    <span>View Plans</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Program 3 */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-44 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=600&q=80"
                      alt="Personal Training"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-9 h-9 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-white border border-slate-700">
                      <Users className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="p-5">
                    <h3 className="text-lg font-bold text-white mb-2">Trainer Coaching &amp; Metrics</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Dedicated coach guidance, standardized circumference metrics, body fat tracking, and form corrections.
                    </p>
                  </div>
                </div>
                <div className="px-5 pb-5">
                  <a
                    href="#plans"
                    className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider"
                    style={{ color: brandAccent }}
                  >
                    <span>View Plans</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Program 4 */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-slate-600 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-44 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=600&q=80"
                      alt="AI Fitness Plans"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-9 h-9 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-white border border-slate-700">
                      <Bot className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <h3 className="text-lg font-bold text-white">AI Workout Plans</h3>
                      {data.has_group_classes && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
                          Classes
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Customized routine generation factoring in your personal goals, equipment, and coach approval.
                    </p>
                  </div>
                </div>
                <div className="px-5 pb-5">
                  <a
                    href="#plans"
                    className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider"
                    style={{ color: brandAccent }}
                  >
                    <span>View Plans</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* About Section & Operational Manifesto */}
        <section
          id="about"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-gradient-to-r from-[#080C14] via-[#0E1524] to-[#080C14]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
              <div className="lg:col-span-6 relative">
                <div className="rounded-2xl overflow-hidden border border-slate-800 relative shadow-2xl">
                  <img
                    src="https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=1000&q=80"
                    alt="Discipline Focus Strong Consistent"
                    className="w-full h-[400px] sm:h-[460px] object-cover object-center filter brightness-90"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent flex flex-col justify-end p-8 sm:p-10">
                    <span
                      className="text-xs font-bold uppercase tracking-widest mb-1.5"
                      style={{ color: brandAccent }}
                    >
                      Facility Manifesto
                    </span>
                    <div className="text-3xl sm:text-5xl font-black text-white uppercase tracking-tight leading-tight">
                      Discipline &bull; Focus &bull; Strong &bull; Consistent
                    </div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-6 space-y-6">
                <span
                  className="text-xs font-bold uppercase tracking-widest block"
                  style={{ color: brandAccent }}
                >
                  About {data.name}
                </span>
                <h2 className="text-3xl sm:text-5xl font-black text-white uppercase leading-tight">
                  Your High-Performance Fitness Hub
                </h2>
                <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
                  We believe fitness is more than just a workout &mdash; it is a lifestyle. Our mission is to help you achieve your physical and athletic potential with modern machines, certified coaches, and touchless digital access.
                </p>

                {/* Facility Details Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                  {data.location && (
                    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Location &amp; Facility
                      </div>
                      <div className="text-base font-bold text-white">
                        {data.location}
                      </div>
                      <div className="text-xs text-slate-400">
                        Equipped with modern fitness equipment, lockers, and certified trainers.
                      </div>
                    </div>
                  )}

                  {(data.public_contact_phone || data.phone) && (
                    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 space-y-1">
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        Contact &amp; Inquiries
                      </div>
                      <div className="text-base font-bold text-white">
                        {data.public_contact_phone || data.phone}
                      </div>
                      <div className="text-xs text-slate-400">
                        Currency accepted: {data.currency || "ETB"}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Membership Plans Section */}
        <section
          id="plans"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span
                className="text-xs font-bold uppercase tracking-widest block mb-2"
                style={{ color: brandAccent }}
              >
                Join Today
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                Membership Plans
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                Select your preferred membership tier. All packages include touchless QR check-in and facility access.
              </p>
            </div>

            {data?.plans && data.plans.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 items-stretch max-w-6xl mx-auto">
                {data.plans.map((plan, index) => {
                  const isFeatured = index === 0;
                  return (
                    <div
                      key={plan.id}
                      className={`rounded-2xl p-8 flex flex-col justify-between transition-all ${
                        isFeatured
                          ? "bg-slate-900 border-2 shadow-2xl relative"
                          : "bg-slate-900/80 border border-slate-800"
                      }`}
                      style={{
                        borderColor: isFeatured ? brandAccent : undefined,
                        boxShadow: isFeatured ? `0 12px 36px ${brandAccent}20` : undefined,
                      }}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-4">
                          {isFeatured && (
                            <span
                              className="px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider text-slate-950 shadow-sm"
                              style={{ backgroundColor: brandAccent }}
                            >
                              Most Popular
                            </span>
                          )}
                          {plan.trainer_inclusive && (
                            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40">
                              Trainer Included
                            </span>
                          )}
                        </div>

                        <h3 className="text-2xl sm:text-3xl font-black text-white uppercase mb-2">
                          {plan.name}
                        </h3>

                        {plan.description && (
                          <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                            {plan.description}
                          </p>
                        )}

                        <div className="mb-6 pb-6 border-b border-slate-800">
                          <span className="text-4xl sm:text-5xl font-black text-white">
                            {Number(plan.price_etb).toLocaleString()}
                          </span>
                          <span
                            className="font-bold text-sm ml-2 uppercase"
                            style={{ color: brandAccent }}
                          >
                            ETB
                          </span>
                          <span className="text-xs text-slate-400 ml-1">
                            / {plan.duration_value} {plan.duration_unit}
                          </span>
                          <div className="text-xs text-slate-500 mt-1">
                            All-inclusive access &bull; No hidden fees
                          </div>
                        </div>

                        <div className="space-y-3 mb-8">
                          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                            Included with Plan
                          </div>
                          <div className="flex items-start gap-2.5 text-sm text-slate-300">
                            <Check className="w-4 h-4 shrink-0 mt-0.5" style={{ color: brandAccent }} />
                            <span>Full facility and machine access</span>
                          </div>
                          <div className="flex items-start gap-2.5 text-sm text-slate-300">
                            <Check className="w-4 h-4 shrink-0 mt-0.5" style={{ color: brandAccent }} />
                            <span>Instant 90s dynamic QR entrance pass</span>
                          </div>
                          <div className="flex items-start gap-2.5 text-sm text-slate-300">
                            <Check className="w-4 h-4 shrink-0 mt-0.5" style={{ color: brandAccent }} />
                            <span>Locker room and amenity access</span>
                          </div>
                          {plan.trainer_inclusive && (
                            <div className="flex items-start gap-2.5 text-sm text-slate-300">
                              <Check className="w-4 h-4 shrink-0 mt-0.5" style={{ color: brandAccent }} />
                              <span>Personal trainer coaching sessions included</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div>
                        <Link
                          to={`/register?plan=${plan.id}`}
                          className="w-full inline-flex items-center justify-center gap-2 px-6 py-4 text-sm font-extrabold uppercase tracking-wider rounded-xl transition min-h-[48px]"
                          style={{
                            backgroundColor: isFeatured ? brandAccent : "#1E293B",
                            color: isFeatured ? "#020617" : "#F8FAFC",
                          }}
                        >
                          <span>Choose Plan</span>
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="p-10 bg-slate-900 border border-slate-800 rounded-2xl text-center max-w-xl mx-auto space-y-3">
                <p className="text-base text-slate-300 font-bold">
                  No active plans currently listed online.
                </p>
                <p className="text-xs text-slate-400">
                  Please visit the front desk for available in-person packages
                  {data.contact_line ? ` ${data.contact_line}` : ""}.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Location & Hours Section */}
        <section
          id="location"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 space-y-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center border"
                  style={{
                    backgroundColor: `${brandAccent}15`,
                    color: brandAccent,
                    borderColor: `${brandAccent}40`,
                  }}
                >
                  <MapPin className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white uppercase">Facility Address</h3>
                <p className="text-sm text-slate-300">
                  {data.location || "Central Addis Ababa, Ethiopia"}
                </p>
                <p className="text-xs text-slate-400">
                  Easy parking, turnstile entry, air-conditioned workout floors.
                </p>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 space-y-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center border"
                  style={{
                    backgroundColor: `${brandAccent}15`,
                    color: brandAccent,
                    borderColor: `${brandAccent}40`,
                  }}
                >
                  <Phone className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white uppercase">Direct Contact</h3>
                <p className="text-sm text-slate-300">
                  Front desk: {data.public_contact_phone || data.phone || "Contact via reception"}
                </p>
                <p className="text-xs text-slate-400">
                  Call or visit reception for inquiries, group rates, or trainer sessions.
                </p>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 space-y-4">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center border"
                  style={{
                    backgroundColor: `${brandAccent}15`,
                    color: brandAccent,
                    borderColor: `${brandAccent}40`,
                  }}
                >
                  <CalendarCheck className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white uppercase">Operating Hours</h3>
                <p className="text-sm text-slate-300">{operatingHours}</p>
                <p className="text-xs text-slate-400">
                  Open through holidays and weekends with uninterrupted badge entry.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* High-Impact Pre-Footer Banner */}
        <section
          className="w-full py-14 sm:py-18 text-slate-950"
          style={{ backgroundColor: brandAccent }}
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
              <div>
                <h3 className="text-2xl sm:text-4xl font-black uppercase tracking-tight">
                  Ready to Reach Your Goals at {data.name}?
                </h3>
                <p className="text-slate-950 font-semibold text-sm sm:text-base mt-1">
                  Register online and receive your instant digital entrance pass.
                </p>
              </div>
              <Link
                to="/register"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-black uppercase tracking-wider bg-slate-950 text-white hover:bg-slate-900 shadow-xl transition min-h-[50px]"
              >
                <span>Register Online</span>
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Modern Carbon Dark Footer */}
      <footer className="w-full bg-[#05070D] border-t border-slate-800/80 py-12">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 space-y-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-6 border-b border-slate-800/80">
            <div className="flex items-center gap-3">
              {data.logo ? (
                <img
                  src={data.logo}
                  alt={`${data.name} logo`}
                  className="w-9 h-9 rounded-lg object-cover"
                />
              ) : (
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-slate-950 font-black text-sm"
                  style={{ backgroundColor: brandAccent }}
                >
                  {data.name.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <span className="text-lg font-black tracking-tight text-white block uppercase">
                  {data.name} Portal
                </span>
                <span className="text-xs text-slate-400">
                  {data.location || "Fitness Center"}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-6 text-sm font-semibold text-slate-400">
              <a href="#programs" className="hover:text-white transition py-1">
                Programs
              </a>
              <a href="#about" className="hover:text-white transition py-1">
                About
              </a>
              <a href="#plans" className="hover:text-white transition py-1">
                Plans &amp; Pricing
              </a>
              <Link to="/login" className="hover:text-white transition py-1">
                Log in
              </Link>
              <Link to="/register" className="hover:text-white transition py-1">
                Register
              </Link>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div>
              &copy; {new Date().getFullYear()} {data.name}. Powered by FitGate Platform.
            </div>
            <div className="flex items-center gap-6">
              <span>Dynamic QR Check-in</span>
              <span>Telebirr &bull; CBE Birr &bull; Chapa</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
