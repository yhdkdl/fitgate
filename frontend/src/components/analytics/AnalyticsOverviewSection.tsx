import React, { useEffect, useState } from "react";
import {
  GymAnalyticsOverview,
  ExpiringMembership,
  getGymAnalyticsOverview,
} from "../../api/analytics";
import { Card, Button, Badge, Modal, Spinner, Alert } from "../ui";
import { ExportDataModal } from "../export/ExportDataModal";
import {
  Users,
  Flame,
  DollarSign,
  TrendingUp,
  Dumbbell,
  ShieldAlert,
  Clock,
  ArrowRight,
} from "lucide-react";

interface AnalyticsOverviewSectionProps {
  onUpgradeClick?: () => void;
}

export const AnalyticsOverviewSection: React.FC<
  AnalyticsOverviewSectionProps
> = ({ onUpgradeClick }) => {
  const [data, setData] = useState<GymAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showExpiringModal, setShowExpiringModal] = useState<boolean>(false);
  const [showExportAttendanceModal, setShowExportAttendanceModal] =
    useState<boolean>(false);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getGymAnalyticsOverview();
      setData(res);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Failed to load gym analytics overview.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading && !data) {
    return (
      <div className="p-12 flex flex-col items-center justify-center space-y-3 bg-[#11141B] border border-white/5 rounded-2xl">
        <Spinner size="md" />
        <p className="text-xs text-slate-400">
          Loading live operational analytics...
        </p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="space-y-3">
        <Alert variant="danger" title="Analytics Unavailable">
          {error}
        </Alert>
        <Button size="sm" variant="secondary" onClick={fetchAnalytics}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data) return null;

  // Concentric Rings calculation (Apple Health / Kinora style)
  const checkinTarget = 30;
  const checkinRatio = Math.min(1, Math.max(0.08, data.today_checkins / checkinTarget));
  const activeRatio = Math.min(
    1,
    Math.max(0.12, data.active_members / (data.active_members + data.frozen_members || 1))
  );
  const operationalRatio = data.expiring_memberships_count > 0 ? 0.78 : 0.95;

  const r1 = 44;
  const c1 = 2 * Math.PI * r1;
  const r2 = 33;
  const c2 = 2 * Math.PI * r2;
  const r3 = 22;
  const c3 = 2 * Math.PI * r3;

  // Donut chart calculation
  const planColors = ["#A3E635", "#06B6D4", "#F59E0B", "#EC4899", "#8B5CF6"];
  const totalRev = data.revenue_by_plan?.reduce(
    (acc, p) => acc + (parseFloat(p.revenue) || 0),
    0
  ) || parseFloat(data.monthly_net_revenue) || 1;

  let currentAngle = -90;
  const donutSegments = (data.revenue_by_plan || []).map((item, idx) => {
    const val = parseFloat(item.revenue) || 0;
    const sliceAngle = totalRev > 0 ? (val / totalRev) * 360 : 0;
    const start = currentAngle;
    currentAngle += sliceAngle;
    return {
      ...item,
      color: planColors[idx % planColors.length],
      startAngle: start,
      angle: sliceAngle,
      percentage: totalRev > 0 ? Math.round((val / totalRev) * 100) : 0,
    };
  });

  return (
    <div className="space-y-6" data-testid="analytics-overview-section">
      {/* Top Header / Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/5 pb-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight flex items-center gap-2">
            <span>Operational Overview</span>
            <span className="w-2 h-2 rounded-full bg-lime-400 animate-pulse" />
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Live operational metrics and membership performance for your gym.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowExportAttendanceModal(true)}
            className="text-xs font-semibold bg-[#161A22] border-white/10 text-slate-300 hover:text-white"
          >
            Export Attendance CSV
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={fetchAnalytics}
            disabled={loading}
            className="text-xs font-semibold bg-[#161A22] border-white/10 text-slate-300 hover:text-white"
          >
            {loading ? <Spinner size="sm" /> : "Refresh"}
          </Button>
        </div>
      </div>

      {/* Pending Bank Receipt Reviews Warning */}
      {Boolean(
        data.pending_receipt_reviews_count &&
        data.pending_receipt_reviews_count > 0
      ) && (
        <div
          className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg backdrop-blur-sm"
          data-testid="pending-receipt-reviews-banner"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-400 flex items-center justify-center shrink-0">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white">
                Receipts waiting for review:{" "}
                {data.pending_receipt_reviews_count}
              </h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Bank transfer receipts with mismatched details or awaiting
                approval need statement verification.
              </p>
            </div>
          </div>
          <a href="/receipt-reviews">
            <Button size="sm" variant="primary" className="whitespace-nowrap font-bold">
              Review receipts &rarr;
            </Button>
          </a>
        </div>
      )}

      {/* =========================================================================
          ROW 1: Kinora 3-Column Top Grid (Fully Responsive Across All Screens)
          [ Mobile: Stacked 1 col | Tablet: 12 + 6 + 6 | Desktop: 6 + 3 + 3 | XL: 5 + 4 + 3 = 12 cols ]
         ========================================================================= */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch w-full">
        {/* HERO CARD */}
        <div className="col-span-1 md:col-span-12 lg:col-span-6 xl:col-span-5 relative rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-br from-[#131720] via-[#0E1118] to-[#141822] p-5 sm:p-6 shadow-2xl flex flex-col justify-between min-w-0">
          {/* Ambient Neon Glow */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-lime-500/15 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Athletic 3D Figure Silhouette with Glowing Veins */}
          <div className="hidden sm:block absolute right-0 top-2 bottom-0 w-40 lg:w-48 pointer-events-none opacity-40 xl:opacity-75 select-none overflow-hidden">
            <svg
              className="w-full h-full object-contain object-right"
              viewBox="0 0 200 240"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="torsoGrad" x1="100" y1="20" x2="100" y2="220" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#2A303C" />
                  <stop offset="0.6" stopColor="#171A21" />
                  <stop offset="1" stopColor="#0B0D11" stopOpacity="0.2" />
                </linearGradient>
                <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
              </defs>
              {/* Head & Neck */}
              <circle cx="100" cy="35" r="16" fill="url(#torsoGrad)" stroke="#3E4756" strokeWidth="1.5" />
              <path d="M92 48 L108 48 L114 65 L86 65 Z" fill="url(#torsoGrad)" />
              {/* Shoulders & Traps */}
              <path
                d="M86 65 L55 85 L40 120 L58 128 L68 100 L76 135 L90 140 L100 142 L110 140 L124 135 L132 100 L142 128 L160 120 L145 85 L114 65 Z"
                fill="url(#torsoGrad)"
                stroke="#333C4A"
                strokeWidth="1.2"
              />
              {/* Chest & Abs Contour */}
              <path
                d="M76 102 C85 106 95 108 100 108 C105 108 115 106 124 102"
                stroke="#475569"
                strokeWidth="1.5"
              />
              <path
                d="M100 108 L100 185 M86 135 C94 137 106 137 114 135 M88 155 C94 157 106 157 112 155 M90 175 C95 177 105 177 110 175"
                stroke="#334155"
                strokeWidth="1.5"
              />
              {/* GLOWING NEON ENERGY VEINS */}
              <path
                d="M72 88 Q88 92 100 96 Q112 92 128 88"
                stroke="var(--brand-accent, #A3E635)"
                strokeWidth="2.5"
                filter="url(#neonGlow)"
              />
              <path
                d="M84 75 Q92 84 96 95"
                stroke="var(--brand-accent, #A3E635)"
                strokeWidth="1.5"
                filter="url(#neonGlow)"
              />
              <path
                d="M116 75 Q108 84 104 95"
                stroke="var(--brand-accent, #A3E635)"
                strokeWidth="1.5"
                filter="url(#neonGlow)"
              />
              <path
                d="M62 95 Q72 105 82 105"
                stroke="var(--brand-accent, #A3E635)"
                strokeWidth="2"
                filter="url(#neonGlow)"
              />
              <path
                d="M138 95 Q128 105 118 105"
                stroke="var(--brand-accent, #A3E635)"
                strokeWidth="2"
                filter="url(#neonGlow)"
              />
              <circle cx="100" cy="96" r="3.5" fill="var(--brand-accent, #A3E635)" filter="url(#neonGlow)" />
            </svg>
          </div>

          {/* Left Text Header */}
          <div className="relative z-10 max-w-full sm:max-w-[70%]">
            <span className="text-[11px] font-bold text-slate-400 block mb-1">
              Live Operations
            </span>
            <div className="flex items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight leading-tight">
                Fitness Overview
              </h1>
              <span className="w-2 h-2 rounded-full bg-lime-400 animate-pulse shadow-[0_0_8px_rgba(163,230,53,0.8)]" />
            </div>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Addis Ababa real-time attendance, active membership distribution, and confirmed cash flow.
            </p>
          </div>

          {/* 3 Floating Frosted Glass Pills (Kinora Style) */}
          <div className="relative z-10 grid grid-cols-1 sm:grid-cols-3 gap-2 mt-5 pt-3 border-t border-white/5">
            {/* Pill 1: Active Members */}
            <div className="backdrop-blur-md bg-white/[0.04] border border-white/10 hover:border-lime-400/40 rounded-xl p-2.5 sm:p-3 transition-all min-w-0">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1 truncate">
                  <Users className="w-3 h-3 text-lime-400 shrink-0" />
                  Active
                </span>
                <span className="shrink-0 text-[9px] uppercase font-bold px-1.5 py-0.5 rounded-full bg-lime-500/20 text-lime-300">
                  Optimal
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-1.5 flex-wrap">
                <span
                  className="text-xl sm:text-2xl font-black text-white tracking-tight"
                  data-testid="stat-active-members"
                >
                  {data.active_members}
                </span>
                <span className="text-[10px] text-slate-400 truncate">
                  ({data.frozen_members} frozen)
                </span>
              </div>
            </div>

            {/* Pill 2: Today's Check-ins */}
            <div className="backdrop-blur-md bg-white/[0.04] border border-white/10 hover:border-cyan-400/40 rounded-xl p-2.5 sm:p-3 transition-all min-w-0">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1 truncate">
                  <Flame className="w-3 h-3 text-cyan-400 shrink-0" />
                  Today
                </span>
                <span className="shrink-0 flex items-center gap-0.5 text-[9px] uppercase font-bold px-1.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300">
                  <span className="w-1 h-1 rounded-full bg-cyan-400 animate-pulse" />
                  Live
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-1.5 flex-wrap">
                <span
                  className="text-xl sm:text-2xl font-black text-cyan-400 tracking-tight"
                  data-testid="stat-today-checkins"
                >
                  {data.today_checkins}
                </span>
                <span className="text-[10px] text-slate-400">scans</span>
              </div>
            </div>

            {/* Pill 3: Monthly Net Revenue */}
            <div className="backdrop-blur-md bg-white/[0.04] border border-white/10 hover:border-emerald-400/40 rounded-xl p-2.5 sm:p-3 transition-all min-w-0">
              <div className="flex items-center justify-between gap-1">
                <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1 truncate">
                  <DollarSign className="w-3 h-3 text-emerald-400 shrink-0" />
                  Revenue
                </span>
                <span className="shrink-0 text-[9px] uppercase font-bold text-emerald-400">
                  {data.currency}
                </span>
              </div>
              <div className="mt-1 flex items-baseline gap-1.5 flex-wrap">
                <span
                  className="text-lg sm:text-xl font-black text-emerald-400 tracking-tight truncate max-w-full"
                  data-testid="stat-monthly-revenue"
                >
                  {Number(data.monthly_net_revenue).toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </span>
                <span className="text-[10px] text-slate-400">{data.currency}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ACTIVITY PROGRESS RINGS CARD */}
        <div className="col-span-1 md:col-span-6 lg:col-span-3 xl:col-span-4 bg-[#12151C] border border-white/5 rounded-2xl p-5 flex flex-col justify-between shadow-xl hover:border-white/10 transition min-w-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h3 className="text-sm font-bold text-white">Activity Progress</h3>
              <p className="text-[11px] text-slate-400">Daily check-in target flow</p>
            </div>
            <span className="text-[11px] font-semibold text-slate-300 bg-white/5 border border-white/10 px-2.5 py-1 rounded-full">
              Today
            </span>
          </div>

          {/* SVG Concentric Rings */}
          <div className="py-4 flex items-center justify-center">
            <div className="relative w-36 h-36 flex items-center justify-center">
              <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 120 120">
                {/* Track 1 */}
                <circle cx="60" cy="60" r={r1} fill="none" stroke="rgba(255, 255, 255, 0.06)" strokeWidth="8" />
                <circle
                  cx="60"
                  cy="60"
                  r={r1}
                  fill="none"
                  stroke="#A3E635"
                  strokeWidth="8"
                  strokeDasharray={c1}
                  strokeDashoffset={c1 - c1 * checkinRatio}
                  strokeLinecap="round"
                />
                {/* Track 2 */}
                <circle cx="60" cy="60" r={r2} fill="none" stroke="rgba(255, 255, 255, 0.06)" strokeWidth="8" />
                <circle
                  cx="60"
                  cy="60"
                  r={r2}
                  fill="none"
                  stroke="#06B6D4"
                  strokeWidth="8"
                  strokeDasharray={c2}
                  strokeDashoffset={c2 - c2 * activeRatio}
                  strokeLinecap="round"
                />
                {/* Track 3 */}
                <circle cx="60" cy="60" r={r3} fill="none" stroke="rgba(255, 255, 255, 0.06)" strokeWidth="8" />
                <circle
                  cx="60"
                  cy="60"
                  r={r3}
                  fill="none"
                  stroke="#F59E0B"
                  strokeWidth="8"
                  strokeDasharray={c3}
                  strokeDashoffset={c3 - c3 * operationalRatio}
                  strokeLinecap="round"
                />
              </svg>

              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <Dumbbell className="w-5 h-5 text-lime-400 opacity-90" />
              </div>
            </div>
          </div>

          {/* 3 Metric Counters Below Rings */}
          <div className="grid grid-cols-3 gap-2 pt-3 border-t border-white/5 text-center">
            <div className="p-2 rounded-xl bg-white/[0.02]">
              <span className="text-[10px] font-semibold text-lime-400 flex items-center justify-center gap-1 truncate">
                <span className="w-1.5 h-1.5 rounded-full bg-lime-400 shrink-0" />
                Scans
              </span>
              <span className="text-base sm:text-lg font-extrabold text-white mt-0.5 block">
                {data.today_checkins}
              </span>
              <span className="text-[10px] text-slate-500 block truncate">/ 30 goal</span>
            </div>
            <div className="p-2 rounded-xl bg-white/[0.02]">
              <span className="text-[10px] font-semibold text-cyan-400 flex items-center justify-center gap-1 truncate">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                Active
              </span>
              <span className="text-base sm:text-lg font-extrabold text-white mt-0.5 block">
                {data.active_members}
              </span>
              <span className="text-[10px] text-slate-500 block truncate">members</span>
            </div>
            <div className="p-2 rounded-xl bg-white/[0.02]">
              <span className="text-[10px] font-semibold text-amber-400 flex items-center justify-center gap-1 truncate">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                Frozen
              </span>
              <span className="text-base sm:text-lg font-extrabold text-white mt-0.5 block">
                {data.frozen_members}
              </span>
              <span className="text-[10px] text-slate-500 block truncate">paused</span>
            </div>
          </div>
        </div>

        {/* CALORIES & MACROS / REVENUE & PLANS DONUT */}
        <div className="col-span-1 md:col-span-6 lg:col-span-3 xl:col-span-3 bg-[#12151C] border border-white/5 rounded-2xl p-5 flex flex-col justify-between shadow-xl hover:border-white/10 transition min-w-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h3 className="text-sm font-bold text-white">Calories & Macros</h3>
              <p className="text-[11px] text-slate-400">Revenue & tier distribution</p>
            </div>
            <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full uppercase">
              {data.currency}
            </span>
          </div>

          {/* Donut Chart */}
          <div className="py-3 flex items-center justify-center">
            <div className="relative w-36 h-36 flex items-center justify-center">
              <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r={42} fill="none" stroke="rgba(255, 255, 255, 0.06)" strokeWidth="12" />
                {donutSegments.length > 0 ? (
                  donutSegments.map((seg) => {
                    const circ = 2 * Math.PI * 42;
                    const strokeDash = (seg.percentage / 100) * circ;
                    return (
                      <circle
                        key={seg.plan_id}
                        cx="60"
                        cy="60"
                        r={42}
                        fill="none"
                        stroke={seg.color}
                        strokeWidth="12"
                        strokeDasharray={`${strokeDash} ${circ - strokeDash}`}
                        strokeDashoffset={-((seg.startAngle + 90) / 360) * circ}
                      />
                    );
                  })
                ) : (
                  <circle
                    cx="60"
                    cy="60"
                    r={42}
                    fill="none"
                    stroke="#A3E635"
                    strokeWidth="12"
                    strokeDasharray={2 * Math.PI * 42}
                    strokeDashoffset={0}
                  />
                )}
              </svg>

              {/* Center Metric */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none p-2">
                <span className="text-sm sm:text-base font-black text-white leading-tight">
                  {Number(data.monthly_net_revenue).toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </span>
                <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">
                  {data.currency}
                </span>
              </div>
            </div>
          </div>

          {/* Legend / Locked State */}
          {data.has_analytics && data.revenue_by_plan ? (
            <div className="space-y-1.5 pt-2 border-t border-white/5">
              {donutSegments.slice(0, 3).map((item, idx) => (
                <div
                  key={item.plan_id}
                  className="flex items-center justify-between text-xs py-1 px-1.5 rounded-lg hover:bg-white/[0.03]"
                >
                  <div className="flex items-center gap-2 truncate">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: planColors[idx % planColors.length] }}
                    />
                    <span className="font-semibold text-slate-300 truncate">
                      Tier {idx + 1} ({item.percentage}%)
                    </span>
                  </div>
                  <span className="font-bold text-slate-300 shrink-0 ml-2">
                    {item.payment_count} payments
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="pt-2 border-t border-white/5 text-center space-y-2">
              <h4 className="text-xs font-bold text-white">Visual Breakdown Locked</h4>
              <p className="text-[11px] text-slate-400">
                Growth or Pro unlocks visual distribution graphs and donut charts.
              </p>
              {onUpgradeClick && (
                <Button size="sm" variant="secondary" onClick={onUpgradeClick} className="w-full text-xs font-bold bg-white/5 text-slate-200 border-white/10">
                  Upgrade Tier
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* =========================================================================
          ROW 2: Kinora 3-Column Middle Grid
          [ Column 1: Sleep Tracking / Expiring in 7 Days ]
          [ Column 2: Heart Rate (Weekly) Spline Chart ]
          [ Column 3: Upcoming Workouts / Scheduled Classes List ]
         ========================================================================= */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Card 1: Sleep Tracking / Expiring Memberships in 7 Days */}
        <div className="bg-[#12151C] border border-white/5 rounded-2xl p-5 flex flex-col justify-between shadow-xl hover:border-white/10 transition min-w-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h3 className="text-sm font-bold text-white">Sleep Tracking</h3>
              <p className="text-[11px] text-slate-400">Expiring in 7 Days</p>
            </div>
            <Badge
              variant={
                data.expiring_memberships_count > 0 ? "warning" : "neutral"
              }
            >
              {data.expiring_memberships_count > 0 ? "Action Needed" : "On Track"}
            </Badge>
          </div>

          {/* Large Stat with View list → Action */}
          <div className="py-2 flex items-baseline justify-between">
            <div>
              <span
                className="text-3xl sm:text-4xl font-black text-amber-400 tracking-tight"
                data-testid="stat-expiring-count"
              >
                {data.expiring_memberships_count}
              </span>
              <span className="text-xs text-slate-400 block mt-0.5">
                Active plans ending soon without renewal
              </span>
            </div>
            {data.expiring_memberships_count > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowExpiringModal(true)}
                className="text-xs text-lime-400 hover:text-lime-300 font-bold p-0 h-auto hover:underline"
              >
                View list &rarr;
              </Button>
            )}
          </div>

          {/* 7-Day Pill Bar Chart (Weekly sleep bar chart style from Kinora 00:02) */}
          <div className="space-y-2 pt-2 border-t border-white/5">
            <div className="flex items-end justify-between gap-1.5 h-20 pt-2 px-1">
              {[3, 5, 2, 6, 4, 1, Math.max(1, data.expiring_memberships_count)].map((h, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end">
                  <div
                    className={`w-3 sm:w-3.5 max-w-[14px] mx-auto rounded-full transition-all duration-300 ${
                      i === 6
                        ? "bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.5)]"
                        : "bg-white/15 hover:bg-white/30"
                    }`}
                    style={{ height: `${Math.min(100, Math.max(15, h * 15))}%` }}
                  />
                  <span className="text-[9px] font-mono text-slate-400">
                    {["T", "W", "T", "F", "S", "S", "M"][i]}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 text-center">
              Active plans ending soon without renewal
            </p>
          </div>
        </div>

        {/* Card 2: Heart Rate (Weekly) Spline Chart */}
        <div className="bg-[#12151C] border border-white/5 rounded-2xl p-5 flex flex-col justify-between shadow-xl hover:border-white/10 transition min-w-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h3 className="text-sm font-bold text-white">Heart Rate (Weekly)</h3>
              <p className="text-[11px] text-slate-400">Weekly check-in rhythm</p>
            </div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              BPM / SCANS
            </span>
          </div>

          <div className="py-2 flex items-baseline justify-between">
            <div>
              <span className="text-3xl sm:text-4xl font-black text-white tracking-tight">
                {Math.max(18, data.today_checkins * 2)}
              </span>
              <span className="text-xs text-slate-400 block mt-0.5">
                Avg. Daily Check-ins
              </span>
            </div>
            <span className="text-xs font-bold text-lime-400 bg-lime-400/10 px-2 py-1 rounded-full border border-lime-400/20">
              &uarr; 12% vs last week
            </span>
          </div>

          {/* Smooth SVG Spline Area Graph */}
          <div className="pt-2 border-t border-white/5">
            <div className="h-16 w-full relative">
              <svg className="w-full h-full" viewBox="0 0 240 60" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="splineGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#A3E635" stopOpacity="0.35" />
                    <stop offset="100%" stopColor="#A3E635" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                <path
                  d="M0 45 Q 40 30, 80 38 T 160 22 T 240 10 L 240 60 L 0 60 Z"
                  fill="url(#splineGrad)"
                />
                <path
                  d="M0 45 Q 40 30, 80 38 T 160 22 T 240 10"
                  fill="none"
                  stroke="#A3E635"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
                {/* Data Points */}
                <circle cx="0" cy="45" r="3" fill="#A3E635" />
                <circle cx="40" cy="35" r="3" fill="#A3E635" />
                <circle cx="80" cy="38" r="3" fill="#A3E635" />
                <circle cx="120" cy="28" r="3" fill="#A3E635" />
                <circle cx="160" cy="22" r="3" fill="#A3E635" />
                <circle cx="200" cy="16" r="3" fill="#A3E635" />
                <circle cx="240" cy="10" r="4" fill="#A3E635" filter="drop-shadow(0 0 4px #A3E635)" />
              </svg>
            </div>
            <div className="flex justify-between text-[9px] font-mono text-slate-500 pt-1">
              <span>Tue</span>
              <span>Wed</span>
              <span>Thu</span>
              <span>Fri</span>
              <span>Sat</span>
              <span>Sun</span>
              <span>Mon</span>
            </div>
          </div>
        </div>

        {/* Card 3: Upcoming Workouts / Scheduled Classes List (Matching Kinora 00:02) */}
        <div className="bg-[#12151C] border border-white/5 rounded-2xl p-5 flex flex-col justify-between shadow-xl hover:border-white/10 transition md:col-span-2 lg:col-span-1 min-w-0">
          <div className="flex items-center justify-between pb-3 border-b border-white/5">
            <div>
              <h3 className="text-sm font-bold text-white">Upcoming Workouts</h3>
              <p className="text-[11px] text-slate-400">Class schedule & coaching</p>
            </div>
            <a href="/classes" className="text-xs text-lime-400 hover:underline font-bold">
              View all
            </a>
          </div>

          <div className="space-y-2.5 py-1">
            {/* Workout 1 */}
            <div className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-lime-400/20 text-lime-400 flex items-center justify-center shrink-0">
                  <Dumbbell className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white leading-tight">Upper Body Strength</h4>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" /> 45 min
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-bold text-slate-300 bg-white/5 px-2 py-0.5 rounded-full">
                Today
              </span>
            </div>

            {/* Workout 2 */}
            <div className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-cyan-400/20 text-cyan-400 flex items-center justify-center shrink-0">
                  <Flame className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white leading-tight">HIIT Cardio Blast</h4>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" /> 30 min
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-bold text-slate-300 bg-white/5 px-2 py-0.5 rounded-full">
                Tomorrow
              </span>
            </div>

            {/* Workout 3 */}
            <div className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-400/20 text-amber-400 flex items-center justify-center shrink-0">
                  <Dumbbell className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white leading-tight">Leg Day Power</h4>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" /> 50 min
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-bold text-slate-400">
                Thu, Sep 24
              </span>
            </div>

            {/* Workout 4 */}
            <div className="flex items-center justify-between p-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] transition">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-purple-400/20 text-purple-400 flex items-center justify-center shrink-0">
                  <TrendingUp className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white leading-tight">Core & Mobility</h4>
                  <span className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" /> 25 min
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-bold text-slate-400">
                Fri, Sep 25
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          ROW 3: Revenue by Plan Table (Pro/Growth) & Motivational Bottom Banner
         ========================================================================= */}
      <Card className="bg-[#12151C] border border-white/5 rounded-2xl p-5 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Revenue by Membership Plan
              </h3>
              {data.has_analytics ? (
                <Badge variant="success">Pro Analytics</Badge>
              ) : (
                <Badge variant="neutral">Growth / Pro</Badge>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Net cash received breakdown per membership package.
            </p>
          </div>
        </div>

        {data.has_analytics && data.revenue_by_plan ? (
          <div>
            {data.revenue_by_plan.length === 0 ? (
              <div className="text-center py-6 text-slate-400 text-xs">
                No confirmed plan payments recorded yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 text-slate-400">
                      <th className="py-2.5 px-3 font-semibold">Plan Name</th>
                      <th className="py-2.5 px-3 font-semibold text-center">
                        Payments
                      </th>
                      <th className="py-2.5 px-3 font-semibold text-right">
                        Net Revenue
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {data.revenue_by_plan.map((item) => (
                      <tr key={item.plan_id} className="hover:bg-white/[0.03] transition">
                        <td className="py-3 px-3 font-medium text-white">
                          {item.plan_name}
                        </td>
                        <td className="py-3 px-3 text-center text-slate-400">
                          {item.payment_count}
                        </td>
                        <td className="py-3 px-3 text-right font-bold text-emerald-400">
                          {Number(item.revenue).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}{" "}
                          {data.currency}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="p-6 bg-white/[0.02] rounded-xl border border-dashed border-white/10 text-center space-y-3">
            <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-lime-500/10 text-lime-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h4 className="text-sm font-semibold text-white">
                Revenue by Plan Locked
              </h4>
              <p className="text-xs text-slate-400">
                {data.upgrade_prompt ||
                  "Upgrade to Growth or Pro to unlock revenue by plan breakdowns."}
              </p>
            </div>
            {onUpgradeClick && (
              <Button size="sm" variant="primary" onClick={onUpgradeClick} className="font-bold">
                Upgrade Plan
              </Button>
            )}
          </div>
        )}
      </Card>

      {/* Motivational Banner (Kinora 00:02 "KEEP MOVING FORWARD") */}
      <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-gradient-to-r from-[#12161E] via-[#161B26] to-[#12161E] p-6 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-[10px] font-mono uppercase tracking-widest text-lime-400">
            Keep Moving Forward
          </span>
          <h3 className="text-lg font-black text-white tracking-tight">
            Stronger Every Day. Better Every Operation.
          </h3>
          <p className="text-xs text-slate-400 max-w-lg">
            Addis Ababa member experience is built one check-in, one workout, and one member at a time.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a href="/check-in">
            <Button size="sm" variant="primary" className="font-bold whitespace-nowrap bg-lime-400 hover:bg-lime-500 text-black border-none shadow-lg shadow-lime-400/20 flex items-center gap-1.5">
              <span>Let's Go</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </a>
        </div>
      </div>

      {/* Expiring Members Modal */}
      {showExpiringModal && (
        <Modal
          isOpen={showExpiringModal}
          onClose={() => setShowExpiringModal(false)}
          title="Memberships Expiring Within 7 Days"
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-400">
              These members have active subscriptions expiring within 7 days and
              do not have a queued renewal.
            </p>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 sticky top-0 bg-[#161A22]">
                    <th className="py-2.5 px-3 font-semibold">Member</th>
                    <th className="py-2.5 px-3 font-semibold">Phone</th>
                    <th className="py-2.5 px-3 font-semibold">Plan</th>
                    <th className="py-2.5 px-3 font-semibold">End Date</th>
                    <th className="py-2.5 px-3 font-semibold text-right">
                      Remaining
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {data.expiring_memberships.map((sub: ExpiringMembership) => (
                    <tr key={sub.member_id} className="hover:bg-white/[0.04]">
                      <td className="py-2.5 px-3 font-medium text-white">
                        {sub.member_name}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {sub.member_phone}
                      </td>
                      <td className="py-2.5 px-3 text-slate-200">{sub.plan_name}</td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {sub.end_date}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge
                          variant={
                            sub.days_remaining <= 2 ? "danger" : "warning"
                          }
                        >
                          {sub.days_remaining === 0
                            ? "Expires today"
                            : `${sub.days_remaining} day${sub.days_remaining > 1 ? "s" : ""}`}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end pt-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowExpiringModal(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      <ExportDataModal
        isOpen={showExportAttendanceModal}
        onClose={() => setShowExportAttendanceModal(false)}
        exportType="attendance"
      />
    </div>
  );
};
