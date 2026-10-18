import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useInRouterContext, useNavigate } from "react-router-dom";
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
  setRefreshToken,
} from "../api/client";
import { clearAppQueryCache } from "../queryClient";
import {
  AUTH_BROADCAST_CHANNEL,
  AUTH_SYNC_STORAGE_KEY,
  broadcastAuthSync,
  getStoredAuthSync,
  type AuthSyncMessage,
} from "../utils/authSync";

interface AuthContextType {
  user: UserSummary | UserProfile | null;
  dashboardConfig: DashboardConfig | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  mustChangePassword: boolean;
  sessionNotice: string | null;
  clearSessionNotice: () => void;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (payload: ProfileUpdateRequest) => Promise<UserProfile>;
  changeUserPassword: (payload: ChangePasswordRequest) => Promise<void>;
  refreshProfile: () => Promise<void>;
  syncSession: () => Promise<void>;
}

const DASHBOARD_KEY = "fitgate_dashboard_config";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Child component to safely connect React Router's navigate function to a ref
 * without throwing when AuthProvider is used outside of a Router context.
 */
const RouterNavigator: React.FC<{
  onNavigateRef: React.MutableRefObject<((path: string) => void) | null>;
}> = ({ onNavigateRef }) => {
  const navigate = useNavigate();
  useEffect(() => {
    onNavigateRef.current = (path: string) => {
      navigate(path);
    };
    return () => {
      onNavigateRef.current = null;
    };
  }, [navigate, onNavigateRef]);
  return null;
};

