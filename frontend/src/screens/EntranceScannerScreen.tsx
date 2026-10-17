import React, { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  AlertTriangle,
  UserX,
  PauseCircle,
  ShieldAlert,
  RefreshCw,
  AlertCircle,
  X,
  Lock,
  ArrowLeft,
  Scan,
} from "lucide-react";
import {
  scanQrToken,
  type ScanResultResponse,
  type ScanResultMember,
} from "../api/attendance";
import { getPublicGymEntry } from "../api/gyms";
import { getAccessToken, onAuthFailure, ApiError } from "../api/client";
import { getTenantFromHostname } from "../utils/tenant";
import { CameraQrScanner } from "../components/attendance/CameraQrScanner";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

interface RefusalDetails {
  reason: string;
  detail: string;
  member?: ScanResultMember;
}

export const EntranceScannerScreen: React.FC = () => {
  const navigate = useNavigate();
  const tenant = getTenantFromHostname();

  const [gymName, setGymName] = useState<string>("FitGate Gym");
  const [gymLogo, setGymLogo] = useState<string | null>(null);

  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Overlay state: null | 'success' | 'refused'
  const [overlayState, setOverlayState] = useState<
    "success" | "refused" | null
  >(null);
  const [successData, setSuccessData] = useState<{
    member: ScanResultMember;
    checkedInAt: string;
  } | null>(null);
  const [refusalData, setRefusalData] = useState<RefusalDetails | null>(null);

  // Manual code entry modal
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualCode, setManualCode] = useState("");
  const [manualError, setManualError] = useState<string | null>(null);

  const autoDismissTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load gym branding (name & logo)
  useEffect(() => {
    let mounted = true;
    async function loadGymInfo() {
      try {
        const entry = await getPublicGymEntry(tenant || undefined);
        if (!mounted) return;
        if (entry.name) setGymName(entry.name);
        if (entry.logo) setGymLogo(entry.logo);
      } catch {
        if (!mounted) return;
        if (tenant) {
          // Capitalize subdomain as fallback
          setGymName(tenant.charAt(0).toUpperCase() + tenant.slice(1) + " Gym");
        }
      }
    }
    loadGymInfo();
    return () => {
      mounted = false;
    };
  }, [tenant]);

  // Criterion 9: Monitor staff session expiration
  useEffect(() => {
    const unsubscribe = onAuthFailure(() => {
      setSessionExpired(true);
    });
    return () => {
      unsubscribe();
      if (autoDismissTimerRef.current) {
        clearTimeout(autoDismissTimerRef.current);
      }
    };
  }, []);

  const clearOverlay = () => {
    if (autoDismissTimerRef.current) {
      clearTimeout(autoDismissTimerRef.current);
      autoDismissTimerRef.current = null;
    }
    setOverlayState(null);
    setSuccessData(null);
    setRefusalData(null);
  };

  const handleScanCode = async (tokenCode: string) => {
    if (!tokenCode || isProcessing || sessionExpired) return;

    setIsProcessing(true);
    setManualError(null);

    try {
      const response: ScanResultResponse = await scanQrToken({
        token: tokenCode.trim(),
      });

      // Clear any prior overlay
      if (autoDismissTimerRef.current) {
        clearTimeout(autoDismissTimerRef.current);
      }

      setSuccessData({
        member: response.member,
        checkedInAt: response.attendance.checked_in_at,
      });
      setOverlayState("success");
      setShowManualModal(false);
      setManualCode("");

      // Criterion 3: Large green screen for about 3 seconds, then returns to scanning
      autoDismissTimerRef.current = setTimeout(() => {
        clearOverlay();
      }, 3000);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        // Staff session expired
        setSessionExpired(true);
        return;
      }

      const errorObj = err as {
        status?: number;
        data?: {
          detail?: string;
          reason?: string;
          member?: ScanResultMember;
        };
        message?: string;
      };

      if (errorObj.status === 401) {
        setSessionExpired(true);
        return;
      }

      const reason = errorObj.data?.reason || "invalid_token";
      const detail =
        errorObj.data?.detail ||
        errorObj.message ||
        "QR code could not be verified.";
      const member = errorObj.data?.member;

      if (autoDismissTimerRef.current) {
        clearTimeout(autoDismissTimerRef.current);
      }

      setRefusalData({ reason, detail, member });
      setOverlayState("refused");
      setShowManualModal(false);
      setManualCode("");

      // Auto dismiss refusal screen after 4.5 seconds to return to scanning
      autoDismissTimerRef.current = setTimeout(() => {
        clearOverlay();
      }, 4500);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualCode.trim()) {
      setManualError("Please enter or paste a valid QR code token.");
      return;
    }
    await handleScanCode(manualCode);
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      return new Date(isoString).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "";
    }
  };

  // Plain language text, icon, and colors for refusal reasons
  const getRefusalConfig = (reason: string) => {
    switch (reason) {
      case "already_checked_in":
        return {
          theme: "amber",
          icon: <AlertTriangle className="w-16 h-16 text-amber-400 shrink-0" />,
          title: "Already Checked In Today",
          message:
            "You have already checked in today. Please speak with reception if you need assistance.",
        };
      case "expired":
        return {
          theme: "rose",
          icon: <UserX className="w-16 h-16 text-rose-400 shrink-0" />,
          title: "Membership Expired",
          message:
            "Your membership plan has expired. Please visit reception or renew online.",
        };
      case "frozen":
        return {
          theme: "amber",
          icon: <PauseCircle className="w-16 h-16 text-amber-400 shrink-0" />,
          title: "Membership Frozen",
          message:
            "Your membership is currently frozen. Please speak with reception to unfreeze your pass.",
        };
      case "suspended":
        return {
          theme: "rose",
          icon: <ShieldAlert className="w-16 h-16 text-rose-400 shrink-0" />,
          title: "Account Suspended",
          message:
            "Your account is suspended by management. Please see reception.",
        };
      case "token_expired":
        return {
          theme: "amber",
          icon: <RefreshCw className="w-16 h-16 text-amber-400 shrink-0" />,
          title: "Pass Code Expired",
          message:
            "Your 90-second QR pass has expired. Please refresh your pass on your phone and scan again.",
        };
      case "token_consumed":
        return {
          theme: "rose",
          icon: <AlertCircle className="w-16 h-16 text-rose-400 shrink-0" />,
          title: "Pass Code Already Used",
          message:
            "This QR code has already been used. Please refresh your pass on your phone for a new code.",
        };
      default:
        return {
          theme: "rose",
          icon: <AlertCircle className="w-16 h-16 text-rose-400 shrink-0" />,
          title: "Check-in Refused",
          message:
            "Unable to verify this QR pass code. Please refresh your pass or visit reception.",
        };
    }
  };

  return (
    <div className="fixed inset-0 bg-black text-white flex flex-col z-50 overflow-hidden font-sans select-none">
      {/* Top Banner (Gym name, Logo, Instruction line) */}
      <header className="w-full bg-slate-950/90 border-b border-slate-800 px-4 py-3 sm:px-6 flex items-center justify-between z-30 shrink-0">
        <div className="flex items-center gap-3">
          {gymLogo ? (
            <img
              src={gymLogo}
              alt={`${gymName} Logo`}
              className="w-10 h-10 object-contain rounded-lg bg-surface p-1 border border-border"
            />
          ) : (
            <div className="w-10 h-10 rounded-lg bg-primary/20 text-primary font-bold text-lg flex items-center justify-center border border-primary/40">
              FG
            </div>
          )}
          <div>
            <h1 className="font-bold text-base sm:text-lg text-slate-100 tracking-tight leading-tight">
              {gymName}
            </h1>
            <p className="text-xs sm:text-sm text-primary font-medium">
              Hold your QR code up to the camera
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => navigate("/dashboard")}
            className="min-h-[44px] min-w-[44px] px-3 flex items-center gap-2 text-xs bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700 focus:ring-2 focus:ring-primary focus:outline-none"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </Button>
        </div>
      </header>

      {/* Main View Area: Camera view taking the whole screen */}
      <main className="relative flex-1 w-full h-full overflow-hidden bg-black flex items-center justify-center">
        <CameraQrScanner
          onScan={handleScanCode}
          variant="fullscreen"
          isProcessing={isProcessing}
          onManualToggle={() => setShowManualModal(true)}
          disabled={Boolean(overlayState || sessionExpired)}
        />

        {/* SUCCESS OVERLAY (Criterion 3: Large green screen for 3s) */}
        {overlayState === "success" && successData && (
          <div
            className="absolute inset-0 bg-emerald-950/95 backdrop-blur-md flex flex-col items-center justify-center p-6 sm:p-8 z-40 text-center animate-in fade-in zoom-in-95 duration-200"
            role="dialog"
            aria-live="assertive"
            aria-label="Check-in Successful"
            onClick={clearOverlay}
          >
            <div className="max-w-md w-full bg-emerald-900/40 border-2 border-emerald-500 rounded-3xl p-6 sm:p-8 flex flex-col items-center gap-6 shadow-2xl">
              <div className="w-20 h-20 rounded-full bg-emerald-500/20 text-emerald-400 border-2 border-emerald-400 flex items-center justify-center shadow-lg">
                <CheckCircle2 className="w-12 h-12" />
              </div>

              {/* Member Photo (No personal contact details per Criterion 5) */}
              {successData.member.photo_url ? (
                <img
                  src={`${successData.member.photo_url}${
                    successData.member.photo_url.includes("?") ? "&" : "?"
                  }token=${encodeURIComponent(getAccessToken() || "")}`}
                  alt={successData.member.full_name}
                  className="w-32 h-32 sm:w-40 sm:h-40 rounded-full object-cover border-4 border-emerald-400 shadow-xl"
                />
              ) : (
                <div className="w-32 h-32 sm:w-40 sm:h-40 rounded-full bg-emerald-800 text-emerald-200 border-4 border-emerald-400 flex items-center justify-center text-5xl font-black shadow-xl">
                  {successData.member.full_name.charAt(0)}
                </div>
              )}

              <div className="space-y-1">
                <span className="text-xs uppercase tracking-wider text-emerald-300 font-bold">
                  Check-in Confirmed
                </span>
                <h2 className="text-2xl sm:text-3xl font-black text-white">
                  Welcome, {successData.member.full_name}!
                </h2>
                <p className="text-sm sm:text-base text-emerald-200 font-medium">
                  Checked in at {formatTime(successData.checkedInAt)}
                </p>
              </div>

              <p className="text-xs text-emerald-300/80">
                Returning to scanner in 3 seconds...
              </p>
            </div>
          </div>
        )}

        {/* REFUSAL OVERLAY (Criterion 4: Large red or amber screen explaining why) */}
        {overlayState === "refused" && refusalData && (
          <div
            className={`absolute inset-0 ${
              getRefusalConfig(refusalData.reason).theme === "amber"
                ? "bg-amber-950/95"
                : "bg-rose-950/95"
            } backdrop-blur-md flex flex-col items-center justify-center p-6 sm:p-8 z-40 text-center animate-in fade-in zoom-in-95 duration-200`}
            role="dialog"
            aria-live="assertive"
            aria-label="Check-in Refused"
            onClick={clearOverlay}
          >
            <div
              className={`max-w-md w-full ${
                getRefusalConfig(refusalData.reason).theme === "amber"
                  ? "bg-amber-900/40 border-amber-500 text-amber-100"
                  : "bg-rose-900/40 border-rose-500 text-rose-100"
              } border-2 rounded-3xl p-6 sm:p-8 flex flex-col items-center gap-5 shadow-2xl`}
            >
              <div className="p-3 rounded-full bg-black/30 border border-current shadow-lg">
                {getRefusalConfig(refusalData.reason).icon}
              </div>

              {/* Optional Photo if member found */}
              {refusalData.member?.photo_url && (
                <img
                  src={`${refusalData.member.photo_url}${
                    refusalData.member.photo_url.includes("?") ? "&" : "?"
                  }token=${encodeURIComponent(getAccessToken() || "")}`}
                  alt={refusalData.member.full_name}
                  className="w-24 h-24 rounded-full object-cover border-2 border-current shadow-md"
                />
              )}

              <div className="space-y-2">
                <span className="text-xs uppercase tracking-wider opacity-80 font-bold">
                  Entrance Notice
                </span>
                <h2 className="text-2xl sm:text-3xl font-black">
                  {getRefusalConfig(refusalData.reason).title}
                </h2>
                {refusalData.member && (
                  <p className="text-sm font-semibold text-white">
                    {refusalData.member.full_name}
                  </p>
                )}
                <p className="text-sm sm:text-base opacity-90 leading-relaxed font-medium">
                  {getRefusalConfig(refusalData.reason).message}
                </p>
              </div>

              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={clearOverlay}
                className="mt-2 min-h-[44px] min-w-[44px] px-6 text-sm font-bold bg-white text-black hover:bg-slate-200 focus:ring-2 focus:ring-white focus:outline-none"
              >
                Scan Again
              </Button>
            </div>
          </div>
        )}

        {/* SESSION EXPIRED MODAL (Criterion 9: 'Staff must sign in again') */}
        {sessionExpired && (
          <div
            className="absolute inset-0 bg-slate-950/95 backdrop-blur-md flex flex-col items-center justify-center p-6 z-50 text-center"
            role="alertdialog"
            aria-modal="true"
            aria-label="Staff Session Expired"
          >
            <div className="max-w-md w-full bg-slate-900 border-2 border-rose-500 rounded-3xl p-6 sm:p-8 flex flex-col items-center gap-5 shadow-2xl">
              <div className="w-16 h-16 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/50 flex items-center justify-center shadow-md">
                <Lock className="w-8 h-8" />
              </div>

              <div className="space-y-2">
                <h2 className="text-xl sm:text-2xl font-bold text-white">
                  Staff Must Sign In Again
                </h2>
                <p className="text-sm text-slate-300">
                  Your staff session has expired. To maintain secure entrance
                  records, a staff member must sign in again.
                </p>
              </div>

              <Button
                type="button"
                variant="primary"
                onClick={() => navigate("/login")}
                className="w-full min-h-[44px] text-sm font-bold flex items-center justify-center gap-2"
              >
                Sign In to FitGate
              </Button>
            </div>
          </div>
        )}

        {/* MANUAL CODE ENTRY MODAL (Criterion 7) */}
        {showManualModal && !overlayState && !sessionExpired && (
          <div
            className="absolute inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-40"
            role="dialog"
            aria-modal="true"
            aria-label="Enter Code Manually"
          >
            <div className="w-full max-w-md bg-slate-900 border border-slate-700 rounded-2xl p-6 shadow-2xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2 text-slate-100 font-bold text-base">
                  <Scan className="w-5 h-5 text-primary" />
                  <span>Enter Code Manually</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowManualModal(false)}
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center text-slate-400 hover:text-white rounded-lg focus:ring-2 focus:ring-primary focus:outline-none"
                  aria-label="Close manual code entry"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleManualSubmit} className="space-y-4">
                <div className="space-y-1">
                  <label
                    htmlFor="entrance-manual-token"
                    className="block text-xs font-medium text-slate-300"
                  >
                    Paste or Type Member QR Code Token
                  </label>
                  <Input
                    id="entrance-manual-token"
                    type="text"
                    value={manualCode}
                    onChange={(e) => setManualCode(e.target.value)}
                    placeholder="Paste member token..."
                    className="font-mono text-xs min-h-[44px] bg-slate-950 border-slate-700 text-white"
                    autoFocus
                  />
                </div>

                {manualError && (
                  <p className="text-xs text-rose-400 font-medium">
                    {manualError}
                  </p>
                )}

                <div className="flex items-center justify-end gap-3 pt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setShowManualModal(false)}
                    className="min-h-[44px] px-4 text-xs font-semibold"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={isProcessing || !manualCode.trim()}
                    className="min-h-[44px] px-5 text-xs font-bold"
                  >
                    {isProcessing ? "Verifying..." : "Verify & Check In"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
