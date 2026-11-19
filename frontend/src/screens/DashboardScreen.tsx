import { ReceiptReviewQueueSection } from "../components/payments/ReceiptReviewQueueSection";
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
import {
  getMyClients,
  getTrainerProfileMe,
  type Trainer,
  type TrainerMyClient,
} from "../api/trainers";
import { AuthenticatedImage } from "../components/ui/AuthenticatedImage";
import { AuditLogSection } from "../components/dashboard/AuditLogSection";
import { AttendanceScannerSection } from "../components/attendance/AttendanceScannerSection";
import { EquipmentSection } from "../components/equipment/EquipmentSection";
import { AnalyticsOverviewSection } from "../components/analytics/AnalyticsOverviewSection";
import { NoticeBoardSection } from "../components/notices/NoticeBoardSection";
import { PlatformNoticesSection } from "../components/superadmin/PlatformNoticesSection";
import { PlatformSupportSection } from "../components/superadmin/PlatformSupportSection";
import { ContactFitGateSection } from "../components/support/ContactFitGateSection";
import { FitGateMessagesSection } from "../components/owner/FitGateMessagesSection";
import { OwnerPlatformMessagesCard } from "../components/owner/OwnerPlatformMessagesCard";
import { ExpensesSection } from "../components/expenses/ExpensesSection";
import { ClassScheduleSection } from "../components/classes/ClassScheduleSection";
import { ExternalLink, Search, Flame } from "lucide-react";
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
    { label: "Classes", path: "/classes" },
    { label: "Check-in", path: "/check-in" },
    { label: "Equipment", path: "/equipment" },
    { label: "Payments", path: "/payments" },
    { label: "Receipt reviews", path: "/receipt-reviews" },
    { label: "Expenses & Reports", path: "/expenses" },
    { label: "Bank transfers", path: "/bank-transfers" },
    { label: "Plans", path: "/plans" },
    { label: "Trainers", path: "/trainers" },
    { label: "Assignments", path: "/assignments" },
    { label: "Freeze requests", path: "/freezes" },
    { label: "Staff", path: "/staff" },
    { label: "Audit log", path: "/audit-log" },
    { label: "Notices", path: "/notices" },
    { label: "FitGate messages", path: "/platform-messages" },
    { label: "Contact FitGate", path: "/support" },
    { label: "Settings", path: "/settings" },
  ],
  manager: [
    { label: "Overview", path: "/dashboard" },
    { label: "Members", path: "/members" },
    { label: "Classes", path: "/classes" },
    { label: "Check-in", path: "/check-in" },
    { label: "Equipment", path: "/equipment" },
    { label: "Payments", path: "/payments" },
    { label: "Receipt reviews", path: "/receipt-reviews" },
    { label: "Expenses & Reports", path: "/expenses" },
    { label: "Plans", path: "/plans" },
    { label: "Trainers", path: "/trainers" },
    { label: "Assignments", path: "/assignments" },
    { label: "Freeze requests", path: "/freezes" },
    { label: "Staff", path: "/staff" },
    { label: "Audit log", path: "/audit-log" },
    { label: "Notices", path: "/notices" },
    { label: "Contact FitGate", path: "/support" },
  ],
  reception: [
    { label: "Members", path: "/members" },
    { label: "Classes", path: "/classes" },
    { label: "Check-in", path: "/check-in" },
    { label: "Equipment", path: "/equipment" },
    { label: "Notices", path: "/notices" },
  ],
  trainer: [
    { label: "Overview", path: "/dashboard" },
    { label: "My classes", path: "/my-classes" },
    { label: "My clients", path: "/my-clients" },
    { label: "Member measurements", path: "/measurements" },
    { label: "Equipment", path: "/equipment" },
    { label: "Notices", path: "/notices" },
  ],
  member: [
    { label: "Home", path: "/dashboard" },
    { label: "Classes", path: "/classes" },
    { label: "My membership", path: "/membership" },
    { label: "Equipment", path: "/equipment" },
    { label: "Freeze request", path: "/freeze-request" },
    { label: "My payments", path: "/payments" },
    { label: "Notices", path: "/notices" },
    { label: "Profile", path: "/profile" },
  ],
  super_admin: [
    { label: "Gyms", path: "/dashboard" },
    { label: "Demo requests", path: "/platform/demo-requests" },
    { label: "Audit log", path: "/platform/audit-log" },
    { label: "Platform Notices", path: "/platform/notices" },
    { label: "Support requests", path: "/platform/support" },
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
  const { user, dashboardConfig, capabilities, logout } = useAuth();
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
    has_group_classes?: boolean;
  } | null>(null);

  const safeBrandColor = getSafeBrandColor(gymBranding?.brand_color);

  const ACCENT_PRESETS = useMemo(() => {
    const presets = [
      { name: "Neon Lime", hex: "#A3E635" },
      { name: "Electric Cyan", hex: "#06B6D4" },
      { name: "Sunset Amber", hex: "#F59E0B" },
      { name: "Hot Magenta", hex: "#EC4899" },
      { name: "Royal Violet", hex: "#8B5CF6" },
    ];
    if (safeBrandColor && !presets.some((p) => p.hex.toLowerCase() === safeBrandColor.toLowerCase())) {
      presets.unshift({ name: "Gym Brand", hex: safeBrandColor });
    }
    return presets;
  }, [safeBrandColor]);

  const [accentColor, setAccentColor] = useState<string>(() => {
    try {
      return localStorage.getItem("fitgate_accent_color") || "#A3E635";
    } catch {
      return "#A3E635";
    }
  });
  const [searchQuery, setSearchQuery] = useState("");

  const handleSelectAccent = (hex: string) => {
    setAccentColor(hex);
    try {
      localStorage.setItem("fitgate_accent_color", hex);
    } catch {
      // Storage unavailable
    }
  };

  const role = user?.role || "member";
  const userRoleNav = useMemo<
    Array<{ label: string; path: string; icon?: React.ReactNode }>
  >(() => {
    const baseNav = ROLE_NAV_ITEMS[role] ||
      (dashboardConfig?.navigation as Array<{
        label: string;
        path: string;
        icon?: React.ReactNode;
      }>) || [
        { label: "Overview", path: "/dashboard" },
        { label: "Profile", path: "/profile" },
      ];
    if (role === "super_admin") return baseNav;

    const caps = capabilities || dashboardConfig?.capabilities;
    return baseNav.filter((item) => {
      if (caps) {
        if (!caps.has_trainer_module && (
          item.path === "/trainers" ||
          item.path === "/assignments" ||
          item.path === "/my-clients" ||
          item.path === "/measurements"
        )) {
          return false;
        }
        if (!caps.has_group_classes && (
          item.path === "/classes" ||
          item.path === "/my-classes"
        )) {
          return false;
        }
        if (!caps.has_freeze && (
          item.path === "/freezes" ||
          item.path === "/freeze-request" ||
          item.path === "/freeze"
        )) {
          return false;
        }
        if (!caps.has_notices && item.path === "/notices") {
          return false;
        }
        if (!caps.has_expenses && item.path === "/expenses") {
          return false;
        }
      } else if (gymBranding && gymBranding.has_group_classes === false) {
        if (item.path === "/classes" || item.path === "/my-classes") return false;
      }
      return true;
    });
  }, [role, dashboardConfig?.navigation, dashboardConfig?.capabilities, capabilities, gymBranding]);

  const currentPath = location.pathname.replace(/\/+$/, "") || "/dashboard";

  // Role permissions routing check: send to own home page if unauthorized
  useEffect(() => {
    if (!user) return;
    const allowedPaths = userRoleNav.map((item) => item.path);
    // Allow special paths
    allowedPaths.push("/profile");
    if (role === "super_admin") {
      allowedPaths.push("/platform/gyms");
      allowedPaths.push("/settings");
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
    if (role === "trainer" && capabilities?.has_trainer_module !== false) {
      getTrainerProfileMe()
        .then((t) => setTrainerWorkload(t))
        .catch(() => { });
      getMyClients()
        .then((c) => setTrainerClients(c))
        .catch(() => { });
    }
  }, [role, capabilities?.has_trainer_module]);

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
            has_group_classes: res.has_group_classes,
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

    // Notice Board (Sprint 28)
    if (currentPath.startsWith("/notices")) {
      return (
        <SectionErrorBoundary title="Notice Board">
          <NoticeBoardSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // Equipment Catalog & Maintenance
    if (currentPath.startsWith("/equipment")) {
      return (
        <SectionErrorBoundary title="Gym Equipment">
          <EquipmentSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // Expenses & Reports (Sprint 29a)
    if (currentPath.startsWith("/expenses")) {
      return (
        <SectionErrorBoundary title="Expenses & Reports">
          <ExpensesSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // Group Classes (Sprint 26)
    if (currentPath.startsWith("/classes")) {
      return (
        <SectionErrorBoundary title="Group Classes">
          <ClassScheduleSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // Bank Receipt Reviews (Sprint 12d)
    if (currentPath.startsWith("/receipt-reviews")) {
      return (
        <SectionErrorBoundary title="Bank Receipt Reviews">
          <ReceiptReviewQueueSection />
        </SectionErrorBoundary>
      );
    }

    // Trainer: My Classes (Sprint 26)
    if (currentPath.startsWith("/my-classes")) {
      return (
        <SectionErrorBoundary title="My Classes">
          <ClassScheduleSection userRole={role} />
        </SectionErrorBoundary>
      );
    }

    // 11b. Super Admin: Platform Notices
    if (currentPath === "/platform/notices" && role === "super_admin") {
      return (
        <SectionErrorBoundary title="Platform Notices">
          <PlatformNoticesSection />
        </SectionErrorBoundary>
      );
    }

    // Super Admin: Support requests
    if (currentPath.startsWith("/platform/support") && role === "super_admin") {
      return (
        <SectionErrorBoundary title="Support Requests">
          <PlatformSupportSection />
        </SectionErrorBoundary>
      );
    }

    // Gym: Contact FitGate (Owner & Manager)
    if (currentPath.startsWith("/support") && (role === "owner" || role === "manager")) {
      return (
        <SectionErrorBoundary title="Contact FitGate">
          <ContactFitGateSection />
        </SectionErrorBoundary>
      );
    }

    // Gym: FitGate Messages (Owner)
    if (currentPath.startsWith("/platform-messages") && role === "owner") {
      return (
        <SectionErrorBoundary title="FitGate Messages">
          <FitGateMessagesSection />
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
          <>
            <SectionErrorBoundary title="FitGate Messages">
              <OwnerPlatformMessagesCard />
            </SectionErrorBoundary>
            <SectionErrorBoundary title="First-run Checklist">
              <FirstRunChecklistCard
                key={checklistKey}
                onOpenBranding={() => navigate("/settings")}
              />
            </SectionErrorBoundary>
          </>
        )}

        {role === "trainer" ? (
          capabilities && !capabilities.has_trainer_module ? (
            <Card className="bg-surface border-border p-8 text-center space-y-3">
              <h2 className="text-xl font-bold text-text">Trainer Module Not Enabled</h2>
              <p className="text-sm text-text-muted max-w-md mx-auto">
                The trainer module is not enabled for your gym. Please contact your gym administrator or owner for more information.
              </p>
            </Card>
          ) : (
            <div className="space-y-6">
              <div className="border-b border-border pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h2 className="text-xl font-bold text-text">
                    Trainer Overview
                  </h2>
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
                  <span className="text-xs text-text-muted block">
                    Client Workload
                  </span>
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-bold text-text">
                      {trainerWorkload
                        ? `${trainerWorkload.client_count} of ${trainerWorkload.max_clients}`
                        : `${trainerClients.length} clients`}
                    </span>
                    {trainerWorkload &&
                      trainerWorkload.client_count >=
                      trainerWorkload.max_clients ? (
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
                  <span className="text-xs text-text-muted block">
                    No Measurements Recorded
                  </span>
                  <span className="text-2xl font-bold text-amber-500">
                    {trainerClients.filter((c) => !c.has_measurements).length}
                  </span>
                  <p className="text-[11px] text-text-muted mt-1">
                    Assigned clients needing initial intake measurements
                  </p>
                </Card>

                <Card className="bg-surface border-border p-5 space-y-1">
                  <span className="text-xs text-text-muted block">
                    Measured Clients
                  </span>
                  <span className="text-2xl font-bold text-primary">
                    {trainerClients.filter((c) => c.has_measurements).length}
                  </span>
                  <p className="text-[11px] text-text-muted mt-1">
                    Clients with body composition history
                  </p>
                </Card>
              </div>

              {/* Clients with no approved plan this week */}
              {(() => {
                const clientsWithoutPlan = trainerClients.filter(
                  (c) => !c.has_approved_plan_this_week
                );
                return (
                  <Card className="bg-surface border-border p-5 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-text uppercase tracking-wider">
                            Clients with no approved plan this week
                          </h3>
                          <Badge
                            variant={
                              clientsWithoutPlan.length > 0
                                ? "warning"
                                : "success"
                            }
                          >
                            {clientsWithoutPlan.length}
                          </Badge>
                        </div>
                        <p className="text-xs text-text-muted mt-0.5">
                          Assigned clients needing review or plan generation for
                          the current week.
                        </p>
                      </div>
                    </div>

                    {clientsWithoutPlan.length === 0 ? (
                      <div className="text-center py-6 text-text-muted text-xs">
                        All assigned clients have an approved workout plan for
                        this week.
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left border-collapse">
                          <thead>
                            <tr className="border-b border-border text-text-muted">
                              <th className="py-2 px-3 font-semibold">Client</th>
                              <th className="py-2 px-3 font-semibold">Status</th>
                              <th className="py-2 px-3 font-semibold text-right">
                                Action
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/50">
                            {clientsWithoutPlan.map((c) => (
                              <tr
                                key={c.assignment_id}
                                className="hover:bg-surface-2/40 cursor-pointer"
                                onClick={() =>
                                  navigate(
                                    `/measurements?memberId=${c.member_id}&tab=training_plans`
                                  )
                                }
                              >
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
                                <td className="py-2.5 px-3">
                                  {c.plan_status_this_week ===
                                    "pending_review" ? (
                                    <Badge variant="warning">
                                      Draft waiting for your review
                                    </Badge>
                                  ) : (
                                    <Badge variant="neutral">No draft yet</Badge>
                                  )}
                                </td>
                                <td className="py-2.5 px-3 text-right">
                                  <Button
                                    size="sm"
                                    variant="secondary"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      navigate(
                                        `/measurements?memberId=${c.member_id}&tab=training_plans`
                                      );
                                    }}
                                    className="text-xs"
                                  >
                                    Open Plan &rarr;
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                );
              })()}

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
                          <th className="py-2 px-3 font-semibold">
                            Membership Plan
                          </th>
                          <th className="py-2 px-3 font-semibold">
                            Assigned Date
                          </th>
                          <th className="py-2 px-3 font-semibold">
                            Measurements
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50">
                        {trainerClients.slice(0, 5).map((c) => (
                          <tr
                            key={c.assignment_id}
                            className="hover:bg-surface-2/40"
                          >
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
                            <td className="py-2.5 px-3 text-text-muted">
                              {c.member_phone}
                            </td>
                            <td className="py-2.5 px-3 text-text">
                              {c.plan_name}
                            </td>
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
          )
        ) : role === "owner" || role === "manager" ? (
          <SectionErrorBoundary title="Operational Analytics">
            <AnalyticsOverviewSection
              onUpgradeClick={() => navigate("/settings")}
            />
          </SectionErrorBoundary>
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
      className="theme-dark theme-kinora min-h-screen bg-[#080B0F] text-slate-100 flex flex-col md:flex-row pb-20 md:pb-0 w-full font-sans"
      style={{
        ["--brand-accent" as string]: accentColor,
        ["--accent-glow" as string]: `${accentColor}33`,
      }}
    >
      {/* Desktop Pinned Left Sidebar (Static across all dashboard screens) */}
      <aside className="hidden md:flex flex-col w-64 border-r border-white/5 bg-[#0C0F14] shrink-0 min-h-screen sticky top-0 h-screen overflow-y-auto justify-between p-4 z-20">
        <div className="space-y-5">
          {/* Gym / Platform Branding at Top of Sidebar */}
          <div className="flex items-center gap-3 px-2 pt-1 pb-4 border-b border-white/5">
            {role === "super_admin" ? (
              <div className="flex items-center gap-2.5">
                <div
                  className="w-9 h-9 rounded-xl text-black font-black text-base flex items-center justify-center shadow-lg"
                  style={{ backgroundColor: accentColor }}
                >
                  FG
                </div>
                <div>
                  <span className="font-extrabold text-base tracking-tight text-white block leading-tight">
                    FitGate Platform
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400">
                    Apex Governance
                  </span>
                </div>
              </div>
            ) : gymBranding?.logo ? (
              <div className="flex items-center gap-2.5">
                <img
                  src={gymBranding.logo}
                  alt={`${gymBranding.name || tenant} logo`}
                  className="w-9 h-9 rounded-xl object-cover border border-white/10"
                />
                <div>
                  <span className="font-extrabold text-base tracking-tight text-white block leading-tight">
                    {gymBranding.name || "FitGate Gym"}
                  </span>
                  {tenant && (
                    <span className="text-[11px] font-mono text-slate-400">
                      {tenant}.fitgate
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                <div
                  className="w-9 h-9 rounded-xl font-black text-base flex items-center justify-center text-black shadow-lg"
                  style={{
                    backgroundColor: accentColor,
                  }}
                >
                  {(gymBranding?.name || tenant || "FG").charAt(0).toUpperCase()}
                </div>
                <div>
                  <span className="font-extrabold text-base tracking-tight text-white block leading-tight">
                    {gymBranding?.name || "FitGate"}
                  </span>
                  {tenant && (
                    <span className="text-[11px] font-mono text-slate-400">
                      {tenant}.fitgate
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Navigation list */}
          <div className="space-y-1">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500 px-3 mb-2">
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
                    className={`flex items-center justify-between px-3.5 py-2.5 text-sm font-semibold rounded-xl transition-all duration-200 min-h-[44px] ${isActive
                      ? "bg-white/[0.08] text-white shadow-xs border border-white/10"
                      : "text-slate-400 hover:text-white hover:bg-white/[0.03]"
                      }`}
                  >
                    <span>{item.label}</span>
                    {isActive && (
                      <span
                        className="w-1.5 h-1.5 rounded-full"
                        style={{
                          backgroundColor: accentColor,
                          boxShadow: `0 0 8px ${accentColor}`,
                        }}
                      />
                    )}
                  </Link>
                );
              })}
            </nav>

            {role !== "super_admin" && (
              <div className="pt-3 px-1">
                <a
                  href="/entry?preview=true"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-300 bg-[#141822] hover:bg-[#1A202E] border border-white/10 rounded-xl transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                    <span>View Landing Page</span>
                  </span>
                  <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-slate-300 font-mono">
                    Public
                  </span>
                </a>
              </div>
            )}

            {/* Operations Streak Tracker (Kinora style) */}
            <div className="pt-3 px-1">
              <div className="bg-[#12151C] border border-white/5 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5" style={{ color: accentColor }} />
                    Current Streak
                  </span>
                  <span className="text-xs font-mono font-bold text-white">
                    12 Days
                  </span>
                </div>
                <div className="flex items-center justify-between pt-1">
                  {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
                    <div key={i} className="flex flex-col items-center gap-1">
                      <span className="text-[9px] font-bold text-slate-500">{d}</span>
                      <span
                        className={`w-1.5 h-1.5 rounded-full ${
                          i < 5 ? "shadow-[0_0_6px]" : "bg-white/10"
                        }`}
                        style={
                          i < 5
                            ? { backgroundColor: accentColor, color: accentColor }
                            : {}
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* User Profile & Logout at Bottom of Sidebar */}
        <div className="pt-4 border-t border-white/5 px-2 space-y-3">
          <div className="flex items-center justify-between">
            <div className="min-w-0 pr-2">
              <span className="text-sm font-bold text-white truncate block">
                {user?.full_name || user?.email?.split("@")[0]}
              </span>
              <span className="text-xs text-slate-400 capitalize block">
                {user?.role}
              </span>
            </div>
            <Badge variant="primary">{user?.role}</Badge>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Link
              to="/profile"
              className="flex-1 inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold bg-white/5 border border-white/10 text-slate-200 rounded-xl hover:bg-white/10 transition min-h-[38px]"
            >
              Profile
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleLogout}
              className="flex-1 text-xs font-semibold text-slate-400 hover:text-red-400 min-h-[38px] bg-white/5 border-white/10"
            >
              Log out
            </Button>
          </div>
        </div>
      </aside>

      {/* Main Workspace: Fills remaining width until the sidebar */}
      <div className="flex-1 flex flex-col min-w-0 w-full overflow-hidden bg-[#080B0F]">
        {/* Top Header Bar across the main workspace */}
        <header className="border-b border-white/5 bg-[#0C0F14]/90 backdrop-blur-md px-4 sm:px-6 lg:px-8 py-3 sticky top-0 z-30 flex items-center justify-between gap-3 flex-wrap sm:flex-nowrap">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile view brand display */}
            <div className="md:hidden flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white truncate max-w-[150px]">
                {gymBranding?.name || "FitGate"}
              </span>
              {tenant && (
                <span className="text-xs font-mono text-slate-400 bg-white/5 px-1.5 py-0.5 rounded border border-white/10 shrink-0">
                  {tenant}
                </span>
              )}
            </div>

            {/* Desktop current section breadcrumb */}
            <div className="hidden md:flex items-center gap-2 text-sm font-medium text-slate-400 min-w-0">
              <span className="truncate max-w-[160px]">{gymBranding?.name || (role === "super_admin" ? "FitGate Platform" : "Gym Portal")}</span>
              <span className="text-slate-600 shrink-0">/</span>
              <span className="text-white font-bold capitalize truncate">
                {userRoleNav.find(n => n.path === currentPath || (n.path !== "/dashboard" && currentPath.startsWith(n.path)))?.label || "Overview"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            {/* Search Input (Kinora pill style) */}
            <div className="hidden xl:flex items-center gap-2 bg-[#141820] border border-white/10 rounded-full px-3.5 py-1.5 text-xs text-slate-200">
              <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <input
                type="text"
                placeholder="Search anything..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent border-none outline-none text-xs text-white placeholder-slate-500 w-28 focus:w-44 transition-all"
              />
            </div>

            {/* Live Accent Theme Selector (Kinora 00:03 style) */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#141820] border border-white/10">
              <span className="text-[10px] uppercase font-bold text-slate-400 mr-0.5">
                Theme
              </span>
              {ACCENT_PRESETS.map((preset) => (
                <button
                  key={preset.hex}
                  type="button"
                  title={preset.name}
                  onClick={() => handleSelectAccent(preset.hex)}
                  className={`w-3.5 h-3.5 rounded-full transition-transform hover:scale-125 ${
                    accentColor === preset.hex
                      ? "ring-2 ring-white scale-110"
                      : "opacity-75 hover:opacity-100"
                  }`}
                  style={{ backgroundColor: preset.hex }}
                />
              ))}
            </div>

            {role !== "super_admin" && (
              <a
                href="/entry?preview=true"
                target="_blank"
                rel="noreferrer"
                className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold text-slate-200 bg-[#161A22] hover:bg-[#1E232E] border border-white/10 transition shrink-0"
              >
                <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                <span>Preview Landing Page</span>
              </a>
            )}
            <NotificationCenter />

            {/* Mobile profile link */}
            <div className="md:hidden flex items-center gap-2">
              <Link
                to="/profile"
                className="inline-flex items-center justify-center px-2.5 py-1 text-xs bg-white/5 border border-white/10 text-white rounded-xl min-h-[36px]"
              >
                Profile
              </Link>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleLogout}
                className="text-xs text-slate-400 hover:text-red-400 min-h-[36px] px-2.5 bg-white/5 border-white/10"
              >
                Log out
              </Button>
            </div>
          </div>
        </header>

        {/* Dynamic Page Content: Full width until the sidebar */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-y-auto w-full min-w-0 max-w-full">
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
              className={`flex flex-col items-center justify-center text-xs px-2 py-1 min-h-[44px] min-w-[44px] transition-colors ${isActive
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
            className={`flex flex-col items-center justify-center text-xs px-2 py-1 min-h-[44px] min-w-[44px] transition-colors ${showMoreMobile
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
                    className={`flex items-center px-4 py-3 text-sm rounded-lg min-h-[44px] ${isActive
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