const AuthNavigatorBridge: React.FC<{
  onNavigateRef: React.MutableRefObject<((path: string) => void) | null>;
}> = ({ onNavigateRef }) => {
  const inRouter = useInRouterContext();
  if (inRouter) {
    return <RouterNavigator onNavigateRef={onNavigateRef} />;
  }
  return null;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<UserSummary | UserProfile | null>(null);
  const userRef = useRef<UserSummary | UserProfile | null>(user);
  useEffect(() => {
    userRef.current = user;
  }, [user]);

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
  const isLoadingRef = useRef(isLoading);
  useEffect(() => {
    isLoadingRef.current = isLoading;
  }, [isLoading]);

  const [sessionNotice, setSessionNotice] = useState<string | null>(null);
  const noticeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const navigateRef = useRef<((path: string) => void) | null>(null);

  const safeNavigate = useCallback((path: string) => {
    if (navigateRef.current) {
      navigateRef.current(path);
    } else if (typeof window !== "undefined") {
      try {
        window.location.assign(path);
      } catch {
        // Ignore navigation error in headless tests
      }
    }
  }, []);

  const setNotice = useCallback((text: string | null) => {
    if (noticeTimeoutRef.current) {
      clearTimeout(noticeTimeoutRef.current);
      noticeTimeoutRef.current = null;
    }
    setSessionNotice(text);
    if (text) {
      noticeTimeoutRef.current = setTimeout(() => {
        setSessionNotice(null);
        noticeTimeoutRef.current = null;
      }, 10000);
    }
  }, []);

  const clearSessionNotice = useCallback(() => {
    setNotice(null);
  }, [setNotice]);

  const handleIncomingSync = useCallback(
    async (msg: AuthSyncMessage) => {
      const currentUser = userRef.current;

      if (msg.type === "LOGOUT") {
        setAccessToken(null);
        clearTokens();
        setUser(null);
        setDashboardConfig(null);
        try {
          sessionStorage.removeItem(DASHBOARD_KEY);
        } catch {
          // Ignore
        }
        clearAppQueryCache();
        setNotice("You were signed out from another tab.");
        safeNavigate("/login");
        return;
      }

      if (msg.type === "LOGIN") {
        const incomingUser = msg.user;
        if (!incomingUser) return;

        const isDifferentUser =
          !currentUser ||
          currentUser.id !== incomingUser.id ||
          currentUser.role !== incomingUser.role ||
          currentUser.gym_id !== incomingUser.gym_id;

        if (!isDifferentUser) {
          return;
        }

        // Clear query cache from previous user so no stale tenant or role data leaks
        clearAppQueryCache();

        if (msg.refreshToken) {
          setRefreshToken(msg.refreshToken);
        }

        try {
          const newAccess = await refreshAccessToken();
          if (newAccess) {
            try {
              const profile = await getProfile();
              setUser(profile);
            } catch {
              setUser(incomingUser);
            }
          } else {
            setUser(incomingUser);
          }
        } catch {
          setUser(incomingUser);
        }

        const dash = msg.dashboard || null;
        setDashboardConfig(dash);
        if (dash) {
          try {
            sessionStorage.setItem(DASHBOARD_KEY, JSON.stringify(dash));
          } catch {
            // Ignore
          }
        }

        const name =
          incomingUser.full_name || incomingUser.email || "another user";
        setNotice(
          `You signed in as ${name} in another tab; this tab now shows that account.`
        );
        safeNavigate("/dashboard");
        return;
      }

      if (msg.type === "UPDATE_PROFILE") {
        if (msg.user && currentUser && currentUser.id === msg.user.id) {
          setUser(msg.user);
        }
      }
    },
    [safeNavigate, setNotice]
  );

  const syncSession = useCallback(async () => {
    if (isLoadingRef.current) return;
    const currentUser = userRef.current;
    const refreshToken = getRefreshToken();

    if (!refreshToken) {
      if (currentUser) {
        await handleIncomingSync({ type: "LOGOUT", timestamp: Date.now() });
      }
      return;
    }

    const storedSync = getStoredAuthSync();
    if (storedSync && storedSync.user) {
      const isDifferent =
        !currentUser ||
        currentUser.id !== storedSync.user.id ||
        currentUser.role !== storedSync.user.role ||
        currentUser.gym_id !== storedSync.user.gym_id;

      if (isDifferent) {
        await handleIncomingSync({
          type: "LOGIN",
          user: storedSync.user,
          dashboard: storedSync.dashboard,
          refreshToken,
          timestamp: storedSync.timestamp,
        });
        return;
      }
    } else if (!currentUser) {
      clearAppQueryCache();
      try {
        const newAccess = await refreshAccessToken();
        if (newAccess) {
          const profile = await getProfile();
          setUser(profile);
          const name = profile.full_name || profile.email;
          setNotice(
            `You signed in as ${name} in another tab; this tab now shows that account.`
          );
          safeNavigate("/dashboard");
        }
      } catch {
        clearTokens();
      }
    }
  }, [handleIncomingSync, safeNavigate, setNotice]);

  useEffect(() => {
    const unsubscribe = onAuthFailure(() => {
      setUser(null);
      setDashboardConfig(null);
      try {
        sessionStorage.removeItem(DASHBOARD_KEY);
      } catch {
        // Ignore
      }
      clearAppQueryCache();
      broadcastAuthSync({ type: "LOGOUT" });
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

    let channel: BroadcastChannel | null = null;
    if (typeof BroadcastChannel !== "undefined") {
      try {
        channel = new BroadcastChannel(AUTH_BROADCAST_CHANNEL);
        channel.onmessage = (event: MessageEvent<AuthSyncMessage>) => {
          if (event.data) {
            void handleIncomingSync(event.data);
          }
        };
      } catch {
        // Ignore
      }
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key === "fitgate_refresh_token") {
        if (!event.newValue) {
          void handleIncomingSync({ type: "LOGOUT", timestamp: Date.now() });
        } else {
          void syncSession();
        }
      } else if (event.key === AUTH_SYNC_STORAGE_KEY) {
        if (!event.newValue) {
          void handleIncomingSync({ type: "LOGOUT", timestamp: Date.now() });
        } else {
          try {
            const parsed = JSON.parse(event.newValue) as AuthSyncMessage;
            void handleIncomingSync(parsed);
          } catch {
            void syncSession();
          }
        }
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        void syncSession();
      }
    };

    if (typeof window !== "undefined") {
      window.addEventListener("storage", handleStorage);
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", handleVisibility);
    }

    return () => {
      unsubscribe();
      if (noticeTimeoutRef.current) {
        clearTimeout(noticeTimeoutRef.current);
      }
      if (channel) {
        try {
          channel.close();
        } catch {
          // Ignore
        }
      }
      if (typeof window !== "undefined") {
        window.removeEventListener("storage", handleStorage);
      }
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibility);
      }
    };
  }, [handleIncomingSync, syncSession]);

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
      broadcastAuthSync({
        type: "LOGIN",
        user: res.user,
        dashboard: dash,
        refreshToken: res.refresh,
      });
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
      clearAppQueryCache();
      broadcastAuthSync({
        type: "LOGOUT",
      });
      setIsLoading(false);
    }
  };

  const updateUser = async (
    payload: ProfileUpdateRequest
  ): Promise<UserProfile> => {
    const updated = await apiUpdateProfile(payload);
    setUser(updated);
    broadcastAuthSync({
      type: "UPDATE_PROFILE",
      user: updated,
    });
    return updated;
  };

  const changeUserPassword = async (payload: ChangePasswordRequest) => {
    const res = await apiChangePassword(payload);
    setAccessToken(res.access);
    setUser(res.user);
    broadcastAuthSync({
      type: "UPDATE_PROFILE",
      user: res.user,
    });
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
        sessionNotice,
        clearSessionNotice,
        login,
        logout,
        updateUser,
        changeUserPassword,
        refreshProfile,
        syncSession,
      }}
    >
      <AuthNavigatorBridge onNavigateRef={navigateRef} />
      {sessionNotice && (
        <div
          role="status"
          aria-live="polite"
          className="bg-primary/10 border-b border-primary/30 text-text px-4 py-2.5 flex items-center justify-between text-sm sticky top-0 z-50 backdrop-blur-md"
        >
          <div className="flex items-center gap-2 max-w-7xl mx-auto w-full justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary inline-block shrink-0" />
              <span className="text-text font-medium">{sessionNotice}</span>
            </div>
            <button
              type="button"
              onClick={clearSessionNotice}
              className="text-text-muted hover:text-text text-xs px-2 py-1 rounded border border-border bg-surface shrink-0 ml-4 min-h-[32px]"
              aria-label="Dismiss notice"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
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
