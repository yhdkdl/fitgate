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
  Flame,
  QrCode,
  ShieldCheck,
  Star,
  Users,
  X,
  Zap,
} from "lucide-react";
import { PLATFORM_PRICING_TIERS } from "../config/platformPricing";
import { buildTenantUrl, validateSubdomain } from "../utils/tenant";
import LightRays from "../components/ui/LightRays";

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
    <div className="min-h-screen bg-[#070A11] text-slate-100 selection:bg-[#A3E635] selection:text-slate-950 flex flex-col font-sans w-full overflow-x-hidden">
      {/* Top Utility Announcement Ribbon - Full Width */}
      <div className="w-full bg-[#0D1424] border-b border-slate-800/80 px-4 sm:px-8 lg:px-12 py-2.5 text-xs text-slate-400">
        <div className="w-full max-w-[1600px] mx-auto flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-[#A3E635] animate-pulse" />
              <span>Addis Ababa, Ethiopia</span>
            </span>
            <span className="hidden sm:inline-block text-slate-600">&bull;</span>
            <span className="hidden sm:inline-block">Tel: +251 911 223 344</span>
            <span className="hidden md:inline-block text-slate-600">&bull;</span>
            <span className="hidden md:inline-block">Chapa, Telebirr &amp; CBE Birr Integrated</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-[#A3E635] font-semibold">RFC 6761 Multi-Tenant Engine</span>
            <Link
              to="/request-demo"
              className="text-white hover:text-[#A3E635] transition font-bold"
            >
              Book Setup &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Main Sticky Header - Full Width */}
      <header className="sticky top-0 z-40 bg-[#070A11]/95 backdrop-blur-md border-b border-slate-800/80 w-full">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 h-20 flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-3 text-white hover:text-[#A3E635] transition-colors focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded-lg p-1"
            aria-label="FitGate Platform Home"
          >
            <div className="w-11 h-11 rounded-xl bg-[#A3E635] flex items-center justify-center text-slate-950 font-black shadow-lg shadow-[#A3E635]/20">
              <Dumbbell className="w-6 h-6 stroke-[2.5]" />
            </div>
            <div>
              <span className="text-2xl font-black tracking-tight block leading-tight text-white">
                FIT<span className="text-[#A3E635]">GATE</span>
              </span>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block leading-tight">
                Gym Operating System
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav
            aria-label="Platform navigation"
            className="hidden md:flex items-center gap-8 text-sm font-semibold tracking-wide text-slate-300"
          >
            <a
              href="#features"
              className="hover:text-[#A3E635] transition-colors py-2 focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded"
            >
              Features
            </a>
            <a
              href="#how-it-works"
              className="hover:text-[#A3E635] transition-colors py-2 focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded"
            >
              How It Works
            </a>
            <a
              href="#pricing"
              className="hover:text-[#A3E635] transition-colors py-2 focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded"
            >
              Pricing
            </a>
            <a
              href="#find-gym"
              className="hover:text-[#A3E635] transition-colors py-2 focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded"
            >
              Go to My Gym
            </a>
          </nav>

          {/* Action Button */}
          <div className="flex items-center gap-3">
            <Link
              to="/request-demo"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-extrabold uppercase tracking-wider text-slate-950 bg-[#A3E635] hover:bg-[#BEF264] active:bg-[#A3E635] rounded-xl shadow-lg shadow-[#A3E635]/25 transition-all focus-visible:ring-2 focus-visible:ring-[#A3E635] min-h-[44px]"
            >
              <span>Request a Demo</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full">
        {/* Hero Section with React Bits <LightRays /> Background - Full Width */}
        <section className="relative overflow-hidden w-full border-b border-slate-800/80 bg-[#070A11] min-h-[85vh] flex flex-col justify-center">
          {/* Background: WebGL2 LightRays & Atmospheric Glows */}
          <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
            <LightRays
              raysOrigin="top-center"
              raysColor="#A3E635"
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
              opacity={0.8}
            />
            {/* Ambient gradients to blend seamlessly into carbon obsidian */}
            <div className="absolute inset-0 bg-gradient-to-t from-[#070A11] via-transparent to-black/30 pointer-events-none" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#070A11]/40 to-[#070A11] pointer-events-none" />
          </div>

          {/* Foreground Hero Content */}
          <div className="relative z-10 w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 py-16 sm:py-24">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
              {/* Left Column: Powerful Copy */}
              <div className="lg:col-span-7 space-y-6">
                <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#A3E635]/10 border border-[#A3E635]/30 text-xs font-bold uppercase tracking-wider text-[#A3E635]">
                  <Flame className="w-4 h-4" />
                  <span>Train Hard. Operate Smarter.</span>
                </div>

                <h1 className="text-4xl sm:text-6xl xl:text-7xl font-black tracking-tight text-white uppercase leading-[1.06]">
                  The Modern All-in-One{" "}
                  <span className="text-[#A3E635]">Operating System</span> for Gyms
                </h1>

                <p className="text-base sm:text-lg text-slate-300/90 font-normal leading-relaxed max-w-2xl">
                  Replace paper attendance registers, unverified member access,
                  and manual cash tracking with FitGate. Equip trainers, automate
                  QR check-ins, generate AI workout plans, and accept digital
                  payments under your gym&apos;s own dedicated web address.
                </p>

                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-2">
                  <Link
                    to="/request-demo"
                    className="inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-extrabold uppercase tracking-wider text-slate-950 bg-[#A3E635] hover:bg-[#BEF264] rounded-xl shadow-xl shadow-[#A3E635]/30 transition-all focus-visible:ring-2 focus-visible:ring-[#A3E635] min-h-[50px]"
                  >
                    <span>Request a Demo</span>
                    <ArrowRight className="w-5 h-5" />
                  </Link>

                  <a
                    href="#find-gym"
                    className="inline-flex items-center justify-center gap-2 px-8 py-4 text-base font-bold text-white bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 hover:border-slate-500 rounded-xl transition-all focus-visible:ring-2 focus-visible:ring-[#A3E635] min-h-[50px] backdrop-blur-xs"
                  >
                    <span>Go to My Gym</span>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                </div>

                {/* Key Pillars */}
                <div className="pt-6 grid grid-cols-3 gap-6 border-t border-slate-800/80 max-w-xl">
                  <div>
                    <div className="text-2xl sm:text-4xl font-black text-white">99.9%</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      System Uptime
                    </div>
                  </div>
                  <div>
                    <div className="text-2xl sm:text-4xl font-black text-[#A3E635]">2.4s</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      QR Entry Speed
                    </div>
                  </div>
                  <div>
                    <div className="text-2xl sm:text-4xl font-black text-white">100%</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-1">
                      Audit-Proof
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Athletic Hero Graphic with Floating Cards & Vertical Highlights */}
              <div className="lg:col-span-5 relative">
                <div className="relative mx-auto max-w-lg lg:max-w-none">
                  {/* Outer Glow Ring */}
                  <div className="absolute -inset-2 bg-gradient-to-tr from-[#A3E635]/30 to-blue-500/20 rounded-3xl blur-2xl opacity-75" />

                  {/* Main Hero Athletic Image */}
                  <div className="relative rounded-2xl overflow-hidden border border-slate-800 bg-slate-900 shadow-2xl">
                    <img
                      src="https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80"
                      alt="Athletic Gym Performance"
                      className="w-full h-[460px] object-cover object-center filter brightness-95 contrast-105"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#070A11] via-transparent to-black/30" />

                    {/* Integrated Right-Side Highlight Pillars (Reflected from reference UI) */}
                    <div className="absolute bottom-4 right-4 left-4 p-4 rounded-xl bg-slate-950/80 backdrop-blur-md border border-slate-800/90 grid grid-cols-2 gap-3 text-left">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center shrink-0">
                          <Users className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white uppercase tracking-wider">
                            Trainer Tools
                          </div>
                          <div className="text-[10px] text-slate-400">Rosters &amp; Metrics</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center shrink-0">
                          <Bot className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="text-xs font-bold text-white uppercase tracking-wider">
                            AI Ethiopian
                          </div>
                          <div className="text-[10px] text-slate-400">Personalized Plans</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Floating Micro-Card 1: Dynamic QR Badge */}
                  <div className="absolute -top-4 -left-4 sm:-left-6 bg-slate-900/95 border border-slate-700/80 rounded-xl p-3.5 shadow-2xl backdrop-blur-md flex items-center gap-3 max-w-[240px]">
                    <div className="w-10 h-10 rounded-lg bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center shrink-0 border border-[#A3E635]/40">
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

                  {/* Floating Micro-Card 2: Digital Telebirr & Chapa */}
                  <div className="absolute -top-4 -right-4 sm:-right-6 bg-slate-900/95 border border-slate-700/80 rounded-xl p-3.5 shadow-2xl backdrop-blur-md flex items-center gap-3 max-w-[260px]">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/40">
                      <CreditCard className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white uppercase tracking-wider">
                        Chapa &amp; Telebirr
                      </div>
                      <div className="text-[11px] text-slate-400 font-medium">
                        Zero manual reconciliation
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Full-Width 4-Item Feature Strip (Directly Inspired by Reference UI) */}
        <div className="w-full bg-[#0B101C] border-b border-slate-800/80 py-6">
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-[#A3E635]/40 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-[#A3E635]/15 text-[#A3E635] flex items-center justify-center shrink-0">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  RFC 6761 Subdomains
                </div>
                <div className="text-xs text-slate-400">
                  Dedicated web address
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-[#A3E635]/40 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-[#A3E635]/15 text-[#A3E635] flex items-center justify-center shrink-0">
                <Zap className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Offline-First Gate
                </div>
                <div className="text-xs text-slate-400">
                  Zero queue bottlenecks
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-[#A3E635]/40 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-[#A3E635]/15 text-[#A3E635] flex items-center justify-center shrink-0">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  AI Ethiopian Plans
                </div>
                <div className="text-xs text-slate-400">
                  Custom nutrition &amp; lifts
                </div>
              </div>
            </div>

            <div className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex items-center gap-3.5 hover:border-[#A3E635]/40 transition-colors">
              <div className="w-10 h-10 rounded-lg bg-[#A3E635]/15 text-[#A3E635] flex items-center justify-center shrink-0">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <div className="text-sm font-bold text-white uppercase tracking-wider">
                  Multi-Branch Ready
                </div>
                <div className="text-xs text-slate-400">
                  Seamless member roaming
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Features Section: Spec §1 & §3 with Athletic Images - Full Width Flow */}
        <section
          id="features"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-bold uppercase tracking-widest text-[#A3E635] block mb-2">
                Core Gym Management Suite
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                Everything You Need to Run Your Gym
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                FitGate brings your entire facility onto a unified, secure cloud
                platform designed specifically for Ethiopian fitness operations.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {/* Feature 1: Membership Management */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1571902943202-507ec2618e8f?auto=format&fit=crop&w=800&q=80"
                      alt="Gym Membership Management"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <CalendarCheck className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      Membership Management
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Easily create customized membership plans, register new
                      members at the front desk or self-service, monitor
                      expirations, and handle membership freeze requests smoothly.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Manage Plans &amp; Expiries</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>

              {/* Feature 2: Contactless QR Check-In */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
                      alt="QR Check-in Turnstile"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <QrCode className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      QR Check-in &amp; Attendance
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Eliminate manual sign-in books with dynamic QR passes.
                      Front-desk reception scans member codes in seconds, verifies
                      active subscription status, and prevents unauthorized entry.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Offline-First Gate Engine</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>

              {/* Feature 3: Trainer Tools */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=800&q=80"
                      alt="Personal Trainer and Body Metrics"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <Dumbbell className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      Trainer Tools &amp; Body Metrics
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Empower trainers with client rosters and standardized body
                      measurement tracking (weight, height, waist, neck, hip) to
                      professionally record progress and calculate estimates.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Roster &amp; Metric Logs</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>

              {/* Feature 4: AI Personal Training Plans */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?auto=format&fit=crop&w=800&q=80"
                      alt="AI Personal Training Workouts"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <Bot className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      AI Personal Training Plans
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Generate customized workout plans based on individual member
                      goals, equipment, and medical background, certified and
                      approved by professional gym trainers before delivery.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Trainer-Approved AI</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>

              {/* Feature 5: Integrated Payments */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1556742049-0a67c5574f73?auto=format&fit=crop&w=800&q=80"
                      alt="Digital Payments Telebirr Chapa"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <CreditCard className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      Online &amp; Manual Payments
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Accept seamless digital payments via Chapa supporting
                      Telebirr, CBE Birr, and cards, alongside verified manual cash
                      recording with full audit logs and receipt tracking.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Cash, Chapa &amp; Banks</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>

              {/* Feature 6: Multi-Branch Management */}
              <div className="group bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden hover:border-[#A3E635]/50 transition-all shadow-xl flex flex-col justify-between">
                <div>
                  <div className="h-52 overflow-hidden relative">
                    <img
                      src="https://images.unsplash.com/photo-1540497077202-7c8a3999166f?auto=format&fit=crop&w=800&q=80"
                      alt="Multi Branch Gym Facilities"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 filter brightness-90"
                    />
                    <div className="absolute top-3 left-3 w-10 h-10 rounded-lg bg-black/70 backdrop-blur-xs flex items-center justify-center text-[#A3E635] border border-slate-700">
                      <Building2 className="w-5 h-5" />
                    </div>
                  </div>
                  <div className="p-6">
                    <h3 className="text-xl font-bold text-white mb-2 group-hover:text-[#A3E635] transition-colors">
                      Multi-Branch Gym Networks
                    </h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Operate multiple gym facilities under one unified domain.
                      Configure branch-scoped staff accounts and offer all-access
                      plans allowing members to roam across locations seamlessly.
                    </p>
                  </div>
                </div>
                <div className="px-6 pb-6">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#A3E635] uppercase tracking-wider">
                    <span>Centralized Governance</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Motivational Social Proof & Ethiopian Gym Stats - Full Width */}
        <section className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-gradient-to-r from-[#080C14] via-[#0E1524] to-[#080C14]">
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
              <div className="lg:col-span-6 relative">
                <div className="rounded-2xl overflow-hidden border border-slate-800 relative shadow-2xl">
                  <img
                    src="https://images.unsplash.com/photo-1517836357463-d25dfeac3438?auto=format&fit=crop&w=1000&q=80"
                    alt="Discipline Focus Strong Consistent"
                    className="w-full h-[400px] sm:h-[460px] object-cover object-center filter brightness-90"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent flex flex-col justify-end p-8 sm:p-10">
                    <span className="text-xs font-bold text-[#A3E635] uppercase tracking-widest mb-1.5">
                      Our Operating Manifesto
                    </span>
                    <div className="text-3xl sm:text-5xl font-black text-white uppercase tracking-tight leading-tight">
                      Discipline &bull; Focus &bull; Strong &bull; Consistent
                    </div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-6 space-y-6">
                <span className="text-xs font-bold uppercase tracking-widest text-[#A3E635] block">
                  Built for Serious Facility Operators
                </span>
                <h2 className="text-3xl sm:text-5xl font-black text-white uppercase leading-tight">
                  Trusted by Forward-Thinking Ethiopian Gym Owners
                </h2>
                <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
                  FitGate automates recurring membership sweeps, eliminates gate
                  fraud with dynamic 90-second QR codes, and delivers automated
                  Telegram broadcast sweeps to ensure zero revenue leakage.
                </p>

                <div className="grid grid-cols-2 gap-6 pt-6 border-t border-slate-800">
                  <div className="space-y-1">
                    <div className="text-3xl sm:text-4xl font-black text-white">150K+</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Check-ins Logged
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-3xl sm:text-4xl font-black text-[#A3E635]">12+</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Supported Ethiopian Banks
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-3xl sm:text-4xl font-black text-[#A3E635]">99.98%</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Platform Uptime
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-3xl sm:text-4xl font-black text-white">24/7</div>
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      Automated Telegram Alerts
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Member Testimonials & Real Owner Reviews (Peak Fitness Aesthetic) - Full Width */}
        <section className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]">
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-bold uppercase tracking-widest text-[#A3E635] block mb-2">
                Operational Track Record
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                What Our Gym Partners Say
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                See how fitness clubs across Addis Ababa transformed entrance gate speed and automated billing.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Review 1 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="flex items-center gap-1 text-[#A3E635] mb-4">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-[#A3E635]" />
                    ))}
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-6 italic">
                    &quot;FitGate completely transformed our front desk. The dynamic QR scanner cleared morning entrance bottlenecks and eliminated non-member access right from day one.&quot;
                  </p>
                </div>
                <div className="flex items-center gap-3 pt-4 border-t border-slate-800">
                  <div className="w-10 h-10 rounded-full bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center font-bold text-sm">
                    DM
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Dawit Mengistu</div>
                    <div className="text-xs text-slate-400">Owner, Bole Medhanialem Fitness</div>
                  </div>
                </div>
              </div>

              {/* Review 2 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="flex items-center gap-1 text-[#A3E635] mb-4">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-[#A3E635]" />
                    ))}
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-6 italic">
                    &quot;Telebirr, CBE Birr, and Chapa integration saved us countless hours of manual bank reconciliation. Cash receipts and digital settlements stay 100% auditable.&quot;
                  </p>
                </div>
                <div className="flex items-center gap-3 pt-4 border-t border-slate-800">
                  <div className="w-10 h-10 rounded-full bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center font-bold text-sm">
                    ST
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Selamawit Tadesse</div>
                    <div className="text-xs text-slate-400">Operations Manager, Kazanchis Hub</div>
                  </div>
                </div>
              </div>

              {/* Review 3 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="flex items-center gap-1 text-[#A3E635] mb-4">
                    {[...Array(5)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-[#A3E635]" />
                    ))}
                  </div>
                  <p className="text-sm text-slate-300 leading-relaxed mb-6 italic">
                    &quot;Our coaches actively log measurements and generate customized workout routines using the AI plan builder. Client engagement and retention rose noticeably.&quot;
                  </p>
                </div>
                <div className="flex items-center gap-3 pt-4 border-t border-slate-800">
                  <div className="w-10 h-10 rounded-full bg-[#A3E635]/20 text-[#A3E635] flex items-center justify-center font-bold text-sm">
                    MB
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">Michael Bekele</div>
                    <div className="text-xs text-slate-400">Head Trainer, Atlas Performance</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* How It Works Section - Full Width */}
        <section
          id="how-it-works"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-gradient-to-b from-[#070A11] via-[#0B101C] to-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-bold uppercase tracking-widest text-[#A3E635] block mb-2">
                Rapid Onboarding
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                How It Works
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                Getting started with FitGate is simple, guided, and requires
                zero hardware installation or software maintenance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Step 1 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 relative flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-[#A3E635]/15 text-[#A3E635] font-black flex items-center justify-center mb-6 text-xl border border-[#A3E635]/30">
                    1
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-3">
                    Request a Demo
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Submit your gym name, location, and contact information. Our
                    team will walk you through the platform and help you select
                    the right tier for your gym.
                  </p>
                </div>
                <div className="pt-6 mt-6 border-t border-slate-800/80">
                  <Link
                    to="/request-demo"
                    className="text-xs font-bold uppercase tracking-wider text-[#A3E635] hover:text-[#BEF264] flex items-center gap-1.5"
                  >
                    <span>Start Demo Intake</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>

              {/* Step 2 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 relative flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-[#A3E635]/15 text-[#A3E635] font-black flex items-center justify-center mb-6 text-xl border border-[#A3E635]/30">
                    2
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-3">
                    Setup After Payment
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Upon bank transfer payment confirmation, Super Admin
                    provisions your isolated tenant database, sets up your
                    branding and branches, and issues your owner access
                    credentials.
                  </p>
                </div>
                <div className="pt-6 mt-6 border-t border-slate-800/80">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Auto-Provisioned in &lt;15 Mins
                  </span>
                </div>
              </div>

              {/* Step 3 */}
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 relative flex flex-col justify-between hover:border-[#A3E635]/40 transition-all shadow-xl">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-[#A3E635]/15 text-[#A3E635] font-black flex items-center justify-center mb-6 text-xl border border-[#A3E635]/30">
                    3
                  </div>
                  <h3 className="text-2xl font-bold text-white mb-3">
                    Your Gym Gets Its Own Address
                  </h3>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    Your gym launches at its dedicated web address (e.g.,{" "}
                    <code className="text-xs bg-slate-950 px-2 py-0.5 rounded text-[#A3E635] font-mono border border-slate-800">
                      yourgym.fitgate.tebebtech.com
                    </code>
                    ). Members and staff sign in right away from any phone,
                    tablet, or PC.
                  </p>
                </div>
                <div className="pt-6 mt-6 border-t border-slate-800/80">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#A3E635]">
                    Custom White-Label Portal
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Section - Full Width */}
        <section
          id="pricing"
          className="w-full py-20 sm:py-28 border-b border-slate-800/80 bg-[#070A11]"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="text-center max-w-3xl mx-auto mb-16">
              <span className="text-xs font-bold uppercase tracking-widest text-[#A3E635] block mb-2">
                Transparent Subscriptions
              </span>
              <h2 className="text-3xl sm:text-5xl font-black tracking-tight text-white uppercase">
                Simple, Predictable Yearly Pricing
              </h2>
              <p className="text-slate-400 text-base sm:text-lg mt-3">
                All plans are billed yearly in Ethiopian Birr. Includes cloud
                hosting, SSL security, regular automated backups, and support.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 max-w-4xl mx-auto gap-8 items-stretch">
              {PLATFORM_PRICING_TIERS.filter((tier) => tier.id !== "pro").map(
                (tier) => {
                  const isPopular = tier.popular;
                  return (
                    <div
                      key={tier.id}
                      className={`rounded-2xl p-8 sm:p-10 flex flex-col justify-between transition-all ${isPopular
                          ? "bg-slate-900 border-2 border-[#A3E635] shadow-2xl shadow-[#A3E635]/15 relative"
                          : "bg-slate-900/80 border border-slate-800"
                        }`}
                    >
                      <div>
                        {tier.badge && (
                          <span className="inline-block px-3.5 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-[#A3E635] text-slate-950 mb-4 shadow-sm">
                            {tier.badge}
                          </span>
                        )}
                        <h3 className="text-3xl font-black text-white uppercase mb-1">
                          {tier.name}
                        </h3>
                        <p className="text-sm text-slate-400 mb-6">
                          {tier.tagline}
                        </p>

                        <div className="mb-6 pb-6 border-b border-slate-800">
                          <span className="text-4xl sm:text-5xl font-black text-white">
                            {tier.pricePerYearETB.toLocaleString()}
                          </span>
                          <span className="text-[#A3E635] font-bold text-sm ml-2 uppercase">
                            ETB / year
                          </span>
                          <div className="text-xs text-slate-500 mt-1">
                            Transparent yearly rate &bull; No hidden fees
                          </div>
                        </div>

                        <div className="space-y-3 mb-8">
                          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                            What&apos;s Included
                          </div>
                          {tier.features.map((feature, idx) => (
                            <div
                              key={idx}
                              className="flex items-start gap-2.5 text-sm"
                            >
                              {feature.included ? (
                                <Check className="w-4 h-4 text-[#A3E635] shrink-0 mt-0.5" />
                              ) : (
                                <X className="w-4 h-4 text-slate-600 shrink-0 mt-0.5" />
                              )}
                              <span
                                className={
                                  feature.included
                                    ? "text-slate-200"
                                    : "text-slate-500 line-through"
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
                          className={`w-full inline-flex items-center justify-center gap-2 px-6 py-4 text-sm font-extrabold uppercase tracking-wider rounded-xl transition-all focus-visible:ring-2 focus-visible:ring-[#A3E635] min-h-[48px] ${isPopular
                              ? "bg-[#A3E635] text-slate-950 hover:bg-[#BEF264] shadow-lg shadow-[#A3E635]/25"
                              : "bg-slate-800 text-white hover:bg-slate-700 border border-slate-700"
                            }`}
                        >
                          <span>Request a Demo</span>
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </div>
        </section>

        {/* "Go to My Gym" Box Section - Full Width */}
        <section
          id="find-gym"
          className="w-full py-20 sm:py-28 bg-[#070A11] border-b border-slate-800/80"
        >
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="max-w-xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 sm:p-10 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-[#A3E635]/5 rounded-bl-full pointer-events-none" />

              <div className="text-center mb-8">
                <div className="w-14 h-14 rounded-2xl bg-[#A3E635]/15 text-[#A3E635] mx-auto flex items-center justify-center mb-4 border border-[#A3E635]/30">
                  <Building2 className="w-7 h-7" />
                </div>
                <h2 className="text-2xl sm:text-3xl font-black text-white uppercase mb-2">
                  Go to My Gym
                </h2>
                <p className="text-sm text-slate-400">
                  Already using FitGate? Type your gym&apos;s subdomain name to
                  jump straight to your member or staff portal.
                </p>
              </div>

              <form onSubmit={handleGoToGym} className="space-y-4">
                <div>
                  <label
                    htmlFor="gym-subdomain-input"
                    className="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2"
                  >
                    Gym Subdomain
                  </label>
                  <div className="flex rounded-xl shadow-sm border border-slate-700 bg-slate-950 focus-within:ring-2 focus-within:ring-[#A3E635] overflow-hidden">
                    <span className="inline-flex items-center px-3.5 text-slate-400 text-xs font-mono select-none bg-slate-900/60 border-r border-slate-800">
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
                      className="block w-full min-w-0 flex-1 border-0 bg-transparent py-3 px-3.5 text-white placeholder-slate-500 text-sm focus:ring-0 focus:outline-none min-h-[44px]"
                      aria-label="Gym Subdomain"
                    />
                    <span className="inline-flex items-center px-3.5 text-slate-400 text-xs font-mono select-none bg-slate-900/60 border-l border-slate-800">
                      {domainPreview}
                    </span>
                  </div>
                </div>

                {gymError && (
                  <div
                    id="gym-subdomain-error"
                    role="alert"
                    className="p-3.5 text-sm rounded-xl bg-red-950/40 border border-red-500/30 text-red-300 flex items-center gap-2"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                    <span>{gymError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full inline-flex items-center justify-center gap-2 px-6 py-3.5 text-sm font-extrabold uppercase tracking-wider text-slate-950 bg-[#A3E635] hover:bg-[#BEF264] active:bg-[#A3E635] rounded-xl shadow-lg shadow-[#A3E635]/20 transition-all focus-visible:ring-2 focus-visible:ring-[#A3E635] min-h-[46px]"
                >
                  <span>Go to Gym</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            </div>
          </div>
        </section>

        {/* High-Impact Pre-Footer Banner - Full Width */}
        <section className="w-full bg-[#A3E635] py-14 sm:py-18 text-slate-950">
          <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
              <div>
                <h3 className="text-2xl sm:text-4xl font-black uppercase tracking-tight">
                  Ready to Elevate Your Fitness Center?
                </h3>
                <p className="text-slate-900 font-semibold text-sm sm:text-base mt-1">
                  Join leading Ethiopian gyms streamlining member check-in and automated billing today.
                </p>
              </div>
              <Link
                to="/request-demo"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-black uppercase tracking-wider bg-slate-950 text-white hover:bg-slate-900 shadow-xl transition-all min-h-[50px]"
              >
                <span>Request a Demo</span>
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Modern High-End Footer - Full Width */}
      <footer className="w-full bg-[#05070D] border-t border-slate-800/80 py-14">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-8 lg:px-12 space-y-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-8 border-b border-slate-800/80">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#A3E635] flex items-center justify-center text-slate-950 font-black">
                <Dumbbell className="w-5 h-5 stroke-[2.5]" />
              </div>
              <div>
                <span className="text-xl font-black tracking-tight text-white block">
                  FIT<span className="text-[#A3E635]">GATE</span>
                </span>
                <span className="text-xs text-slate-400">
                  All-in-One Gym Operating System
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-6 text-sm font-semibold text-slate-400">
              <a href="#features" className="hover:text-[#A3E635] transition-colors py-1">
                Features
              </a>
              <a href="#how-it-works" className="hover:text-[#A3E635] transition-colors py-1">
                How It Works
              </a>
              <a href="#pricing" className="hover:text-[#A3E635] transition-colors py-1">
                Pricing
              </a>
              <Link to="/request-demo" className="hover:text-[#A3E635] transition-colors py-1">
                Request a Demo
              </Link>
              {/* Discreet Platform Sign In link for Super Admin */}
              <Link
                to="/login"
                className="text-slate-500 hover:text-white underline text-xs py-1 focus-visible:ring-2 focus-visible:ring-[#A3E635] rounded"
                aria-label="Platform sign in"
              >
                Platform sign in
              </Link>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div>
              &copy; 2026 FitGate Platform. All rights reserved. Designed for Ethiopian Gyms.
            </div>
            <div className="flex items-center gap-6">
              <span>Security: RFC 6761 &bull; AutoSSL</span>
              <span>Payments: Chapa &bull; Telebirr &bull; CBE Birr</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
