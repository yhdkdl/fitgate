import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Building2,
  CalendarCheck,
  Check,
  CreditCard,
  Dumbbell,
  ExternalLink,
  QrCode,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { PLATFORM_PRICING_TIERS } from "../config/platformPricing";
import { buildTenantUrl, validateSubdomain } from "../utils/tenant";

export const LandingScreen: React.FC = () => {
  const [gymSubdomain, setGymSubdomain] = useState("");
  const [gymError, setGymError] = useState<string | null>(null);

  // SEO: Update page title and meta description
  useEffect(() => {
    document.title = "FitGate — All-in-One Gym Operating System";
    let metaDesc = document.querySelector('meta[name="description"]');
    const prevDesc = metaDesc ? metaDesc.getAttribute("content") : null;
    const descriptionText =
      "FitGate is the all-in-one gym management operating system for Ethiopian fitness centers. Streamline membership management, QR check-in, attendance, trainer tools, and online payments.";

    if (!metaDesc) {
      metaDesc = document.createElement("meta");
      metaDesc.setAttribute("name", "description");
      document.head.appendChild(metaDesc);
    }
    metaDesc.setAttribute("content", descriptionText);

    return () => {
      if (prevDesc !== null && metaDesc) {
        metaDesc.setAttribute("content", prevDesc);
      }
    };
  }, []);

  const handleGoToGym = (e: React.FormEvent) => {
    e.preventDefault();
    setGymError(null);

    const validation = validateSubdomain(gymSubdomain);
    if (!validation.valid || !validation.subdomain) {
      setGymError(
        validation.error ||
          "Please enter a valid gym subdomain (letters, numbers, and hyphens only)."
      );
      return;
    }

    const destinationUrl = buildTenantUrl(validation.subdomain);
    if (typeof window !== "undefined") {
      window.location.assign(destinationUrl);
    }
  };

  // Preview helper for apex/port display
  const currentHost =
    typeof window !== "undefined" ? window.location.hostname : "localhost";
  const currentPort =
    typeof window !== "undefined" && window.location.port
      ? `:${window.location.port}`
      : "";
  const domainPreview =
    currentHost === "localhost" || currentHost === "127.0.0.1"
      ? `.localhost${currentPort}`
      : `.${currentHost}${currentPort}`;

  return (
    <div className="min-h-screen bg-bg text-text selection:bg-primary selection:text-white flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="sticky top-0 z-40 bg-surface/90 backdrop-blur border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 sm:h-20 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-3 text-text hover:text-primary transition-colors focus-visible:ring-2 focus-visible:ring-ring rounded-lg p-1"
            aria-label="FitGate Platform Home"
          >
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center text-white shadow-md shadow-primary/20">
              <Dumbbell className="w-6 h-6" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight block leading-tight">
                FitGate
              </span>
              <span className="text-xs text-text-muted font-normal block leading-tight">
                Gym Operating System
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav
            aria-label="Platform navigation"
            className="hidden md:flex items-center gap-6 text-sm text-text-muted"
          >
            <a
              href="#features"
              className="hover:text-text transition-colors py-2 focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              className="hover:text-text transition-colors py-2 focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              How It Works
            </a>
            <a
              href="#pricing"
              className="hover:text-text transition-colors py-2 focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              Pricing
            </a>
            <a
              href="#find-gym"
              className="hover:text-text transition-colors py-2 focus-visible:ring-2 focus-visible:ring-ring rounded"
            >
              Go to My Gym
            </a>
          </nav>

          {/* Action Button */}
          <div className="flex items-center gap-3">
            <Link
              to="/request-demo"
              className="inline-flex items-center justify-center px-4 py-2 text-sm font-semibold text-white bg-primary hover:bg-primary-hover active:bg-primary-hover rounded-xl shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring min-h-[44px]"
            >
              Request a Demo
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden py-16 sm:py-24 border-b border-border/40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mx-auto text-center">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-2 border border-border text-xs text-primary font-medium mb-6">
                <Sparkles className="w-4 h-4" />
                <span>Purpose-Built for Ethiopian Fitness Centers</span>
              </div>
              <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-text leading-tight sm:leading-tight mb-6">
                The Modern All-in-One Operating System for Gyms
              </h1>
              <p className="text-base sm:text-lg text-text-muted leading-relaxed mb-8">
                Replace paper attendance registers, unverified member access,
                and manual cash tracking with FitGate. Equip trainers, automate
                QR check-ins, generate AI workout plans, and accept digital
                payments under your gym&apos;s own dedicated web address.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  to="/request-demo"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 text-base font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl shadow-lg shadow-primary/25 transition-all focus-visible:ring-2 focus-visible:ring-ring min-h-[44px]"
                >
                  Request a Demo
                  <ArrowRight className="w-5 h-5" />
                </Link>
                <a
                  href="#find-gym"
                  className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 text-base font-semibold text-text bg-surface-2 hover:bg-surface border border-border rounded-xl transition-colors focus-visible:ring-2 focus-visible:ring-ring min-h-[44px]"
                >
                  Go to My Gym
                  <ExternalLink className="w-4 h-4 text-text-muted" />
                </a>
              </div>
            </div>

            {/* Quick Feature Highlights Banner */}
            <div className="mt-12 sm:mt-16 grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 max-w-4xl mx-auto text-center">
              <div className="bg-surface border border-border rounded-card p-4">
                <QrCode className="w-6 h-6 text-primary mx-auto mb-2" />
                <div className="text-sm font-semibold text-text">
                  QR Check-In
                </div>
                <div className="text-xs text-text-muted">
                  Instant validation
                </div>
              </div>
              <div className="bg-surface border border-border rounded-card p-4">
                <Users className="w-6 h-6 text-primary mx-auto mb-2" />
                <div className="text-sm font-semibold text-text">
                  Trainer Tools
                </div>
                <div className="text-xs text-text-muted">
                  Body metrics & logs
                </div>
              </div>
              <div className="bg-surface border border-border rounded-card p-4">
                <CreditCard className="w-6 h-6 text-primary mx-auto mb-2" />
                <div className="text-sm font-semibold text-text">
                  Chapa & Cash
                </div>
                <div className="text-xs text-text-muted">
                  Telebirr & CBE Birr
                </div>
              </div>
              <div className="bg-surface border border-border rounded-card p-4">
                <Building2 className="w-6 h-6 text-primary mx-auto mb-2" />
                <div className="text-sm font-semibold text-text">
                  Multi-Branch
                </div>
                <div className="text-xs text-text-muted">Unified network</div>
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section
          id="features"
          className="py-16 sm:py-24 border-b border-border/40"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-text mb-3">
                Everything You Need to Run Your Gym
              </h2>
              <p className="text-text-muted text-base">
                FitGate brings your entire facility onto a unified, secure cloud
                platform designed specifically for Ethiopian fitness operations.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {/* Feature 1: Membership Management */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <CalendarCheck className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Membership Management
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Easily create customized membership plans, register new
                  members at the front desk or self-service, monitor
                  expirations, and handle membership freeze requests smoothly.
                </p>
              </div>

              {/* Feature 2: Contactless QR Check-In */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <QrCode className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  QR Check-in & Attendance
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Eliminate manual sign-in books with dynamic QR passes.
                  Front-desk reception scans member codes in seconds, verifies
                  active subscription status, and prevents unauthorized entry.
                </p>
              </div>

              {/* Feature 3: Trainer Tools */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <Dumbbell className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Trainer Tools & Body Metrics
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Empower trainers with client rosters and standardized body
                  measurement tracking (weight, height, waist, neck, hip) to
                  professionally record progress and calculate estimates.
                </p>
              </div>

              {/* Feature 4: AI Personal Training Plans */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <Bot className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  AI Personal Training Plans
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Generate customized workout plans based on individual member
                  goals, equipment, and medical background, certified and
                  approved by professional gym trainers before delivery.
                </p>
              </div>

              {/* Feature 5: Integrated Payments */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <CreditCard className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Online & Manual Payments
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Accept seamless digital payments via Chapa supporting
                  Telebirr, CBE Birr, and cards, alongside verified manual cash
                  recording with full audit logs and receipt tracking.
                </p>
              </div>

              {/* Feature 6: Multi-Branch Management */}
              <div className="bg-surface border border-border rounded-card p-6 flex flex-col">
                <div className="w-12 h-12 rounded-xl bg-surface-2 border border-border flex items-center justify-center text-primary mb-4">
                  <Building2 className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Multi-Branch Gym Networks
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Operate multiple gym facilities under one unified domain.
                  Configure branch-scoped staff accounts and offer all-access
                  plans allowing members to roam across locations seamlessly.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section */}
        <section
          id="how-it-works"
          className="py-16 sm:py-24 bg-surface/50 border-b border-border/40"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-text mb-3">
                How It Works
              </h2>
              <p className="text-text-muted text-base">
                Getting started with FitGate is simple, guided, and requires
                zero hardware installation or software maintenance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
              {/* Step 1 */}
              <div className="bg-surface border border-border rounded-card p-6 relative flex flex-col">
                <div className="w-10 h-10 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center mb-4 text-base border border-primary/30">
                  1
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Request a Demo
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Submit your gym name, location, and contact information. Our
                  team will walk you through the platform and help you select
                  the right tier for your gym.
                </p>
              </div>

              {/* Step 2 */}
              <div className="bg-surface border border-border rounded-card p-6 relative flex flex-col">
                <div className="w-10 h-10 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center mb-4 text-base border border-primary/30">
                  2
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Setup After Payment
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Upon bank transfer payment confirmation, Super Admin
                  provisions your isolated tenant database, sets up your
                  branding and branches, and issues your owner access
                  credentials.
                </p>
              </div>

              {/* Step 3 */}
              <div className="bg-surface border border-border rounded-card p-6 relative flex flex-col">
                <div className="w-10 h-10 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center mb-4 text-base border border-primary/30">
                  3
                </div>
                <h3 className="text-lg font-semibold text-text mb-2">
                  Your Gym Gets Its Own Address
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  Your gym launches at its dedicated web address (e.g.,{" "}
                  <code className="text-xs bg-surface-2 px-1 py-0.5 rounded text-text">
                    yourgym.fitgate.tebebtech.com
                  </code>
                  ). Members and staff sign in right away from any phone,
                  tablet, or PC.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section
          id="pricing"
          className="py-16 sm:py-24 border-b border-border/40"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-text mb-3">
                Simple, Predictable Yearly Pricing
              </h2>
              <p className="text-text-muted text-base">
                All plans are billed yearly in Ethiopian Birr. Includes cloud
                hosting, SSL security, regular automated backups, and support.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 max-w-4xl mx-auto gap-8 items-stretch">
              {PLATFORM_PRICING_TIERS.filter((tier) => tier.id !== "pro").map((tier) => {
                const isPopular = tier.popular;
                return (
                  <div
                    key={tier.id}
                    className={`rounded-card p-6 sm:p-8 flex flex-col justify-between transition-all ${
                      isPopular
                        ? "bg-surface-2 border-2 border-primary shadow-xl shadow-primary/10 relative"
                        : "bg-surface border border-border"
                    }`}
                  >
                    <div>
                      {tier.badge && (
                        <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-primary/20 text-primary border border-primary/30 mb-4">
                          {tier.badge}
                        </span>
                      )}
                      <h3 className="text-2xl font-bold text-text mb-1">
                        {tier.name}
                      </h3>
                      <p className="text-sm text-text-muted mb-6">
                        {tier.tagline}
                      </p>

                      <div className="mb-6 pb-6 border-b border-border">
                        <span className="text-3xl sm:text-4xl font-extrabold text-text">
                          {tier.pricePerYearETB.toLocaleString()}
                        </span>
                        <span className="text-text-muted text-sm ml-2">
                          ETB / year
                        </span>
                        <div className="text-xs text-text-muted mt-1">
                          Placeholder pricing · Billed annually
                        </div>
                      </div>

                      <div className="space-y-3 mb-8">
                        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                          What&apos;s Included
                        </div>
                        {tier.features.map((feature, idx) => (
                          <div
                            key={idx}
                            className="flex items-start gap-2.5 text-sm"
                          >
                            {feature.included ? (
                              <Check className="w-4 h-4 text-success shrink-0 mt-0.5" />
                            ) : (
                              <X className="w-4 h-4 text-text-muted/40 shrink-0 mt-0.5" />
                            )}
                            <span
                              className={
                                feature.included
                                  ? "text-text"
                                  : "text-text-muted/60"
                              }
                            >
                              {feature.name}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <Link
                        to="/request-demo"
                        className={`w-full inline-flex items-center justify-center px-4 py-3 text-sm font-semibold rounded-xl transition-colors focus-visible:ring-2 focus-visible:ring-ring min-h-[44px] ${
                          isPopular
                            ? "bg-primary text-white hover:bg-primary-hover shadow-md shadow-primary/20"
                            : "bg-surface-2 text-text hover:bg-border border border-border"
                        }`}
                      >
                        Request a Demo
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* "Go to My Gym" Box Section */}
        <section
          id="find-gym"
          className="py-16 sm:py-24 bg-surface/30 border-b border-border/40"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-xl mx-auto bg-surface border border-border rounded-card p-6 sm:p-10 shadow-lg">
              <div className="text-center mb-6">
                <div className="w-12 h-12 rounded-xl bg-primary/20 text-primary mx-auto flex items-center justify-center mb-3">
                  <Building2 className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-bold text-text mb-2">
                  Go to My Gym
                </h2>
                <p className="text-sm text-text-muted">
                  Already using FitGate? Type your gym&apos;s subdomain name to
                  jump straight to your member or staff portal.
                </p>
              </div>

              <form onSubmit={handleGoToGym} className="space-y-4">
                <div>
                  <label
                    htmlFor="gym-subdomain-input"
                    className="block text-sm font-medium text-text mb-1"
                  >
                    Gym Subdomain
                  </label>
                  <div className="flex rounded-input shadow-sm border border-border focus-within:ring-2 focus-within:ring-ring bg-surface-2">
                    <span className="inline-flex items-center px-3 rounded-l-input text-text-muted text-xs select-none">
                      https://
                    </span>
                    <input
                      id="gym-subdomain-input"
                      type="text"
                      maxLength={63}
                      value={gymSubdomain}
                      onChange={(e) => {
                        setGymSubdomain(e.target.value);
                        if (gymError) setGymError(null);
                      }}
                      placeholder="e.g. bolehub"
                      aria-invalid={!!gymError}
                      aria-describedby={
                        gymError ? "gym-subdomain-error" : undefined
                      }
                      className="block w-full min-w-0 flex-1 border-0 bg-transparent py-2.5 px-3 text-text placeholder-text-muted/60 text-sm focus:ring-0 focus:outline-none min-h-[44px]"
                      aria-label="Gym Subdomain"
                    />
                    <span className="inline-flex items-center px-3 rounded-r-input text-text-muted text-xs select-none bg-surface border-l border-border">
                      {domainPreview}
                    </span>
                  </div>
                </div>

                {gymError && (
                  <div
                    id="gym-subdomain-error"
                    role="alert"
                    className="p-3 text-sm rounded-lg bg-danger/10 border border-danger/30 text-danger flex items-center gap-2"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{gymError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-3 text-sm font-semibold text-white bg-primary hover:bg-primary-hover active:bg-primary-hover rounded-xl shadow transition-colors focus-visible:ring-2 focus-visible:ring-ring min-h-[44px]"
                >
                  Go to Gym
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-surface border-t border-border py-8 sm:py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2 text-text font-bold text-lg">
              <Dumbbell className="w-5 h-5 text-primary" />
              <span>FitGate</span>
              <span className="text-xs text-text-muted font-normal ml-2">
                All-in-One Gym Operating System
              </span>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-text-muted">
              <a
                href="#features"
                className="hover:text-text transition-colors py-2"
              >
                Features
              </a>
              <a
                href="#how-it-works"
                className="hover:text-text transition-colors py-2"
              >
                How It Works
              </a>
              <a
                href="#pricing"
                className="hover:text-text transition-colors py-2"
              >
                Pricing
              </a>
              <Link
                to="/request-demo"
                className="hover:text-text transition-colors py-2"
              >
                Request a Demo
              </Link>
              {/* Discreet Platform Sign In link for Super Admin */}
              <Link
                to="/login"
                className="text-text-muted/80 hover:text-text underline text-xs py-2 focus-visible:ring-2 focus-visible:ring-ring rounded"
                aria-label="Platform sign in"
              >
                Platform sign in
              </Link>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-border/60 text-center text-xs text-text-muted">
            © 2026 FitGate Platform. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};
