import React, { useState } from "react";
import {
  QrCode,
  Scan,
  UserCheck,
  AlertTriangle,
  UserX,
  Clock,
  ShieldAlert,
  Edit3,
  Calendar,
  X,
  CheckCircle2,
  Camera,
  Maximize2,
} from "lucide-react";
import {
  scanQrToken,
  manualAttendanceOverride,
  type ScanResultResponse,
  type ManualOverrideResultResponse,
} from "../../api/attendance";
import { listGymMembers, type Member } from "../../api/members";
import { getAccessToken } from "../../api/client";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Badge } from "../ui/Badge";
import { Alert } from "../ui/Alert";
import { FormField } from "../ui/FormField";
import { Spinner } from "../ui/Spinner";
import { AttendanceLogCard } from "./AttendanceLogCard";
import { CameraQrScanner } from "./CameraQrScanner";
import { TodayCheckinsList } from "./TodayCheckinsList";

import {
  focusFirstInvalidField,
  validateTextLength,
} from "../../utils/validators";

interface AttendanceScannerSectionProps {
  userRole?: string;
}

export const AttendanceScannerSection: React.FC<
  AttendanceScannerSectionProps
> = ({ userRole }) => {
  const [tokenInput, setTokenInput] = useState("");
  const [todayRefreshKey, setTodayRefreshKey] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [showCameraScanner, setShowCameraScanner] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResultResponse | null>(null);
  const [overrideResult, setOverrideResult] =
    useState<ManualOverrideResultResponse | null>(null);

  const [scanError, setScanError] = useState<{
    detail: string;
    reason: string;
    member?: { full_name: string; photo_url?: string; status: string };
  } | null>(null);

  // Manual Override Modal state
  const [showOverrideModal, setShowOverrideModal] = useState(false);
  const [overrideMemberId, setOverrideMemberId] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const [overrideFieldErrors, setOverrideFieldErrors] = useState<Record<string, string>>({});
  const [overrideError, setOverrideError] = useState<{
    detail: string;
    reason: string;
  } | null>(null);

  // Manual Override member search state
  const [overrideSearch, setOverrideSearch] = useState("");
  const [overrideSearchResults, setOverrideSearchResults] = useState<Member[]>(
    []
  );
  const [isSearchingMembers, setIsSearchingMembers] = useState(false);
  const [selectedOverrideMember, setSelectedOverrideMember] =
    useState<Member | null>(null);

  // Search gym members when staff types name, email, or phone (max 10 results)
  React.useEffect(() => {
    if (!showOverrideModal) return;
    const query = overrideSearch.trim();
    if (!query) {
      setOverrideSearchResults([]);
      return;
    }

    let isCurrent = true;
    const timer = setTimeout(async () => {
      setIsSearchingMembers(true);
      try {
        const results = await listGymMembers({ search: query, limit: 10 });
        if (isCurrent) {
          setOverrideSearchResults(results.slice(0, 10));
        }
      } catch {
        if (isCurrent) {
          setOverrideSearchResults([]);
        }
      } finally {
        if (isCurrent) {
          setIsSearchingMembers(false);
        }
      }
    }, 200);

    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [overrideSearch, showOverrideModal]);

  const handleSelectMember = (member: Member) => {
    setSelectedOverrideMember(member);
    setOverrideMemberId(member.id);
    setOverrideSearch("");
    setOverrideSearchResults([]);
  };

  const handleClearSelectedMember = () => {
    setSelectedOverrideMember(null);
    setOverrideMemberId("");
    setOverrideSearch("");
    setOverrideSearchResults([]);
  };

  // Attendance history modal state
  const [selectedMemberForHistory, setSelectedMemberForHistory] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const processScanToken = async (rawToken: string) => {
    if (!rawToken.trim()) return;

    setScanning(true);
    setScanResult(null);
    setOverrideResult(null);
    setScanError(null);

    try {
      const result = await scanQrToken({ token: rawToken.trim() });
      setScanResult(result);
      setTokenInput("");
      setTodayRefreshKey((k) => k + 1);
    } catch (err: unknown) {
      const errorObj = err as {
        data?: {
          detail?: string;
          reason?: string;
          member?: { full_name: string; photo_url?: string; status: string };
        };
        message?: string;
      };
      const detail =
        errorObj.data?.detail || errorObj.message || "Failed to process scan.";
      const reason = errorObj.data?.reason || "error";
      setScanError({
        detail,
        reason,
        member: errorObj.data?.member,
      });
    } finally {
      setScanning(false);
    }
  };

  const handleScanSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    await processScanToken(tokenInput);
  };

  const handleCameraScan = (scannedToken: string) => {
    setTokenInput(scannedToken);
    processScanToken(scannedToken);
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setOverrideError(null);
    setOverrideFieldErrors({});

    const errors: Record<string, string> = {};
    if (!overrideMemberId.trim()) {
      errors["override-search"] = "Please select a member for manual override.";
    }

    const reasonErr = validateTextLength(overrideReason, "Override reason", 5, 500);
    if (reasonErr) {
      errors["override-reason"] = reasonErr;
    }

    if (Object.keys(errors).length > 0) {
      setOverrideFieldErrors(errors);
      focusFirstInvalidField(errors);
      return;
    }

    setOverrideSubmitting(true);

    try {
      const result = await manualAttendanceOverride({
        member_id: overrideMemberId.trim(),
        reason: overrideReason.trim(),
      });
      setOverrideResult(result);
      setTodayRefreshKey((k) => k + 1);
      setScanResult(null);
      setScanError(null);
      setShowOverrideModal(false);
      setOverrideReason("");
      setOverrideMemberId("");
      setSelectedOverrideMember(null);
      setOverrideSearch("");
      setOverrideSearchResults([]);
      setOverrideFieldErrors({});
    } catch (err: unknown) {
      const errorObj = err as {
        data?: { detail?: string; reason?: string };
        message?: string;
      };
      setOverrideError({
        detail:
          errorObj.data?.detail ||
          errorObj.message ||
          "Failed to process manual override.",
        reason: errorObj.data?.reason || "error",
      });
    } finally {
      setOverrideSubmitting(false);
    }
  };

  // Helper to render distinguishable reason badges and tips
  const renderReasonBadge = (reason: string) => {
    switch (reason) {
      case "already_checked_in":
        return (
          <div className="flex items-center gap-1.5 text-amber-400 font-semibold text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            Duplicate check-in detected today. Staff have been notified.
          </div>
        );
      case "expired":
        return (
          <div className="flex items-center gap-1.5 text-rose-400 font-semibold text-xs">
            <UserX className="w-4 h-4 text-rose-400" />
            Membership expired. Member must renew plan before check-in.
          </div>
        );
      case "frozen":
        return (
          <div className="flex items-center gap-1.5 text-sky-400 font-semibold text-xs">
            <Clock className="w-4 h-4 text-sky-400" />
            Membership is currently frozen.
          </div>
        );
      case "suspended":
        return (
          <div className="flex items-center gap-1.5 text-rose-500 font-semibold text-xs">
            <ShieldAlert className="w-4 h-4 text-rose-500" />
            Account is suspended by management.
          </div>
        );
      case "token_expired":
        return (
          <div className="flex items-center gap-1.5 text-amber-400 font-semibold text-xs">
            <Clock className="w-4 h-4 text-amber-400" />
            QR token window (90s) expired. Member must refresh pass.
          </div>
        );
      case "token_consumed":
        return (
          <div className="flex items-center gap-1.5 text-rose-400 font-semibold text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            Token already used. Single-use enforcement active.
          </div>
        );
      default:
        return null;
    }
  };

  const activeMember = scanResult?.member || overrideResult?.member;
  const activeAttendance = scanResult?.attendance || overrideResult?.attendance;

  return (
    <div className="space-y-6">
      {/* Top Banner / Controls */}
      <Card className="bg-surface border-border p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <QrCode className="w-6 h-6 text-primary" />
              <h2 className="text-xl font-bold text-text">
                Front Desk Attendance Scanner
              </h2>
            </div>
            <p className="text-sm text-text-muted mt-1">
              Validate dynamic 90s QR tokens, detect duplicate attempts, and
              execute reception overrides.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href="/attendance/scanner"
              className="inline-flex items-center justify-center min-h-[44px] px-3 py-1.5 rounded-input border border-border bg-surface-2 text-text hover:bg-border/60 gap-2 text-xs font-semibold focus:ring-2 focus:ring-primary focus:outline-none transition-colors"
              aria-label="Open Entrance Scanner tablet page"
            >
              <Maximize2 className="w-4 h-4 text-primary" />
              Entrance Scanner
            </a>
            <Button
              type="button"
              variant={showCameraScanner ? "primary" : "secondary"}
              size="sm"
              onClick={() => setShowCameraScanner((prev) => !prev)}
              className="min-h-[44px] flex items-center gap-2 text-xs font-semibold focus:ring-2 focus:ring-primary focus:outline-none"
              aria-label={
                showCameraScanner ? "Close camera" : "Scan with camera"
              }
            >
              <Camera className="w-4 h-4" />
              {showCameraScanner ? "Close Camera" : "Scan with camera"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setShowOverrideModal(true);
                setOverrideError(null);
              }}
              className="min-h-[44px] flex items-center gap-2 text-xs font-semibold"
            >
              <Edit3 className="w-4 h-4 text-amber-400" />
              Manual Override
            </Button>
          </div>
        </div>

        {/* Live Camera Scanner View */}
        {showCameraScanner && (
          <div className="mb-6">
            <CameraQrScanner
              onScan={handleCameraScan}
              onClose={() => setShowCameraScanner(false)}
              isProcessing={scanning}
            />
          </div>
        )}

        {/* Scan Input Form */}
        <form onSubmit={handleScanSubmit} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <Input
                type="text"
                placeholder="Scan QR token or paste token JWT..."
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                maxLength={2048}
                disabled={scanning}
                className="font-mono text-xs pr-10 min-h-[44px]"
                autoFocus
              />
              <Scan className="w-4 h-4 text-text-muted absolute right-3 top-3.5 pointer-events-none" />
            </div>

            <Button
              type="submit"
              variant="primary"
              disabled={scanning || !tokenInput.trim()}
              className="min-h-[44px] px-6 flex items-center justify-center gap-2 font-semibold"
            >
              {scanning ? (
                <>
                  <Spinner size="sm" />
                  Verifying...
                </>
              ) : (
                <>
                  <Scan className="w-4 h-4" />
                  Verify & Check In
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Result Card: Success */}
        {activeMember && activeAttendance && (
          <div className="mt-6 p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in duration-300">
            <div className="flex items-center gap-4">
              {activeMember.photo_url ? (
                <img
                  src={`${activeMember.photo_url}${activeMember.photo_url.includes("?") ? "&" : "?"}token=${encodeURIComponent(getAccessToken() || "")}`}
                  alt={activeMember.full_name}
                  className="w-16 h-16 rounded-full object-cover border-2 border-emerald-500 shadow-sm"
                />
              ) : (
                <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 flex items-center justify-center font-bold text-xl">
                  {activeMember.full_name.charAt(0)}
                </div>
              )}

              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-lg text-text">
                    {activeMember.full_name}
                  </h3>
                  <Badge variant="primary">
                    {activeMember.status.toUpperCase()}
                  </Badge>
                  {activeAttendance.is_override && (
                    <Badge variant="secondary">OVERRIDE</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-text-muted mt-1">
                  <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>
                    Checked in at{" "}
                    {new Date(
                      activeAttendance.checked_in_at
                    ).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })}
                  </span>
                  <span>•</span>
                  <span>{activeAttendance.date}</span>
                </div>
                {activeAttendance.override_reason && (
                  <p className="text-xs text-amber-300/90 mt-1 italic">
                    Reason: {activeAttendance.override_reason}
                  </p>
                )}
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                setSelectedMemberForHistory({
                  id: activeMember.id,
                  name: activeMember.full_name,
                })
              }
              className="min-h-[44px] flex items-center gap-1.5 text-xs self-stretch sm:self-center"
            >
              <Calendar className="w-3.5 h-3.5 text-primary" />
              View History
            </Button>
          </div>
        )}

        {/* Result Card: Error */}
        {scanError && (
          <div className="mt-6 p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 space-y-3 animate-in fade-in duration-300">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-bold text-sm text-text">
                    Check-in Rejected ({scanError.reason})
                  </h4>
                  <p className="text-xs text-rose-300 mt-0.5">
                    {scanError.detail}
                  </p>
                </div>
              </div>

              {scanError.member && (
                <Badge variant="danger">
                  {scanError.member.status.toUpperCase()}
                </Badge>
              )}
            </div>

            {renderReasonBadge(scanError.reason)}

            {/* Quick action to manual override if member is active */}
            {userRole &&
              ["owner", "manager", "reception"].includes(userRole) && (
                <div className="pt-2 border-t border-rose-500/20 flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (scanError.member) {
                        // Prefill modal
                      }
                      setShowOverrideModal(true);
                    }}
                    className="min-h-[36px] text-xs font-semibold"
                  >
                    Open Manual Override
                  </Button>
                </div>
              )}
          </div>
        )}
      </Card>

      {/* Live Today's Check-ins List (Criteria 12-14) */}
      <TodayCheckinsList refreshTrigger={todayRefreshKey} />

      {/* Selected Member Attendance History Modal / Section */}
      {selectedMemberForHistory && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-text">
              Member Attendance Calendar
            </h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSelectedMemberForHistory(null)}
              className="min-h-[36px] text-xs"
            >
              Close History
            </Button>
          </div>
          <AttendanceLogCard
            memberId={selectedMemberForHistory.id}
            memberName={selectedMemberForHistory.name}
          />
        </div>
      )}

      {/* Manual Override Modal */}
      {showOverrideModal && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
          <div className="bg-surface border border-border rounded-2xl p-6 max-w-md w-full shadow-2xl relative space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-primary" />
                <h3 className="font-bold text-lg text-text">
                  Manual Attendance Override
                </h3>
              </div>
              <button
                onClick={() => setShowOverrideModal(false)}
                className="text-text-muted hover:text-text p-1 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-text-muted">
              Records an official manual check-in when a member cannot scan.
              Requires an active subscription and creates an immutable AuditLog
              entry.
            </p>

            {overrideError && (
              <Alert variant="danger">
                <div className="text-xs">
                  <span className="font-semibold block">
                    Override Denied ({overrideError.reason})
                  </span>
                  {overrideError.detail}
                </div>
              </Alert>
            )}

            <form onSubmit={handleOverrideSubmit} className="space-y-4" noValidate>
              <FormField
                label="Member"
                htmlFor="override-search"
                required
                error={overrideFieldErrors["override-search"]}
              >
                {selectedOverrideMember ? (
                  <div className="p-3 bg-surface-2 border border-primary/30 rounded-input flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-text truncate">
                          {selectedOverrideMember.full_name}
                        </span>
                        <Badge variant="primary">
                          {selectedOverrideMember.status.toUpperCase()}
                        </Badge>
                      </div>
                      <p className="text-xs text-text-muted truncate mt-0.5">
                        {selectedOverrideMember.email}
                        {selectedOverrideMember.phone &&
                          ` • ${selectedOverrideMember.phone}`}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handleClearSelectedMember}
                      className="min-h-[36px] text-xs shrink-0"
                    >
                      Change
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="relative">
                      <Input
                        id="override-search"
                        type="text"
                        placeholder="Search member by name, email, or phone..."
                        maxLength={100}
                        value={overrideSearch}
                        onChange={(e) => {
                          const val = e.target.value;
                          setOverrideSearch(val);
                          // Also allow direct paste of member UUID
                          if (
                            val.trim().length === 36 &&
                            val.trim().includes("-")
                          ) {
                            setOverrideMemberId(val.trim());
                          }
                        }}
                        className="text-xs min-h-[44px] pr-8"
                        autoFocus
                      />
                      {isSearchingMembers && (
                        <div className="absolute right-3 top-3.5 pointer-events-none">
                          <Spinner size="sm" />
                        </div>
                      )}
                    </div>

                    {overrideSearchResults.length > 0 && (
                      <div className="max-h-48 overflow-y-auto bg-surface-2 border border-border rounded-input divide-y divide-border/60 shadow-lg">
                        {overrideSearchResults.map((m) => (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => handleSelectMember(m)}
                            className="w-full text-left p-2.5 hover:bg-surface transition-colors flex items-center justify-between gap-2 min-h-[44px]"
                          >
                            <div className="min-w-0">
                              <p className="font-semibold text-xs text-text truncate">
                                {m.full_name}
                              </p>
                              <p className="text-[11px] text-text-muted truncate">
                                {m.email} {m.phone && `• ${m.phone}`}
                              </p>
                            </div>
                            <Badge
                              variant={
                                m.status === "active" ? "primary" : "secondary"
                              }
                            >
                              {m.status.toUpperCase()}
                            </Badge>
                          </button>
                        ))}
                      </div>
                    )}

                    {overrideSearch.trim() &&
                      !isSearchingMembers &&
                      overrideSearchResults.length === 0 && (
                        <p className="text-xs text-text-muted italic px-1">
                          No members found matching &quot;{overrideSearch}
                          &quot;.
                        </p>
                      )}
                  </div>
                )}
              </FormField>

              <FormField
                label="Override Reason (5 to 500 characters)"
                htmlFor="override-reason"
                required
                error={overrideFieldErrors["override-reason"]}
              >
                <textarea
                  id="override-reason"
                  placeholder="Explain why manual override was needed (e.g. phone died, camera broken)..."
                  maxLength={500}
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  className="w-full bg-surface-2 border border-border rounded-input p-3 text-xs text-text focus:outline-none focus:ring-1 focus:ring-primary min-h-[80px]"
                  required
                />
              </FormField>

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowOverrideModal(false)}
                  className="flex-1 min-h-[44px]"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={
                    overrideSubmitting ||
                    !overrideMemberId.trim() ||
                    !overrideReason.trim()
                  }
                  className="flex-1 min-h-[44px] flex items-center justify-center gap-2 font-semibold"
                >
                  {overrideSubmitting ? (
                    <>
                      <Spinner size="sm" />
                      Recording...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      Confirm Override
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
