import React, { createContext, useContext, useEffect, useState } from "react";
import {
  changePassword as apiChangePassword,
  getProfile,
  login as apiLogin,
  logout as apiLogout,
  updateProfile as apiUpdateProfile,
  type ChangePasswordRequest,
  type DashboardConfig,
  type LoginRequest,
  type ProfileUpdateRequest,
  type UserProfile,
  type UserSummary,
} from "../api/auth";
import {
  clearTokens,
  getRefreshToken,
  onAuthFailure,
  refreshAccessToken,
  setAccessToken,
} from "../api/client";

interface AuthContextType {
  user: UserSummary | UserProfile | null;
  dashboardConfig: DashboardConfig | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  mustChangePassword: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (payload: ProfileUpdateRequest) => Promise<UserProfile>;
  changeUserPassword: (payload: ChangePasswordRequest) => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const DASHBOARD_KEY = "fitgate_dashboard_config";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<UserSummary | UserProfile | null>(null);
  const [dashboardConfig, setDashboardConfig] =
    useState<DashboardConfig | null>(() => {
      try {
        const stored = sessionStorage.getItem(DASHBOARD_KEY);
        return stored ? JSON.parse(stored) : null;
      } catch {
        return null;
      }
    });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Unsubscribe listener when auth fails completely (e.g. invalid refresh)
    const unsubscribe = onAuthFailure(() => {
      setUser(null);
      setDashboardConfig(null);
      try {
        sessionStorage.removeItem(DASHBOARD_KEY);
      } catch {
        // Ignore
      }
    });

    async function initSession() {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        setIsLoading(false);
        return;
      }

      try {
        const newAccess = await refreshAccessToken();
        if (newAccess) {
          const profile = await getProfile();
          setUser(profile);
        } else {
          setUser(null);
          setDashboardConfig(null);
        }
      } catch {
        clearTokens();
        setUser(null);
        setDashboardConfig(null);
      } finally {
        setIsLoading(false);
      }
    }

    initSession();

    return () => {
      unsubscribe();
    };
  }, []);

  const login = async (credentials: LoginRequest) => {
    setIsLoading(true);
    try {
      const res = await apiLogin(credentials);
      setUser(res.user);
      const dash = (res.dashboard as unknown as DashboardConfig) || null;
      setDashboardConfig(dash);
      if (dash) {
        try {
          sessionStorage.setItem(DASHBOARD_KEY, JSON.stringify(dash));
        } catch {
          // Ignore
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setDashboardConfig(null);
      try {
        sessionStorage.removeItem(DASHBOARD_KEY);
      } catch {
        // Ignore
      }
      setIsLoading(false);
    }
  };

  const updateUser = async (
    payload: ProfileUpdateRequest
  ): Promise<UserProfile> => {
    const updated = await apiUpdateProfile(payload);
    setUser(updated);
    return updated;
  };

  const changeUserPassword = async (payload: ChangePasswordRequest) => {
    const res = await apiChangePassword(payload);
    setAccessToken(res.access);
    setUser(res.user);
  };

  const refreshProfile = async () => {
    const profile = await getProfile();
    setUser(profile);
  };

  const mustChangePassword = Boolean(user?.must_change_password);
  const isAuthenticated = Boolean(user);

  return (
    <AuthContext.Provider
      value={{
        user,
        dashboardConfig,
        isLoading,
        isAuthenticated,
        mustChangePassword,
        login,
        logout,
        updateUser,
        changeUserPassword,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export function useOptionalAuth(): AuthContextType | null {
  return useContext(AuthContext) || null;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
