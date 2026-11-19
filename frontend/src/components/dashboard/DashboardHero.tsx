import React from "react";
import { Link } from "react-router-dom";
import Antigravity from "../ui/Antigravity";
import { useAuth } from "../../context/AuthContext";

interface DashboardHeroProps {
  gymName?: string;
  tenant?: string | null;
  brandColor?: string | null;
  className?: string;
}

export const DashboardHero: React.FC<DashboardHeroProps> = ({
  gymName,
  tenant,
  brandColor,
  className = "",
}) => {
  const { user } = useAuth();
  const role = user?.role;

  // React Bits Signature Palette integrated with dynamic gym brand color
  const heroColors = brandColor
    ? [brandColor, "#5227FF", "#FF9FFC", "#B497CF"]
    : ["#5227FF", "#FF9FFC", "#B497CF"];

  const getRoleLabel = () => {
    switch (role) {
      case "super_admin":
        return "Platform Command Center";
      case "owner":
        return "Gym Performance Hub";
      case "manager":
        return "Daily Floor Operations";
      case "trainer":
        return "Performance Analytics";
      case "reception":
        return "Front Desk Terminal";
      case "member":
        return "Digital Member Pass";
      default:
        return "Intelligent Operating System";
    }
  };

  const getSubheading = () => {
    switch (role) {
      case "super_admin":
        return "Real-time telemetry, multi-tenant directory, and platform governance across all provisioned Ethiopian fitness centers.";
      case "owner":
        return "Monitor real-time gym floor attendance, membership health, automated Chapa payments, and financial performance.";
      case "manager":
        return "Keep day-to-day check-ins, staff coordination, and member queries running seamlessly with zero friction.";
      case "trainer":
        return "Review AI training drafts, record client body composition metrics, and track weekly workout progress.";
      case "reception":
        return "Rapid QR badge scanner, payment receipt issuance, and instant entrance verification.";
      case "member":
        return "Your 90-second dynamic QR badge, active membership status, and tailored workout programs.";
      default:
        return "Streamline fitness center operations with automated billing, biometric check-in, and real-time telemetry.";
    }
  };

  const primaryAccent = brandColor || "#5227FF";

  return (
    <div
      style={{ width: "100%", height: "400px", position: "relative" }}
      className={`w-full overflow-hidden bg-white ${className}`}
    >
      {/* Background Interactive Antigravity Canvas from React Bits (Full width to sidebar) */}
      <div className="absolute inset-0 z-0 pointer-events-auto">
        <Antigravity
          colors={heroColors}
          count={1500}
          magnetRadius={9}
          ringRadius={7}
          particleSize={0.9}
          autoAnimate={true}
          interactive={true}
          clickBurst={true}
          lightMode={true}
        />
      </div>

      {/* Foreground Hero Content Spanning Full Width until Sidebar */}
      <div className="relative z-10 w-full h-full px-6 sm:px-10 py-6 sm:py-8 flex flex-col justify-between pointer-events-none select-none">
        {/* Top Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-3 pointer-events-auto">
          <div className="flex items-center gap-2.5">
            <span
              className="inline-flex items-center px-3.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider text-white shadow-xs"
              style={{ backgroundColor: primaryAccent }}
            >
              {role === "super_admin"
                ? "FITGATE PLATFORM"
                : (gymName || tenant || "FITGATE GYM").toUpperCase()}
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-200 shadow-2xs">
              {getRoleLabel()}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              LIVE TELEMETRY
            </span>
          </div>
        </div>

        {/* Center Headline & Content */}
        <div className="my-auto py-2 max-w-3xl pointer-events-none">
          <div className="inline-flex items-center gap-2 text-[11px] font-bold tracking-widest uppercase text-slate-500 mb-2 px-2.5 py-0.5 rounded-md bg-slate-100 border border-slate-200 pointer-events-auto shadow-2xs">
            <span>React Bits Particle Engine</span>
            <span>&bull;</span>
            <span>1500 Interactive Vectors</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 drop-shadow-xs leading-tight">
            {user
              ? `Welcome back, ${user.full_name || user.email.split("@")[0]}!`
              : `Welcome to ${gymName || "FitGate Platform"}`}
          </h1>
          <p className="mt-2 text-sm sm:text-base font-medium text-slate-600 leading-relaxed max-w-2xl">
            {getSubheading()}
          </p>
        </div>

        {/* Bottom Actions and Status Badges */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 pointer-events-auto">
          {/* Quick Context Pills */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold bg-slate-50 text-slate-800 border border-slate-200 shadow-2xs">
              Role: <span className="ml-1 text-slate-900 font-bold capitalize">{role || "Guest"}</span>
            </span>
            {tenant && (
              <span className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold bg-slate-50 text-slate-800 border border-slate-200 shadow-2xs">
                Subdomain: <span className="ml-1 text-slate-900 font-mono">{tenant}.fitgate</span>
              </span>
            )}
            <span className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs">
              Full Width Canvas Active
            </span>
          </div>

          {/* Quick Role-Specific Navigation Buttons */}
          <div className="flex items-center gap-2">
            {role === "super_admin" && (
              <Link
                to="/platform/demo-requests"
                className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition shadow-xs"
              >
                Demo Requests
              </Link>
            )}
            {role === "owner" && (
              <Link
                to="/members"
                className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition shadow-xs"
              >
                Manage Members
              </Link>
            )}
            {role === "manager" && (
              <Link
                to="/check-in"
                className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition shadow-xs"
              >
                Front Desk Scanner
              </Link>
            )}
            {role === "trainer" && (
              <Link
                to="/my-clients"
                className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition shadow-xs"
              >
                My Clients
              </Link>
            )}
            {role === "member" && (
              <Link
                to="/profile"
                className="inline-flex items-center px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 transition shadow-xs"
              >
                My Profile
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardHero;
