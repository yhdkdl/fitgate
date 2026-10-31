import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { NotificationCenter } from "../components/ui/NotificationCenter";
import { SectionErrorBoundary } from "../components/ui/SectionErrorBoundary";
import { getPublicGymEntry } from "../api/gyms";
import {
  GymManagementSection,
  type GymPrefillData,
} from "../components/superadmin/GymManagementSection";
import { DemoRequestSection } from "../components/superadmin/DemoRequestSection";
import { FirstRunChecklistCard } from "../components/owner/FirstRunChecklistCard";
import { GymBrandingSection } from "../components/owner/GymBrandingSection";
import { StaffManagementSection } from "../components/owner/StaffManagementSection";
import { MembershipPlansSection } from "../components/owner/MembershipPlansSection";
import { PaymentGatewaySection } from "../components/owner/PaymentGatewaySection";
import { GymPaymentsSection } from "../components/staff/GymPaymentsSection";
import { GymFreezesSection } from "../components/staff/GymFreezesSection";
import { MemberFreezeSection } from "../components/member/MemberFreezeSection";
import { MemberManagementSection } from "../components/dashboard/MemberManagementSection";
import { MemberSelfSection } from "../components/dashboard/MemberSelfSection";
import { MemberPaymentCompleteSection } from "../components/member/MemberPaymentCompleteSection";
import { TrainerMeasurementsSection } from "../components/trainer/TrainerMeasurementsSection";
import { TrainersManagementSection } from "../components/owner/TrainersManagementSection";
import { AssignmentsSection } from "../components/owner/AssignmentsSection";
import { MyClientsSection } from "../components/trainer/MyClientsSection";
import { getMyClients, getTrainerProfileMe, type Trainer, type TrainerMyClient } from "../api/trainers";
import { AuthenticatedImage } from "../components/ui/AuthenticatedImage";
import { AuditLogSection } from "../components/dashboard/AuditLogSection";
import { AttendanceScannerSection } from "../components/attendance/AttendanceScannerSection";
import { useAuth } from "../context/AuthContext";
import { getTenantFromHostname } from "../utils/tenant";

interface NavItem {
  label: string;
  path: string;
}

const ROLE_NAV_ITEMS: Record<string, NavItem[]> = {
  owner: [
    { label: "Overview", path: "/dashboard" },
    { label: "Members", path: "/members" },
    { label: "Check-in", path: "/check-in" },
    { label: "Payments", path: "/payments" },
    { label: "Bank transfers", path: "/bank-transfers" },
    { label: "Plans", path: "/plans" },
    { label: "Trainers", path: "/trainers" },
    { label: "Assignments", path: "/assignments" },
    { label: "Freeze requests", path: "/freezes" },
    { label: "Staff", path: "/staff" },
    { label: "Audit log", path: "/audit-log" },
    { label: "Settings", path: "/settings" },
  ],
  manager: [
    { label: "Overview", path: "/dashboard" },
    { label: "Members", path: "/members" },
    { label: "Check-in", path: "/check-in" },
    { label: "Payments", path: "/payments" },
    { label: "Plans", path: "/plans" },
    { label: "Trainers", path: "/trainers" },
    { label: "Assignments", path: "/assignments" },
    { label: "Freeze requests", path: "/freezes" },
    { label: "Staff", path: "/staff" },
    { label: "Audit log", path: "/audit-log" },
  ],
  reception: [
    { label: "Members", path: "/members" },
    { label: "Check-in", path: "/check-in" },
  ],
  trainer: [
    { label: "Overview", path: "/dashboard" },
    { label: "My clients", path: "/my-clients" },
    { label: "Member measurements", path: "/measurements" },
  ],
  member: [
    { label: "Home", path: "/dashboard" },
    { label: "My membership", path: "/membership" },
    { label: "Freeze request", path: "/freeze-request" },
    { label: "My payments", path: "/payments" },
    { label: "Profile", path: "/profile" },
  ],
  super_admin: [
    { label: "Gyms", path: "/dashboard" },
    { label: "Demo requests", path: "/platform/demo-requests" },
    { label: "Audit log", path: "/platform/audit-log" },
    { label: "Profile", path: "/profile" },
  ],
};

