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
import { RegisterScreen } from "./screens/RegisterScreen";
import { VerifyEmailScreen } from "./screens/VerifyEmailScreen";
import { getTenantFromHostname } from "./utils/tenant";

const RootRoute: React.FC = () => {
  const tenant = getTenantFromHostname();
  if (tenant) {
    return <GymEntryScreen />;
  }
  return <Navigate to="/dashboard" replace />;
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
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfileScreen />
            </ProtectedRoute>
          }
        />

        {/* Dynamic subpaths from dashboard navigation */}
        <Route
          path="/platform/*"
          element={
            <ProtectedRoute allowedRoles={["super_admin"]}>
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
          path="/staff/*"
          element={
            <ProtectedRoute allowedRoles={["owner", "manager"]}>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        <Route
          path="/plans/*"
          element={
            <ProtectedRoute>
              <DashboardScreen />
            </ProtectedRoute>
          }
        />

        {/* Default fallback */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
