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

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <Routes>
        {/* Public auth screens */}
        <Route path="/login" element={<LoginScreen />} />
        <Route path="/forgot-password" element={<ForgotPasswordScreen />} />
        <Route path="/reset-password" element={<ResetPasswordScreen />} />

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

        {/* Default fallbacks */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
