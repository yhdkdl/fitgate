import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { Spinner } from "../ui/Spinner";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
  allowForcedPasswordChangeOnly?: boolean;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
  allowForcedPasswordChangeOnly = false,
}) => {
  const { user, isAuthenticated, isLoading, mustChangePassword } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <div className="flex flex-col items-center gap-3">
          <Spinner size="lg" />
          <p className="text-text-muted text-sm">Loading session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If password change is forced, block all routes except /force-change-password
  if (mustChangePassword && !allowForcedPasswordChangeOnly) {
    return <Navigate to="/force-change-password" replace />;
  }

  // If user already changed password but tries to visit /force-change-password, redirect to dashboard
  if (!mustChangePassword && allowForcedPasswordChangeOnly) {
    return <Navigate to="/dashboard" replace />;
  }

  // Role guard check
  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-surface border border-border rounded-card p-6 text-center">
          <h2 className="text-xl font-bold text-danger mb-2">Access Denied</h2>
          <p className="text-text-muted mb-4">
            Your role ({user.role}) does not have permission to access this
            area.
          </p>
          <a
            href="/dashboard"
            className="inline-flex items-center justify-center px-4 py-2 bg-primary text-white rounded-input hover:bg-primary-hover min-h-[44px]"
          >
            Go to Dashboard
          </a>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
