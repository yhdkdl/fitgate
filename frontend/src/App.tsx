import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { DashboardScreen } from "./screens/DashboardScreen";
import { ForcedChangePasswordScreen } from "./screens/ForcedChangePasswordScreen";
import { ForgotPasswordScreen } from "./screens/ForgotPasswordScreen";
import { LoginScreen } from "./screens/LoginScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { ResetPasswordScreen } from "./screens/ResetPasswordScreen";
import { SetPasswordScreen } from "./screens/SetPasswordScreen";
import { RequestDemoScreen } from "./screens/RequestDemoScreen";
import { GymEntryScreen } from "./screens/GymEntryScreen";
import { LandingScreen } from "./screens/LandingScreen";
import { RegisterScreen } from "./screens/RegisterScreen";
import { VerifyEmailScreen } from "./screens/VerifyEmailScreen";
import { EntranceScannerScreen } from "./screens/EntranceScannerScreen";
import { getTenantFromHostname } from "./utils/tenant";

import { useAuth } from "./context/AuthContext";

const RootRoute: React.FC = () => {
  const tenant = getTenantFromHostname();
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  if (tenant) {
    return <GymEntryScreen />;
  }
  return <LandingScreen />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <Routes>
        {/* Public auth and marketing screens */}
        <Route path="/" element={<RootRoute />} />
        <Route path="/entry" element={<GymEntryScreen />} />
        <Route path="/login" element={<LoginScreen />} />
        <Route path="/register" element={<RegisterScreen />} />
        <Route path="/verify-email" element={<VerifyEmailScreen />} />
        <Route path="/request-demo" element={<RequestDemoScreen />} />
        <Route path="/forgot-password" element={<ForgotPasswordScreen />} />
        <Route path="/reset-password" element={<ResetPasswordScreen />} />
        <Route path="/set-password" element={<SetPasswordScreen />} />

        {/* Forced password change screen (accessible ONLY when must_change_password is true) */}
        <Route
          path="/force-change-password"
          element={
            <ProtectedRoute allowForcedPasswordChangeOnly={true}>
              <ForcedChangePasswordScreen />
            </ProtectedRoute>
          }
        />

        {/* Authenticated user screens */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/members"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "reception"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/members/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "reception"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/check-in"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "reception"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/payments"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "member"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/bank-transfers"
          element={
            <ProtectedRoute allowedRoles={["owner"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/plans"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/trainers"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/trainers/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/assignments"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/assignments/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/freezes"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/staff"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/staff/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/audit-log"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "super_admin"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/settings"
          element={
            <ProtectedRoute allowedRoles={["owner"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/membership"
          element={
            <ProtectedRoute allowedRoles={["member"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/membership/*"
          element={
            <ProtectedRoute allowedRoles={["member"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/my-clients"
          element={
            <ProtectedRoute allowedRoles={["trainer"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/my-clients/*"
          element={
            <ProtectedRoute allowedRoles={["trainer"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/measurements"
          element={
            <ProtectedRoute allowedRoles={["trainer"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/measurements/*"
          element={
            <ProtectedRoute allowedRoles={["trainer"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/platform/*"
          element={
            <ProtectedRoute allowedRoles={["super_admin"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfileScreen />
            </ProtectedRoute>
          }
        />

        {/* Dedicated Entrance Scanner tablet view */}
        <Route
          path="/attendance/scanner"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager", "reception"]}>
              <EntranceScannerScreen />
            </ProtectedRoute>
          }
        />
        <Route
          path="/scanner"
          element={<Navigate to="/attendance/scanner" replace />}
        />

        {/* Default fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