const ROLE_HOMES: Record<string, string> = {
  super_admin: "/dashboard",
  owner: "/dashboard",
  manager: "/dashboard",
  reception: "/members",
  trainer: "/dashboard",
  member: "/dashboard",
};

function getSafeBrandColor(hex?: string | null): string {
  if (!hex || !/^#[0-9a-fA-F]{6}$/.test(hex)) {
    return "#2563EB";
  }
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const toL = (c: number) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  const L = 0.2126 * toL(r) + 0.7152 * toL(g) + 0.0722 * toL(b);
  const surfaceL = 0.0071; // #0E1626
  const ratio = (Math.max(L, surfaceL) + 0.05) / (Math.min(L, surfaceL) + 0.05);
  if (ratio < 3.0) {
    return "#2563EB";
  }
  return hex;
}

export const DashboardScreen: React.FC = () => {
  const { user, dashboardConfig, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const tenant = getTenantFromHostname();

  const [checklistKey, setChecklistKey] = useState(0);
  const [trainerWorkload, setTrainerWorkload] = useState<Trainer | null>(null);
  const [trainerClients, setTrainerClients] = useState<TrainerMyClient[]>([]);
  const [showMoreMobile, setShowMoreMobile] = useState(false);
  const [prefillGymData, setPrefillGymData] = useState<GymPrefillData | null>(
    null
  );
  const [gymBranding, setGymBranding] = useState<{
    name?: string;
    logo?: string | null;
    brand_color?: string | null;
  } | null>(null);

  const role = user?.role || "member";
  const userRoleNav = useMemo<Array<{ label: string; path: string; icon?: React.ReactNode }>>(
    () =>
      ROLE_NAV_ITEMS[role] ||
      (dashboardConfig?.navigation as Array<{ label: string; path: string; icon?: React.ReactNode }>) || [
        { label: "Overview", path: "/dashboard" },
        { label: "Profile", path: "/profile" },
      ],
    [role, dashboardConfig?.navigation]
  );

  const currentPath = location.pathname.replace(/\/+$/, "") || "/dashboard";

  // Role permissions routing check: send to own home page if unauthorized
  useEffect(() => {
    if (!user) return;
    const allowedPaths = userRoleNav.map((item) => item.path);
    // Allow special paths
    allowedPaths.push("/profile");
    if (role === "super_admin") {
      allowedPaths.push("/platform/gyms");
    }

    const isAllowed = allowedPaths.some(
      (p) =>
        currentPath === p ||
        (p !== "/dashboard" && currentPath.startsWith(p + "/"))
    );

    if (!isAllowed) {
      const home = ROLE_HOMES[role] || "/dashboard";
      navigate(home, { replace: true });
    }
  }, [currentPath, role, user, userRoleNav, navigate]);

  useEffect(() => {
    if (role === "trainer") {
      getTrainerProfileMe()
        .then((t) => setTrainerWorkload(t))
        .catch(() => {});
      getMyClients()
        .then((c) => setTrainerClients(c))
        .catch(() => {});
    }
  }, [role]);

  useEffect(() => {
    if (!tenant) return;
    let isMounted = true;
    getPublicGymEntry(tenant)
      .then((res) => {
        if (isMounted && res) {
          setGymBranding({
            name: res.name,
            logo: res.logo,
            brand_color: res.brand_color,
          });
        }
      })
      .catch(() => {
        // Ignore fallback
      });
    return () => {
      isMounted = false;
    };
  }, [tenant, checklistKey]);

  const safeBrandColor = getSafeBrandColor(gymBranding?.brand_color);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const widgets = dashboardConfig?.widgets || [
    { id: "overview", title: "General Overview" },
  ];

  // Mobile navigation partitioning: at most 5 items (first 4 + More, or all if <= 5)
  const isMobileMoreNeeded = userRoleNav.length > 5;
  const mobileVisibleNav = isMobileMoreNeeded
    ? userRoleNav.slice(0, 4)
    : userRoleNav;
  const mobileMoreNav = isMobileMoreNeeded ? userRoleNav.slice(4) : [];

  // Determine current page render
  const renderCurrentPage = () => {
    // 1. Member: Payment Complete page
    if (
      currentPath === "/membership/payment-complete" ||
      currentPath.startsWith("/membership/payment-complete")
    ) {
      return (
        <SectionErrorBoundary title="Payment Status">
          <MemberPaymentCompleteSection />
        </SectionErrorBoundary>
      );
    }

    // 2. Member: My Membership page
    if (
      currentPath === "/membership" ||
      currentPath.startsWith("/membership/")
    ) {
      return (
        <SectionErrorBoundary title="My Membership">
          <MemberSelfSection view="membership" />
        </SectionErrorBoundary>
      );
    }

    // 2. Staff: Members management page
    if (currentPath === "/members" || currentPath.startsWith("/members/")) {
      return (
        <SectionErrorBoundary title="Members">
          <MemberManagementSection
            userRole={role}
            onMemberRegistered={() => setChecklistKey((k) => k + 1)}
          />
        </SectionErrorBoundary>
      );
    }

    // 2. Check-in page (Scanner & live list)
    if (currentPath.startsWith("/check-in")) {
      return (
        <SectionErrorBoundary title="Check-in">
          <AttendanceScannerSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // 3. Payments ledger page
    if (currentPath.startsWith("/payments")) {
      if (role === "member") {
        return (
          <SectionErrorBoundary title="My Payments">
            <MemberSelfSection view="payments" />
          </SectionErrorBoundary>
        );
      }
      return (
        <SectionErrorBoundary title="Payments">
          <GymPaymentsSection defaultTab="payments" />
        </SectionErrorBoundary>
      );
    }

    // 4. Bank transfers page (unreconciled list)
    if (currentPath.startsWith("/bank-transfers")) {
      return (
        <SectionErrorBoundary title="Bank Transfers">
          <GymPaymentsSection defaultTab="unreconciled" />
        </SectionErrorBoundary>
      );
    }

    // 5. Membership Plans page
    if (currentPath.startsWith("/plans")) {
      return (
        <SectionErrorBoundary title="Membership Plans">
          <MembershipPlansSection
            onPlansUpdated={() => setChecklistKey((k) => k + 1)}
          />
        </SectionErrorBoundary>
      );
    }

    // 6. Freeze requests page (Staff) & Freeze request page (Member)
    if (
      currentPath === "/freeze-request" ||
      currentPath.startsWith("/freeze-request/") ||
      currentPath === "/freeze" ||
      currentPath.startsWith("/freeze/") ||
      (role === "member" && currentPath.startsWith("/freezes"))
    ) {
      return (
        <SectionErrorBoundary title="Freeze Request">
          <MemberFreezeSection />
        </SectionErrorBoundary>
      );
    }

    if (currentPath.startsWith("/freezes")) {
      return (
        <SectionErrorBoundary title="Freeze Requests">
          <GymFreezesSection />
        </SectionErrorBoundary>
      );
    }

    // 6b. Trainers Management page
    if (currentPath.startsWith("/trainers")) {
      return (
        <SectionErrorBoundary title="Trainers">
          <TrainersManagementSection />
        </SectionErrorBoundary>
      );
    }

    // 6c. Trainer Assignments page
    if (currentPath.startsWith("/assignments")) {
      return (
        <SectionErrorBoundary title="Trainer Assignments">
          <AssignmentsSection />
        </SectionErrorBoundary>
      );
    }

    // 7. Staff Management page
    if (currentPath.startsWith("/staff")) {
      return (
        <SectionErrorBoundary title="Staff Management">
          <StaffManagementSection
            onStaffUpdated={() => setChecklistKey((k) => k + 1)}
          />
        </SectionErrorBoundary>
      );
    }

    // 8. Audit Log page
    if (
      currentPath.startsWith("/audit-log") ||
      currentPath.startsWith("/platform/audit-log")
    ) {
      return (
        <SectionErrorBoundary title="Audit Log">
          <AuditLogSection
            userRole={role}
            isPlatform={role === "super_admin"}
          />
        </SectionErrorBoundary>
      );
    }

    // 9. Settings page (Branding, payment gateway, freeze & reminder days)
    if (currentPath.startsWith("/settings")) {
      return (
        <div className="space-y-6">
          <SectionErrorBoundary title="Gym Branding & Settings">
            <GymBrandingSection
              onUpdated={() => setChecklistKey((k) => k + 1)}
            />
          </SectionErrorBoundary>

          <SectionErrorBoundary title="Payment Gateway">
            <PaymentGatewaySection
              onUpdated={() => setChecklistKey((k) => k + 1)}
            />
          </SectionErrorBoundary>
        </div>
      );
    }

    // 10b. Trainer: My clients
    if (currentPath.startsWith("/my-clients")) {
      return (
        <SectionErrorBoundary title="My Clients">
          <MyClientsSection />
        </SectionErrorBoundary>
      );
    }

    // 11. Trainer: Member measurements
    if (currentPath.startsWith("/measurements")) {
      return (
        <SectionErrorBoundary title="Trainer Measurements">
          <TrainerMeasurementsSection />
        </SectionErrorBoundary>
      );
    }

    // 12. Super Admin: Demo requests
    if (currentPath.startsWith("/platform/demo-requests")) {
      return (
        <SectionErrorBoundary title="Demo Requests">
          <DemoRequestSection
            onConvertToGym={(data) => {
              setPrefillGymData(data);
              navigate("/dashboard");
            }}
          />
        </SectionErrorBoundary>
      );
    }

    // 13. Default: /dashboard (Overview / Home / Gyms)
    if (role === "super_admin") {
      return (
        <SectionErrorBoundary title="Gyms">
          <GymManagementSection
            prefillData={prefillGymData}
            onClearPrefill={() => setPrefillGymData(null)}
          />
        </SectionErrorBoundary>
      );
    }

    if (role === "member") {
      return (
        <SectionErrorBoundary title="Member Home">
          <MemberSelfSection view="home" />
        </SectionErrorBoundary>
      );
    }

    // Owner, Manager, Trainer: Overview (Short summary only: cards & checklist)
    return (
      <div className="space-y-6">
        {role === "owner" && (
          <SectionErrorBoundary title="First-run Checklist">
            <FirstRunChecklistCard
              key={checklistKey}
              onOpenBranding={() => navigate("/settings")}
            />
          </SectionErrorBoundary>
        )}

        {role === "trainer" ? (
          <div className="space-y-6">
            <div className="border-b border-border pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h2 className="text-xl font-bold text-text">Trainer Overview</h2>
                <p className="text-xs text-text-muted">
                  Your live client workload and measurement tracking overview.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => navigate("/measurements")}
                >
                  Member measurements
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => navigate("/my-clients")}
                >
                  My clients
                </Button>
              </div>
            </div>

            {/* Overview Stat Cards (Item J: X of Y clients, clients with no measurements) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Card className="bg-surface border-border p-5 space-y-1">
                <span className="text-xs text-text-muted block">Client Workload</span>
                <div className="flex items-baseline justify-between">
                  <span className="text-2xl font-bold text-text">
                    {trainerWorkload
                      ? `${trainerWorkload.client_count} of ${trainerWorkload.max_clients}`
                      : `${trainerClients.length} clients`}
                  </span>
                  {trainerWorkload && trainerWorkload.client_count >= trainerWorkload.max_clients ? (
                    <Badge variant="warning">At Capacity</Badge>
                  ) : (
                    <Badge variant="success">Capacity Available</Badge>
                  )}
                </div>
                <p className="text-[11px] text-text-muted mt-1">
                  Active client assignments
                </p>
              </Card>

              <Card className="bg-surface border-border p-5 space-y-1">
                <span className="text-xs text-text-muted block">No Measurements Recorded</span>
                <span className="text-2xl font-bold text-amber-500">
                  {trainerClients.filter((c) => !c.has_measurements).length}
                </span>
                <p className="text-[11px] text-text-muted mt-1">
                  Assigned clients needing initial intake measurements
                </p>
              </Card>

              <Card className="bg-surface border-border p-5 space-y-1">
                <span className="text-xs text-text-muted block">Measured Clients</span>
                <span className="text-2xl font-bold text-primary">
                  {trainerClients.filter((c) => c.has_measurements).length}
                </span>
                <p className="text-[11px] text-text-muted mt-1">
                  Clients with body composition history
                </p>
              </Card>
            </div>

            {/* 5 Newest Assigned Clients (Item J) */}
            <Card className="bg-surface border-border p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-text uppercase tracking-wider">
                    Newest Assigned Clients
                  </h3>
                  <p className="text-xs text-text-muted mt-0.5">
                    Your 5 most recently assigned members
                  </p>
                </div>
                {trainerClients.length > 5 && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => navigate("/my-clients")}
                    className="text-xs text-primary"
                  >
                    View all ({trainerClients.length}) &rarr;
                  </Button>
                )}
              </div>

              {trainerClients.length === 0 ? (
                <div className="text-center py-8 text-text-muted text-xs">
                  You do not have any assigned clients at this time.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border text-text-muted">
                        <th className="py-2 px-3 font-semibold">Client</th>
                        <th className="py-2 px-3 font-semibold">Phone</th>
                        <th className="py-2 px-3 font-semibold">Membership Plan</th>
                        <th className="py-2 px-3 font-semibold">Assigned Date</th>
                        <th className="py-2 px-3 font-semibold">Measurements</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {trainerClients.slice(0, 5).map((c) => (
                        <tr key={c.assignment_id} className="hover:bg-surface-2/40">
                          <td className="py-2.5 px-3 font-medium text-text">
                            <div className="flex items-center gap-2.5">
                              {c.photo_url ? (
                                <AuthenticatedImage
                                  src={c.photo_url}
                                  alt={c.member_name}
                                  className="w-7 h-7 rounded-full object-cover border border-border shrink-0"
                                />
                              ) : (
                                <div className="w-7 h-7 rounded-full bg-primary/20 text-primary font-bold flex items-center justify-center text-[10px] border border-border shrink-0">
                                  {c.member_name.slice(0, 2).toUpperCase()}
                                </div>
                              )}
                              <span>{c.member_name}</span>
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-text-muted">{c.member_phone}</td>
                          <td className="py-2.5 px-3 text-text">{c.plan_name}</td>
                          <td className="py-2.5 px-3 text-text-muted">
                            {new Date(c.assigned_at).toLocaleDateString()}
                          </td>
                          <td className="py-2.5 px-3">
                            {c.has_measurements ? (
                              <Badge variant="success">Recorded</Badge>
                            ) : (
                              <Badge variant="warning">No measurements</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        ) : (
          <div>
            <h2 className="text-lg font-semibold text-text mb-4">
              Operational Overview
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {widgets.map((widget) => (
                <Card
                  key={widget.id}
                  className="bg-surface hover:border-border/80 transition-shadow p-5"
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-sm text-text">
                      {widget.title}
                    </h3>
                    <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  </div>
                  <p className="text-xs text-text-muted">
                    Live operational tracking
                  </p>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className="min-h-screen bg-bg text-text flex flex-col pb-20 md:pb-0"
      style={{ ["--brand-accent" as string]: safeBrandColor }}
    >
      {/* Top Header */}
      <header className="border-b border-border bg-surface px-4 py-3 sm:px-6 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            {role === "super_admin" ? (
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-primary/20 text-primary font-bold text-lg flex items-center justify-center border border-primary/30">
                  FG
                </div>
                <div>
                  <span className="font-bold text-base tracking-tight text-text">
                    FitGate Platform
                  </span>
                  <span className="ml-2 text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded border border-border">
                    Apex Admin
                  </span>
                </div>
              </div>
            ) : gymBranding?.logo ? (
              <img
                src={gymBranding.logo}
                alt={`${gymBranding.name || tenant} logo`}
                className="w-9 h-9 rounded-lg object-cover border border-border"
              />
            ) : (
              <div
                className="w-9 h-9 rounded-lg font-bold text-lg flex items-center justify-center border text-white"
                style={{
                  backgroundColor: safeBrandColor,
                  borderColor: safeBrandColor,
                }}
              >
                {(gymBranding?.name || tenant || "FG").charAt(0).toUpperCase()}
              </div>
            )}

            {role !== "super_admin" && (
              <div>
                <span className="font-bold text-base tracking-tight text-text">
                  {gymBranding?.name || "FitGate"}
                </span>
                {tenant && (
                  <span
                    className="ml-2 text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded border border-border"
                    style={{
                      borderLeftColor: safeBrandColor,
                      borderLeftWidth: "3px",
                    }}
                  >
                    {tenant}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-sm font-medium text-text">
                {user?.full_name || user?.email}
              </span>
              <div className="flex items-center gap-1 mt-0.5">
                <Badge variant="primary">{user?.role}</Badge>
              </div>
            </div>

            <NotificationCenter />

            <Link
              to="/profile"
              className="inline-flex items-center justify-center px-3 py-1.5 text-sm bg-surface-2 border border-border text-text rounded-input hover:bg-border/60 min-h-[44px]"
            >
              Profile
            </Link>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleLogout}
              className="text-text-muted hover:text-danger min-h-[44px]"
            >
              Log out
            </Button>
          </div>
        </div>
      </header>

      {/* Main content wrapper with desktop sidebar and responsive content */}
      <div className="flex flex-1 max-w-7xl w-full mx-auto">
        {/* Desktop Sidebar */}
        <aside className="hidden md:flex flex-col w-60 border-r border-border bg-surface/50 p-4 shrink-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted px-3 mb-2">
            Navigation
          </div>
          <nav className="space-y-1">
            {userRoleNav.map((item, idx) => {
              const isActive =
                item.path === "/dashboard"
                  ? currentPath === "/dashboard"
                  : currentPath === item.path ||
                    currentPath.startsWith(item.path + "/");

              return (
                <Link
                  key={idx}
                  to={item.path}
                  className={`flex items-center px-3 py-2 text-sm font-medium rounded-input transition-colors min-h-[44px] ${
                    isActive
                      ? "bg-primary text-white shadow-sm font-semibold"
                      : "text-text hover:bg-surface-2 hover:text-white"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Dynamic Page Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-y-auto">
          {renderCurrentPage()}
        </main>
      </div>

      {/* Mobile Bottom Navigation (at most 5 items per DESIGN.md) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border z-40 flex items-center justify-around py-1 px-1">
        {mobileVisibleNav.map((item, idx) => {
          const isActive =
            item.path === "/dashboard"
              ? currentPath === "/dashboard"
              : currentPath === item.path ||
                currentPath.startsWith(item.path + "/");

          return (
            <Link
              key={idx}
              to={item.path}
              className={`flex flex-col items-center justify-center text-xs px-2 py-1 min-h-[44px] min-w-[44px] transition-colors ${
                isActive
                  ? "text-primary font-bold"
                  : "text-text-muted hover:text-text"
              }`}
            >
              <span className="font-medium text-center truncate max-w-[70px]">
                {item.label}
              </span>
            </Link>
          );
        })}

        {isMobileMoreNeeded && (
          <button
            type="button"
            onClick={() => setShowMoreMobile((prev) => !prev)}
            className={`flex flex-col items-center justify-center text-xs px-2 py-1 min-h-[44px] min-w-[44px] transition-colors ${
              showMoreMobile
                ? "text-primary font-bold"
                : "text-text-muted hover:text-text"
            }`}
          >
            <span className="text-base leading-none">•••</span>
            <span className="text-[10px] mt-0.5">More</span>
          </button>
        )}
      </nav>

      {/* Mobile "More" Drawer / Popover Menu */}
      {showMoreMobile && isMobileMoreNeeded && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex flex-col justify-end"
          onClick={() => setShowMoreMobile(false)}
        >
          <div
            className="bg-surface border-t border-border p-4 rounded-t-xl space-y-2 max-h-[70vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                More Options
              </span>
              <button
                type="button"
                onClick={() => setShowMoreMobile(false)}
                className="text-text-muted hover:text-text font-bold text-lg px-2"
              >
                &times;
              </button>
            </div>
            <div className="space-y-1 pt-1">
              {mobileMoreNav.map((item, idx) => {
                const isActive =
                  currentPath === item.path ||
                  currentPath.startsWith(item.path + "/");
                return (
                  <Link
                    key={idx}
                    to={item.path}
                    onClick={() => setShowMoreMobile(false)}
                    className={`flex items-center px-4 py-3 text-sm rounded-lg min-h-[44px] ${
                      isActive
                        ? "bg-primary text-white font-semibold"
                        : "text-text hover:bg-surface-2"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
              <div className="pt-2 border-t border-border">
                <Link
                  to="/profile"
                  onClick={() => setShowMoreMobile(false)}
                  className="flex items-center px-4 py-3 text-sm rounded-lg text-text hover:bg-surface-2 min-h-[44px]"
                >
                  Profile
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    setShowMoreMobile(false);
                    handleLogout();
                  }}
                  className="w-full text-left flex items-center px-4 py-3 text-sm rounded-lg text-danger hover:bg-danger/10 min-h-[44px]"
                >
                  Log out
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
