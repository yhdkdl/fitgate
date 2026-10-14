import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import {
  GymManagementSection,
  type GymPrefillData,
} from "../components/superadmin/GymManagementSection";
import { DemoRequestSection } from "../components/superadmin/DemoRequestSection";
import { FirstRunChecklistCard } from "../components/owner/FirstRunChecklistCard";
import { GymBrandingSection } from "../components/owner/GymBrandingSection";
import { StaffManagementSection } from "../components/owner/StaffManagementSection";
import { MemberManagementSection } from "../components/dashboard/MemberManagementSection";
import { MemberSelfSection } from "../components/dashboard/MemberSelfSection";
import { useAuth } from "../context/AuthContext";
import { getTenantFromHostname } from "../utils/tenant";

export const DashboardScreen: React.FC = () => {
  const { user, dashboardConfig, logout } = useAuth();
  const navigate = useNavigate();
  const tenant = getTenantFromHostname();

  const [adminTab, setAdminTab] = useState<"gyms" | "leads">("gyms");
  const [showBranding, setShowBranding] = useState(false);
  const [checklistKey, setChecklistKey] = useState(0);
  const [prefillGymData, setPrefillGymData] = useState<GymPrefillData | null>(
    null
  );

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const navItems = dashboardConfig?.navigation || [
    { label: "Overview", path: "/dashboard" },
    { label: "Profile", path: "/profile" },
  ];

  const widgets = dashboardConfig?.widgets || [
    { id: "overview", title: "General Overview" },
  ];

  return (
    <div className="min-h-screen bg-bg text-text flex flex-col pb-16 md:pb-0">
      {/* Top Header */}
      <header className="border-b border-border bg-surface px-4 py-3 sm:px-6 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-primary/20 text-primary font-bold text-lg flex items-center justify-center border border-primary/30">
              FG
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-text">
                FitGate
              </span>
              {tenant && (
                <span className="ml-2 text-xs text-text-muted bg-surface-2 px-2 py-0.5 rounded border border-border">
                  {tenant}
                </span>
              )}
            </div>
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
              className="text-text-muted hover:text-danger"
            >
              Sign Out
            </Button>
          </div>
        </div>
      </header>

      {/* Main content wrapper with desktop sidebar and responsive grid */}
      <div className="flex flex-1 max-w-7xl w-full mx-auto">
        {/* Desktop Sidebar */}
        <aside className="hidden md:flex flex-col w-56 border-r border-border bg-surface/50 p-4 shrink-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted px-3 mb-2">
            Navigation
          </div>
          <nav className="space-y-1">
            {navItems.map((item, idx) => (
              <Link
                key={idx}
                to={item.path}
                className="flex items-center px-3 py-2 text-sm font-medium rounded-input text-text hover:bg-surface-2 hover:text-white transition-colors min-h-[44px]"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>

        {/* Dashboard Main Area */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-6 overflow-y-auto">
          {/* Welcome title banner */}
          <div className="bg-surface border border-border rounded-card p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold text-text">
                  {dashboardConfig?.title || "Platform Dashboard"}
                </h1>
                <p className="text-sm text-text-muted mt-1">
                  Welcome back,{" "}
                  <span className="text-text font-medium">
                    {user?.full_name || user?.email}
                  </span>
                  . Here is your operational view for role{" "}
                  <span className="font-semibold text-primary">
                    {user?.role}
                  </span>
                  .
                </p>
              </div>
              <div>
                <Badge variant="success">Active Session</Badge>
              </div>
            </div>
          </div>

          {/* Super Admin Platform Hub */}
          {user?.role === "super_admin" && (
            <div className="space-y-6">
              <div className="flex items-center gap-2 border-b border-border pb-2">
                <button
                  onClick={() => setAdminTab("gyms")}
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                    adminTab === "gyms"
                      ? "bg-primary text-white shadow-sm"
                      : "text-text-muted hover:text-text hover:bg-surface-2"
                  }`}
                >
                  Gym Tenants
                </button>
                <button
                  onClick={() => setAdminTab("leads")}
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                    adminTab === "leads"
                      ? "bg-primary text-white shadow-sm"
                      : "text-text-muted hover:text-text hover:bg-surface-2"
                  }`}
                >
                  Demo Requests & Leads
                </button>
              </div>

              {adminTab === "gyms" ? (
                <GymManagementSection
                  prefillData={prefillGymData}
                  onClearPrefill={() => setPrefillGymData(null)}
                />
              ) : (
                <DemoRequestSection
                  onConvertToGym={(data) => {
                    setPrefillGymData(data);
                    setAdminTab("gyms");
                  }}
                />
              )}
            </div>
          )}

          {/* Gym Owner Onboarding & Branding */}
          {user?.role === "owner" && (
            <div className="space-y-6">
              <FirstRunChecklistCard
                key={checklistKey}
                onOpenBranding={() => setShowBranding(true)}
              />

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-2">
                <div>
                  <h2 className="text-lg font-semibold text-text">
                    Gym Branding & Settings
                  </h2>
                  <p className="text-xs text-text-muted">
                    Manage your gym's brand accent color, logo, and member
                    renewal notices.
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setShowBranding((prev) => !prev)}
                  className="self-start sm:self-center"
                >
                  {showBranding ? "Hide Branding" : "Configure Branding"}
                </Button>
              </div>

              {showBranding && <GymBrandingSection onUpdated={() => {}} />}

              <StaffManagementSection
                onStaffUpdated={() => setChecklistKey((k) => k + 1)}
              />

              <MemberManagementSection
                userRole={user?.role}
                onMemberRegistered={() => setChecklistKey((k) => k + 1)}
              />
            </div>
          )}

          {/* Gym Manager Hub */}
          {user?.role === "manager" && (
            <div className="space-y-6">
              <StaffManagementSection />
              <MemberManagementSection userRole={user?.role} />
            </div>
          )}

          {/* Reception / Trainer Hub */}
          {(user?.role === "reception" || user?.role === "trainer") && (
            <div className="space-y-6">
              <MemberManagementSection userRole={user?.role} />
            </div>
          )}

          {/* Member Self-Service Hub */}
          {user?.role === "member" && (
            <div className="space-y-6">
              <MemberSelfSection />
            </div>
          )}

          {/* Widgets Grid */}
          <div>
            <h2 className="text-lg font-semibold text-text mb-4">
              Dashboard Widgets
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
              {widgets.map((widget) => (
                <Card
                  key={widget.id}
                  className="bg-surface hover:border-border/80 transition-shadow"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-base text-text">
                      {widget.title}
                    </h3>
                    <span className="w-2.5 h-2.5 rounded-full bg-primary/70 animate-pulse" />
                  </div>
                  <p className="text-sm text-text-muted mb-4">
                    Real-time data stream for {widget.title.toLowerCase()}.
                  </p>
                  <div className="h-20 bg-surface-2/60 border border-border/50 rounded-lg flex items-center justify-center text-xs text-text-muted">
                    Widget placeholder:{" "}
                    <code className="ml-1 text-primary">{widget.id}</code>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Bottom Navigation (320px responsive) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border z-40 flex items-center justify-around py-2 px-1">
        {navItems.slice(0, 4).map((item, idx) => (
          <Link
            key={idx}
            to={item.path}
            className="flex flex-col items-center justify-center text-xs text-text-muted hover:text-primary px-2 py-1 min-h-[44px] min-w-[44px]"
          >
            <span className="font-medium text-center">{item.label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
};
